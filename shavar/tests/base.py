import hashlib
import io
import os.path

from pyramid import testing

from mozsvc.tests.support import TestCase

from shavar.types import Chunk, ChunkList


hashes = {'moz': hashlib.sha256('https://www.mozilla.org/').digest(),
          'goog': hashlib.sha256('https://www.google.com/').digest(),
          'hub': hashlib.sha256('https://github.com/').digest(),
          'py': hashlib.sha256('http://www.python.org/').digest()}

simple_adds = [Chunk(chunk_type='a', number=17, hashes=set([hashes['goog'],
                                                            hashes['moz']]),
                     hash_size=32)]
simple_subs = [Chunk(chunk_type='s', number=18, hashes=set([hashes['goog'],
                                                            hashes['moz']]),
                     hash_size=32)]

conf_tmpl = """
[shavar]
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

[heka]
logger = ichnaea
severity = 4
stream_class = heka.streams.DebugCaptureStream
encoder = heka.encoders.NullEncoder

[heka_plugin_raven]
provider = heka_raven.raven_plugin:config_plugin
dsn = udp://username:password@localhost:9001/2
override = True
"""


class DummyRequest(testing.DummyRequest):
    """This is a stupid subclass so I can get a body_file property"""

    @property
    def body_file(self):
        if not hasattr(self, '_buffered'):
            self._buffered = io.BufferedReader(io.BytesIO(self.body))
        return self._buffered


def dummy(body, path="/downloads", **kwargs):
    params = {"apikey": "testing",
              "client": "api",
              "appver": "0.0",
              "pver":   "2.0"}
    if kwargs:
        params.update(kwargs)
    return DummyRequest(params=params, body=body)


def test_file(fname):
    return os.path.join(os.path.dirname(__file__), fname)


# Ensure that test runners don't think this is an actual testcase.
test_file.__test__ = False


class ShavarTestCase(TestCase):

    hm = hashes['moz']
    hg = hashes['goog']
    _d = ''.join([hm, hg])
    add = "a:17:32:%d\n%s" % (len(_d), _d)
    sub = "s:18:32:%d\n%s" % (len(_d), _d)

    def setUp(self):
        self.maxDiff = None
        super(ShavarTestCase, self).setUp()

    def get_configurator(self):
        config = super(ShavarTestCase, self).get_configurator()
        config.include("shavar")
        return config


def chunkit(n, typ, *urls):
    return Chunk(number=n, chunk_type=typ,
                 hashes=[hashlib.sha256(u).digest() for u in urls])


DELTA_RESULT = ChunkList(add_chunks=[chunkit(1, 'a',
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
