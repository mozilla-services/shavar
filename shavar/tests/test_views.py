from shavar.tests.base import dummy, hashes, ShavarTestCase


class ViewTests(ShavarTestCase):

    def test_0_list_view(self):
        from shavar.views import list_view
        request = dummy('', path='/list')
        response = list_view(request)
        self.assertEqual(response.text,
                         "mozpub-track-digest256\nmoz-abp-shavar\n")

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
        expected = "n:2700\n" \
                   "i:mozpub-track-digest256\n" \
                   "a:4:32:64\n" \
                   "\xd9\xa7\xffA\xe0\xd8\x92\xbe\x17\xb3\xc3\x04\xf3fA\xf4:" \
                   "\xc1\x1d$\xbe\x13\xa6\x19\xd2\x14\x02DW\xc8\x02\xf2" \
                   "\xdaw\xc4\xd1\xe3\xf8\x10\xbaz\x0b\x83&l\x7f\xaeI\xba" \
                   "\xcf\x0b\xe0\xd2\x86F>k68\xee\xe7\xea+\xeb" \
                   "a:5:32:64\n" \
                   "\x82\x7f2\x0e\x94\xc2\xaf,\xc9\xc7d\x9d\x9e\xc9\t\x06<J" \
                   "\xf5\xe7\xebsh\x86\n3\xfe\xe0\xab\xdc?\xb1" \
                   "%\x85\xf3\xc9\xc0?j\xf2\x9f\xeeC\x90_`\x10j\xc8\x1c\x9d" \
                   "\xe5\xea\xa5\xd1,\xf0\x92\xa0\x93\x17o\x82\x83" \
                   "s:3:32:32\n" \
                   "\t\xa8\xb90\xc8\xb7\x9e|1>^t\x1e\x1dY\xc3\x9a\xe9\x1b" \
                   "\xc1\xf1\x0c\xde\xfah\xb4{\xf7u\x19\xbeW" \
                   "i:moz-abp-shavar\n" \
                   "u:https://tracking.services.mozilla.com/moz-abp-shavar/4" \
                   "\n" \
                   "u:https://tracking.services.mozilla.com/moz-abp-shavar/6\n"

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected)

    def test_2_gethash_view(self):
        from shavar.views import gethash_view
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
        expected = "n:2700\n" \
                   "i:mozpub-track-digest256\n" \
                   "ad:1,2,7,9,10,11,12,13,14,16\n" \
                   "a:17:32:64\n" \
                   "\xd0\xe1\x96\xa0\xc2]5\xdd\n\x84Y<\xba\xe0\xf3\x833\xaaX" \
                   "R\x996DN\xa2dS\xea\xb2\x8d\xfc\x86\xfdm~\xb5\xf82\x1f" \
                   "\x8a\xden)\\;RW\xcaK\xb0\x90V1Z\x0bz\xe3?\xf6\x00\x81g" \
                   "\xcd\x97"

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected)

        # New downloads request means there should be no adddel or subdel
        # entries in the response even if not_publishing_deltas is enabled
        # for the list.
        req = "mozpub-track-digest256;"
        expected = "n:2700\n" \
                   "i:mozpub-track-digest256\n" \
                   "a:17:32:64\n" \
                   "\xd0\xe1\x96\xa0\xc2]5\xdd\n\x84Y<\xba\xe0\xf3\x833\xaaX" \
                   "R\x996DN\xa2dS\xea\xb2\x8d\xfc\x86\xfdm~\xb5\xf82\x1f" \
                   "\x8a\xden)\\;RW\xcaK\xb0\x90V1Z\x0bz\xe3?\xf6\x00\x81g" \
                   "\xcd\x97"

        request = dummy(req, path='/downloads')
        response = downloads_view(request)
        self.assertEqual(response.body, expected)
