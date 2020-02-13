# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import unittest2
import tempfile
import os
import time
import itertools

from mozsvc.secrets import Secrets, FixedSecrets, DerivedSecrets


class TestSecrets(unittest2.TestCase):

    def setUp(self):
        self._files = []

    def tearDown(self):
        for file in self._files:
            if os.path.exists(file):
                os.remove(file)

    def tempfile(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        self._files.append(path)
        return path

    def test_read_write(self):
        secrets = Secrets()

        # We can only add one secret per second to the file, since
        # they are timestamped to 1s resolution.  Fake it.
        real_time = time.time
        time.time = itertools.count(int(real_time())).__next__
        try:
            secrets.add('phx23456')
            secrets.add('phx23456')
            secrets.add('phx23')
        finally:
            time.time = real_time

        phx23456_secrets = secrets.get('phx23456')
        self.assertEqual(len(secrets.get('phx23456')), 2)
        self.assertEqual(len(secrets.get('phx23')), 1)

        path = self.tempfile()

        secrets.save(path)

        secrets2 = Secrets(path)
        self.assertEqual(len(secrets2.get('phx23456')), 2)
        self.assertEqual(len(secrets2.get('phx23')), 1)
        self.assertEqual(secrets2.get('phx23456'), phx23456_secrets)

    def test_multiple_files(self):
        # creating two distinct files
        secrets = Secrets()
        secrets.add('phx23456')
        one = self.tempfile()
        secrets.save(one)

        secrets = Secrets()
        secrets.add('phx123')
        two = self.tempfile()
        secrets.save(two)

        # loading the two files
        files = one, two
        secrets = Secrets(files)
        keys = list(secrets.keys())
        keys.sort()
        self.assertEqual(keys, ['phx123', 'phx23456'])

    def test_fixed_secrets(self):
        secrets = FixedSecrets(['one', 'two'])
        self.assertEqual(secrets.get('phx123'), ['one', 'two'])
        self.assertEqual(secrets.get('phx234'), ['one', 'two'])

    def test_derived_secrets(self):
        master_secrets = ['abcdef', '1234567890']
        secrets = DerivedSecrets(master_secrets)
        derived1 = secrets.get('phx123')
        derived2 = secrets.get('phx987')
        # Secrets for the same node should derived consistently.
        self.assertEqual(derived1, secrets.get('phx123'))
        self.assertEqual(derived2, secrets.get('phx987'))
        # Secrets for different nodes should be different.
        self.assertEqual(set(derived1).intersection(derived2), set())
        # Length of derived secret mathches length of master secret.
        for derived in (derived1, derived2):
            self.assertEqual(len(derived), len(master_secrets))
            for d, m in zip(derived, master_secrets):
                self.assertEqual(len(d), len(m))
