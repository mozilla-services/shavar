import itertools
import json
import os.path
import posixpath

from shavar.exceptions import ParseError
from shavar.types import Chunk, ChunkList, Downloads, DownloadsListInfo


def parse_downloads(request):
    parsed = Downloads()

    limit = request.registry.settings.get("shavar.max_downloads_chunks",
                                          10000)

    for lineno, line in enumerate(request.body_file):
        line = line.strip()

        if not line or line.isspace():
            continue

        line = line.decode('utf-8')
        # Did client provide max size preference?
        if line.startswith("s;"):
            if lineno != 0:
                return ParseError("Size request can only be the first line!")
            req_size = line.split(";", 1)[1]
            # Almost certainly redundant due to stripping the line above
            req_size = req_size.strip()
            try:
                req_size = int(req_size)
            except ValueError:
                raise ParseError("Invalid requested size")
            parsed.req_size = req_size
            continue

        if ";" not in line:
            return ParseError("Bad downloads request: no semi-colon")

        lname, chunklist = line.split(";", 1)
        if not lname or '-' not in lname:
            raise ParseError("Invalid list name: \"%s\"" % lname)
        info = DownloadsListInfo(lname, limit=limit)

        chunks = chunklist.split(":")
        # Check for MAC
        if len(chunks) >= 1 and chunks[-1] == "mac":
            if request.GET.get('pver') == '3.0':
                raise ParseError('MAC not supported in protocol version 3')
            info.wants_mac = True
            chunks.pop(-1)
        # Client claims to have chunks for this list
        if not chunks or (len(chunks) == 1 and not chunks[0]):
            parsed.append(info)
            continue
        # Uneven number of chunks should only occur if 'mac' was specified
        if len(chunks) % 2 != 0:
            raise ParseError("Invalid LISTINFO for %s" % lname)

        while chunks:
            ctype = chunks.pop(0)
            if ctype not in ('a', 's'):
                raise ParseError("Invalid CHUNKTYPE \"%s\" for %s" % (ctype,
                                                                      lname))

            list_of_chunks = chunks.pop(0)
            for chunk in list_of_chunks.split(','):
                try:
                    chunk = int(chunk)
                except ValueError:
                    if chunk.find('-'):
                        low, high = chunk.split('-', 1)
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

                        info.add_range_claim(ctype, low, high)
                else:  # Resist temptation to indent!  It's a try/except/else
                    info.add_claim(ctype, chunk)
        parsed.append(info)
    return parsed


def parse_gethash(request):
    parsed = []

    # Early check to be sure we have something within the limits of a
    # reasonably sized header.  Reasonable size defined as an arbitrary max
    # of 2**8 bytes and a minimum of 3("4:4", a single prefix).  256 is
    # probably waaaaaaaaaaay too large for a gethash request header.
    eoh = request.body.find(b'\n')
    if eoh < 3 or eoh >= 256:
        raise ParseError("Improbably small or large gethash header size: %d"
                         % eoh)

    body_file = request.body_file

    # determine size of individual prefixes and length of payload
    header = body_file.readline().decode()
    try:
        prefix_len, payload_len = [int(x) for x in header.split(':', 1)]
    except ValueError:
        raise ParseError('Invalid prefix or payload size: "%s"' % header)
    if ((payload_len % prefix_len != 0)
            or (payload_len < prefix_len)):
        raise ParseError("Payload length invalid: \"%d\"" % payload_len)

    prefix_total = payload_len / prefix_len
    prefixes_read = 0
    total_read = 0
    while prefixes_read < prefix_total:
        prefix = body_file.read(prefix_len)
        if len(prefix) < prefix_len:
            break
        total_read += len(prefix)
        prefixes_read += 1
        parsed.append(prefix)

    if prefixes_read != prefix_total:
        raise ParseError("Hash read mismatch: client claimed %d, read %d" %
                         (prefix_total, prefixes_read))

    if total_read != payload_len:
        raise ParseError("Mismatch on gethash parse: client: %d, actual: %d" %
                         (payload_len, total_read))

    return set(parsed)  # unique-ify


