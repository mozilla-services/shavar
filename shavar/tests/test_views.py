import os
from webtest import TestApp
from swagger_parser import SwaggerParser
import yaml

from shavar.tests.base import dummy, hashes, ShavarTestCase
from shavar import __version__


TEST_INI = os.path.join(os.path.dirname(__file__), 'test.ini')


class ViewTests(ShavarTestCase):

    def test_0_list_view(self):
        from shavar.views import list_view
        request = dummy('', path='/list')
        response = list_view(request)
        self.assertEqual(response.text,
                         "moz-abp-shavar\nmozpub-track-digest256\n"
                         "testpub-bananas-digest256\n")

    def test_3_newkey_view(self):
        # from shavar.views import newkey_view
        # Not implemented at the moment because Mozilla requires HTTPS for its
        # hosting site.  As a result the implmementation has been delayed a
        # bit.
        pass


class DeltaViewTests(ShavarTestCase):

    ini_file = 'tests_delta.ini'

    def test_1_downloads_view(self):
        from shavar.views import downloads_view
        req = "moz-abp-shavar;a:1-2,5:s:3\n"
        req += "mozpub-track-digest256;a:1-2:s:6"

        # expected response
        n_header = b"n:1800\n"
        abp_i_header = b"i:moz-abp-shavar\n"
        abp_chunk_download_urls = [
            b"u:https://tracking.services.mozilla.com/moz-abp-shavar/4\n",
            b"u:https://tracking.services.mozilla.com/moz-abp-shavar/6\n"
        ]
        mozpub_i_header = b"i:mozpub-track-digest256\n"
        # chunk 4
        mozpub_chunk_4_list_header = b'a:4:32:64\n'
        mozpub_chunk_4_hashes = [
            (b'\xd9\xa7\xffA\xe0\xd8\x92\xbe\x17\xb3\xc3\x04\xf3fA\xf4:\xc1'
             b'\x1d$\xbe\x13\xa6\x19\xd2\x14\x02DW\xc8\x02\xf2'),
            (b'\xdaw\xc4\xd1\xe3\xf8\x10\xbaz\x0b\x83&l\x7f\xaeI\xba\xcf\x0b'
             b'\xe0\xd2\x86F>k68\xee\xe7\xea+\xeb')
        ]
        # chunk 5
        mozpub_chunk_5_list_header = b"a:5:32:64\n"
        mozpub_chunk_5_hashes = [
            (b'\x82\x7f2\x0e\x94\xc2\xaf,\xc9\xc7d\x9d\x9e\xc9\t\x06<J\xf5\xe7'
             b'\xebsh\x86\n3\xfe\xe0\xab\xdc?\xb1'),
            (b'%\x85\xf3\xc9\xc0?j\xf2\x9f\xeeC\x90_`\x10j\xc8\x1c\x9d\xe5\xea'
             b'\xa5\xd1,\xf0\x92\xa0\x93\x17o\x82\x83')
        ]
        # chunk 3
        mozpub_chunk_3_list_header = b"s:3:32:32\n"
        mozpub_sub_hash_1 = (
            b'\t\xa8\xb90\xc8\xb7\x9e|1>^t\x1e\x1dY\xc3\x9a\xe9\x1b\xc1\xf1'
            b'\x0c\xde\xfah\xb4{\xf7u\x19\xbeW'
        )

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        actual = response.body
        self.assertEqual(actual[:len(n_header)], n_header)
        actual = actual.replace(n_header, b'')
        self.assertEqual(actual[:len(abp_i_header)], abp_i_header)
        actual = actual.replace(abp_i_header, b'')
        urls_len = len(abp_chunk_download_urls[0] + abp_chunk_download_urls[0])
        self.assertIn(abp_chunk_download_urls[0], actual[:urls_len])
        self.assertIn(abp_chunk_download_urls[1], actual[:urls_len])
        actual = actual[urls_len:]

        self.assertEqual(actual[:len(mozpub_i_header)], mozpub_i_header)
        actual = actual.replace(mozpub_i_header, b'')
        self.assertEqual(actual[:len(mozpub_chunk_4_list_header)],
                         mozpub_chunk_4_list_header)
        actual = actual.replace(mozpub_chunk_4_list_header, b'')
        chunk_len = len(mozpub_chunk_4_hashes[0] + mozpub_chunk_4_hashes[1])
        self.assertIn(mozpub_chunk_4_hashes[0], actual[:chunk_len])
        self.assertIn(mozpub_chunk_4_hashes[1], actual[:chunk_len])
        actual = actual[chunk_len:]
        self.assertEqual(actual[:len(mozpub_chunk_5_list_header)],
                         mozpub_chunk_5_list_header)
        actual = actual.replace(mozpub_chunk_5_list_header, b'')
        chunk_len = len(mozpub_chunk_5_hashes[0] + mozpub_chunk_5_hashes[1])
        self.assertIn(mozpub_chunk_5_hashes[0], actual[:chunk_len])
        self.assertIn(mozpub_chunk_5_hashes[1], actual[:chunk_len])
        actual = actual[chunk_len:]
        self.assertEqual(actual,
                         mozpub_chunk_3_list_header + mozpub_sub_hash_1)

        # Make sure redirects on an empty list are working correctly
        baseurl = "tracking.services.mozilla.com/test-redir-digest256"
        req = "test-redir-digest256;"
        expected = "n:1800\n" \
                   "i:test-redir-digest256\n" \
                   "u:{baseurl}/1\n" \
                   "u:{baseurl}/2\n" \
                   "u:{baseurl}/4\n" \
                   "u:{baseurl}/5\n" \
                   "u:{baseurl}/3\n" \
                   "u:{baseurl}/6\n".format(baseurl=baseurl)

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected.encode())

    def test_2_gethash_view(self):
        from shavar.views import gethash_view
        prefixes = (b"\xd0\xe1\x96\xa0"
                    b"\xfdm~\xb5"
                    b"v\x9c\xf8i"
                    b"\t\xa8\xb90")
        body = "4:{payload_len}\n".format(payload_len=len(prefixes))
        body = body.encode() + prefixes
        header_1 = b"moz-abp-shavar:1:64\n"
        chunk_1 = [hashes['moz'], hashes['goog']]
        header_2 = b"moz-abp-shavar:2:64\n"
        chunk_2 = [hashes['hub'], hashes['py']]
        request = dummy(body, path='/gethash')
        response = gethash_view(request)
        actual = response.body

        self.assertEqual(actual[:len(header_1)], header_1)
        actual = actual.replace(header_1, b'')
        chunk_len = len(chunk_1[0] + chunk_1[1])
        self.assertIn(chunk_1[0], actual[:chunk_len])
        self.assertIn(chunk_1[1], actual[:chunk_len])
        actual = actual[chunk_len:]
        chunk_len = len(chunk_2[0] + chunk_2[1])
        self.assertEqual(actual[:len(header_2)], header_2)
        actual = actual.replace(header_2, b'')
        self.assertIn(chunk_2[0], actual[:chunk_len])
        self.assertIn(chunk_2[1], actual[:chunk_len])
        # Make sure we return a 204 No Content for a prefix that doesn't map
        # to a hash we're serving
        request = dummy("4:4\n\x00\x00\x00\x00", path='/gethash')
        response = gethash_view(request)
        self.assertEqual(response.code, 204)


