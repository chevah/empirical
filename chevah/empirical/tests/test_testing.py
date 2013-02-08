# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Tests for the testing infrastructure.

Stay tunes, the infinite loop is near...
'''
from __future__ import with_statement
from urllib2 import urlopen

from chevah.empirical.mockup import (
    factory,
    MockHTTPResponse,
    MockHTTPServer,
    )
from chevah.empirical.testcase import ChevahTestCase


class TestTestingInfrastructure(ChevahTestCase):
    '''General application configuration tests.'''

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


class TestFactory(ChevahTestCase):
    '''Test for factory methods.'''

    def test_getUniqueString(self):
        """
        getUniqueString will return different values at each call.

        Value is unicode.
        """
        self.assertNotEqual(
            factory.getUniqueString(),
            factory.getUniqueString(),
            )
        self.assertIsInstance(unicode, factory.getUniqueString())

    def test_getUniqueInteger(self):
        """
        getUniqueInteger will return different values at each call.
        """
        self.assertNotEqual(
            factory.getUniqueInteger(),
            factory.getUniqueInteger(),
            )
