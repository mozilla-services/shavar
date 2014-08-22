import os.path
from urlparse import urlparse

from konfig import Config
from shavar.exceptions import MissingListData
from shavar.sources import DirectorySource, FileSource


_CACHE = {}
# A (hopefully) slightly quicker index into looking up full length hashes
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


def clear_caches():
    global _CACHE, _PREFIXES
    _CACHE = {}
    _PREFIXES = {}


def get_list(list_name):
    if list_name not in _CACHE:
        raise MissingListData('Not serving requested list "%s"', list_name)
    return _CACHE[list_name]


def add_prefixes(list_name, prefix_chunk_map):
    """
    The SB wire protocol doesn't require a list to check against for a given
    hash prefix from the client, so all lists have to be checked.  Easier to
    have prefixes registered at data load time.
    """
    global _PREFIXES
    for prefix, chunks in prefix_chunk_map.items():
        if prefix not in _PREFIXES:
            _PREFIXES[prefix] = {}
        if not list_name in _PREFIXES[prefix]:
            _PREFIXES[prefix][list_name] = set()
        _PREFIXES[prefix][list_name].update(set(chunks))


def lookup_prefixes(prefixes):
    """
    prefixes is an iterable of hash prefixes to look up

    Returns a hash of the format:

    { prefix0: { list-name0: { chunk_num0: [ full-hash, ... ],
                               chunk_num1: [ full-hash, ... ],
                               ... },
                 list-name1: { chunk_num0: [ full-hash, ... ],
                               ... },
                 ... },
      prefix1: { ... }
    }

    Prefixes that aren't found are ignored
    """

    found = {}

    for prefix in prefixes:
        if prefix in _PREFIXES:
            prefix_data = _PREFIXES[prefix]
            if prefix not in found:
                found[prefix] = {}
            for list_name in prefix_data:
                sblist = get_list(list_name)
                for chunk in sblist.fetch_adds(prefix_data[list_name]):
                    found[prefix][list_name] = {chunk['chunk']:
                                                chunk['prefixes'][prefix]}
    return found


class SafeBrowsingList(object):
    """
    Manages comparisons and data freshness
    """

    # Size of prefixes in bytes
    prefix_size = 4
    type = 'invalid'

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

    def delta(self, adds, subs):
        """
        Calculates the delta necessary for a given client to catch up to the
        server's idea of "current"

        This current iteration is very simplistic algorithm
        """
        current_adds, current_subs = self._source.list_chunks()

        # FIXME Should we call issuperset() first to be sure we're not getting
        # weird stuff from the request?
        a_delta = current_adds.difference(adds)
        s_delta = current_subs.difference(subs)
        return sorted(a_delta), sorted(s_delta)

    def fetch(self, add_chunks=[], sub_chunks=[]):
        details = self._source.fetch(add_chunks, sub_chunks)
        details['type'] = self.type
        return details

    def fetch_adds(self, add_chunks):
        return self.fetch(add_chunks, [])['adds']

    def fetch_subs(self, sub_chunks):
        return self.fetch([], sub_chunks)['subs']


class Digest256(SafeBrowsingList):

    prefix_size = 32
    type = 'digest256'


class Shavar(SafeBrowsingList):

    prefix_size = 4
    type = 'shavar'
