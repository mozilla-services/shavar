import os.path

from pyramid import testing


def dummy(body, path="/downloads", **kwargs):
    params = {"apikey": "",
              "client": "api",
              "appver": "0.0",
              "pver":   "2.0"}
    if kwargs:
        params.update(kwargs)
    return testing.DummyRequest(params=params, body=body)

def test_file(fname):
    return os.path.join(os.path.dirname(__file__), fname)
