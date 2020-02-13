# -*- coding: utf-8 -*-

# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import unittest
import os.path

from mozsvc.util import (round_time, resolve_name, maybe_resolve_name,
                         dnslookup)


class TestUtil(unittest.TestCase):

    def test_round_time(self):

        # returns a two-digits decimal of the current time
        res = round_time()
        self.assertEqual(len(str(res).split('.')[-1]), 2)

        # can take a timestamp
        res = round_time(129084.198271987)
        self.assertEqual(str(res), '129084.20')

        # can take a str timestamp
        res = round_time('129084.198271987')
        self.assertEqual(str(res), '129084.20')

        # bad values raise ValueErrors
        self.assertRaises(ValueError, round_time, 'bleh')
        self.assertRaises(ValueError, round_time, object())

        # changing the precision
        res = round_time(129084.198271987, precision=3)
        self.assertEqual(str(res), '129084.198')

    def test_resolve_name(self):

        # Resolving by absolute path
        self.assertEqual(os.path.abspath, resolve_name("os.path.abspath"))
        self.assertEqual(os.path.abspath, resolve_name("os.path:abspath"))

        # Resolving by relative path to package object
        self.assertEqual(os.path.abspath, resolve_name(".path.abspath", os))
        self.assertEqual(os.path.abspath, resolve_name(".path:abspath", os))

        # Resolving by relative path to package name
        self.assertEqual(os.path.abspath, resolve_name(".abspath", "os.path"))
        self.assertEqual(os.path.abspath, resolve_name(":abspath", "os.path"))

    def test_maybe_resolve_name(self):

        self.assertEqual(os.path, maybe_resolve_name("os.path"))
        self.assertEqual(os.path, maybe_resolve_name(os.path))
        self.assertEqual(None, maybe_resolve_name(None))

    def test_dnslookup(self):

        # TODO: This priodically breaks when Tarek gets a new IP
        # for his server, we should use something more stable...
        ZIADE_DOT_ORG = "163.172.47.3"

        self.assertEqual(dnslookup('http://ziade.org/'),
                         'http://%s/' % (ZIADE_DOT_ORG,))

        self.assertEqual(dnslookup('http://user:pass@ziade.org:80/path'),
                         'http://user:pass@%s:80/path' % (ZIADE_DOT_ORG,))
