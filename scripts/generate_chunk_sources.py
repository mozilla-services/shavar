#!/usr/bin/env python

import hashlib
import sys

chunks = {1: {'a': ['https://www.mozilla.org/', 'https://www.google.com/']},
          2: {'a': ['https://github.com/', 'http://www.python.org/']},
          3: {'s': ['https://github.com/']},
          4: {'a': ['http://www.haskell.org/', 'https://www.mozilla.com/']},
          5: {'a': ['http://www.erlang.org', 'http://golang.org/']},
          6: {'s': ['http://golang.org']}}

blob = ''

for num, chunk in chunks.items():
    for addsub, urls in chunk.items():
        blob += "%s:%d:32:" % (addsub, num)
        hashstring = ''
        for url in urls:
            hashstring += hashlib.sha256(url).digest()
        blob += "%d\n" % len(hashstring)
        blob += hashstring
        blob += "\n"

sys.stdout.write(blob)
