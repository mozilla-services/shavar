import os.path
from urlparse import urlparse

from konfig import Config
from shavar.exceptions import MissingListData
from shavar.sources import DirectorySource, FileSource


_CACHE = {}
_PREFIXES = {}


def configure_lists(config_file, lists_to_serve):
    global _CACHE
    config = Config(config_file)

    if not lists_to_serve:
        raise ValueError("lists_served appears to be empty or missing "
                         "in the config \"%s\"!" % config.filename)

    for lname in lists_to_serve:
        if config.has_section(lname):
            settings = config.get_map(lname)
        else:
            defaults = config.get_map('shavar')
            settings = {'type': 'shavar',
                        'source': os.path.join(defaults.get('lists_root',
                                                            ''), lname)}

        type_ = settings.get('type', '')
        if type_ == 'digest256':
            l = Digest256(lname, settings['source'], settings)
        elif type_ == 'shavar':
            l = Shavar(lname, settings['source'], settings)
        else:
            raise ValueError('Unknown list type for "%s": "%s"' % (lname,
                                                                   type_))

        _CACHE.update({lname: l})


def get_list(list_name):
    if list_name not in _CACHE:
        raise MissingListData('Not serving requested list "%s"', list_name)
    return _CACHE[list_name]


def lookup_prefixes(prefixes):
    """
    prefixes is an iterable of hash prefixes to look up

    The SB wire protocol doesn't require a list to check against for a given
    hash prefix from the client, so all lists have to be checked.  Easier to
    have prefixes registered at data load time.
    """
    found = {}

    for prefix in prefixes:
        if prefix in _PREFIXES:
            if prefix not in found:
                found[prefix] = {}
            for list_name in _PREFIXES[prefix]:
                sblist = get_list(list_name)
                adds = sblist.fetch(_PREFIXES[prefix][list_name], [])['adds']
                for chunk in adds:
                    found[prefix][list_name] = {chunk['chunk']:
                                                chunk['prefixes'][prefix]}
    return found


def add_prefixes(list_name, prefix_chunk_map):
    global _PREFIXES
    for prefix, chunks in prefix_chunk_map.items():
        if prefix not in _PREFIXES:
            _PREFIXES[prefix] = {}
        if not list_name in _PREFIXES[prefix]:
            _PREFIXES[prefix][list_name] = set()
        _PREFIXES[prefix][list_name].update(set(chunks))


class SafeBrowsingList(object):
    """
    Manages comparisons and data freshness
    """

    # Size of prefixes in bytes
    prefix_size = 4

    def __init__(self, list_name, source_url, settings):
        self.name = list_name
        self.source_url = source_url
        self.url = urlparse(source_url)
        self.settings = settings
        if (self.url.scheme == 'file' or
            not (self.url.scheme and self.url.netloc)):
            self._source = FileSource(self.source_url)
        else:
            raise Exception('Only filesystem access supported at this time')
        self._source.load()
        add_prefixes(self.name, self._source.prefixes)

    def refresh(self):
        self._source.refresh()

    def delta(self, chunks):
        """
        Calculates the delta necessary for a given client to catch up to the
        current server's idea of "current"

        This current iteration is very simplistic algorithm
        """
        adds, subs = self._source.list_chunks()

        # FIXME Should we call issuperset() first to be sure we're not getting
        # weird stuff from the request?
        a_delta = adds.difference(chunks['adds'])
        s_delta = subs.difference(chunks['subs'])
        return a_delta, s_delta

    def fetch(self, adds=[], subs=[]):
        to_add, to_sub = self._source.fetch(adds, subs)
        return {'adds': to_add, 'subs': to_sub, 'type': 'invalid'}


class Digest256(SafeBrowsingList):
    """
    Stub of a class to short circuit lookup functions
    """

    # Size of prefixes in bytes
    prefix_size = 32

    def __init__(self, list_name, source_url, settings):
        super(Digest256, self).__init__(list_name, source_url, settings)

    def refresh(self):
        self._blob = self.fetch()

    def delta(self, chunks):
        return {'adds': {1: self.fetch()}, 'subs': None, 'type': 'digest256'}

    def fetch(self, adds=[], subs=[]):
        return self._source.fetch(adds, subs)


class Shavar(SafeBrowsingList):

    def fetch(self, *chunks):
        return self._source.fetch(*chunks)
