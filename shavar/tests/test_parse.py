import hashlib
import StringIO
import unittest

from shavar.parse import parse_downloads, parse_gethash, parse_file_source
from shavar.tests.base import dummy, test_file

class ParseTest(unittest.TestCase):

    def test_parse_download(self):
        """
        Test bodies taken from
        https://developers.google.com/safe-browsing/developers_guide_v2
        """
        # empty list
        p = parse_downloads(dummy("acme-malware-shavar;"))
        self.assertEqual(p,
                         {"lists": [("acme-malware-shavar", False, [])],
                          "req_size": None})

        # empty list w/ MAC
        p = parse_downloads(dummy("acme-malware-shavar;mac"))
        self.assertEqual(p,
                         {"lists": [("acme-malware-shavar", True, [])],
                          "req_size": None})

        # with size
        p = parse_downloads(dummy("s;200\nacme-malware-shavar;"))
        self.assertEqual(p,
                         {"lists": [("acme-malware-shavar", False, [])],
                          "req_size": 200})

        # with chunks
        p = parse_downloads(dummy("googpub-phish-shavar;a:1,2,3,4,5"))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", False,
                                     {"adds": set([1, 2, 3, 4, 5]),
                                       'subs': set()})],
                          "req_size": None})

        # chunks w/ MAC
        p = parse_downloads(dummy("googpub-phish-shavar;a:1,2,3:mac"))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", True,
                                     {'adds': set([1, 2, 3]),
                                      'subs': set()})],
                          "req_size": None})

        # chunks w/ ranges
        p = parse_downloads(dummy("googpub-phish-shavar;a:1-5,10,12"))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", False,
                                     {"adds": set([1, 2, 3, 4, 5, 10, 12]),
                                      'subs': set()})],
                          "req_size": None})

        # with add & subtract chunks
        p = parse_downloads(dummy("googpub-phish-shavar;a:1-5,10:s:3-8"))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", False,
                                     {"adds": set([1, 2, 3, 4, 5, 10]),
                                      "subs": set([3, 4, 5, 6, 7, 8])})],
                          "req_size": None})

        # with add & subtract chunks out of order
        p = parse_downloads(dummy("googpub-phish-shavar;a:3-5,1,10"))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", False,
                                     {"adds": set([1, 3, 4, 5, 10]),
                                      'subs': set()})],
                          "req_size": None})

        # with multiple lists
        s = "googpub-phish-shavar;a:1-3,5:s:4-5\n"
        s += "acme-white-shavar;a:1-7:s:1-2"
        p = parse_downloads(dummy(s))
        self.assertEqual(p,
                         {"lists": [("googpub-phish-shavar", False,
                                     {"adds": set([1, 2, 3, 5]),
                                      "subs": set([4, 5])}),
                                    ("acme-white-shavar", False,
                                     {"adds": set([1, 2, 3, 4, 5, 6, 7]),
                                      "subs": set([1, 2])})],
                          "req_size": None})

    def test_parse_download_errors(self):
        pass

    def test_parse_gethash(self):
        h = "4:32\n"
        d = ("\xdd\x01J\xf5",
             "\xedk8\xd9",
             "\x13\x0e?F",
             "o\x85\x0eF",
             "\xd2\x1b\x95\x11",
             "\x99\xd5:\x18",
             "\xef)\xee\x93",
             "AaN\xaf")
        s = ''
        s += h
        for i in d:
            s += i
        p = parse_gethash(dummy(s, path="/gethash"))
        self.assertEqual(p, list(d))

    def test_parse_gethash_errors(self):
        pass

    def test_parse_file_source(self):
        hm = hashlib.sha256('https://www.mozilla.org/').digest()
        hg = hashlib.sha256('https://www.google.com/').digest()
        d = ''.join([hm, hg])
        add = "a:17:32:%d\n%s" % (len(d), d)
        sub = "s:18:32:%d\n%s" % (len(d), d)
        asserts = {hg[:4]: [hg], hm[:4]: [hm]}
        self.assertEqual(parse_file_source(StringIO.StringIO(add)),
                         {'adds': {17: {'chunk': 17, 'size': 32,
                                        'prefixes': asserts}},
                          'subs': {}})
        self.assertEqual(parse_file_source(StringIO.StringIO(sub)),
                         {'subs': {18: {'chunk': 18, 'size': 32,
                                        'prefixes': asserts}},
                          'adds': {}})
        # Both adds and subs with a spurious newline in between
        both = "%s\n%s" % (add, sub)
        self.assertEqual(parse_file_source(StringIO.StringIO(both)),
                         {'adds': {17: {'chunk': 17, 'size': 32,
                                        'prefixes': asserts}},
                          'subs': {18: {'chunk': 18, 'size': 32,
                                        'prefixes': asserts}}})

    def test_parse_file_source_delta(self):
        def hashit(n, *urls):
            H = {'chunk': n, 'size': 32, 'prefixes': {}}
            for u in urls:
                h = hashlib.sha256(u).digest()
                H['prefixes'][h[:4]] = [h]
            return H

        result = {'adds': {1: hashit(1, 'https://www.mozilla.org/',
                                     'https://www.google.com/'),
                           2: hashit(2, 'https://github.com/',
                                     'http://www.python.org/'),
                           4: hashit(4, 'http://www.haskell.org/',
                                      'https://www.mozilla.com/'),
                           5: hashit(5, 'http://www.erlang.org',
                                     'http://golang.org/')},
                  'subs': {3: hashit(3, 'https://github.com/'),
                           6: hashit(6, 'http://golang.org')}}

        p = parse_file_source(open(test_file('delta_chunk_source')))
        self.assertEqual(p, result)

    def test_parse_file_source_errors(self):
        pass