class NoDeltaViewTests(ShavarTestCase):

    ini_file = 'tests_no_delta.ini'

    def test_2_downloads_view(self):
        from shavar.views import downloads_view

        req = "mozpub-track-digest256;a:1-2,7,9-14,16:s:6"

        downloads_resp_header = (
            b"n:1800\n"
            b"i:mozpub-track-digest256\n"
        )
        chunks_to_add = b"ad:1,2,7,9,10,11,12,13,14,16\n"
        list_header = b"a:17:32:64\n"
        hash_1 = (
            b"\xd0\xe1\x96\xa0\xc2]5\xdd\n\x84Y<\xba\xe0\xf3\x833\xaaXR"
            b"\x996DN\xa2dS\xea\xb2\x8d\xfc\x86"
        )
        hash_2 = (
            b"\xfdm~\xb5\xf82\x1f\x8a\xden)\\;RW\xcaK\xb0\x90V1Z"
            b"\x0bz\xe3?\xf6\x00\x81g\xcd\x97"
        )
        expected = downloads_resp_header + chunks_to_add + list_header

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(expected, response.body[:len(expected)])
        # In the Chunk class the hash attritube is a set of hashes. Since a set
        # is an unordered collection the order for `b''.join(chunk.hashes)` in
        # format_downloads will vary.
        self.assertIn(hash_1, response.body[len(expected):])
        self.assertIn(hash_2, response.body[len(expected):])

        # New downloads request means there should be no adddel or subdel
        # entries in the response even if not_publishing_deltas is enabled
        # for the list.
        req = "mozpub-track-digest256;"
        expected = downloads_resp_header + list_header

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(expected, response.body[:len(expected)])
        self.assertIn(hash_1, response.body[len(expected):])
        self.assertIn(hash_2, response.body[len(expected):])


class VersionViewTest(ShavarTestCase):

    def test_1_test_version_view(self):
        from shavar.views.version import version_view
        request = dummy('', path="/__version__")
        response = version_view(request)
        # compare against version.json in the top level dir
        with open('version.json', 'rb') as f:
            self.assertEqual(response.body, f.read())


class SwaggerViewTest(ShavarTestCase):
    def setUp(self):
        super(SwaggerViewTest, self).setUp()
        from shavar import main
        config = {'__file__': TEST_INI}
        settings = {}
        app = main(config, **settings)
        self.testapp = TestApp(app)

    def test_swagger_view(self):
        res = self.testapp.get('/__api__', status=200)
        # make sure it's compliant
        parser = SwaggerParser(swagger_dict=yaml.load(res.body))
        spec = parser.specification
        self.assertEqual(spec['info']['version'], __version__)
        self.assertEqual(spec['schemes'], ['https'])
        self.assertEqual(spec['host'], 'shavar.stage.mozaws.net')

        # now testing that every GET endpoint is present
        for path, items in spec['paths'].items():
            for verb, options in items.items():
                verb = verb.upper()
                if verb != 'GET':
                    continue
                statuses = [int(st) for st in options['responses'].keys()]
                res = self.testapp.get(path, status=statuses)
