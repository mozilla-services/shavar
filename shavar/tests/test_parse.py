import hashlib
import StringIO
import unittest

from shavar.parse import parse_downloads, parse_gethash, parse_file_source
from shavar.types import ChunkList, Chunk, Downloads, DownloadsListInfo
from shavar.tests.base import (
    dummy,
    hashes,
    test_file)


class ParseTest(unittest.TestCase):

    hg = hashes['goog']
    hm = hashes['moz']

    def setUp(self):
        self.maxDiff = None

    def test_parse_download(self):
        """
        Test bodies taken from
        https://developers.google.com/safe-browsing/developers_guide_v2
        """
        # empty list
        p = parse_downloads(dummy("acme-malware-shavar;"))
        d = Downloads()
        d.append(DownloadsListInfo("acme-malware-shavar"))
        self.assertEqual(p, d)

        # empty list w/ MAC
        p = parse_downloads(dummy("acme-malware-shavar;mac"))
        d = Downloads()
        d.append(DownloadsListInfo("acme-malware-shavar", wants_mac=True))
        self.assertEqual(p, d)

        # with size
        p = parse_downloads(dummy("s;200\nacme-malware-shavar;"))
        d = Downloads(200)
        d.append(DownloadsListInfo("acme-malware-shavar"))
        self.assertEqual(p, d)

        # with chunks
        p = parse_downloads(dummy("googpub-phish-shavar;a:1,2,3,4,5"))
        d = Downloads()
        dli = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli)
        dli.add_range_claim('a', 1, 5)
        self.assertEqual(p, d)

        # chunks w/ MAC
        p = parse_downloads(dummy("googpub-phish-shavar;a:1,2,3:mac"))
        d = Downloads()
        dli = DownloadsListInfo("googpub-phish-shavar", wants_mac=True)
        d.append(dli)
        dli.add_range_claim('a', 1, 3)
        self.assertEqual(p, d)

        # chunks w/ ranges
        p = parse_downloads(dummy("googpub-phish-shavar;a:1-5,10,12"))
        d = Downloads()
        dli = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli)
        dli.add_range_claim('a', 1, 5)
        dli.add_claim('a', 10)
        dli.add_claim('a', 12)
        self.assertEqual(p, d)

        # with add & subtract chunks
        p = parse_downloads(dummy("googpub-phish-shavar;a:1-5,10:s:3-8"))
        d = Downloads()
        dli = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli)
        dli.add_range_claim('a', 1, 5)
        dli.add_claim('a', 10)
        dli.add_range_claim('s', 3, 8)
        self.assertEqual(p, d)

        # with add & subtract chunks out of order
        p = parse_downloads(dummy("googpub-phish-shavar;a:3-5,1,10"))
        d = Downloads()
        dli = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli)
        dli.add_range_claim('a', 3, 5)
        dli.add_claim('a', 1)
        dli.add_claim('a', 10)
        self.assertEqual(p, d)

        # with multiple lists
        s = "googpub-phish-shavar;a:1-3,5:s:4-5\n"
        s += "acme-white-shavar;a:1-7:s:1-2"
        p = parse_downloads(dummy(s))

        d = Downloads()
        dli0 = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli0)
        dli0.add_range_claim('a', 1, 3)
        dli0.add_claim('a', 5)
        dli0.add_range_claim('s', 4, 5)

        dli1 = DownloadsListInfo("acme-white-shavar")
        d.append(dli1)
        dli1.add_range_claim('a', 1, 7)
        dli1.add_range_claim('s', 1, 2)
        self.assertEqual(p, d)

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
        self.assertEqual(p, set(d))

    def test_parse_gethash_errors(self):
        pass

    def test_parse_file_source(self):
        d = ''.join([self.hm, self.hg])
        add = "a:17:32:%d\n%s" % (len(d), d)
        sub = "s:18:32:%d\n%s" % (len(d), d)

        adds = [Chunk(chunk_type='a', number=17, hashes=set([self.hg,
                                                             self.hm]),
                      hash_size=32)]
        subs = [Chunk(chunk_type='s', number=18, hashes=set([self.hg,
                                                             self.hm]),
                      hash_size=32)]

        self.assertEqual(parse_file_source(StringIO.StringIO(add)),
                         ChunkList(add_chunks=adds))
        self.assertEqual(parse_file_source(StringIO.StringIO(sub)),
                         ChunkList(sub_chunks=subs))
        # Both adds and subs with a spurious newline in between
        both = "%s\n%s" % (add, sub)
        self.assertEqual(parse_file_source(StringIO.StringIO(both)),
                         ChunkList(add_chunks=adds, sub_chunks=subs))

    def test_parse_file_source_delta(self):
        def chunkit(n, typ, *urls):
            return Chunk(number=n, chunk_type=typ,
                         hashes=[hashlib.sha256(u).digest() for u in urls])

        result = ChunkList(add_chunks=[chunkit(1, 'a',
                                               'https://www.mozilla.org/',
                                               'https://www.google.com/'),
                                       chunkit(2, 'a', 'https://github.com/',
                                               'http://www.python.org/'),
                                       chunkit(4, 'a',
                                               'http://www.haskell.org/',
                                               'https://www.mozilla.com/'),
                                       chunkit(5, 'a', 'http://www.erlang.org',
                                               'http://golang.org/')],
                           sub_chunks=[chunkit(3, 's',
                                               'https://github.com/'),
                                       chunkit(6, 's',
                                               'http://golang.org')])
        p = parse_file_source(open(test_file('delta_chunk_source')))
        self.assertEqual(p, result)

    def test_parse_file_source_errors(self):
        pass
