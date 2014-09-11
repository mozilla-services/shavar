from shavar.lists import get_list, lookup_prefixes, Digest256
from shavar.tests.base import dummy, hashes, ShavarTestCase


class ListsTest(ShavarTestCase):

    def test_0_get_list(self):
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        sblist = get_list(dumdum, 'mozpub-track-digest256')
        self.assertIsInstance(sblist, Digest256)

    def test_1_lookup_prefixes(self):
        dumdum = dummy(body='4:4\n%s' % hashes['goog'][:4], path='/gethash')
        prefixes = lookup_prefixes(dumdum, [self.hg[:4]])
        self.assertEqual(prefixes, {'moz-abp-shavar': {17: [hashes['goog']]}})


class DeltaListsTest(ShavarTestCase):

    ini_file = "tests_delta.ini"

    def test_2_delta(self):
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
