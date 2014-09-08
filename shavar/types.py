
class Chunk(object):
    "Object for ease of interacting with parsed chunk data"

    def __init__(self, chunk_type='a', number=None, hashes=[], hash_size=32):
        if chunk_type not in ('a', 's'):
            raise ValueError('Invalid chunk type: "%s"' % chunk_type)

        if number is None:
            raise ValieError('Invalid chunk number: "%d"' % number)

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

    def find_prefix(self, prefix):
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

    def find_prefix(self, prefix):
        list_o_chunks = []
        for number, chunk in self.adds.iteritems():
            if chunk.find_prefix(prefix):
                list_o_chunks.append(chunk)
        return list_o_chunks

    def insert_chunk(self, chunk):
        chunk_list = self.adds
        if chunk.type == 's':
            chunk_list = self.subs
        if chunk.number in chunk_list:
            raise ValueError("Duplicate chunk number: %d" % chunk.number)
        chunk_list[chunk.number] = chunk


class Downloads(list):

    def __init__(self, req_size=0):
        if type(req_size) != int:
            raise TypeError('req_size not an integer: "%s"' % req_size)

        self.req_size = req_size
        super(Downloads, self).__init__()

    def __eq__(self, other):
        if (type(self) != type(other)
                or self.req_size != other.req_size
                or not super(Downloads, self).__eq__(other)):
            return False
        return True


class DownloadsListInfo(object):

    def __init__(self, list_name, wants_mac=False, adds=[], subs=[]):
        self.name = list_name
        self.wants_mac = wants_mac
        self.adds = set(adds)
        self.subs = set(subs)

    def add_claim(self, typ, chunk_num):
        if typ == 's':
            self.subs.add(chunk_num)
        else:
            self.adds.add(chunk_num)

    def add_range_claim(self, typ, low, high):
        for i in xrange(low, high + 1):
            self.add_claim(typ, i)

    def __eq__(self, other):
        if (type(self) != type(other)
                or self.name != other.name
                or self.wants_mac != other.wants_mac
                or self.adds != other.adds
                or self.subs != other.subs):
            return False
        return True

    def __repr__(self):
        return "%s('%s, wants_mac=%s, adds=%s, subs=%s)" \
            % (self.__class__.__name__, self.name, self.wants_mac, self.adds,
               self.subs)