def get_header(blob, eol):
    try:
        header = blob[:eol].decode()
    except UnicodeDecodeError:
        raise ParseError('Invalid unicode string found in chunk header: '
                         '"%s"' % blob[:eol])
    return header


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

    parsed = ChunkList()
    while True:
        blob = handle.read(32)

        # Consume any unnecessary newlines in front of chunks
        blob = blob.lstrip(b'\n')

        if not blob:
            break

        if len(blob) < 8:
            raise ParseError("Incomplete chunk file? Could only read %d "
                             "bytes of header." % len(blob))

        eol = blob.find(b'\n')
        if eol < 8:
            raise ParseError('Impossibly short chunk header: "%s"' % eol)
        header = get_header(blob, eol)

        if header.count(':') != 3:
            raise ParseError('Incorrect number of fields in chunk header: '
                             '"%s"' % header)

        add_sub, chunk_num, hash_len, read_len = header.split(':', 3)

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

        blob = blob[eol + 1:]
        blob += handle.read(read_len - len(blob))
        if blob is None or len(blob) < read_len:
            raise ParseError('Chunk data truncated for chunk %d' % chunk_num)

        hashes = []
        pos = 0
        while pos < read_len:
            hashes.append(blob[pos:pos + hash_len])
            pos += hash_len

        parsed.insert_chunk(Chunk(chunk_type=add_sub, number=chunk_num,
                                  hashes=hashes))

    return parsed


def parse_dir_source(handle, exists_cb=os.path.exists, open_cb=open):
    """
    Expects a file alike object with the contents of a JSON formatted index
    file that has the following structure:

    {
        "name": "mozpub-tracking-digest256",
        "basedir": "mozpub-tracking-digest256",
        "chunks": {
            "1": {
                "path": "mozpub-tracking-digest256/1",
                "hashes(optional)": [ "", "" ],
                "prefixes(optional)": [ "", "" ]
            },
            "2": {
                "path": "mozpub-tracking-digest256/2",
                "hashes": [ "", "" ],
                "prefixes": [ "", "" ]
            }
        }
    }

    The basedir, hashes, and prefixes entries are optional.  The chunks to be
    served will be parsed with parse_file_source().  If hashes and prefixes are
    provided, they will be verified against the data provided in the given
    chunk file.
    """
    try:
        index = json.load(handle)
    except ValueError as e:
        raise ParseError("Could not parse index file: %s" % e)

    if 'name' not in index:
        raise ParseError("Incorrectly formatted index: missing list name")

    if 'chunks' not in index:
        raise ParseError("Incorrectly formatted index: missing chunks")

    if 'basedir' in index:
        basedir = posixpath.join(os.path.dirname(handle.name),
                                 index['basedir'])
    else:
        basedir = os.path.dirname(handle.name)

    parsed = ChunkList()
    for key in index['chunks'].keys():
        # A little massaging to make the data structure a little cleaner
        try:
            index['chunks'][int(key)] = index['chunks'][key]
            del index['chunks'][key]
        except KeyError:
            raise ParseError("Some weird behaviour with the list of chunks "
                             "in \"%s\"" % handle.filename)

        chunk_file = posixpath.join(basedir, key)

        if not exists_cb(chunk_file):
            raise ParseError("Invalid chunk filename: \"%s\"" % chunk_file)

        with open_cb(chunk_file, 'rb') as f:
            chunk_list = parse_file_source(f)

        # Only one chunk per file
        if len(chunk_list) > 1:
            raise ParseError("More than one chunk in chunk file \"%s\""
                             % chunk_file)

        for chunk in itertools.chain(iter(chunk_list.adds.values()),
                                     iter(chunk_list.subs.values())):
            parsed.insert_chunk(chunk)

    return parsed
