# -*- coding: utf-8 -*-
'''Module containing helpers for testing the Chevah server.'''
from __future__ import with_statement

from select import error as SelectError
from threading import Thread
import BaseHTTPServer
import errno
import hashlib
import httplib
import os
import random
import string
import threading
import urllib
import uuid

from OpenSSL import SSL, crypto

from twisted.internet import address, defer
from twisted.internet.protocol import Factory
from twisted.internet.tcp import Port


from chevah.compat import DefaultAvatar, system_users
from chevah.empirical.filesystem import LocalTestFilesystem
from chevah.empirical.constants import (
    TEST_NAME_MARKER,
    )


class StoppableHttpServer(BaseHTTPServer.HTTPServer):
    """
    BaseHTTPServer but with a stopabele server_forever.
    """
    def serve_forever(self):
        """Handle one request at a time until stopped."""
        self.stop = False
        while not self.stop:
            try:
                self.handle_request()
            except SelectError, e:
                # See Python http://bugs.python.org/issue7978
                if e.args[0] == errno.EINTR:
                    continue
                raise


class ThreadedHTTPServer(Thread):
    """
    HTTP Server that runs in a thread.

    This is actual a threaded wrapper around an HTTP server.

    Only use it for testing.
    """
    TIMEOUT = 1

    def __init__(
            self, responses=None, ip='127.0.0.1', port=0, debug=False,
            cond=None):
        Thread.__init__(self)
        self.ready = False
        self.cond = cond
        self._ip = ip
        self._port = port

    def run(self):
        self.cond.acquire()
        timeout = 0
        self.httpd = None
        while self.httpd is None:
            try:
                self.httpd = StoppableHttpServer(
                    (self._ip, self._port), MockRequestHandler)
            except Exception, e:
                # I have no idea why this code works.
                # It is a copy paste from:
                # http://www.ianlewis.org/en/testing-using-mocked-server
                import socket
                import errno
                import time
                if (isinstance(e, socket.error) and
                        errno.errorcode[e.args[0]] == 'EADDRINUSE' and
                        timeout < self.TIMEOUT):
                    timeout += 1
                    time.sleep(1)
                else:
                    self.cond.notifyAll()
                    self.cond.release()
                    self.ready = True
                    raise e

        self.ready = True
        if self.cond:
            self.cond.notifyAll()
            self.cond.release()
        # Start the actual HTTP server.
        self.httpd.serve_forever()


class MockHTTPServer(object):
    """
    A context manager which runs a HTTP server for testing simple
    HTTP requests.

    After the server is started the ip and port are available in the
    context management instance.

    responses = [MockHTTPResponse(url='/hello.html', response='Hello!)]
    with MochHTTPServer(responses=responses) as httpd:
        print 'Listening at %s:%d' % (httpd.id, httpd.port)
        self.assertEqual('Hello!', your_get())

    responses = [
        MockHTTPResponse(
            url='/hello.php', request='user=John',
            response_content='Hello John!, response_code=202)]
    with MockHTTPServer(responses=responses) as httpd:
        self.assertEqual(
            'Hello John!',
            get_you_post(url='hello.php', data='user=John'))
    """

    def __init__(self, responses=None, ip='127.0.0.1', port=0, debug=False):
        '''Initialize a new MockHTTPServer.

         * ip - IP to listen. Leave empty to listen to any interface.
         * port - Port to listen. Leave 0 to pick a random port.
         * responses - A list of MockHTTPResponse defining the behavior of
                        this server.
        '''
        # Since we can not pass an instance of MockRequestHandler
        # we do on the fly patching here.
        MockRequestHandler.debug = debug
        if responses is None:
            MockRequestHandler.valid_responses = []
        else:
            MockRequestHandler.valid_responses = responses

        self.cond = threading.Condition()
        self.server = ThreadedHTTPServer(cond=self.cond, ip=ip, port=port)

    def __enter__(self):
        self.cond.acquire()
        self.server.start()

        # Wait until the server is ready.
        while not self.server.ready:
            self.cond.wait()
        self.cond.release()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.stopServer()
        self.server.join(1)
        return False

    @property
    def port(self):
        return self.server.httpd.server_address[1]

    @property
    def ip(self):
        return self.server.httpd.server_address[0]

    def stopServer(self):
        conn = httplib.HTTPConnection("%s:%d" % (self.ip, self.port))
        conn.request("QUIT", "/")
        conn.getresponse()


class MockRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    valid_responses = []

    debug = False

    def log_message(self, *args):
        pass

    def do_QUIT(self):
        """
        send 200 OK response, and set server.stop to True
        """
        self.send_response(200)
        self.end_headers()
        self.server.stop = True

    def do_GET(self):
        response = self._getResponse()
        if response:
            self.send_response(response.response_code)
            self.send_header("Content-type", response.content_type)
            self.end_headers()
            self.wfile.write(response.test_response_content)
        else:
            self.send_error(404)

    def _getResponse(self):
        '''Return the MockHTTPResponse for the current request.'''
        for response in self.__class__.valid_responses:
            if self.path == response.url:
                return response
        # If no response was found, return None.
        return None

    def do_POST(self):
        if self._haveValidURL():
            length = int(self.headers.getheader('content-length'))
            request = self.rfile.read(length)
            response = self._postResponse(request)
            if response:
                self.send_response(response.response_code)
                self.send_header("Content-type", response.content_type)
                self.end_headers()
                self.wfile.write(response.test_response_content)
            else:
                if self.debug:
                    print '\nserver got data - %s\nserver exp data - %s\n' % (
                        request, unicode(self._getAcceptedRequests()))
                self.send_error(400)
        else:
            if self.debug:
                print '\nserver got url - %s\nserver exp url - %s\n' % (
                    self.path, unicode(self._getAcceptedURLs()))
            self.send_error(404)

    def _postResponse(self, request):
        '''Return a tuple containing the'''
        for response in self.__class__.valid_responses:
            if response.url == self.path and response.request == request:
                return response
        return None

    def _getAcceptedURLs(self):
        '''Return the list of URLs accepted by the server.'''
        result = []
        for response in self.__class__.valid_responses:
            result.append(response.url)
        return result

    def _getAcceptedRequests(self):
        '''Return the list of request contents accepted by this server.'''
        result = []
        for response in self.__class__.valid_responses:
            if response.url == self.path:
                result.append(response.request)
        return result

    def _haveValidURL(self):
        '''Return True if the current request is in the list of URLs
        accepted by the server.'''
        for response in self.__class__.valid_responses:
            if self.path == response.url:
                return True
        return False


class MockHTTPResponse(object):
    '''A class encapsulating the required data for configuring a response
    generated by the MockHTTPServer.

    It contains the following data:
        * url - url that will trigger this response
        * request - request that will trigger the response once the url is
                    matched
        * response_content - content of the response
        * response_code - HTTP code of the response
        * content_type - Content type of the HTTP response
    '''

    def __init__(self, url='', request='', response_content='',
                 response_code=200, content_type='text/html'):
        self.url = url
        self.request = request
        self.test_response_content = response_content
        self.response_code = response_code
        self.content_type = content_type


class TestSSLContextFactory(object):
    '''An SSLContextFactory used in tests.'''

    def __init__(self, factory, method=None, cipher_list=None,
                 certificate_path=None, key_path=None):
        self.method = method
        self.cipher_list = cipher_list
        self.certificate_path = certificate_path
        self.key_path = key_path
        self._context = None

    def getContext(self):
        if self._context is None:
            self._context = factory.makeSSLContext(
                method=self.method,
                cipher_list=self.cipher_list,
                certificate_path=self.certificate_path,
                key_path=self.key_path,
                )
        return self._context


