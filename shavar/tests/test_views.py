from shavar.tests.base import dummy, hashes, ShavarTestCase


class ViewTests(ShavarTestCase):

    def test_0_list_view(self):
        from shavar.views import list_view
        request = dummy('', path='/list')
        response = list_view(request)
        self.assertEqual(response.text,
                         "mozpub-track-digest256\nmoz-abp-shavar\n")

    def test_3_newkey_view(self):
        from shavar.views import newkey_view
        if False:
            expected = ''
            request = dummy('', path='/newkey')
            response = newkey_view(request)
            self.assertEqual(response.body, expected)


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
