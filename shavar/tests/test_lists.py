import tempfile
import unittest

from pyramid import testing

from shavar import read_config
from shavar.lists import configure_lists, get_list, lookup_prefixes, Digest256
from shavar.tests.base import (
    conf_tmpl,
    dummy,
    hashes,
    test_file)


class ListsTest(unittest.TestCase):

    hm = hashes['moz']
    hg = hashes['goog']

    def _config(self, fname='chunk_source'):
        conf = tempfile.NamedTemporaryFile()
        source = test_file(fname)
        conf.write(conf_tmpl.format(source=source))
        conf.flush()
        conf.seek(0)
        self.config = testing.setUp()
        # I can't imagine why rfkelly found this to be a subwonderful
        # technique.  Nope.
        read_config(conf.name, self.config.registry.settings)
        configure_lists(conf.name, self.config.registry)
        return conf

    def setUp(self):
        self.maxDiff = None
        self.conf = self._config()

    def tearDown(self):
        self.conf.close()
        self.conf = None
        testing.tearDown()

    def test_0_get_list(self):
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        sblist = get_list(dumdum, 'mozpub-track-digest256')
        self.assertIsInstance(sblist, Digest256)

    def test_1_lookup_prefixes(self):
        dumdum = dummy(body='4:4\n%s' % hashes['goog'][:4], path='/gethash')
        prefixes = lookup_prefixes(dumdum, [self.hg[:4]])
        self.assertEqual(prefixes, {'moz-abp-shavar': {17: [hashes['goog']]}})

    def test_2_delta(self):
        self.conf = self._config('delta_chunk_source')
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        sblist = get_list(dumdum, 'mozpub-track-digest256')
        # By way of explanation:
        #
        # In the data file.
        #   Chunks 1, 2, 4, and 5 are "add" chunks
        #   Chunks 3 and 6 are "sub" chunks
        #
        # So delta([1, 2], [3]) should return
        #    ([4, 5], [6])
        self.assertEqual(sblist.delta([1, 2], [3]), ([4, 5], [6]))


class Digest256ListTest(unittest.TestCase):
    pass
