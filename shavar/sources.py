import os

# posixpath instead of os.path because posixpath will always use / as the path
# separator.  Basically a Windows portability consideration.
import posixpath
import tempfile
import time
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

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
        self.chunk_index = {"adds": set(()), "subs": set(())}
        self.prefixes = None
        self.no_data = True

    def load(self):
        raise NotImplementedError

    def _populate_chunks(self, fp, parser_func, *args, **kwargs):
        try:
            self.chunks = parser_func(fp, *args, **kwargs)
            self.last_check = int(time.time())
            self.last_refresh = int(time.time())
            self.chunk_index = {
                "adds": set(self.chunks.adds.keys()),
                "subs": set(self.chunks.subs.keys()),
            }
        except ParseError as e:
            raise ParseError(f'Error parsing "{self.url.path}": {e}')

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

        chunks = {"adds": [], "subs": []}
        for chunk_num in adds:
            chunks["adds"].append(self.chunks.adds[chunk_num])
        for chunk_num in subs:
            chunks["subs"].append(self.chunks.subs[chunk_num])
        return chunks

    def list_chunks(self):
        self.refresh()
        return (self.chunk_index["adds"], self.chunk_index["subs"])

    def find_prefix(self, prefix):
        return self.chunks.find_prefix(prefix)


# FIXME  Some of the logic here probably needs to be migrated into the Source
#        class
class FileSource(Source):
    """
    Source for single files accessible via simple filesystem calls
    """

    def load(self):
        if not os.path.exists(self.url.path) or os.stat(self.url.path).st_size <= 2:
            # We can't find the data for that list
            self.no_data = True
            raise NoDataError(f'Known list, no data found: "{self.url.path}"')

        with open(self.url.path, "rb") as f:
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

    index_name = "index.json"

    def __init__(self, source_url, refresh_interval):
        if (
            source_url[-1] == "/"
            or source_url[-len(self.index_name) :] != self.index_name
        ):
            source_url = posixpath.join(source_url, self.index_name)

        # Relative path to a directory, tweak slightly so urlparse will parse
        # it correctly
        if source_url[6] != "/":
            source_url = source_url[6:]

        super(DirectorySource, self).__init__(source_url, refresh_interval)

    def load(self):
        if not os.path.exists(self.url.path):
            self.no_data = True
            raise NoDataError(
                f'Known list, no directory index found: "{self.url.path}"'
            )

        with open(self.url.path, "r") as f:
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
        self.key_name = self.url.path.lstrip("/")

    def _s3(self):
        return boto3.client("s3")

    def _head_object(self, s3=None):
        if s3 is None:
            s3 = self._s3()
        try:
            return s3.head_object(Bucket=self.url.netloc, Key=self.key_name)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchKey", "NoSuchBucket"):
                return None
            raise NoDataError(f'Could not access "{self.source_url}": {e}')

    def load(self):
        s3 = self._s3()

        try:
            s3.head_bucket(Bucket=self.url.netloc)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self.no_data = True
                raise NoDataError(f'No chunk file found at "{self.source_url}"')
            raise NoDataError(f'Could not find bucket "{self.url.netloc}": {e}')

        meta = self._head_object(s3)
        if meta is None:
            self.no_data = True
            raise NoDataError(f'No chunk file found at "{self.source_url}"')

        with tempfile.TemporaryFile() as fp:
            s3.download_fileobj(self.url.netloc, self.key_name, fp)
            fp.seek(0)
            self._populate_chunks(fp, parse_file_source)
            self.current_etag = meta["ETag"]
        self.no_data = False

    def needs_refresh(self):
        meta = self._head_object()
        if meta is None:
            return False
        return meta["ETag"] != self.current_etag


class S3DirectorySource(S3FileSource):
    index_name = "index.json"

    def __init__(self, source_url, refresh_interval):
        if (
            source_url[-1] == "/"
            or source_url[-len(self.index_name) :] != self.index_name
        ):
            source_url = posixpath.join(source_url, self.index_name)
        super(S3DirectorySource, self).__init__(source_url, refresh_interval)

    def load(self):
        s3 = self._s3()

        try:
            s3.head_bucket(Bucket=self.url.netloc)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                raise NoDataError(f'No such bucket "{self.url.netloc}"')
            raise

        def s3exists(path):
            key = posixpath.join(posixpath.dirname(self.url.path), path).lstrip("/")
            try:
                s3.head_object(Bucket=self.url.netloc, Key=key)
                return True
            except ClientError:
                return False

        def s3open(path, mode):
            key = posixpath.join(posixpath.dirname(self.url.path), path).lstrip("/")
            fp = tempfile.TemporaryFile()
            s3.download_fileobj(self.url.netloc, key, fp)
            fp.seek(0)
            return fp

        meta = self._head_object(s3)
        if not meta:
            self.no_data = True
            raise NoDataError(f'No index file found at "{self.source_url}"')

        with tempfile.TemporaryFile() as fp:
            s3.download_fileobj(self.url.netloc, self.key_name, fp)
            fp.seek(0)
            try:
                self._populate_chunks(
                    fp, parse_dir_source, exists_cb=s3exists, open_cb=s3open
                )
            except ParseError as e:
                raise NoDataError(f"Parsing failure: {e}")
            self.current_etag = meta["ETag"]
        self.no_data = False
