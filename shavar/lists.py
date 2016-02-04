from urlparse import urlparse

from shavar.exceptions import MissingListDataError, NoDataError
from shavar.sources import (
    DirectorySource,
    FileSource,
    S3DirectorySource,
    S3FileSource
)


def includeme(config):
    lists_to_serve = config.registry.settings.get('shavar.lists_served', [])
    if not lists_to_serve:
        raise ValueError("lists_served appears to be empty or missing "
                         "in the config \"%s\"!" % config.filename)

    if isinstance(lists_to_serve, basestring):
        lists_to_serve = [lists_to_serve]

    config.registry['shavar.serving'] = {}

    for lname in lists_to_serve:
        # Make sure we have a refresh interval set for the data source for the
        # lists
        setting_name = 'refresh_check_interval'
        settings = config.registry.settings.getsection(lname)
        default = config.registry.settings.get('shavar.%s' %
                                               setting_name,
                                               10 * 60)
        if setting_name not in settings:
            settings[setting_name] = default

        # defaults = config.get_map('shavar')
        # settings = {'type': 'shavar',
        #            'source': os.path.join(defaults.get('lists_root',
        #                                                ''), lname)}

        type_ = settings.get('type', '')
        if type_ == 'digest256':
            list_ = Digest256(lname, settings['source'], settings)
        elif type_ == 'shavar':
            list_ = Shavar(lname, settings['source'], settings)
        else:
            raise ValueError('Unknown list type for "%s": "%s"' % (lname,
                                                                   type_))

        config.registry['shavar.serving'][lname] = list_


def get_list(request, list_name):
    if list_name not in request.registry['shavar.serving']:
        errmsg = 'Not serving requested list "%s"' % (list_name,)
        raise MissingListDataError(errmsg)
    return request.registry['shavar.serving'][list_name]


def lookup_prefixes(request, prefixes):
    """
    prefixes is an iterable of hash prefixes to look up

    Returns a dict of the format:

    { list-name0: { chunk_num0: [ full-hash, ... ],
                    chunk_num1: [ full-hash, ... ],
                    ... },
      list-name1: { chunk_num0: [ full-hash, ... ],
                    ... },
      ... }
    }

    Prefixes that aren't found are ignored
    """

    found = {}

    for list_name, sblist in request.registry['shavar.serving'].iteritems():
        for prefix in prefixes:
            list_o_chunks = sblist.find_prefix(prefix)
            if not list_o_chunks:
                continue
            if list_name not in found:
                found[list_name] = {}
            for chunk in list_o_chunks:
                if chunk.number not in found[list_name]:
                    found[list_name][chunk.number] = []
                found[list_name][chunk.number].extend(chunk.get_hashes(prefix))
    return found


class SafeBrowsingList(object):
    """
    Manages comparisons and data freshness
    """

    # Size of prefixes in bytes
    hash_size = 32
    prefix_size = 4
    type = 'invalid'

    def __init__(self, list_name, source_url, settings):
        self.name = list_name
        self.source_url = source_url
        self.url = urlparse(source_url)
        self.settings = settings

        scheme = self.url.scheme.lower()
        interval = settings.get('refresh_check_interval', 10 * 60)
        if (scheme == 'file' or not (self.url.scheme and self.url.netloc)):
            cls = FileSource
        elif scheme == 's3+file':
            cls = S3FileSource
        elif scheme == 'dir':
            cls = DirectorySource
        elif scheme == 's3+dir':
            cls = S3DirectorySource
        else:
            raise ValueError('Only local single files, local directories, S3 '
                             'single files, and S3 directory sources are '
                             'supported at this time')

        self._source = cls(self.source_url, refresh_interval=interval)
        try:
            self._source.load()
        except NoDataError, e:
            # FIXME log it
            e

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
        try:
            details = self._source.fetch(add_chunks, sub_chunks)
        except NoDataError:
            details = {'adds': (), 'subs': ()}
        details['type'] = self.type
        return details

    def fetch_adds(self, add_chunks):
        return self.fetch(add_chunks, [])['adds']

    def fetch_subs(self, sub_chunks):
        return self.fetch([], sub_chunks)['subs']

    def find_prefix(self, prefix):
        # Don't bother looking for prefixes that aren't the right size
        if len(prefix) != self.prefix_size:
            return ()
        return self._source.find_prefix(prefix)


class Digest256(SafeBrowsingList):

    prefix_size = 32
    type = 'digest256'


class Shavar(SafeBrowsingList):

    prefix_size = 4
    type = 'shavar'
