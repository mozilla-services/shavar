import os
# posixpath instead of os.path because posixpath will always use / as the path
# separator.  Basically a Windows portability consideration.
import posixpath
import tempfile
import time
from urllib.parse import urlparse

from boto.exception import S3ResponseError
from boto.s3.connection import S3Connection

from shavar.exceptions import NoDataError, ParseError
from shavar.parse import parse_dir_source, parse_file_source
from shavar.types import ChunkList


class Source(object):
    """
    Base class for data sources
    """

    def __init__(self, source_url, refresh_interval):
        self.source_url = source_url
        self.url = urlparse(self.source_url)
        self.interval = int(refresh_interval)
        self.last_refresh = 0
        self.last_check = 0
        # Initialize with an empty data set so we can always continue to serve
        self.chunks = ChunkList()
        self.chunk_index = {'adds': set(()), 'subs': set(())}
        self.prefixes = None
        self.no_data = True

    def load(self):
        raise NotImplementedError

    def _populate_chunks(self, fp, parser_func, *args, **kwargs):
        try:
            self.chunks = parser_func(fp, *args, **kwargs)
            self.last_check = int(time.time())
            self.last_refresh = int(time.time())
            self.chunk_index = {'adds': set(self.chunks.adds.keys()),
                                'subs': set(self.chunks.subs.keys())}
        except ParseError as e:
            raise ParseError('Error parsing "%s": %s' % (self.url.path, e))

    def refresh(self):
        # Prevent constant refresh checks
        now = int(time.time())
        if now - self.interval >= self.last_check:
            self.last_check = now
            if self.needs_refresh():
                self.load()
        return False

    def needs_refresh(self):
        return False

    def fetch(self, adds, subs):
        self.refresh()

        chunks = {'adds': [], 'subs': []}
        for chunk_num in adds:
            chunks['adds'].append(self.chunks.adds[chunk_num])
        for chunk_num in subs:
            chunks['subs'].append(self.chunks.subs[chunk_num])
        return chunks

    def list_chunks(self):
        self.refresh()
        return (self.chunk_index['adds'], self.chunk_index['subs'])

    def find_prefix(self, prefix):
        return self.chunks.find_prefix(prefix)


# FIXME  Some of the logic here probably needs to be migrated into the Source
#        class
class FileSource(Source):
    """
    Source for single files accessible via simple filesystem calls
    """

    def load(self):
        if (not os.path.exists(self.url.path)
                or os.stat(self.url.path).st_size <= 2):
            # We can't find the data for that list
            self.no_data = True
            raise NoDataError('Known list, no data found: "%s"'
                              % self.url.path)

        with open(self.url.path, 'rb') as f:
            self._populate_chunks(f, parse_file_source)
        self.no_data = False

    def needs_refresh(self):
        if int(os.stat(self.url.path).st_mtime) <= self.last_refresh:
            return False
        return True


# Inherits from FileSource to use that subclass's needs_refresh method
class DirectorySource(FileSource):
    """
    Loads chunks from a directory containing individual chunk files with a
    JSON formatted index file.
    """

    index_name = 'index.json'

    def __init__(self, source_url, refresh_interval):
        if (source_url[-1] == '/'
                or source_url[-len(self.index_name):] != self.index_name):
            source_url = posixpath.join(source_url, self.index_name)

        # Relative path to a directory, tweak slightly so urlparse will parse
        # it correctly
        if (source_url[6] != '/'):
            source_url = source_url[6:]

        super(DirectorySource, self).__init__(source_url, refresh_interval)

    def load(self):
        if not os.path.exists(self.url.path):
            self.no_data = True
            raise NoDataError('Known list, no directory index found: "%s"'
                              % self.url.path)

        with open(self.url.path, 'r') as f:
            self._populate_chunks(f, parse_dir_source)
        self.no_data = False


class S3FileSource(Source):
    """
    Loads chunks from a single file in S3 in the on-the-wire format
    """

    def __init__(self, source_url, refresh_interval):
        super(S3FileSource, self).__init__(source_url, refresh_interval)
        self.current_etag = None
        # eliminate preceding slashes in the S3 key name
        elems = list(posixpath.split(posixpath.normpath(self.url.path)))
        while '/' == elems[0]:
            elems.pop(0)
        self.key_name = posixpath.join(*elems)

    def _get_key(self):
        try:
            conn = S3Connection()
            bucket = conn.get_bucket(self.url.netloc)
        except S3ResponseError as e:
            raise NoDataError("Could not find bucket \"%s\": %s"
                              % (self.url.netloc, e))
        return bucket.get_key(self.key_name)

    def load(self):
        s3key = self._get_key()
        if not s3key:
            self.no_data = True
            raise NoDataError('No chunk file found at "%s"' % self.source_url)

        with tempfile.TemporaryFile() as fp:
            s3key.get_contents_to_file(fp)
            # Need to forcibly reset to the beginning of the file
            fp.seek(0)
            self._populate_chunks(fp, parse_file_source)
            self.current_etag = s3key.etag
        self.no_data = False

    def needs_refresh(self):
        s3key = self._get_key()
        if s3key.etag == self.current_etag:
            return False
        return True


class S3DirectorySource(S3FileSource):

    index_name = 'index.json'

    def __init__(self, source_url, refresh_interval):
        if (source_url[-1] == '/'
                or source_url[-len(self.index_name):] != self.index_name):
            source_url = posixpath.join(source_url, self.index_name)
        super(S3DirectorySource, self).__init__(source_url,
                                                refresh_interval)

    def load(self):
        # for the closures to minimize the number of connections to S3
        conn = S3Connection()

        try:
            bucket = conn.get_bucket(self.url.netloc)
        except S3ResponseError as e:
            if e.status == 404:
                raise NoDataError("No such bucket \"{0}\""
                                  .format(self.url.netloc))

        def s3exists(path):
            # Construct the path to the key
            key = posixpath.join(posixpath.dirname(self.url.path), path)
            return bucket.get_key(key)

        def s3open(path, mode):
            key = s3exists(path)
            fp = tempfile.TemporaryFile()
            key.get_contents_to_file(fp)
            fp.seek(0)
            return fp

        s3key = self._get_key()

        if not s3key:
            self.no_data = True
            raise NoDataError('No index file found at "%s"'
                              % posixpath.join(self.source_url))

        with tempfile.TemporaryFile() as fp:
            s3key.get_contents_to_file(fp)
            fp.seek(0)
            try:
                self._populate_chunks(fp, parse_dir_source,
                                      exists_cb=s3exists,
                                      open_cb=s3open)
            except ParseError as e:
                raise NoDataError("Parsing failure: {0}".format(str(e)))

            self.current_etag = s3key.etag
        self.no_data = False
