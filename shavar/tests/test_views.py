import tempfile
import unittest

from konfig import Config
from pyramid import testing

from shavar import read_config
from shavar.lists import configure_lists
from shavar.tests.base import conf_tmpl, dummy, hashes, test_file


class ViewTests(unittest.TestCase):

    def _config(self, fname='chunk_source', deltas=False):
        conf = tempfile.NamedTemporaryFile()
        source = test_file(fname)
        conf.write(conf_tmpl.format(source=source, deltas=deltas))
        conf.flush()
        conf.seek(0)
        c = Config(conf.name)
        self.config = testing.setUp(settings=c)
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

    def test_0_list_view(self):
        from shavar.views import list_view
        request = dummy('', path='/list')
        response = list_view(request)
        self.assertEqual(response.text,
                         "mozpub-track-digest256\nmoz-abp-shavar\n")

    def test_1_downloads_view(self):
        from shavar.views import downloads_view
        # Use a more complex source than the default
        self.conf = self._config('delta_chunk_source')

        req = "moz-abp-shavar;a:1-2,5:s:3\n"
        req += "mozpub-track-digest256;a:1-2:s:6"
        expected = "n:2700\n" \
                   "i:mozpub-track-digest256\n" \
                   "a:4:32:64\n" \
                   "\xd9\xa7\xffA\xe0\xd8\x92\xbe\x17\xb3\xc3\x04\xf3fA\xf4:" \
                   "\xc1\x1d$\xbe\x13\xa6\x19\xd2\x14\x02DW\xc8\x02\xf2" \
                   "\xdaw\xc4\xd1\xe3\xf8\x10\xbaz\x0b\x83&l\x7f\xaeI\xba\xcf" \
                   "\x0b\xe0\xd2\x86F>k68\xee\xe7\xea+\xeb" \
                   "a:5:32:64\n" \
                   "\x82\x7f2\x0e\x94\xc2\xaf,\xc9\xc7d\x9d\x9e\xc9\t\x06<J" \
                   "\xf5\xe7\xebsh\x86\n3\xfe\xe0\xab\xdc?\xb1" \
                   "%\x85\xf3\xc9\xc0?j\xf2\x9f\xeeC\x90_`\x10j\xc8\x1c\x9d" \
                   "\xe5\xea\xa5\xd1,\xf0\x92\xa0\x93\x17o\x82\x83" \
                   "s:3:32:32\n" \
                   "\t\xa8\xb90\xc8\xb7\x9e|1>^t\x1e\x1dY\xc3\x9a\xe9\x1b\xc1" \
                   "\xf1\x0c\xde\xfah\xb4{\xf7u\x19\xbeW" \
                   "i:moz-abp-shavar\n" \
                   "u:https://tracking.services.mozilla.com/moz-abp-shavar/4\n" \
                   "u:https://tracking.services.mozilla.com/moz-abp-shavar/6\n"

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected)

    def test_2_downloads_view(self):
        from shavar.views import downloads_view
        self.conf = self._config('no_deltas_chunk_source', deltas=True)

        # req = "moz-abp-shavar;a:1-2,5:s:3\n"
        req = "mozpub-track-digest256;a:1-2:s:6"
        expected = "n:2700\n" \
                   "i:mozpub-track-digest256\n" \
                   "ad:1-16\n" \
                   "a:17:32:64\n" \
                   "\xd0\xe1\x96\xa0\xc2]5\xdd\n\x84Y<\xba\xe0\xf3\x833\xaaXR" \
                   "\x996DN\xa2dS\xea\xb2\x8d\xfc\x86\xfdm~\xb5\xf82\x1f\x8a" \
                   "\xden)\\;RW\xcaK\xb0\x90V1Z\x0bz\xe3?\xf6\x00\x81g\xcd\x97"

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected)

    def test_3_gethash_view(self):
        from shavar.views import gethash_view
        # Use a more complex source than the default
        self.conf = self._config('delta_chunk_source')
        prefixes = "\xd0\xe1\x96\xa0" \
                   "\xfdm~\xb5" \
                   "v\x9c\xf8i" \
                   "\t\xa8\xb90"
        body = "4:{payload_len}\n{payload}".format(payload=prefixes,
                                                   payload_len=len(prefixes))
        expected = "moz-abp-shavar:1:64\n{0}{1}" \
                   "moz-abp-shavar:2:64\n{2}{3}".format(hashes['moz'],
                                                        hashes['goog'],
                                                        hashes['hub'],
                                                        hashes['py'])
        request = dummy(body, path='/gethash')
        response = gethash_view(request)
        self.assertEqual(response.body, expected)

    def test_4_newkey_view(self):
        from shavar.views import newkey_view
        if False:
            expected = ''
            request = dummy('', path='/newkey')
            response = newkey_view(request)
            self.assertEqual(response.body, expected)
