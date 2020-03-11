import io

from shavar.exceptions import ParseError
from shavar.parse import (
    parse_downloads,
    parse_gethash,
    parse_file_source,
    parse_dir_source)
from shavar.types import (
    Chunk,
    ChunkList,
    Downloads,
    DownloadsListInfo,
    LimitExceededError)
from shavar.tests.base import (
    DELTA_RESULT,
    dummy,
    hashes,
    test_file,
    ShavarTestCase)


class ParseTest(ShavarTestCase):

    ini_file = 'tests.ini'

    hg = hashes['goog']
    hm = hashes['moz']

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

        # with multiple lists, at least one empty
        # See https://github.com/mozilla-services/shavar/issues/56
        s = "googpub-phish-shavar;\n"
        s += "acme-white-shavar;a:1-7:s:1-2"
        p = parse_downloads(dummy(s))

        d = Downloads()
        dli0 = DownloadsListInfo("googpub-phish-shavar")
        d.append(dli0)

        dli1 = DownloadsListInfo("acme-white-shavar")
        d.append(dli1)
        dli1.add_range_claim('a', 1, 7)
        dli1.add_range_claim('s', 1, 2)
        self.assertEqual(p, d)

    def test_parse_download_errors(self):
        self.assertRaises(LimitExceededError, parse_downloads,
                          dummy("mozpub-track-digest256;a:1-20000"))

        self.assertRaises(LimitExceededError, parse_downloads,
                          dummy("mozpub-track-digest256;a:1-1002"))

        self.assertRaises(ParseError, parse_downloads,
                          dummy("mozpub-track-digest256"))

    def test_parse_gethash(self):
        h = b"4:32\n"
        d = (b"\xdd\x01J\xf5",
             b"\xedk8\xd9",
             b"\x13\x0e?F",
             b"o\x85\x0eF",
             b"\xd2\x1b\x95\x11",
             b"\x99\xd5:\x18",
             b"\xef)\xee\x93",
             b"AaN\xaf")
        s = b''
        s += h
        for i in d:
            s += i
        p = parse_gethash(dummy(s, path="/gethash"))
        self.assertEqual(p, set(d))
        # Make sure no repeats of issue #32 pop up: test with a single hash
        # prefix
        s = b"4:4\n\xdd\x01J\xf5"
        p = parse_gethash(dummy(s, path="/gethash"))
        self.assertEqual(p, set([b"\xdd\x01J\xf5"]))

    def test_parse_gethash_errors(self):
        # Too short
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("4:\n"))
        self.assertEqual(str(ecm.exception),
                         "Improbably small or large gethash header size: 2")
        # Too long
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("4:" + "1" * 256 + "\n"))
        self.assertEqual(str(ecm.exception),
                         "Improbably small or large gethash header size: 258")
        # Invalid sizes
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("steve:4\n"))
        self.assertEqual(str(ecm.exception),
                         'Invalid prefix or payload size: "steve:4\n"')
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("4:steve\n"))
        self.assertEqual(str(ecm.exception),
                         'Invalid prefix or payload size: "4:steve\n"')
        # Improper payload length
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("4:17\n"))
        self.assertEqual(str(ecm.exception),
                         'Payload length invalid: "17"')
        # Ditto but with a payload shorter than the prefix
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("8:4\n"))
        self.assertEqual(str(ecm.exception),
                         'Payload length invalid: "4"')
        # It seems some clients are hitting the gethash endpoint with a
        # request intended for the downloads endpoint
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("mozpub-track-digest256;a:1423242002"))
        self.assertEqual(str(ecm.exception),
                         "Improbably small or large gethash header size: -1")
        # See https://github.com/mozilla-services/shavar/issues/67
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy("1:10000000000\n"))
        self.assertEqual(str(ecm.exception),
                         "Hash read mismatch: client claimed 10000000000, "
                         "read 0")
        # Stated length of payload is longer than actual payload.  Only 7
        # bytes instead of 8 here.
        with self.assertRaises(ParseError) as ecm:
            parse_gethash(dummy(b"4:8\n\xdd\x01J\xf5\xedk8"))
        self.assertEqual(str(ecm.exception),
                         "Hash read mismatch: client claimed 2, read 1")

    def test_parse_file_source(self):
        d = b''.join([self.hm, self.hg])
        add = b"a:17:32:%d\n%s" % (len(d), d)
        sub = b"s:18:32:%d\n%s" % (len(d), d)

        adds = [Chunk(chunk_type='a', number=17, hashes=set([self.hg,
                                                             self.hm]),
                      hash_size=32)]
        subs = [Chunk(chunk_type='s', number=18, hashes=set([self.hg,
                                                             self.hm]),
                      hash_size=32)]

        self.assertEqual(parse_file_source(io.BytesIO(add)),
                         ChunkList(add_chunks=adds))
        self.assertEqual(parse_file_source(io.BytesIO(sub)),
                         ChunkList(sub_chunks=subs))
        # Both adds and subs with a spurious newline in between
        both = b"%s\n%s" % (add, sub)
        self.assertEqual(parse_file_source(io.BytesIO(both)),
                         ChunkList(add_chunks=adds, sub_chunks=subs))

    def test_parse_file_source_delta(self):
        p = parse_file_source(open(test_file('delta_chunk_source'), 'rb'))
        self.assertEqual(p, DELTA_RESULT)

    def test_parse_file_source_errors(self):
        pass

    def test_parse_dir_source(self):
        p = parse_dir_source(
            open(test_file('delta_dir_source/index.json'), 'rb')
        )
        self.assertEqual(p, DELTA_RESULT)
        # Test with the use of basedir
        p = parse_dir_source(open(test_file('index.json')))
        self.assertEqual(p, DELTA_RESULT)
