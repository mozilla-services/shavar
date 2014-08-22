import unittest

from pyramid import testing
from shavar.tests.base import dummy


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_list_view(self):
        from shavar.views import list_view
        request = dummy('', path='/list')
        info = list_view(request)
        self.assertEqual(info['project'], 'shavar')

    def test_downloads_view(self):
        from shavar.views import downloads_view
        request = dummy(body, path='/downloads')
        info = downloads_view(request)
        self.assertEqual(info, body)
