import hashlib
import tempfile
import time
import unittest

from shavar.sources import DirectorySource, FileSource


class FileSourceTest(unittest.TestCase):

    hm = hashlib.sha256('https://www.mozilla.org/').digest()
    hg = hashlib.sha256('https://www.google.com/').digest()
    _d = ''.join([hm, hg])
    add = "a:17:32:%d\n%s" % (len(_d), _d)
    sub = "s:18:32:%d\n%s" % (len(_d), _d)
    vals = {hm[:4]: [17], hg[:4]: [17]}

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
        self.assertEqual(f.prefixes, self.vals)

    def test_refresh(self):
        # FIXME Timing issues causing intermittent failures.
        if 0:
            f = FileSource("file://" + self.source.name,
                           refresh_interval=0.1)
            f.load()
            lc = f.last_check
            lr = f.last_refresh
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
#        f = FileSource("file://" + self.source.name)
#        f.load()
#        self.assertEqual(f.fetch([17], [18]), self.vals)


class DirectorySourceTest(unittest.TestCase):

    def test_directory_source(self):
        pass
