import os
import posixpath

import boto
from boto.s3.key import Key
from moto import mock_s3

from shavar.exceptions import MissingListDataError
from shavar.lists import (
    get_list,
    lookup_prefixes,
    Digest256,
    match_with_versioned_list,
    get_versioned_list_name
)
from shavar.tests.base import dummy, hashes, ShavarTestCase, test_file


class ListsTest(ShavarTestCase):

    def test_0_get_list(self):
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        sblist = get_list(dumdum, 'mozpub-track-digest256')
        self.assertIsInstance(sblist, Digest256)

    def test_1_lookup_prefixes(self):
        dumdum = dummy(body='4:4\n%s' % hashes['goog'][:4], path='/gethash')
        prefixes = lookup_prefixes(dumdum, [self.hg[:4]])
        self.assertEqual(prefixes, {'moz-abp-shavar': {17: [hashes['goog']]}})

    def test_2_get_list_list_not_served(self):
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        self.assertRaises(
            MissingListDataError, get_list, dumdum, 'this-list-dne'
        )

    def test_3_match_with_versioned_list_version_not_specified(self):
        list_name = match_with_versioned_list(
            'none', ['70.0', '71.0'], 'mozpub-track-digest256')
        self.assertEquals(list_name, 'mozpub-track-digest256')

    def test_4_match_with_versioned_list_version_lower_than_supported(self):
        list_name = match_with_versioned_list(
            '68.0', ['70.0', '71.0'], 'mozpub-track-digest256')
        self.assertEquals(list_name, '69.0-mozpub-track-digest256')

    def test_5_match_with_versioned_list_version_exact_match(self):
        list_name = match_with_versioned_list(
            '70.0', ['70.0', '71.0'], 'mozpub-track-digest256')
        self.assertEquals(list_name, '70.0-mozpub-track-digest256')

    def test_6_match_with_versioned_list_version_fuzzy_match(self):
        list_name = match_with_versioned_list(
            '71.0a1', ['70.0', '71.0'], 'mozpub-track-digest256')
        self.assertEquals(list_name, '71.0-mozpub-track-digest256')

    def test_7_match_with_versioned_list_version_fuzzy_match(self):
        list_name = match_with_versioned_list(
            '72.0a1', ['70.0', '71.0'], 'mozpub-track-digest256')
        self.assertEquals(list_name, 'mozpub-track-digest256')

    def test_8_get_versioned_list_name(self):
        list_name = get_versioned_list_name('70.0', 'mozpub-track-digest256')
        self.assertEquals(list_name, '70.0-mozpub-track-digest256')


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


class S3SourceListsTest(ShavarTestCase):

    ini_file = "tests_s3.ini"

    lists_served_bucket_name = 'shavar-lists-dev'

    bucket_name = 'boost-a-nanny'
    key_name = 'delta_chunk_source'

    dir_bucket_name = 'pickle-farthing'
    dir_list_name = 'testpub-bananas-digest256'

    def setUp(self):
        self.mock = mock_s3()
        self.mock.start()

        #
        # Populate the data in mock S3
        #
        conn = boto.connect_s3()

        # s3+dir lists_served bucket first
        b = conn.create_bucket(self.lists_served_bucket_name)
        for fname in ['mozpub-track-digest256.ini',
                      'testpub-bananas-digest256.ini']:
            k = Key(b)
            k.name = fname
            f = open(os.path.join(
                os.path.dirname(__file__), 'lists_served_s3', fname
            ))
            k.set_contents_from_file(f)

        # s3+file contents
        b = conn.create_bucket(self.bucket_name)
        k = Key(b)
        k.name = self.key_name
        with open(test_file(self.key_name), 'rb') as f:
            k.set_contents_from_file(f)

        # s3+dir keys and contents
        b = conn.create_bucket(self.dir_bucket_name)
        for fname in ('index.json', '1', '2', '3', '4', '5', '6'):
            k = Key(b)
            k.name = posixpath.join(self.dir_list_name, fname)
            with open(test_file(posixpath.join('delta_dir_source', fname)),
                      'rb') as f:
                k.set_contents_from_file(f)

        # initialize the internal list data structure via the normal method
        super(S3SourceListsTest, self).setUp()

    def tearDown(self):
        self.mock.stop()
        super(S3SourceListsTest, self).tearDown()

    def test_3_s3_sources_in_list_instantiation(self):
        # Basically the same tests in test_0_get_list and test_2_delta above
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        for list_ in ('mozpub-track-digest256', 'testpub-bananas-digest256'):
            sblist = get_list(dumdum, list_)
            self.assertIsInstance(sblist, Digest256)
            self.assertEqual(sblist.delta([1, 2], [3]), ([4, 5], [6]))


class DataRefreshTest(ShavarTestCase):

    def test_5_data_refresh(self):
        dumdum = dummy(body='4:4\n%s' % self.hg[:4], path='/gethash')
        d = dumdum.registry.settings.get('shavar.refresh_check_interval')
        self.assertEqual(d, 29)
        abp = dumdum.registry['shavar.serving']['moz-abp-shavar']
        self.assertEqual(abp._source.interval, 29)
        track = dumdum.registry['shavar.serving']['mozpub-track-digest256']
        self.assertEqual(track._source.interval, 23)
