import os
import posixpath
import tempfile
import time

import boto
from boto.s3.key import Key
from moto import mock_s3_deprecated as mock_s3

from shavar.exceptions import NoDataError
from shavar.sources import (
    DirectorySource,
    FileSource,
    S3DirectorySource,
    S3FileSource)
from shavar.types import ChunkList
from shavar.tests.base import (
    DELTA_RESULT,
    ShavarTestCase,
    simple_adds,
    simple_subs,
    test_file)


class FileSourceTest(ShavarTestCase):

    def setUp(self):
        source = tempfile.NamedTemporaryFile(delete=False)
        source.write(self.add + b'\n' + self.sub)
        source.flush()
        source.seek(0)
        self.source = source
        return self.source

    def tearDown(self):
        self.source.close()
        del self.source

    def test_load(self):
        f = FileSource("file://" + self.source.name, 1)
        f.load()
        self.assertEqual(f.chunks, ChunkList(add_chunks=simple_adds,
                                             sub_chunks=simple_subs))

    def test_refresh(self):
        # FIXME Timing issues causing intermittent failures.
        f = FileSource("file://" + self.source.name, 0.5)
        f.load()
        self.assertFalse(f.refresh())
        self.source.seek(0)
        self.source.write(self.add + b'\n' + self.sub)
        self.source.flush()
        self.source.seek(0)
        times = os.stat(self.source.name)
        os.utime(self.source.name, (times.st_atime, times.st_mtime + 2))
        self.assertTrue(f.needs_refresh())

    def test_list_chunks(self):
        f = FileSource("file://" + self.source.name, 1)
        f.load()
        self.assertEqual(f.list_chunks(), (set([17]), set([18])))

    def test_no_data(self):
        f = FileSource("file://tarantula", 1)
        self.assertRaises(NoDataError, f.load)

#    def test_fetch(self):
#        vals = {self.hm[:4]: [17], self.hg[:4]: [17]}
#        f = FileSource("file://" + self.source.name)
#        f.load()
#        self.assertEqual(f.fetch([17], [18]), vals)


class TestDirectorySource(ShavarTestCase):

    def test_load(self):
        path = test_file("delta_dir_source")
        d = DirectorySource("dir://{0}".format(path), 1)
        d.load()
        self.assertEqual(d.chunks, DELTA_RESULT)

    def test_refresh(self):
        path = test_file("delta_dir_source")
        d = DirectorySource("dir://{0}".format(path), 1)
        d.load()
        times = os.stat(d.url.path)
        os.utime(d.url.path, (times.st_atime, int(time.time()) + 2))
        self.assertTrue(d.needs_refresh())

    def test_no_data(self):
        d = DirectorySource("dir://tarantula", 1)
        self.assertRaises(NoDataError, d.load)


class TestS3FileSource(ShavarTestCase):

    # I have no idea where I came up with this name or what it might mean but
    # it's a keeper.
    bucket_name = 'boost-a-nanny'
    key_name = 'beebop/donkula'

    def test_load(self):
        with mock_s3():
            conn = boto.connect_s3()
            b = conn.create_bucket(self.bucket_name)
            k = Key(b)
            k.name = self.key_name
            k.set_contents_from_string(self.add + b'\n' + self.sub)

            f = S3FileSource("s3+file://{0}/{1}".format(self.bucket_name,
                                                        self.key_name),
                             0.5)
            f.load()
            self.assertEqual(f.chunks, ChunkList(add_chunks=simple_adds,
                                                 sub_chunks=simple_subs))

    def test_refresh(self):
        with mock_s3():
            conn = boto.connect_s3()
            b = conn.create_bucket(self.bucket_name)
            k = Key(b)
            k.name = self.key_name
            k.set_contents_from_string(self.add + b'\n' + self.sub)

            f = S3FileSource("s3+file://{0}/{1}".format(self.bucket_name,
                                                        self.key_name),
                             0.5)
            f.load()
            # Change the content of the file to change the MD5 reported
            k.set_contents_from_string("%s\n%s" % (self.sub, self.add))
            self.assertTrue(f.needs_refresh())

    def test_no_data(self):
        with mock_s3():
            source_url = "s3+file://{0}/{1}".format(self.bucket_name,
                                                    self.key_name)

            # No bucket
            f = S3FileSource(source_url, 0.5)
            with self.assertRaises(NoDataError) as ecm:
                f.load()
            self.assertEqual(str(ecm.exception),
                             'Could not find bucket "{0}": S3ResponseError: '
                             '404 Not Found\n'.format(self.bucket_name))

            # Empty bucket
            boto.connect_s3().create_bucket(self.bucket_name)
            f = S3FileSource(source_url, 0.5)
            with self.assertRaises(NoDataError) as ecm:
                f.load()
            self.assertEqual(str(ecm.exception),
                             'No chunk file found at "{0}"'
                             .format(source_url))


class TestS3DirectorySource(ShavarTestCase):

    bucket_name = 'pickle-farthing'
    list_name = 'testpub-bananas-digest256'

    def test_load(self):
        with mock_s3():
            conn = boto.connect_s3()
            b = conn.create_bucket(self.bucket_name)
            for fname in ('index.json', '1', '2', '3', '4', '5', '6'):
                k = Key(b)
                k.name = posixpath.join(self.list_name, fname)
                with open(test_file(posixpath.join('delta_dir_source', fname)),
                          'rb') as f:
                    k.set_contents_from_file(f)

            d = S3DirectorySource("s3+dir://{0}/{1}".format(self.bucket_name,
                                                            self.list_name), 1)
            d.load()
            self.assertEqual(d.chunks, DELTA_RESULT)

    def test_no_data(self):
        source_url = "s3+dir://tarantula/bigandblue/"
        index_url = posixpath.join(source_url, 'index.json')

        index_body = """{
                            "name": "tarantula",
                            "chunks": {
                                "1": {
                                    "path": "1"
                                }
                            }
                        }"""

        with mock_s3():
            # No bucket
            d = S3DirectorySource(source_url, 1)
            with self.assertRaises(NoDataError) as ecm:
                d.load()
            self.assertEqual(str(ecm.exception),
                             'No such bucket "tarantula"')

            # Empty bucket
            # save bucket object for use in index-no-data-file test below
            b = boto.connect_s3().create_bucket("tarantula")
            d = S3DirectorySource(source_url, 1)
            with self.assertRaises(NoDataError) as ecm:
                d.load()
            self.assertEqual(str(ecm.exception),
                             'No index file found at "{0}"'
                             .format(index_url))

            # Index present but with missing data files
            k = Key(b)
            k.name = 'bigandblue/index.json'
            k.set_contents_from_string(index_body)
            d = S3DirectorySource(source_url, 1)
            with self.assertRaises(NoDataError) as ecm:
                d.load()
            self.assertEqual(str(ecm.exception),
                             'Parsing failure: Error parsing '
                             '"/bigandblue/index.json": Invalid chunk '
                             'filename: "1"')
