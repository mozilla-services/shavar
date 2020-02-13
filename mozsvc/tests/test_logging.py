
import os
import json
import logging
import unittest2

from testfixtures import LogCapture

from mozsvc.util import JsonLogFormatter


class TestJsonLogFormatter(unittest2.TestCase):

    def setUp(self):
        self.handler = LogCapture()
        self.formatter = JsonLogFormatter()

    def tearDown(self):
        self.handler.uninstall()

    def test_basic_operation(self):
        logging.debug("simple test")
        self.assertEqual(len(self.handler.records), 1)
        details = json.loads(self.formatter.format(self.handler.records[0]))
        self.assertEqual(details["message"], "simple test")
        self.assertEqual(details["name"], "root")
        self.assertEqual(details["pid"], os.getpid())
        self.assertEqual(details["op"], "root")
        self.assertEqual(details["v"], 1)
        self.assertTrue("time" in details)

    def test_custom_paramters(self):
        logger = logging.getLogger("mozsvc.test.test_logging")
        logger.warn("custom test %s", "one", extra={
            "more": "stuff",
            "op": "mytest",
        })
        self.assertEqual(len(self.handler.records), 1)
        details = json.loads(self.formatter.format(self.handler.records[0]))
        self.assertEqual(details["message"], "custom test one")
        self.assertEqual(details["name"], "mozsvc.test.test_logging")
        self.assertEqual(details["op"], "mytest")
        self.assertEqual(details["more"], "stuff")

    def test_logging_error_tracebacks(self):
        try:
            raise ValueError("\n")
        except Exception:
            logging.exception("there was an error")
        self.assertEqual(len(self.handler.records), 1)
        details = json.loads(self.formatter.format(self.handler.records[0]))
        self.assertEqual(details["message"], "there was an error")
        self.assertEqual(details["error"], "ValueError('\\n',)")
        tblines = details["traceback"].strip().split("\n")
        self.assertEqual(tblines[-1], details["error"])
        self.assertEqual(tblines[-2], "<type 'exceptions.ValueError'>")
