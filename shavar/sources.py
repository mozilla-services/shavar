import os
import time
from urlparse import urlparse

from shavar.exceptions import NoDataError, ParseError
from shavar.parse import parse_file_source

class Source(object):
    """
    Base class for data sources
    """

    def __init__(self, source_url, refresh_interval=12 * 60 * 60):
        self.source_url = source_url
        self.url = urlparse(self.source_url)
        self.interval = refresh_interval
        self.last_refresh = 0
        self.last_check = 0
        self.chunks = None
        self.prefixes = None

    def load(self):
        raise NotImplemented

    def refresh(self):
        raise NotImplemented

    def fetch(self, adds, subs):
        raise NotImplemented

    def list_chunks(self):
        adds = []
        subs = []
        for type_ in 'adds', 'subs':
            for chunk in self.chunks[type_].keys():
                locals()[type_].append(chunk)
        return set(adds), set(subs)


# FIXME  Some of the logic here probably needs to be migrated into the Source
#        class
class FileSource(Source):
    """
    Source for single files accessible via simple filesystem calls
    """

    def load(self):
        if not os.path.exists(self.url.path):
            # We can't find the data for that list
            raise NoDataError('Known list, no data found: "%s"' % self.url.path)

        try:
            with open(self.url.path, 'rb') as f:
                self.chunks = parse_file_source(f)
                self.last_check = int(time.time())
                self.last_refresh = int(time.time())
        except ParseError, e:
            raise ParseError('Error parsing "%s": %s' % (self.url.path, e))
        except:
            raise NoDataError('Known list, read failure: "%s"' % self.name)

        prefixes = {}
        for num, chunk in self.chunks['adds'].items():
            for prefix in chunk['prefixes']:
                if prefix not in prefixes:
                    prefixes[prefix] = []
                prefixes[prefix].append(num)
        self.prefixes = prefixes

    def refresh(self):
        # Prevent constant refresh checks
        if int(os.stat(self.url.path).st_mtime) <= self.last_refresh:
            self.last_check = int(time.time())
            return False
        self.load()
        return True

    def fetch(self, adds=[], subs=[]):
        if int(time.time()) - self.last_refresh > self.interval:
            self.refresh()
        chunks = {'adds': [], 'subs': []}
        for type_ in 'adds', 'subs':
            for chunk in locals()[type_]:
                chunks[type_].append(self.chunks[type_][chunk])
        return chunks


class DirectorySource(Source):
    pass
