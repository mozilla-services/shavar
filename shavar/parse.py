from shavar.exceptions import ParseError


def parse_downloads(request):
    parsed = {'req_size': None, 'lists': []}

    body = request.body
    body.strip()
    stanzas = body.split("\n")

    # Did client provide max size prefernce?
    if stanzas[0].startswith("s;"):
        size = stanzas.pop(0)
        req_size = size.split(";", 2)[1]
        req_size.strip()
        try:
            req_size = int(req_size)
        except ValueError:
            raise ParseError("Invalid requested size")
        parsed['req_size'] = req_size

    for stanza in stanzas:
        if not stanza:
            next
        wants_mac = False
        lname, chunklist = stanza.split(";", 2)
        chunks = chunklist.split(":")
        # Check for MAC
        if len(chunks) >= 1 and chunks[-1] == "mac":
            if request.GET.get('pver') == '3.0':
                raise ParseError('MAC not supported in protocol version 3')
            wants_mac = True
            chunks.pop(-1)
        # Client claims to have chunks for this list
        if not chunks or (len(chunks) == 1 and not chunks[0]):
            parsed['lists'].append((lname, wants_mac, []))
            return parsed
        # Uneven number of chunks should only occur if 'mac' was specified
        if len(chunks) % 2 != 0:
            raise ParseError("Invalid LISTINFO for %s" % lname)

        claims = {'a': [], 's': []}
        while chunks:
            ctype = chunks.pop(0)
            if ctype not in ('a', 's'):
                raise ParseError("Invalid CHUNKTYPE \"%s\" for %s" % (ctype,
                                                                      lname))

            claim = []
            chunk = chunks.pop(0)
            chunk_list = chunk.split(',')
            for chunk in chunk_list:
                try:
                    chunk = int(chunk)
                except ValueError:
                    if chunk.find('-'):
                        low, high = chunk.split('-', 2)
                        # FIXME should probably be stricter about testing for
                        #       pure integers only on the input
                        try:
                            low = int(low)
                            high = int(high)
                        except ValueError:
                            raise ParseError("Invalid RANGE \"%s\" for %s" %
                                             (chunk, lname))
                        if low >= high:
                            raise ParseError("Invalid RANGE \"%s\" for %s" %
                                             (chunk, lname))

                        claim.extend(range(low, high + 1))
                except:
                    chunk_def = "%s:%s" % (ctype, chunk)
                    raise ParseError("Invalid chunk \"%s\" for %s" %
                                     (chunk_def, lname))
                else:
                    claim.append(chunk)
            claims[ctype].extend(claim)
        parsed['lists'].append((lname, wants_mac, {'adds': set(claims['a']),
                                                   'subs': set(claims['s'])}))
    return parsed


def parse_gethash(request):
    parsed = []

    body = request.body
    body.strip()

    # determine size of individual prefixes and length of payload
    eoh = body.find('\n')
    header = body[:eoh]
    prefix_len, read_len = [int(x) for x in header.split(':', 2)]
    if read_len % prefix_len != 0:
        raise ParseError("Body length invalid: \"%d\"" % read_len)

    prefix_total = read_len / prefix_len
    prefixes_read = 0
    start = eoh + 1
    while prefixes_read < prefix_total:
        prefix = body[start:start + prefix_len]
        start += prefix_len
        prefixes_read += 1
        parsed.append(prefix)

    # FIXME: won't reach for both of these?
    if prefixes_read != prefix_total:
        raise ParseError("Hash read mismatch: client claimed %d, read %d" %
                         (prefix_total, prefixes_read))
    if start != len(body):
        raise ParseError("Mismatch on gethash parse: client: %d, actual: %d" %
                         (len(body), start))

    return parsed


def parse_file_source(handle):
    """
    Parses a chunk list formatted file
    """
    # We should almost certainly* find the end of the first newline within the
    # first 32 bytes of the file.  It consists of a colon delimited string
    # with the following members:
    #
    #  - type of chunk: 'a' or 's' == 1
    #  - chunk number:  assuming len(2**32) == max of 10
    #  - number of bytes in the hash prefix size: 4 bytes for shavar or
    #                                             32 digest256 == max of 2
    #  - length of the raw data following in octets: len(2**32) == max of 10
    #
    #  These total 23 plus 3 bytes for colons plus one byte for the newline
    #  bring the grand total for likely maximum length to 27 with a minimum
    #  of 8 bytes("1:1:4:1\n").
    #
    #  So 32 byte read should be more than sufficient.
    #
    # * If 64 bit ints get involved, there are other issues to address

    parsed = {'adds': {}, 'subs': {}}
    while True:
        blob = handle.read(32)

        # Consume any unnecessary newlines in front of chunks
        blob = blob.lstrip('\n')

        if not blob:
            break

        if len(blob) < 8:
            raise ParseError("Incomplete chunk file? Could only read %d "
                             "bytes of header." % len(blob))

        eol = blob.find('\n')
        if eol < 8:
            raise ParseError('Impossibly short chunk header: "%s"' % eol)
        header = blob[:eol]

        if header.count(':') != 3:
            raise ParseError('Incorrect number of colons in chunk header: '
                             '"%s"' % header)

        add_sub, chunk_num, hash_len, read_len = header.split(':', 4)

        if len(add_sub) != 1:
            raise ParseError('Chunk type is too long: "%s"' % header)
        if add_sub not in ('a', 's'):
            raise ParseError('Invalid chunk type: "%s"' % header)

        try:
            chunk_num = int(chunk_num)
            hash_len = int(hash_len)
            read_len = int(read_len)
        except ValueError:
            raise ParseError('Non-integer chunk values: "%s"' % header)

        if read_len % hash_len != 0:
            raise ParseError('Chunk data length not a multiple of prefix '
                             'size: "%s"' % header)

        blob = blob[eol+1:]
        blob += handle.read(read_len - len(blob))
        if blob is None or len(blob) < read_len:
            raise ParseError('Chunk data truncated for chunk %d' % chunk_num)

        prefixes = {}
        pos = 0
        while pos < read_len:
            h = blob[pos:pos + hash_len]
            pos += hash_len
            prefix = h[:4]
            if prefix in prefixes:
                prefixes[prefix].append(h)
            else:
                prefixes[prefix] = [h]

        hashes = {'chunk': chunk_num, 'size': hash_len, 'prefixes': prefixes}

        # FIXME This is so stupid
        if add_sub == 'a':
            add_sub = 'adds'
        elif add_sub == 's':
            add_sub = 'subs'

        if chunk_num in parsed[add_sub]:
            raise ParseError('Duplicate chunk in file: "%s' % header)

        parsed[add_sub][chunk_num] = hashes

    return parsed


def parse_dir_source(handle):
    pass
