# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Tests for the testing infrastructure.

Stay tunes, the infinite loop is near...
'''
from __future__ import with_statement
from urllib2 import URLError, urlopen

from chevah.empirical.mockup import (
    ChevahCommonsFactory,
    ResponseDefinition,
    HTTPServerContext,
    )
from chevah.empirical import EmpiricalTestCase, mk


class TestHTTPServerContext(EmpiricalTestCase):
    """
    Tests for HTTPServerContext.
    """

    def openPage(self, location, data=None):
        """
        Open a page using default mocked server.
        """
        try:
            return urlopen(
                'http://%s:%d%s' % (
                    self.httpd.ip, self.httpd.port, location),
                data=data,
                )
        except URLError as error:
            return error

    def test_HTTPServerContext_default(self):
        """
        Check HTTPServerContext.
        """
        response = ResponseDefinition(
            url='/test.html',
            response_content='test',
            method='GET',
            persistent=False,
            )

        with HTTPServerContext([response]) as httpd:
            self.assertIsNotNone(httpd.ip)
            self.assertIsNotNone(httpd.port)
            response = urlopen(
                "http://%s:%d/test.html" % (httpd.ip, httpd.port))
            self.assertEqual('test', response.read())

    def test_GET_no_response(self):
        """
        Return 404 when no response is configured.
        """
        with HTTPServerContext([]) as self.httpd:
            response = self.openPage('/test.html')

        self.assertEqual(404, response.code)

    def test_GET_not_found(self):
        """
        Return 404 when no configured response matches the requested URL.
        """
        response = ResponseDefinition(url='/other')
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/test.html')

        self.assertEqual(404, response.code)

    def test_GET_bad_method(self):
        """
        Return 404 when no configured response matches the requested method.
        """
        response = ResponseDefinition(method='POST', url='/url')
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/url')

        self.assertEqual(404, response.code)

    def test_GET_not_persistent(self):
        """
        Return 400 when request should be persistent but it is not.
        """
        response = ResponseDefinition(url='/url', persistent=True)
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/url')

        self.assertEqual(400, response.code)
        self.assertEqual('Connection is not persistent', response.reason)

    def test_GET_persistent_ignore(self):
        """
        When set to None it will ignore the persistance check.
        """
        response = ResponseDefinition(url='/url', persistent=None)
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/url')

        self.assertEqual(200, response.code)

    def test_do_POST_good(self):
        """
        A request of type POST is matched when request content also match.
        """
        response = ResponseDefinition(
            method='POST',
            url='/url',
            request='request-body',
            persistent=False,
            response_code=242,
            response_message='All good.',
            response_content='content',
            )
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/url', data='request-body')

        self.assertEqual(242, response.code)
        self.assertEqual('content', response.read())

    def test_do_POST_invalid_content(self):
        """
        A request of type POST is not matched when request content differs.
        """
        response = ResponseDefinition(
            method='POST',
            url='/url',
            request='request-body',
            persistent=False,
            )
        with HTTPServerContext([response]) as self.httpd:
            response = self.openPage('/url', data='other-body')

        self.assertEqual(404, response.code)


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

    class OneFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    class OtherFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    def test_getUniqueInteger(self):
        """
        Integer is unique between various classes implementing the factory.
        """
        one = self.OneFactory()
        other = self.OtherFactory()

        self.assertNotEqual(
            one.getUniqueInteger(),
            other.getUniqueInteger(),
            )
