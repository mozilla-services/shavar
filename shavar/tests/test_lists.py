import hashlib
import tempfile
import unittest

from shavar.lists import (
    clear_caches,
    configure_lists,
    get_list,
    lookup_prefixes)
from shavar.tests.base import test_file


CONF = """[shavar]
default_proto_ver = 2.0
lists_served = mozpub-track-digest256
               moz-abp-shavar
lists_root = tests

[mozpub-track-digest256]
type = digest256
source = {source}

[moz-abp-shavar]
type = shavar
source = {source}
redirect_url_base = https://tracking.services.mozilla.com/
"""


class ListsTest(unittest.TestCase):

    def _config(self, fname='chunk_source'):
        conf = tempfile.NamedTemporaryFile()
        source = test_file(fname)
        conf.write(CONF.format(source=source))
        conf.flush()
        conf.seek(0)
        configure_lists(conf.name, ('mozpub-track-digest256',
                                    'moz-abp-shavar'))
        return conf

    def setUp(self):
        self.conf = self._config()

    def tearDown(self):
        clear_caches()
        self.conf.close()
        self.conf = None

    def test_lookup_prefixes(self):
        hm = hashlib.sha256('https://www.mozilla.org/').digest()
        hg = hashlib.sha256('https://www.google.com/').digest()
        self.assertEqual(lookup_prefixes(['\xd0\xe1\x96\xa0']),
                         {'\xd0\xe1\x96\xa0': {'moz-abp-shavar': {17: [hg]},
                                               'mozpub-track-digest256':
                                               {17: [hg]}}})
        self.assertEqual(lookup_prefixes(['\xd0\xe1\x96\xa0', '\xfdm~\xb5']),
                         {'\xd0\xe1\x96\xa0': {'moz-abp-shavar': {17: [hg]},
                                               'mozpub-track-digest256':
                                               {17: [hg]}},
                          '\xfdm~\xb5': {'moz-abp-shavar': {17: [hm]},
                                         'mozpub-track-digest256':
                                         {17: [hm]}}})

    def test_delta(self):
        self.conf = self._config('delta_chunk_source')
        sblist = get_list('mozpub-track-digest256')
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
