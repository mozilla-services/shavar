import tempfile
import time

import boto
from boto.s3.key import Key
from moto import mock_s3

from shavar.sources import FileSource, S3FileSource
from shavar.types import ChunkList
from shavar.tests.base import ShavarTestCase, simple_adds, simple_subs


class FileSourceTest(ShavarTestCase):

    def setUp(self):
        source = tempfile.NamedTemporaryFile(delete=False)
        source.write("%s\n%s" % (self.add, self.sub))
        source.flush()
        source.seek(0)
        self.source = source
        return self.source

    def tearDown(self):
        self.source.close()
        del self.source

    def test_load(self):
        f = FileSource("file://" + self.source.name)
        f.load()
        self.assertEqual(f.chunks, ChunkList(add_chunks=simple_adds,
                                             sub_chunks=simple_subs))

    def test_refresh(self):
        # FIXME Timing issues causing intermittent failures.
        if 0:
            f = FileSource("file://" + self.source.name,
                           refresh_interval=0.1)
            f.load()
            self.assertFalse(f.refresh())
            self.source.seek(0)
            self.source.write("%s\n%s" % (self.add, self.sub))
            self.source.flush()
            self.source.seek(0)
            time.sleep(1)
            self.assertTrue(f.refresh())

    def test_list_chunks(self):
        f = FileSource("file://" + self.source.name)
        f.load()
        self.assertEqual(f.list_chunks(), (set([17]), set([18])))

#    def test_fetch(self):
#        vals = {self.hm[:4]: [17], self.hg[:4]: [17]}
#        f = FileSource("file://" + self.source.name)
#        f.load()
#        self.assertEqual(f.fetch([17], [18]), vals)


class TestS3FileSource(ShavarTestCase):

    # I have no idea where I came up with this name or what it might mean but
    # it's keeper.
    bucket_name = 'boost-a-nanny'
    key_name = 'donkula'

    def test_load(self):
        with mock_s3():
            conn = boto.connect_s3()
            b = conn.create_bucket(self.bucket_name)
            k = Key(b)
            k.name = self.key_name
            k.set_contents_from_string("%s\n%s" % (self.add, self.sub))

            f = S3FileSource("s3+file://{0}/{1}".format(self.bucket_name,
                                                        self.key_name))
            f.load()
            self.assertEqual(f.chunks, ChunkList(add_chunks=simple_adds,
                                                 sub_chunks=simple_subs))

    def test_refresh_check(self):
        with mock_s3():
            conn = boto.connect_s3()
            b = conn.create_bucket(self.bucket_name)
            k = Key(b)
            k.name = self.key_name
            k.set_contents_from_string("%s\n%s" % (self.add, self.sub))

            f = S3FileSource("s3+file://{0}/{1}".format(self.bucket_name,
                                                        self.key_name))
            f.load()
            # Change the content of the file to change the MD5 reported
            k.set_contents_from_string("%s\n%s" % (self.sub, self.add))
            self.assertTrue(f.needs_refresh())
