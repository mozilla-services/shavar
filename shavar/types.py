from shavar.exceptions import ParseError


class Chunk(object):
    "Object for ease of interacting with parsed chunk data"

    def __init__(self, chunk_type='a', number=None, hashes=[], hash_size=32):
        if chunk_type not in ('a', 's'):
            raise ParseError('Invalid chunk type: "%s"' % chunk_type)

        if number is None:
            raise ParseError('Invalid chunk number: "%d"' % number)

        self.type = chunk_type
        self.number = number
        self.hashes = set(hashes)
        self.hash_len = hash_size
        self._prefix_cache = {}

    def __repr__(self):
        return "%s(chunk_type='%s', number=%d, hashes=%s, hash_size=%d)" \
            % (self.__class__.__name__, self.type, self.number, self.hashes,
               self.hash_len)

    def __eq__(self, other):
        if (type(self) != type(other)
              or self.type != other.type
              or self.number != other.number
              or self.hashes != other.hashes
              or self.hash_len != other.hash_len):
            return False
        return True

    def has_prefix(self, prefix):
        if prefix in self._prefix_cache:
            return True
        for hash_ in self.hashes:
            if hash_.startswith(prefix):
                self._prefix_cache[prefix] = True
                return True
        return False

    def get_hashes(self, prefix):
        hashes = []
        for hash_ in self.hashes:
            if hash_.startswith(prefix):
                hashes.append(hash_)
        return hashes


class ChunkList(object):
    "Simplify interaction with server side lists of chunks"

    def __init__(self, add_chunks=[], sub_chunks=[]):
        self._chunk_nums = []
        self.adds = {}
        self.subs = {}
        for chunk in add_chunks:
            self.adds[chunk.number] = chunk
        for chunk in sub_chunks:
            self.subs[chunk.number] = chunk

    def __repr__(self):
        return "%s(add_chunks=%s, sub_chunks=%s)" \
            % (self.__class__.__name__, self.adds.values(), self.subs.values())

    def __eq__(self, other):
        if (type(self) != type(other)
              or self.adds != other.adds
              or self.subs != other.subs):
            return False
        return True

    def has_prefix(self, prefix):
        list_o_chunks = []
        for number, chunk in self.adds.iteritems():
            if chunk.has_prefix(prefix):
                list_o_chunks.append(chunk)
        return list_o_chunks

    def add_chunk(self, chunk):
        chunk_list = self.adds
        if chunk.type == 's':
            chunk_list = self.subs
        if chunk.number in chunk_list:
            raise ParseError("Duplicate chunk number: %d" % chunk.number)
        chunk_list[chunk.number] = chunk
