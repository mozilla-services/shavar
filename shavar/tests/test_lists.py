import hashlib
import os.path
import tempfile
import unittest

from shavar.lists import configure_lists, lookup_prefixes

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

    def setUp(self):
        conf = tempfile.NamedTemporaryFile()
        source = os.path.join(os.path.dirname(__file__), 'chunk_source')
        conf.write(CONF.format(source=source))
        conf.flush()
        conf.seek(0)
        self.conf = conf
        configure_lists(self.conf.name, ('mozpub-track-digest256',
                                         'moz-abp-shavar'))

    def tearDown(self):
        self.conf.close()
        del self.conf

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


class Digest256ListTest(unittest.TestCase):
    pass
