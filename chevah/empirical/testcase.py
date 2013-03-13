# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
TestCase used for Chevah project.
"""
from contextlib import contextmanager
from StringIO import StringIO
from time import sleep
import inspect
import threading
import os
import socket
import sys

from bunch import Bunch
from mock import patch
from nose import SkipTest
from twisted.internet.defer import Deferred
from twisted.internet.posixbase import _SocketWaker, _UnixWaker, _SIGCHLDWaker
from twisted.python.failure import Failure

# For Python below 2.7 we use the separate unittest2 module.
# It comes by default in Pthon 2.7.
if sys.version_info[0:2] < (2, 7):
    from unittest2 import TestCase
    # Shut up you linter.
    TestCase
else:
    from unittest import TestCase

from zope.interface.verify import verifyObject

from chevah.compat import (
    DefaultAvatar,
    LocalFilesystem,
    process_capabilities,
    system_users,
    SuperAvatar,
    )
from chevah.empirical.mockup import factory
from chevah.empirical.constants import (
    TEST_NAME_MARKER,
    )


# Import reactor last in case some other modules are changing the reactor.
from twisted.internet import reactor


class Contains(object):
    """
    Marker class used in tests when something needs to contain a value.
    """
    def __init__(self, value):
        self.value = value


class TwistedTestCase(TestCase):
    """
    Test case for Twisted specific code.

    Provides support for running deferred and start/stop the reactor during
    tests.
    """

    EXCEPTED_DELAYED_CALLS = [
        '_resetLogDateTime',
        ]

    EXCEPTED_READERS = [
        _UnixWaker,
        _SocketWaker,
        _SIGCHLDWaker,
        ]

    def setUp(self):
        super(TwistedTestCase, self).setUp()
        self._timeout_reached = False
        self._reactor_timeout_failure = None

    @property
    def _caller_success_member(self):
        """
        Retrieve the 'success' member from the None test case.
        """
        success = None
        for i in xrange(2, 6):
            try:
                success = inspect.stack()[i][0].f_locals['success']
                break
            except KeyError:
                success = None
        if success is None:
            raise AssertionError(u'Failed to find "success" attribute.')
        return success

    def tearDown(self):
        try:
            if self._caller_success_member:
                # Check for a clean reactor at shutdown, only if test
                # passed.
                self.assertIsNone(self._reactor_timeout_failure)
                self.assertReactorIsClean()
        finally:
            self.cleanReactor()
        super(TwistedTestCase, self).tearDown()

    def _reactorQueueToString(self):
        """
        Return a string representation of all delayed calls from reactor
        queue.
        """
        result = []
        for delayed in reactor.getDelayedCalls():
            result.append(str(delayed.func))
        return '\n'.join(result)

    @classmethod
    def cleanReactor(cls):
        """
        Remove all delayed calls, readers and writers from the reactor.
        """
        try:
            reactor.removeAll()
        except (RuntimeError, KeyError):
            # FIXME:863:
            # When running threads the reactor is cleaned from multiple places
            # and removeAll will fail since it detects that internal state
            # is changed from other source.
            pass
        reactor.threadCallQueue = []
        for delayed_call in reactor.getDelayedCalls():
            if delayed_call.active():
                delayed_call.cancel()

    def _raiseReactorTimeoutError(self, timeout):
        """
        Signal an timeout error while executing the reactor.
        """
        self._timeout_reached = True
        failure = AssertionError(
            u'Reactor took more than %.2f seconds to execute.' % timeout)
        self._reactor_timeout_failure = failure

    def _initiateTestReactor(self, timeout=1, have_thread=False):
        """
        Do the steps required to initiate a reactor for testing.
        """
        self._timeout_reached = False

        # Set up timeout.
        self._reactor_timeout_call = reactor.callLater(
            timeout, self._raiseReactorTimeoutError, timeout)

        reactor._startedBefore = False
        reactor._started = False
        reactor.startRunning()

        if have_thread:
            # Thread are always hard to sync, and this is why we need to
            # sleep for a few second so that the operating system will
            # call the thread and allow it to sync its state with the main
            # reactor.
            sleep(0.11)

    def _iterateTestReactor(self, debug=False):
        """
        Iterate the reactor.
        """
        reactor.runUntilCurrent()
        if debug:
            '''When debug is enabled with iterate using 1 second steps,
            to have a much better debug output.
            Otherwise the debug messages will flood the output.'''
            print (
                u'delayed: %s\n'
                u'threads: %s\n'
                u'writers: %s\nreaders:%s\n\n' % (
                    self._reactorQueueToString(),
                    reactor.threadCallQueue,
                    reactor.getWriters(),
                    reactor.getReaders(),
                    ))
            t2 = reactor.timeout()
            t = reactor.running and t2
            reactor.doIteration(t)
        else:
            reactor.doIteration(False)

    def _shutdownTestReactor(self):
        """
        Called at the end of a test reactor run.
        """
        if not self._timeout_reached:
            # Everything fine, disable timeout.
            if not self._reactor_timeout_call.cancelled:
                self._reactor_timeout_call.cancel()

        # Let the reactor know that we want to stop reactor.
        reactor.stop()
        # Let the reactor run one more time to execute the stop code.
        reactor.iterate()
        # Set flag to fake a clean reactor.
        reactor._startedBefore = False
        reactor._started = False

    def assertReactorIsClean(self):
        """
        Check that the reactor has no delayed calls, readers or writers.
        """

        def raise_failure(location, reason):
            raise AssertionError(
                'Reactor is not clean. %s: %s' % (location, reason))

        # Look at threads queue.
        if len(reactor.threadCallQueue) > 0:
            raise_failure('threads', str(reactor.threadCallQueue))

        if len(reactor.getWriters()) > 0:
            raise_failure('writers', str(reactor.getWriters()))

        for reader in reactor.getReaders():
            excepted = False
            for reader_type in self.EXCEPTED_READERS:
                if isinstance(reader, reader_type):
                    excepted = True
                    break
            if not excepted:
                raise_failure('readers', str(reactor.getReaders()))

        for delayed_call in reactor.getDelayedCalls():
            if delayed_call.active():
                delayed_str = str(delayed_call).split()[-1][:-1]
                if delayed_str in self.EXCEPTED_DELAYED_CALLS:
                    continue
                raise_failure('delayed calls', delayed_call)

    def runDeferred(self, deferred, timeout=1, debug=False):
        """
        Run the deferred in the reactor loop.

        Starts the reactor, waits for deferred execution,
        raises error in timeout, stops the reactor.

        This will do recursive calls, in case the original deferred returns
        another deferred.

        This is low level method. In most tests you would like to use
        `getDeferredFailure` or `getDeferredResult`.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            self.runDeferred(deferred)

            self.assertIsNotFailure(deferred)
            self.assertEqual('something', deferred.result)
        """
        if not isinstance(deferred, Deferred):
            raise AssertionError('This is not a deferred.')

        try:
            self._initiateTestReactor(timeout=timeout)
            self._runDeferred(deferred, timeout=timeout, debug=debug)
        finally:
            self._shutdownTestReactor()

    def _runDeferred(self, deferred, timeout, debug):
        """
        Does the actual deferred execution.
        """
        if not deferred.called:
            deferred_done = False
            while not deferred_done:
                self._iterateTestReactor(debug=debug)
                deferred_done = deferred.called

                if self._timeout_reached:
                    raise AssertionError(
                        'Deferred took more than %d to execute.' % timeout)

        result = deferred.result
        if isinstance(result, Deferred):
            self._runDeferred(result, timeout=timeout, debug=debug)

    def executeReactor(self, timeout=1, debug=False, run_once=False,
                       have_thread=False):
        """
        Run reactor until no more delayed calls, readers or
        writers or threads are in the queues.

        Set run_once=True to only run the reactor once. This is useful if
        you have persistent deferred which will be removed only at the end
        of test.

        Set have_thread=True if you are dealing with threads.

        Only use this for very high level integration code, where you don't
        have the change to get a "root" deferred.
        In most tests you would like to use one of the
        `getDeferredFailure` or `getDeferredResult`.

        Usage::

            protocol = factory.makeFTPProtocol()
            transport = factory.makeStringTransportProtocol()
            protocol.makeConnection(transport)
            transport.protocol = protocol

            protocol.lineReceived('FEAT')
            self.executeReactor()
            result = transport.value()

            self.assertStartsWith('211-Features:\n', result)
        """
        self._initiateTestReactor(timeout=timeout, have_thread=have_thread)

        # Set it to True to enter the first loop.
        have_callbacks = True
        while have_callbacks and not self._timeout_reached:
            self._iterateTestReactor(debug=debug)

            have_callbacks = False

            # Look at delayed calls.
            for delayed in reactor.getDelayedCalls():
                # We skip our own timeout call.
                if delayed is self._reactor_timeout_call:
                    continue
                delayed_str = str(delayed).split()[-1][:-1]
                is_exception = False
                for excepted_callback in self.EXCEPTED_DELAYED_CALLS:
                    if excepted_callback in delayed_str:
                        is_exception = True
                if not is_exception:
                    have_callbacks = True
                    continue

            if run_once:
                if have_callbacks:
                    raise AssertionError(
                        u'Reactor queue still contains delayed deferred.\n'
                        u'%s' % (self._reactorQueueToString()))
                break

            # Look at writters buffers:
            if len(reactor.getWriters()) > 0:
                have_callbacks = True
                continue

            for reader in reactor.getReaders():
                have_callbacks = True
                for excepted_reader in self.EXCEPTED_READERS:
                    if isinstance(reader, excepted_reader):
                        have_callbacks = False
                        break
                if have_callbacks:
                    break

            # Look at threads queue.
            if len(reactor.threadCallQueue) > 0:
                have_callbacks = True
                continue

        self._shutdownTestReactor()

    def getDeferredFailure(self, deferred, timeout=1, debug=False):
        """
        Run the deferred and return the failure.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            failure = self.getDeferredFailure(deferred)

            self.assertFailureType(AuthentiationError, failure)
        """
        self.runDeferred(deferred, timeout=timeout, debug=debug)
        self.assertIsFailure(deferred)
        failure = deferred.result
        self.ignoreFailure(deferred)
        return failure

    def getDeferredResult(self, deferred, timeout=1, debug=False):
        """
        Run the deferred and return the result.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            result = self.getDeferredResult(deferred)

            self.assertEqual('something', result)
        """
        self.runDeferred(deferred, timeout=timeout, debug=debug)
        self.assertIsNotFailure(deferred)
        return deferred.result

    def assertWasCalled(self, deferred):
        """
        Check that deferred was called.
        """
        if not deferred.called:
            raise AssertionError('This deferred was not called yet.')

    def assertFailureType(self, failure_class, failure_or_deferred):
        """
        Check that failure is of a given type.
        """
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        if not failure.check(failure_class):
            raise AssertionError(
                u'Failure %s is not of type %s' % (
                    failure, failure_class))

    def ignoreFailure(self, deferred):
        """
        Ignore the current failure on the deferred.

        It transforms an failure into result `None` so that the failure
        will not be raised at reactor shutdown for not being handled.
        """
        deferred.addErrback(lambda failure: None)

    def assertIsFailure(self, deferred):
        """
        Check that deferred is a failure.
        """
        if not isinstance(deferred.result, Failure):
            raise AssertionError(u'Deferred is not a failure.')

    def assertIsNotFailure(self, deferred):
        """
        Raise assertion error if deferred is a Failure.

        The failed deferred is handled by this method, to avoid propagating
        the error into the reactor.
        """
        self.assertWasCalled(deferred)

        if isinstance(deferred.result, Failure):
            error = deferred.result.value
            self.ignoreFailure(deferred)
            raise AssertionError(
                u'Deferred contains a failure: %s' % (error))


class ChevahTestCase(TwistedTestCase):
    """
    Test case for Chevah tests.

    Checks that temporary folder is clean at exit.
    """

    def setUp(self):
        super(ChevahTestCase, self).setUp()
        self.test_segments = None
        self.Bunch = Bunch
        self.Contains = Contains
        self.os_name = os.name
        self.Patch = patch

    def tearDown(self):
        if self.test_segments:
            if factory.fs.isFolder(self.test_segments):
                factory.fs.deleteFolder(
                    self.test_segments, recursive=True)
            if factory.fs.isFile(self.test_segments):
                factory.fs.deleteFile(self.test_segments)
        # FIXME:922:
        # Move all filesystem checks into a specialized class
        self.assertTempIsClean()

        threads = threading.enumerate()
        if len(threads) > 1:
            # FIXME:1077:
            # For now we don't clean the whole reactor so Twisted is
            # an exception here.
            for thread in threads:
                thread_name = thread.getName()
                if thread_name == 'MainThread':
                    continue
                if thread_name == 'threaded_reactor':
                    continue
                if thread_name.startswith(
                        'PoolThread-twisted.internet.reactor'):
                    continue

                raise AssertionError(
                    'There are still active threads, '
                    'beside the main thread: %s - %s' % (
                        thread_name, threads))

        super(ChevahTestCase, self).tearDown()

    def shortDescription(self):
        """
        The short description for the test.

        bla.bla.tests. is removed.
        The format is customized for Chevah Nose runner.
        """
        class_name = str(self.__class__)[8:-2]
        class_name = class_name.replace('.Test', ':Test')
        tests_start = class_name.find('.tests.') + 7
        class_name = class_name[tests_start:]

        return "%s - %s.%s" % (
            self._testMethodName,
            class_name,
            self._testMethodName)

    def getHostname(self):
        """
        Return the hostname of the current system.
        """
        return socket.gethostname()

    @classmethod
    def initialize(cls, drop_user):
        '''Initialize the testing environment.'''
        cls._drop_user = drop_user
        os.environ['DROP_USER'] = drop_user

        if 'LOGNAME' in os.environ and not 'USER' in os.environ:
            os.environ['USER'] = os.environ['LOGNAME']

        if 'USER' in os.environ and not 'USERNAME' in os.environ:
            os.environ['USERNAME'] = os.environ['USER']

        if 'USERNAME' in os.environ and not 'USER' in os.environ:
            os.environ['USER'] = os.environ['USERNAME']

        # Make sure that we have a temporary folder on Windows.
        # When the temporary folder is missing, we try to create it.
        if os.name == 'nt':
            temp_segments = factory.fs.temp_segments
            if not factory.fs.isFolder(temp_segments):
                factory.fs.createFolder(temp_segments)

        ChevahTestCase.assertTempIsClean(silent=True)

    @classmethod
    def haveSuperPowers(cls):
        '''Return true if we can access privileged OS operations.'''
        if os.name == 'posix' and cls._drop_user == '-':
            return False
        if not process_capabilities.impersonate_local_account:
            return False
        return True

    @classmethod
    def dropPrivileges(cls):
        '''Drop privileges to normal users.'''
        if cls._drop_user == '-':
            return

        os.environ['USERNAME'] = cls._drop_user
        os.environ['USER'] = cls._drop_user
        # Test suite should be started as root and we drop effective user
        # privileges.
        system_users.dropPrivileges(username=cls._drop_user)

    @staticmethod
    def skipTest(message=''):
        '''Return a SkipTest exception.'''
        return SkipTest(message)

    @property
    def _caller_success_member(self):
        '''Retrieve the 'success' member from the test case.'''
        success = None
        for i in xrange(2, 6):
            try:
                success = inspect.stack()[i][0].f_locals['success']
                break
            except KeyError:
                success = None
        if success is None:
            raise AssertionError(u'Failed to find "success" attribute.')
        return success

    @contextmanager
    def listenPort(self, ip, port):
        '''Context manager for binding a port.'''
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.bind((ip, port))
        test_socket.listen(0)
        yield
        try:
            test_socket.shutdown(2)
        except socket.error, error:
            if 'solaris-10' in self.getHostname() and error.args[0] == 134:
                pass
            else:
                raise

    @staticmethod
    def assertTempIsClean(silent=False):
        '''Assert that the temporary folder does not contains any testing
        specific files for folders.'''
        temp_segments = factory.fs.temp_segments

        if not factory.fs.exists(temp_segments):
            return

        # In case we are running the test suite as super user,
        # we use super filesystem for cleaning.
        if os.environ['USER'] == os.environ['DROP_USER']:
            temp_avatar = SuperAvatar()
        else:
            temp_avatar = DefaultAvatar()

        temp_avatar._home_folder_path = factory.fs.temp_path
        temp_avatar._root_folder_path = factory.fs.temp_path

        temp_filesystem = LocalFilesystem(avatar=temp_avatar)
        dirty = False
        for member in (temp_filesystem.getFolderContent([])):
            if member.find(TEST_NAME_MARKER) != -1:
                dirty = True
                segments = [member]
                if temp_filesystem.isFolder(segments):
                    temp_filesystem.deleteFolder(segments, recursive=True)
                else:
                    temp_filesystem.deleteFile(segments)

        if dirty and not silent:
            raise AssertionError(u'Temporary folder is not clean.')

    def assertIsFalse(self, value):
        '''Raise an exception if value is not 'False'.'''
        if not value is False:
            raise AssertionError('%s is not False.' % str(value))

    def assertIsTrue(self, value):
        '''Raise an exception if value is not 'True'.'''
        if not value is True:
            raise AssertionError('%s is not True.' % str(value))

    def assertIsInstance(self, expected_type, value, msg=None):
        """
        Raise an expection if `value` is not an instance of `expected_type`
        """
        # In Python 2.7 isInstance is already defined, but with swapped
        # arguments.
        if not inspect.isclass(expected_type):
            expected_type, value = value, expected_type

        if not isinstance(value, expected_type):
            raise AssertionError(
                "Expecting type %s, but got %s. %s" % (
                    expected_type, type(value), msg))

    def assertIsListening(self, ip, port, debug=False, clear_log=False):
        '''Check if the port and address are in listening mode.'''
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1.0)
        try:
            test_socket.connect((ip, port))
            sock_name = test_socket.getsockname()
            test_socket.shutdown(2)
            if debug:
                print 'Connected as: %s:%d' % (sock_name[0], sock_name[1])
        except:
            raise AssertionError(
                u'It seems that no one is listening on %s:%d' % (
                    ip, port))
        if clear_log:
            # Clear the log since we don't care about log generated by
            # assertIsListening.
            # We need to wait a bit.
            import time
            time.sleep(0.1)
            self.clearLog()

    def assertIsNotListening(self, ip, port):
        '''Check if the port and address are in listening mode.'''
        try:
            self.assertIsListening(ip, port)
        except AssertionError:
            return
        raise AssertionError(
            u'It seems that someone is listening on %s:%d' % (
                ip, port))

    def assertEqual(self, first, second, msg=None):
        '''Extra checkes for assert equal.'''
        try:
            super(ChevahTestCase, self).assertEqual(first, second, msg)
        except AssertionError, error:
            raise AssertionError(error.message.encode('utf-8'))

        if (type(first) == unicode and type(second) == str):
            if not msg:
                msg = u'Type of "%s" is unicode while for "%s" is str.' % (
                    first, second)
            raise AssertionError(msg.encode('utf-8'))

        if (type(first) == str and type(second) == unicode):
            if not msg:
                msg = u'Type of "%s" is str while for "%s" is unicode.' % (
                    first, second)
            raise AssertionError(msg)

    def assertFailureType(self, failure_class, failure_or_deferred):
        '''Raise assertion error if failure is not of required type.'''
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        if failure.type is not failure_class:
            raise AssertionError(
                u'Failure %s is not of type %s' % (
                    failure, failure_class))

    def assertFailureID(self, failure_id, failure_or_deferred):
        """
        Raise assertion error if failure does not have the required id.
        """
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        try:
            actual_id = getattr(failure.value, 'id')
        except:
            actual_id = getattr(failure.value, 'event_id')

        if actual_id != failure_id:
            raise AssertionError(
                u'Failure id for %s is not %s, but %s' % (
                    failure, str(failure_id), str(actual_id)))

    def assertFailureData(self, data, failure_or_deferred):
        """
        Raise assertion error if failure does not contain the required data.
        """
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        failure_data = failure.value.data
        try:
            failure_id = getattr(failure.value, 'id')
        except:
            failure_id = getattr(failure.value, 'event_id')

        self._checkData(
            kind=u'Failure',
            kind_id=failure_id,
            expected_data=data,
            current_data=failure_data,
            )

    def assertExceptionID(self, exception_id, exception):
        """
        Raise assertion error if exception does not have the required id.
        """
        try:
            actual_id = getattr(exception, 'id')
        except:
            actual_id = getattr(exception, 'event_id')

        if actual_id != exception_id:
            raise AssertionError(
                u'Exception id for %s is not %s, but %s' % (
                    exception, str(exception_id), str(actual_id)))

    def _checkData(self, kind, kind_id, expected_data, current_data):
        """
        Helper for sharing same code between various data checkers.
        """
        for key, value in expected_data.iteritems():
            try:
                current_value = current_data[key]

                if isinstance(value, Contains):
                    if not value.value in current_value:
                        raise AssertionError(
                            u'%s %s, for data "%s" does not contains "%s", '
                            u'but is "%s"' % (
                                kind, str(kind_id), key, value.value,
                                current_value))
                else:
                    if value != current_value:
                        raise AssertionError(
                            u'%s %s, for data "%s" is not "%s", but "%s"' % (
                                kind, str(kind_id), key, value,
                                current_value))
            except KeyError:
                raise AssertionError(
                    u'%s %s, has no data "%s". Data is:\n%s' % (
                            kind, str(kind_id), key, current_data))

    def assertExceptionData(self, data, exception):
        """
        Raise assertion error if exception does not contain the required data.
        """
        try:
            actual_id = getattr(exception, 'id')
        except:
            actual_id = getattr(exception, 'event_id')

        self._checkData(
            kind=u'Exception',
            kind_id=actual_id,
            expected_data=data,
            current_data=exception.data,
            )

    def assertIsEmpty(self, target):
        """
        Raise AsertionError if target is not empty.
        """
        if len(target) != 0:
            raise AssertionError(u'Value is not empty.\n%s.' % (target))

    def assertIsNotEmpty(self, target):
        """
        Raise AsertionError if target is empty.
        """
        if len(target) == 0:
            raise AssertionError(u'Value is empty.\n%s.' % (target))

    def assertIn(self, target, source):
        '''
        Raise AsertionError if source is not in target.
        '''
        if not source in target:
            raise AssertionError(u'"%s" not in "%s".' % (source, target))

    def assertContains(self, token, source):
        '''
        Raise AssertionError if source does not contain `token`.
        '''
        if not token in source:
            raise AssertionError('"%s" does not contains "%s".' % (
                source, token))

    def assertNotContains(self, token, source):
        '''
        Raise AssertionError if source does contain `token`.
        '''
        if token in source:
            raise AssertionError('"%s" contains "%s".' % (
                source, token))

    def assertTextContains(self, pattern, source):
        """
        Raise AssertionError if pattern is not found in source.
        """
        if not pattern in pattern:
            raise AssertionError(
                '"%s" not contained in\n%s.' % (pattern, source))

    def assertStartsWith(self, start, source):
        """
        Raise AssertionError if `source` does not starts with `start`.
        """
        if not source.startswith(start):
            raise AssertionError(
                '"%s" does not starts with "%s"' % (source, start))

    def assertEndsWith(self, end, source):
        """
        Raise AssertionError if `source` does not ends with `end`.
        """
        if not source.endswith(end):
            raise AssertionError(
                '"%s" does not end with "%s"' % (source, end))

    def assertProvides(self, interface, obj):
        self.assertTrue(
            interface.providedBy(obj),
            'Object %s does not provided interface %s.' % (obj, interface))
        verifyObject(interface, obj)

    def assertNotProvides(self, interface, obj):
        self.assertFalse(
            interface.providedBy(obj),
            'Object %s does not provided interface %s.' % (obj, interface))

    def assertImplements(self, interface, klass):
        self.assertTrue(
            interface.implementedBy(klass),
            u'Class %s does not implements interface %s.' % (
                klass, interface))


class CommandTestCase(ChevahTestCase):
    '''A test case that catches sys.exit, sys.stdout and sys.stderr.

    It is designed to be used for testing command line tools.
    '''

    def setUp(self):
        '''Monkey patch the sys.stdout and sys.exit.'''
        super(CommandTestCase, self).setUp()

        def _fake_exit(exit_code):
            '''Method for monkey patching sys.exit.'''
            self.exit_code = exit_code

        self.exit_code = None
        self.test_stdout = StringIO()
        self.test_stderr = StringIO()
        self.sys_exit = sys.exit
        sys.exit = _fake_exit
        sys.stdout = self.test_stdout
        sys.stderr = self.test_stderr

    def tearDown(self):
        self.test_stdout.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.exit = self.sys_exit
        super(CommandTestCase, self).tearDown()


def setup_os(users, groups):
    '''Create testing environemnt

    Add users, groups, create temporary folders and other things required
    by the testing system.
    '''
    from chevah.compat.administration import OSAdministration

    os_administration = OSAdministration()
    for group in groups:
        os_administration.addGroup(group)

    for user in users:
        os_administration.addUser(user)

    for group in groups:
        os_administration.addUsersToGroup(group, group.members)


def teardown_os(users, groups):
    '''Revert changes from setUpOS.'''

    from chevah.compat.administration import OSAdministration

    os_administration = OSAdministration()

    for group in groups:
        os_administration.deleteGroup(group)

    for user in users:
        os_administration.deleteUser(user)
