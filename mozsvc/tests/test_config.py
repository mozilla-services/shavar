# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import unittest
import tempfile
import os
from io import StringIO

from mozsvc.config import (Config, SettingsDict, load_into_settings,
                           get_configurator)


_FILE_ONE = """\
[DEFAULT]
extends = %s

[one]
foo = bar
num = -12
st = "o=k"
lines = 1
        two
        3

env = some ${__STUFF__}
location =  $${HERE}

[two]
a = b
"""

_FILE_TWO = """\
[one]
foo = baz
two = "a"

[three]
more = stuff
location = ${HERE}
"""

_FILE_THREE = """\
[DEFAULT]
extends = no-no,no-no-no-no,no-no-no-no,theresnolimit

[one]
foo = bar
"""

_FILE_FOUR = """\
[global]
foo = bar
baz = bawlp

[auth]
a = b
c = d

[storage]
e = f
g = h

[multi:once]
storage.i = j
storage.k = l

[multi:thrice]
storage.i = jjj
storage.k = lll
"""

_EXTRA = """\
[some]
stuff = True

[other]
thing = ok
"""


class ConfigTestCase(unittest.TestCase):

    def setUp(self):
        os.environ['__STUFF__'] = 'stuff'
        fp, filename = tempfile.mkstemp()
        f = os.fdopen(fp, 'w')
        f.write(_FILE_TWO)
        f.close()
        self.file_one = StringIO(_FILE_ONE % filename)
        self.file_two = filename
        self.file_three = StringIO(_FILE_THREE)

        fp, filename = tempfile.mkstemp()
        f = os.fdopen(fp, 'w')
        f.write(_FILE_FOUR)
        f.close()
        self.file_four = filename

    def tearDown(self):
        if '__STUFF__' in os.environ:
            del os.environ['__STUFF__']
        os.remove(self.file_two)

    def test_reader(self):
        config = Config(self.file_one)

        # values conversion
        self.assertEqual(config.get('one', 'foo'), 'bar')
        self.assertEqual(config.get('one', 'num'), -12)
        self.assertEqual(config.get('one', 'st'), 'o=k')
        self.assertEqual(config.get('one', 'lines'), [1, 'two', 3])
        self.assertEqual(config.get('one', 'env'), 'some stuff')

        # getting a map
        map = config.get_map()
        self.assertEqual(map['one.foo'], 'bar')

        map = config.get_map('one')
        self.assertEqual(map['foo'], 'bar')

        # extends
        self.assertEqual(config.get('three', 'more'), 'stuff')
        self.assertEqual(config.get('one', 'two'), 'a')

    def test_nofile(self):
        # if a user tries to use an inexistant file in extensions,
        # pops an error
        self.assertRaises(IOError, Config, self.file_three)

    def test_load_into_settings(self):
        settings = {}
        load_into_settings(self.file_four, settings)
        self.assertEqual(settings["storage.e"], "f")
        self.assertEqual(settings["storage.g"], "h")
        self.assertEqual(settings["multi.once.storage.i"], "j")
        self.assertEqual(settings["multi.thrice.storage.i"], "jjj")

    def test_get_configurator(self):
        global_config = {"__file__": self.file_four}
        settings = {"pyramid.testing": "test"}
        config = get_configurator(global_config, **settings)
        settings = config.get_settings()
        self.assertEqual(settings["pyramid.testing"], "test")
        self.assertEqual(settings["storage.e"], "f")
        self.assertEqual(settings["storage.g"], "h")
        self.assertEqual(settings["multi.once.storage.i"], "j")
        self.assertEqual(settings.getsection("multi")["once.storage.i"], "j")
        self.assertEqual(settings.getsection("multi.once")["storage.i"], "j")
        self.assertEqual(settings.getsection("multi.once.storage")["i"], "j")

    def test_get_configurator_nofile(self):
        global_config = {"blah": "blech"}
        settings = {"pyramid.testing": "test"}
        config = get_configurator(global_config, **settings)
        settings = config.get_settings()
        self.assertEqual(settings["pyramid.testing"], "test")

    def test_settings_dict_copy(self):
        settings = SettingsDict({
            "a.one": 1,
            "a.two": 2,
            "b.three": 3,
            "four": 4,
        })
        new_settings = settings.copy()
        self.assertEqual(settings, new_settings)
        self.assertTrue(isinstance(new_settings, SettingsDict))

    def test_settings_dict_getsection(self):
        settings = SettingsDict({
            "a.one": 1,
            "a.two": 2,
            "b.three": 3,
            "four": 4,
        })
        self.assertEqual(settings.getsection("a"), {"one": 1, "two": 2})
        self.assertEqual(settings.getsection("b"), {"three": 3})
        self.assertEqual(settings.getsection("c"), {})
        self.assertEqual(settings.getsection(""), {"four": 4})

    def test_settings_dict_setdefaults(self):
        settings = SettingsDict({
            "a.one": 1,
            "a.two": 2,
            "b.three": 3,
            "four": 4,
        })
        settings.setdefaults({"a.two": "TWO", "a.five": 5, "new": "key"})
        self.assertEqual(settings.getsection("a"),
                          {"one": 1, "two": 2, "five": 5})
        self.assertEqual(settings.getsection("b"), {"three": 3})
        self.assertEqual(settings.getsection("c"), {})
        self.assertEqual(settings.getsection(""), {"four": 4, "new": "key"})

    def test_location_interpolation(self):
        config = Config(self.file_one)
        # file_one is a StringIO, so it has no location.
        self.assertEqual(config.get('one', 'location'), '${HERE}')
        # file_two is a real file, so it has a location.
        file_two_loc = os.path.dirname(self.file_two)
        self.assertEqual(config.get('three', 'location'), file_two_loc)
