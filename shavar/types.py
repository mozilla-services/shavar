class Chunk(object):
    "Object for ease of interacting with parsed chunk data"

    def __init__(self, chunk_type="a", number=None, hashes=None, hash_size=32):
        if hashes is None:
            hashes = []
        if chunk_type not in ("a", "s"):
            raise ValueError(f'Invalid chunk type: "{chunk_type}"')

        if number is None:
            raise ValueError(f'Invalid chunk number: "{number}"')

        self.type = chunk_type
        self.number = number
        self.hashes = set(hashes)
        self.hash_len = hash_size
        self._prefix_cache = {}

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"chunk_type='{self.type}', number={self.number}, "
            f"hashes={self.hashes}, hash_size={self.hash_len})"
        )

    def __eq__(self, other):
        if (
            type(self) != type(other)
            or self.type != other.type
            or self.number != other.number
            or self.hashes != other.hashes
            or self.hash_len != other.hash_len
        ):
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

    def __init__(self, add_chunks=None, sub_chunks=None):
        if add_chunks is None:
            add_chunks = []
        if sub_chunks is None:
            sub_chunks = []
        self.adds = {}
        self.subs = {}
        for chunk in add_chunks:
            self.adds[chunk.number] = chunk
        for chunk in sub_chunks:
            self.subs[chunk.number] = chunk

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"add_chunks={list(self.adds.values())}, "
            f"sub_chunks={list(self.subs.values())})"
        )

    def __eq__(self, other):
        if (
            type(self) != type(other)
            or self.adds != other.adds
            or self.subs != other.subs
        ):
            return False
        return True

    def __len__(self):
        return len(self.adds) + len(self.subs)

    def find_prefix(self, prefix):
        list_o_chunks = []
        for number, chunk in self.adds.items():
            if chunk.find_prefix(prefix):
                list_o_chunks.append(chunk)
        return list_o_chunks

    def insert_chunk(self, chunk):
        chunk_list = self.adds
        if chunk.type == "s":
            chunk_list = self.subs
        if chunk.number in chunk_list:
            raise ValueError(f"Duplicate chunk number: {chunk.number}")
        chunk_list[chunk.number] = chunk


class Downloads(list):
    def __init__(self, req_size=0):
        if not isinstance(req_size, int):
            raise TypeError(f'req_size not an integer: "{req_size}"')

        self.req_size = req_size
        super(Downloads, self).__init__()

    def __eq__(self, other):
        if (
            type(self) != type(other)
            or self.req_size != other.req_size
            or not super(Downloads, self).__eq__(other)
        ):
            return False
        return True


class LimitExceededError(Exception):
    """
    Raised when a /downloads request would exceed the limit of the number
    of chunks for a given request
    """


class DownloadsListInfo(object):
    def __init__(self, list_name, wants_mac=False, adds=None, subs=None, limit=10 * 1000):
        if adds is None:
            adds = []
        if subs is None:
            subs = []
        self.name = list_name
        self.wants_mac = wants_mac
        self.limit = limit
        if len(adds) > self.limit:
            raise LimitExceededError(
                f"Number of add chunks({len(adds)}) exceeds limit: {self.limit}"
            )
        self.adds = set(adds)
        if len(subs) > self.limit:
            raise LimitExceededError(
                f"Number of sub chunks({len(subs)}) exceeds limit: {self.limit}"
            )
        self.subs = set(subs)

    def add_claim(self, typ, chunk_num):
        # We do bounds checking after the fact because sets only store unique
        # items and don't duplicate
        if typ == "s":
            self.subs.add(chunk_num)
            if len(self.subs) > self.limit:
                raise LimitExceededError(
                    f"Number of sub chunks({len(self.subs)}) exceeds limit: {self.limit}"
                )
        else:
            self.adds.add(chunk_num)
            if len(self.adds) > self.limit:
                raise LimitExceededError(
                    f"Number of add chunks({len(self.adds)}) exceeds limit: {self.limit}"
                )

    def add_range_claim(self, typ, low, high):
        for i in range(low, high + 1):
            self.add_claim(typ, i)

    def __eq__(self, other):
        if (
            type(self) != type(other)
            or self.name != other.name
            or self.wants_mac != other.wants_mac
            or self.adds != other.adds
            or self.subs != other.subs
        ):
            return False
        return True

    def __repr__(self):
        return (
            f"{self.__class__.__name__}('{self.name}', "
            f"wants_mac={self.wants_mac}, adds={self.adds}, subs={self.subs})"
        )