class ChevahCommonsFactory(object):
    '''This class creates objects from chevah.utils module.

    It is designed to help with the tests and creating 'mock' objects.
    '''

    # Class member used for generating unique integers.
    _unique_id = random.randint(0, 5000)

    def ascii(self):
        """
        Return a unique (per session) ASCII string.
        """
        return 'ascii_str' + str(self.getUniqueInteger())

    def TCPPort(self, factory=None, address='', port=1234):
        """
        Return a Twisted TCP Port.
        """
        if factory is None:
            factory = Factory()

        return Port(port, factory, interface=address)

    def string(self, *args, **kwargs):
        """
        Shortcut for getUniqueString.
        """
        return self.getUniqueString(*args, **kwargs)

    def number(self, *args, **kwargs):
        """
        Shortcut for getUniqueInteger.
        """
        return self.getUniqueInteger(*args, **kwargs)

    def uuid1(self):
        """
        Generate a random UUID1 based on current machine.
        """
        return uuid.uuid1()

    def uuid4(self):
        """
        Generate a random UUID4.
        """
        return uuid.uuid4()

    @property
    def username(self):
        """
        The account under which this process is executed.
        """
        return unicode(os.environ['USER'])

    def md5(self, content):
        """
        Return MD5 digest for `content`.

        Content must by byte string.
        """
        md5_sum = hashlib.md5()
        md5_sum.update(content)
        return md5_sum.digest()

    def getUniqueString(self, length=None):
        """
        A string unique for this session.
        """
        base = u'str' + unicode(self.getUniqueInteger())

        # The minimum length so that we don't truncate the unique string.
        min_length = len(base) + len(TEST_NAME_MARKER)
        extra_text = ''

        if length:
            # We add an extra 3 characters for safety.. since integers are not
            # padded.
            if min_length + 1 > length:
                raise AssertionError(
                    "Can not generate an unique string shorter than %d" % (
                        length))
            else:
                extra_length = length - min_length
                extra_text = ''.join(
                    random.choice(string.ascii_uppercase + string.digits)
                    for ignore in range(extra_length)
                    )

        return base + extra_text + TEST_NAME_MARKER

    def getUniqueInteger(self):
        """
        An integer unique for this session.
        """
        self.__class__._unique_id += 1
        return self.__class__._unique_id

    def makeToken(self, credentials):
        """
        Generate the Windows token for credentials.

        Only useful on Windows.
        On Unix it should return None.
        """
        if os.name != 'nt':
            return None

        result, token = system_users.authenticateWithUsernameAndPassword(
            username=credentials.username,
            password=credentials.password,
            )
        if not result:
            raise AssertionError(
                u'Failed to get a valid token for "%s" with "%s".' % (
                    credentials.username, credentials.password))
        return token

    def makeLocalTestFilesystem(self, avatar=None):
        if avatar is None:
            avatar = DefaultAvatar()
            avatar.home_folder_path = self.fs.temp_path
            avatar.root_folder_path = None

        return LocalTestFilesystem(avatar=avatar)

    _local_test_filesystem = None

    @property
    def local_test_filesystem(self):
        '''Return the default local test filesystem.'''
        if self.__class__._local_test_filesystem is None:
            self.__class__._local_test_filesystem = (
                LocalTestFilesystem(avatar=DefaultAvatar()))
        return self.__class__._local_test_filesystem

    @property
    def fs(self):
        '''Shortcut for local_test_filesystem.'''
        return self.local_test_filesystem

    def makeFilename(self, length=32, prefix=u'', suffix=u''):
        '''Return a random valid filename.'''
        name = unicode(self.getUniqueInteger()) + TEST_NAME_MARKER
        return prefix + name + ('a' * (length - len(name))) + suffix

    def makeIPv4Address(self, host='localhost', port=None, protocol='TCP'):
        """
        Creates an IPv4 address.
        """
        if port is None:
            port = random.randrange(20000, 30000)

        ipv4 = address.IPv4Address(protocol, host, port)
        return ipv4

    def makeSSLContext(
        self, method=None, cipher_list=None,
        certificate_path=None, key_path=None,
            ):
        '''Create an SSL context.'''
        if method is None:
            method = SSL.SSLv23_METHOD

        if key_path is None:
            key_path = certificate_path

        ssl_context = SSL.Context(method)

        if certificate_path:
            ssl_context.use_certificate_file(certificate_path)
        if key_path:
            ssl_context.use_privatekey_file(key_path)

        if cipher_list:
            ssl_context.set_cipher_list(cipher_list)

        return ssl_context

    def makeSSLContextFactory(
        self, method=None, cipher_list=None,
        certificate_path=None, key_path=None,
            ):
        '''Return an instance of SSLContextFactory.'''
        return TestSSLContextFactory(
            self, method=method, cipher_list=cipher_list,
            certificate_path=certificate_path, key_path=key_path)

    def makeSSLCertificate(self, path):
        '''Return an SSL instance loaded from path.'''
        certificate = None
        cert_file = open(path, 'r')
        try:
            certificate = crypto.load_certificate(
                crypto.FILETYPE_PEM, cert_file.read())
        finally:
            cert_file.close()
        return certificate

    def encodePathToURI(self, path):
        """
        Return the URI encoding pathname.
        """
        path = path.encode('utf-8')
        return urllib.quote(path, '/')

    def makeDeferredSucceed(self, data=None):
        """
        Creates a deferred for which already succeeded.
        """
        return defer.succeed(data)

    def makeDeferredFail(self, failure=None):
        """
        Creates a deferred which already failed.
        """
        return defer.fail(failure)


factory = ChevahCommonsFactory()
