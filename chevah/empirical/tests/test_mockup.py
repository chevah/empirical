# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Tests for the testing infrastructure.

Stay tunes, the infinite loop is near...
'''
from __future__ import with_statement
from urllib2 import urlopen

from chevah.empirical.mockup import (
    MockHTTPResponse,
    MockHTTPServer,
    )
from chevah.empirical import EmpiricalTestCase, mk


class TestMockHTTPServer(EmpiricalTestCase):
    """
    Tests for MockHTTPServer.
    """

    def test_MockHTTPServer_default(self):
        """
        Check MockHTTPServer.
        """
        responses = [
            MockHTTPResponse(url='/test.html', response_content='test')]

        with MockHTTPServer(responses) as httpd:
            self.assertIsNotNone(httpd.ip)
            self.assertIsNotNone(httpd.port)
            f = urlopen(
                "http://%s:%d/test.html" % (httpd.ip, httpd.port))
            self.assertEqual('test', f.read())


class TestFactory(EmpiricalTestCase):
    """
    Test for test objects factory.
    """

    def test_string(self):
        """
        It will return different values at each call.

        Value is Unicode.
        """
        self.assertNotEqual(
            mk.string(),
            mk.string(),
            )
        self.assertIsInstance(unicode, mk.string())

    def test_number(self):
        """
        It will return different values at each call.
        """
        self.assertNotEqual(
            mk.number(),
            mk.number(),
            )

    def test_ascii(self):
        """
        It will return different values at each call.

        Value is str.
        """
        self.assertNotEqual(
            mk.ascii(),
            mk.ascii(),
            )
        self.assertIsInstance(str, mk.ascii())
