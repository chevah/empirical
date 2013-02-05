# -*- coding: utf-8 -*-
'''Module containing helpers for testing the Chevah server.'''
from __future__ import with_statement

from select import error as SelectError
from StringIO import StringIO
from threading import currentThread, Thread, Timer
import base64
import BaseHTTPServer
import logging
import os
import random
import string
import urllib
import urllib2

from mock import Mock
from OpenSSL import SSL, crypto
from twisted.internet import address, defer, interfaces as internet_interfaces
from twisted.web import (
    http,
    http_headers,
    server as web_server,
    resource as web_resource,
    )
from zope.interface import implements

from chevah.compat import DefaultAvatar, system_users
from chevah.empirical.filesystem import LocalTestFilesystem
from chevah.empirical.constants import (
    TEST_NAME_MARKER,
    )
from chevah.utils.avatar import ApplicationAvatar, OSAvatar
from chevah.utils.configuration_file import (
    FileConfigurationProxy,
    )
from chevah.utils.constants import (
    LOG_SECTION_DEFAULTS,
    )
from chevah.utils.credentials import (
    PasswordCredentials,
    FTPPasswordCredentials,
    FTPSPasswordCredentials,
    HTTPBasicAuthCredentials,
    HTTPSBasicAuthCredentials,
    SSHKeyCredentials,
    SSHPasswordCredentials,
    SSLCertificateCredentials,
    )
from chevah.utils.event import (
    EventDefinition,
    EventGroupDefinition,
    EventsDefinition,
    )
from chevah.utils.json_file import JSONFile
from chevah.utils.json_rpc import JSONRPCResource
from chevah.utils.logger import (
    _Logger,
    LogEntry,
    )
from chevah.utils.log_configuration_section import (
    LogConfigurationSection,
    )


class MockHTTPServer(object):
    '''Mock HTTP server used for testing simple HTTP requests.

    This is a context manager class.
    '''
    # Time in second after the sever will be forced to shutdown.
    TIMEOUT = 4.0

    def __init__(self, responses=None, ip='127.0.0.1', port=0, debug=False):
        '''Initialize a new MockHTTPServer.

         * ip - IP to listen. Leave empty to listen to any interface.
         * port - Port to listen. Leave 0 to pick a random port.
         * responses - A list of MockHTTPResponse defining the behavior of
                        this server.

        After the server is started the ip and port are available in the
        context management instance.
        >>> responses = [
        ...     MockHTTPResponse(url='/hello.html', response='Hello!)]
        >>> with MochHTTPServer(responses=responses) as httpd:
        ...     print 'Listening at %s:%d' % (httpd.id, httpd.port)
        ...     self.assertEqual('Hello!', your_get())

        >>> responses = [
        ...     MockHTTPResponse(
        ...         url='/hello.php', request='user=John',
        ...         response_content='Hello John!, response_code=202)]
        >>> with MockHTTPServer(responses=responses) as httpd:
        ...     self.assertEqual(
        ...         'Hello John!',
        ...         get_you_post(url='hello.php', data='user=John'))
        '''

        MockRequestHandler.debug = debug
        if responses is None:
            MockRequestHandler.valid_responses = []
        else:
            MockRequestHandler.valid_responses = responses
        self._server = BaseHTTPServer.HTTPServer(
            (ip, port), MockRequestHandler)
        (self.ip, self.port) = self._server.server_address
        self._stopped = False
        self._server_process = Thread(target=self._serve_page)
        self._server_timeout = Timer(self.TIMEOUT, self._force_close)

    def _serve_page(self):
        '''Server a request while the server should still run.'''
        while not self._stopped:
            try:
                self._server.handle_request()
            except SelectError, error:
                pass

    def _force_close(self):
        '''Do what it takes to close and clear the server.'''
        try:
            urllib2.urlopen('http://%s:%d' % (self.ip, self.port))
        except:
            pass
        if currentThread is not None:
            self._server_process.join(0.1)

    def __enter__(self):
        self._server_process.start()
        self._server_timeout.start()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self._stopped = True
        self._server_timeout.cancel()
        try:
            # Try to close the thread now
            self._server_process.join(0.01)
        except:
            # First attempt of closing the thread failed, so the server
            # is still accepting one last request.
            # We make the last request.
            urllib2.urlopen('http://%s:%d' % (self.ip, self.port))
            # Try to close the thread again.
            self._server_process.join(2)
        return False


class MockRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    valid_responses = []

    debug = False

    def log_message(self, *args):
        pass

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
            if (response.url == self.path and
                response.request == request):
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


class DummyHTTPChannel(object):
    port = 80
    disconnected = False

    def __init__(self, site=None, peer=None, host=None, resource=None):
        self.written = StringIO()
        self.producers = []
        if peer is None:
            peer = factory.makeIPv4Address(host='192.168.1.1', port=1234)

        if host is None:
            host = factory.makeIPv4Address(host='10.0.0.1', port=self.port)

        if site is None:
            site = factory.makeTwistedWebSite(resource=resource)

        self.site = site
        self._peer = peer
        self._host = host

    def getPeer(self):
        return self._peer

    def write(self, bytes):
        assert isinstance(bytes, str)
        self.written.write(bytes)

    def writeSequence(self, iovec):
        map(self.write, iovec)

    def getHost(self):
        return self._host

    def registerProducer(self, producer, streaming):
        self.producers.append((producer, streaming))

    def loseConnection(self):
        self.disconnected = True

    def requestDone(self, request):
        pass


class DummyHTTPSChannel(object):

    implements(internet_interfaces.ISSLTransport)
    port = 443


class DummyWebRequest(object):
    """
    A dummy Twisted Web Request used in tests.
    """

    def __init__(self,
            postpath=None, prepath=None, session=None, resource=None,
            data=None, peer=None, site=None,
            uri=None, clientproto=None, method=None, secured=False,
            path=None, host=None):

        channel = factory.makeTwistedWebHTTPChannel()

        if site is None:
            site = factory.makeTwistedWebSite(resource)
        channel.site = site
        self.site = site

        # Data writen.
        self.content = StringIO()
        self.written = []

        if data:
            self.content.write(data)
            self.content.seek(0)

        # Full URL including arguments
        if uri is None:
            uri = '/uri-not-defined'
        self.uri = uri

        # HTTP URL arguments POST or GET
        self.args = {}

        # HTTP URL without arguments
        self.path = path

        if prepath is None:
            prepath = self.uri.split('/')[:1]

        if postpath is None:
            postpath = []

        if peer is None:
            peer = factory.makeIPv4Address()

        self.sitepath = []

        self.prepath = prepath
        self.postpath = postpath
        self.client = peer

        self.secured = secured

        if clientproto is None:
            clientproto = 'HTTP/1.0'
        self.clientproto = clientproto

        if method is None:
            method = 'GET'
        self.method = method.upper()

        self.session = None
        self.protoSession = session or web_server.Session(0, self)

        self._code = None
        self._message = None

        self.responseHeaders = http_headers.Headers()
        self.requestHeaders = http_headers.Headers()

        # This should be called after we have defined the request headers.
        if host is None:
            host = 'dummy.host.tld'
        self.setRequestHeader('host', host)

        self.received_cookies = {}
        self.cookies = []  # outgoing cookies

        self._finishedDeferreds = []
        self.finished = 0

    def __repr__(self):
        return (
            'DummyWebRequest for "%(uri)s", code: %(code)s\n'
            'response content: "%(response_content)s"\n'
            'response headers: "%(response_headers)s' % ({
            'uri': self.uri,
            'code': self.code,
            'response_content': self.test_response_content,
            'response_headers': dict(self.responseHeaders.getAllRawHeaders()),
            }))

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message

    @property
    def test_response_content(self):
        """
        Return the data written to the request during tests.
        """
        return ''.join(self.written)

    def getSession(self, sessionInterface=None):
        if not self.session:

            assert not self.written, (
                "Session cannot be requested after data has been written.")

            cookiename = string.join(['TWISTED_SESSION'] + self.sitepath, "_")
            sessionCookie = self.getCookie(cookiename)
            if sessionCookie:
                try:
                    self.session = self.site.getSession(sessionCookie)
                except KeyError:
                    pass
            # if it still hasn't been set, fix it up.
            if not self.session:
                self.session = self.site.makeSession()
                self.addCookie(cookiename, self.session.uid, path='/')
        self.session.touch()
        if sessionInterface:
            return self.session.getComponent(sessionInterface)
        return self.session

    def write(self, data):
        self.written.append(data)

    def isSecure(self):
        return self.secured

    def getHeader(self, name):
        """
        Public method for a Request.
        """
        value = self.requestHeaders.getRawHeaders(name)
        if value is not None:
            return value[-1]

    def setHeader(self, name, value):
        """
        Public method for a Request.
        """
        self.responseHeaders.setRawHeaders(name, [value])

    def getRequestHeader(self, name):
        """
        Testing method to get request headers.

        This is here so that we can have clear/explicit tests.
        """
        return self.getHeader(name)

    def setRequestHeader(self, name, value):
        """
        Testing method to set request headers.

        This is here so that we can have clear/explicit tests.
        """
        self.requestHeaders.setRawHeaders(name.lower(), [value])

    def getResponseHeader(self, name):
        """
        Testing method to get response headers.

        This is here so that we can have clear/explicit tests.
        """
        value = self.responseHeaders.getRawHeaders(name)
        if value is not None:
            return value[-1]

    def setResponseHeader(self, name, value):
        """
        Testing method to set response headers.

        This is here so that we can have clear/explicit tests.
        """
        self.setHeaser(self, name, value)

    def setLastModified(self, when):
        assert not self.written, (
            "Last-Modified cannot be set after data has been written: %s." % (
                "@@@@".join(self.written)))

    def setETag(self, tag):
        assert not self.written, (
            "ETag cannot be set after data has been written: %s." % (
                "@@@@".join(self.written)))

    def getCookie(self, key):
        return self.received_cookies.get(key)

    def addCookie(self,
            k, v, expires=None, domain=None, path=None, max_age=None,
            comment=None, secure=None
            ):
        """
        Set an outgoing HTTP cookie.

        In general, you should consider using sessions instead of cookies, see
        L{twisted.web.server.Request.getSession} and the
        L{twisted.web.server.Session} class for details.
        """
        cookie = '%s=%s' % (k, v)
        if expires is not None:
            cookie = cookie + "; Expires=%s" % expires
        if domain is not None:
            cookie = cookie + "; Domain=%s" % domain
        if path is not None:
            cookie = cookie + "; Path=%s" % path
            if max_age is not None:
                cookie = cookie + "; Max-Age=%s" % max_age
            if comment is not None:
                cookie = cookie + "; Comment=%s" % comment
            if secure:
                cookie = cookie + "; Secure"
            self.cookies.append(cookie)

    def redirect(self, url):
        """
        Utility function that does a redirect.

        The request should have finish() called after this.
        """
        self.setResponseCode(http.FOUND)
        self.setHeader("location", url)

    def registerProducer(self, prod, s):
        self.go = 1
        while self.go:
            prod.resumeProducing()

    def unregisterProducer(self):
        self.go = 0

    def processingFailed(self, reason):
        """
        Errback and L{Deferreds} waiting for finish notification.
        """
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.errback(reason)

    def setResponseCode(self, code, message=None):
        """
        Set the HTTP status response code, but takes care that this is called
        before any data is written.
        """
        assert not self.written, (
            "Response code cannot be set after data has been written: %s." % (
                "@@@@".join(self.written)))
        self._code = code
        self._message = message

    def render(self, resource):
        """
        Render the given resource as a response to this request.

        This implementation only handles a few of the most common behaviors of
        resources.  It can handle a render method that returns a string or
        C{NOT_DONE_YET}.  It doesn't know anything about the semantics of
        request methods (eg HEAD) nor how to set any particular headers.
        Basically, it's largely broken, but sufficient for some tests at
        least.
        It should B{not} be expanded to do all the same stuff L{Request} does.
        Instead, L{DummyRequest} should be phased out and L{Request} (or some
        other real code factored in a different way) used.
        """
        result = resource.render(self)
        if result is web_server.NOT_DONE_YET:
            return
        self.write(result)
        self.finish()

    def finish(self):
        """
        Record that the request is finished and callback and L{Deferred}s
        waiting for notification of this.
        """
        self.finished = self.finished + 1
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.callback(None)

    def notifyFinish(self):
        """
        Return a L{Deferred} which is called back with C{None} when the
        request is finished.
        This will probably only work if you haven't called C{finish} yet.
        """
        finished = defer.Deferred()
        self._finishedDeferreds.append(finished)
        return finished


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
    _unique_id = 0

    @property
    def username(self):
        """
        The account under which this process is executed.
        """
        return unicode(os.environ['USER'])

    def getUniqueString(self, length=None):
        """
        A string unique for this session.
        """
        base = u'str' + unicode(self.getUniqueInteger())

        # The minimum lenght so that we don't truncate the unique string.
        min_length = len(base) + len(TEST_NAME_MARKER)
        extra_text = ''

        if length:
            # We add an extra 3 characters for safety.. since integers are not
            # padded.
            if min_length + 1 > length:
                raise AssertionError(
                    "Can not generate an unique string shortern than %d" % (
                        length))
            else:
                extra_length = length - min_length
                extra_text = ''.join(
                    random.choice(string.ascii_uppercase + string.digits)
                        for x in range(extra_length))

        return base + extra_text + TEST_NAME_MARKER

    def getUniqueInteger(self):
        """
        An integer unique for this session.
        """
        self.__class__._unique_id += 1
        return self.__class__._unique_id

    def _makeGenericPasswordCredentials(self,
            credentials_class,
            username=None, password=None, token=None,
            ):
        '''Create PasswordCredentials.'''
        if username is None:
            username = self.username
        else:
            username = unicode(username)

        if password is not None:
            password = unicode(password)

        credentials = credentials_class(
            username=username,
            password=password,
            )

        return credentials

    def makeFTPPasswordCredentials(self, *args, **kwargs):
        return self._makeGenericPasswordCredentials(
            FTPPasswordCredentials, *args, **kwargs)

    def makeFTPSPasswordCredentials(self, *args, **kwargs):
        return self._makeGenericPasswordCredentials(
            FTPSPasswordCredentials, *args, **kwargs)

    def makeSSHPasswordCredentials(self, *args, **kwargs):
        return self._makeGenericPasswordCredentials(
            SSHPasswordCredentials, *args, **kwargs)

    def makeHTTPBasicAuthCredentials(self, *args, **kwargs):
        return self._makeGenericPasswordCredentials(
            HTTPBasicAuthCredentials, *args, **kwargs)

    def makeHTTPSBasicAuthCredentials(self, *args, **kwargs):
        return self._makeGenericPasswordCredentials(
            HTTPSBasicAuthCredentials, *args, **kwargs)

    def makeToken(self, credentials):
        """
        Generate the Windows token for credentials.

        Only useful on WIndows.
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

    def makePasswordCredentials(self,
            username=None, password=None, token=None,
            ):
        '''Create PasswordCredentials.'''
        if username is None:
            username = self.getUniqueString()
        else:
            username = unicode(username)

        if password is not None:
            password = unicode(password)

        credentials = PasswordCredentials(
            username=username,
            password=password,
            )
        return credentials

    def makeSSHKeyCredentials(self,
            username=None,
            key=None,
            key_algorithm=None, key_data=None, key_signed_data=None,
            key_signature=None,
            *args, **kwargs
            ):

        if username is None:
            username = self.username
        else:
            username = unicode(username)

        if key is not None:
            key_parts = key.split()
            key_algorithm = key_parts[0]
            key_data = base64.decodestring(key_parts[1])

        credentials = SSHKeyCredentials(
            username=username,
            key_algorithm=key_algorithm,
            key_data=key_data,
            key_signed_data=key_signed_data,
            key_signature=key_signature,
            *args, **kwargs
            )

        return credentials

    def makeSSLCertificateCredentials(self,
            username=None,
            certificate=None,
            *args, **kwargs
            ):

        if username is None:
            username = self.username
        else:
            username = unicode(username)

        credentials = SSLCertificateCredentials(
            username=username,
            certificate=certificate,
            *args, **kwargs
            )

        return credentials

    def makeOSAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            lock_in_home_folder=False,
            token=None,
            ):
        """
        Creates a valid OSAvatar.
        """
        if name is None:
            name = self.username

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        return OSAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            lock_in_home_folder=lock_in_home_folder,
            token=token,
            )

    def makeApplicationAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            ):
        """
        Creates a valid OSAvatar.
        """
        if name is None:
            name = self.getUniqueString()

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        # Application avatars are locked inside home folders.
        if root_folder_path is None:
            root_folder_path = home_folder_path

        return ApplicationAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            )

    def makeLogEntry(self):
        id = 100
        text = u'Entry content ' + factory.getUniqueString()
        avatar = self.makeApplicationAvatar()
        peer = self.makeIPv4Address()
        return LogEntry(
            message_id=id, text=text, avatar=avatar, peer=peer)

    def makeLocalTestFilesystem(self, avatar=None):
        if avatar is None:
            avatar = DefaultAvatar()
            avatar.home_folder_path = self.fs.temp_path
            avatar.root_folder_path = None

        return LocalTestFilesystem(avatar=avatar)

    def makeTestRunnerFilesystem(self):
        '''Create a local test filesystem for the user under which the
        tests are executed.'''
        return LocalTestFilesystem(avatar=DefaultAvatar())

    _local_test_filesystem = None

    @property
    def local_test_filesystem(self):
        '''Return the default local test filesystem.'''
        if self.__class__._local_test_filesystem is None:
            self.__class__._local_test_filesystem = (
                self.makeTestRunnerFilesystem())
        return self.__class__._local_test_filesystem

    @property
    def fs(self):
        '''Shortcut for local_test_filesystem.'''
        return self.local_test_filesystem

    def makeFilename(self, length=32, prefix=u'', suffix=u''):
        '''Return a random valid filename.'''
        name = unicode(self.getUniqueInteger()) + TEST_NAME_MARKER
        return prefix + name + ('a' * (length - len(name))) + suffix

    def makeJSONRPCResource(self):
        '''Create a JSONRPCResource.'''
        return JSONRPCResource()

    def makeIPv4Address(self, host='localhost', port=None, protocol='TCP'):
        """
        Creates an IPv4 address.
        """
        if port is None:
            port = random.randrange(20000, 30000)

        ipv4 = address.IPv4Address(protocol, host, port)
        return ipv4

    def makeTwistedWebHTTPChannel(self, peer=None, host=None):
        channel = DummyHTTPChannel(peer=peer, host=host)
        return channel

    def makeTwistedWebHTTPSChannel(self, peer=None, host=None):
        channel = DummyHTTPSChannel(peer=peer, host=host)
        return channel

    def makeTwistedWebSite(self, resource=None):
        if resource is None:
            resource = web_resource.Resource()

        site = web_server.Site(resource)
        return site

    def makeTwistedWebRequest(self, *args, **kwargs):
        '''Create a Twisted Web Request.

        This request can either be used directly on a resource or it can
        be used on a site to get the resource for that request.
        '''
        request = DummyWebRequest(*args, **kwargs)
        return request

    def makeSSLContext(self, method=None, cipher_list=None,
                            certificate_path=None, key_path=None):
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

    def makeSSLContextFactory(self, method=None, cipher_list=None,
                            certificate_path=None, key_path=None):
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

    def makeLogConfigurationSection(self, proxy=None):
        if proxy is None:
            content = (
                '[log]\n'
                'log_file: Disabled\n'
                'log_syslog: Disabled\n'
                )
            proxy = self.makeFileConfigurationProxy(
                content=content,
                defaults=LOG_SECTION_DEFAULTS,
                )

        return LogConfigurationSection(proxy=proxy)

    def makeFileConfigurationProxy(self, content=None, defaults=None):
        if content is None:
            content = ''
        proxy_file = FileConfigurationProxy(
            configuration_file=StringIO(content),
            defaults=defaults)
        proxy_file.load()
        return proxy_file

    def makeJSONFile(self, content=None, load=True):
        """
        Create a JSONFile.
        """
        json_file = JSONFile(file=StringIO(content))
        if load:
            json_file.load()
        return json_file

    def makeLogger(self, log_name=None):
        result = _Logger()

        if not log_name:
            log_name = factory.getUniqueString()

        result._log = logging.getLogger(log_name)
        return result

    def makeEventGroupDefinition(self, name=None, description=None):
        """Creates an EventGroupDefinition."""
        if name is None:
            name = factory.getUniqueString()
        if description is None:
            description = factory.getUniqueString()

        event_group = EventGroupDefinition(name=name, description=description)

        return event_group

    def makeEventDefinition(self, id=None, message=None, groups=None,
            version_added=None, version_removed=None):
        """Creates an EventGroupDefinition."""
        if id is None:
            id = factory.getUniqueString()
        if message is None:
            message = factory.getUniqueString()

        event_definition = EventDefinition(
            id=id,
            message=message,
            groups=groups,
            version_added=version_added,
            version_removed=version_removed,
            )

        return event_definition

    def makeEventsDefinition(self,
            configuration_file=None, content=None,
            load=True,
            ):
        """Creates an EventHandler."""
        if configuration_file is None:
            if content is None:
                content = u''
            configuration_file = StringIO(content)

        config = EventsDefinition(file=configuration_file)

        if load:
            config.load()
        return config

    def encodePathToURI(self, path):
        """
        Return the URI encoding pathname.
        """
        path = path.encode('utf-8')
        return urllib.quote(path, '/')

    def makeMock(self):
        """
        Creates a Mock.
        """
        mock = Mock()
        return mock

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
