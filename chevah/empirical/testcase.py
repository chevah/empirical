# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''TestCase factories for Chevah server.'''
from contextlib import contextmanager
from collections import deque
from StringIO import StringIO
from time import sleep
import inspect
import os
import re
import socket
import sys

from bunch import Bunch
from mock import patch
from nose import SkipTest
from twisted.internet.defer import Deferred
from twisted.internet.posixbase import _SocketWaker, _UnixWaker, _SIGCHLDWaker
from twisted.python import threadable
from twisted.python.failure import Failure
# Workaround for twisted reactor restart.
threadable.registerAsIOThread()
from unittest2 import TestCase
from zope.interface.verify import verifyObject
import simplejson as json


from chevah.compat import (
    DefaultAvatar,
    LocalFilesystem,
    process_capabilities,
    system_users,
    )
from chevah.empirical.mockup import factory
from chevah.empirical.constants import (
    TEST_NAME_MARKER,
    )
from chevah.utils.constants import (
    CONFIGURATION_DISABLED_VALUES,
    CONFIGURATION_INHERIT,
    )

from chevah.utils.logger import Logger
from chevah.utils import events_handler

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

     * provides support for running deferred and start/stop the reactor.
     * checks that temporary folder is clean at exit
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

        # Fake a reactor start/restart.
        reactor.fireSystemEvent('startup')

        if have_thread:
            # Thread are always hard to sync, and this is why we need to
            # sleep for a few second so that the operating system will
            # call the thread and allow it to sync its state with the main
            # reactor.
            sleep(0.11)

    def _shutdownTestReactor(self):
        """
        Called at the end of a test reactor run.
        """
        if not self._timeout_reached:
            # Everything fine, disable timeout.
            if not self._reactor_timeout_call.cancelled:
                self._reactor_timeout_call.cancel()

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

    def runDeferred(self, deferred, timeout=1, debug=True):
        """
        Run the deferred in the reactor loop.

        Starts the reactor, waits for deferred execution,
        raises error in timeout, stops the reactor.

        This is low level method. In most tests you would like to use on
        of the `getDeferredFailure` or `getDeferredResult`.

        Usage::

            credentials = factory.makeCredentials()

            deferred = checker.requestAvatarId(credentials)
            self.runDeferred(deferred)

            self.assertIsNotFailure(deferred)
            self.assertEqual('something', deferred.result)
        """
        self._initiateTestReactor(timeout=timeout)
        self._runDeferred(deferred, timeout=timeout, debug=debug)
        self._shutdownTestReactor()

    def _runDeferred(self, deferred, timeout, debug):
        """
        Does the actual deferred execution.
        """
        if not deferred.called:
            deferred_done = False
            while not deferred_done:
                if debug:
                    # When debug is enabled with iterate using 1 second
                    # _runDeferred to have a much better debug output.
                    #Otherwise the debug messages will flood the output.
                    reactor.iterate(1)
                    print u'%s\n\n' % self._reactorQueueToString()
                else:
                    reactor.iterate()
                deferred_done = deferred.called

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
                reactor.iterate(1)
            else:
                reactor.iterate()

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
        """
        self.runDeferred(deferred, timeout=timeout, debug=debug)
        self.assertIsFailure(deferred)
        failure = deferred.result
        self.ignoreFailure(deferred)
        return failure

    def getDeferredResult(self, deferred, timeout=1, debug=False):
        """
        Run the deferred and return the result.
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

     * provides support for running deferred and start/stop the reactor.
     * checks that temporary folder is clean at exit
    """

    def setUp(self):
        super(ChevahTestCase, self).setUp()
        self.home_folder_segments = None
        self.Bunch = Bunch
        self.Contains = Contains
        self.os_name = os.name
        self.Patch = patch

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

    def tearDown(self):
        if self.home_folder_segments:
            factory.fs.deleteFolder(
                self.home_folder_segments, recursive=True)
        # FIXME:922:
        # Move all filesystem checks into a specialized class
        self.assertTempIsClean()
        super(ChevahTestCase, self).tearDown()

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
            temp_avatar = system_users.getSuperAvatar()
        else:
            temp_avatar = DefaultAvatar()

        temp_avatar.home_folder_path = factory.fs.temp_path
        temp_avatar.root_folder_path = factory.fs.temp_path

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

    def assertIsInstance(self, expected_type, value):
        """
        Raise an expection if `value` is not an instance of `expected_type`
        """
        if not isinstance(value, expected_type):
            raise AssertionError(
                "Expecting type %s, but got %s." % (
                    expected_type, type(value)))

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

        if failure.value.id != failure_id:
            raise AssertionError(
                u'Failure id for %s is not %s, but %s' % (
                    failure, str(failure_id), str(failure.value.id)))

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
        failure_id = failure.value.id

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
        if exception.id != exception_id:
            raise AssertionError(
                u'Exception id for %s is not %s, but %s' % (
                    exception, str(exception_id), str(exception.id)))

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
        self._checkData(
            kind=u'Exception',
            kind_id=exception.id,
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

    def assertIsException(self, expected_id, exception):
        if not expected_id == exception.id:
            raise AssertionError(
                'Expecting exception with id "%d", got "%d:%s".' % (
                    expected_id, exception.id, exception.text))

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

    def defaultBoolean(self, option):
        '''Return default boolean value.'''
        _boolean_states = {'1': True, 'yes': True, 'true': True,
                                      'on': True,
                           '0': False, 'no': False, 'false': False,
                                       'off': False}
        return _boolean_states[
            self.CONFIGURATION_DEFAULTS[option].lower()]

    def defaultString(self, option):
        '''Return default boolean value.'''
        return self.CONFIGURATION_DEFAULTS[option]

    def defaultStringOrNone(self, option):
        '''Return default boolean value.'''
        value = self.CONFIGURATION_DEFAULTS[option]
        if value in CONFIGURATION_DISABLED_VALUES:
            return None

    def defaultInteger(self, option):
        '''Return default boolean value.'''
        return int(self.CONFIGURATION_DEFAULTS[option])

    def getHostname(self):
        return socket.gethostname()

    def assertPropertyString(self, config_factory, key):
        """
        Helper for string properties.
        """
        raw_config = u'%s: something_ță\n' % (key)
        config = config_factory(raw_config=raw_config)

        option = getattr(config, key)
        self.assertEqual(u'something_ță', option)

        setattr(config, key, u'else_ță')
        option = getattr(config, key)
        self.assertEqual(u'else_ță', option)

    def _checkPropertyStringInherit(self, config_factory, key):
        """
        Helper for checking inherit values for a string.
        """
        raw_config = u'%s: Inherit\n' % (key)
        config = config_factory(raw_config=raw_config)

        option = getattr(config, key).lower()
        self.assertEqual(CONFIGURATION_INHERIT[0], option)

        # Setting sinonim for Inherit, will return Inherit base value.
        setattr(config, key, CONFIGURATION_INHERIT[1])

        option = getattr(config, key).lower()
        self.assertEqual(CONFIGURATION_INHERIT[0], option)

    def assertPropertyStringInherit(self, config_factory, key):
        """
        Helper for testing string properties which can be inherited.
        """
        self.assertPropertyString(config_factory=config_factory, key=key)
        self._checkPropertyStringInherit(
            config_factory=config_factory, key=key)

    def _checkPropertyStringNone(self, config_factory, key):
        """
        Helper for checking None values for a string.
        """
        raw_config = u'%s: Disabled\n' % (key)
        config = config_factory(raw_config=raw_config)
        option = getattr(config, key)
        self.assertIsNone(option)

        setattr(config, key, None)
        option = getattr(config, key)
        self.assertIsNone(option)

        setattr(config, key, u'Disabled')
        option = getattr(config, key)
        self.assertIsNone(option)

    def assertPropertyStringOrNone(self, config_factory, key):
        """
        Helper for string properties which can be None.
        """
        self.assertPropertyString(config_factory=config_factory, key=key)
        self._checkPropertyStringNone(config_factory=config_factory, key=key)

    def assertPropertyStringSpecial(self, config_factory, key):
        """
        Helper for string properties which can have special values.
        """
        self.assertPropertyString(config_factory=config_factory, key=key)
        self._checkPropertyStringNone(config_factory=config_factory, key=key)
        self._checkPropertyStringInherit(
            config_factory=config_factory, key=key)

    def assertPropertyBoolean(self, config_factory, key):
        """
        Helper for testing boolean properties.
        """
        raw_config = u'%s: False\n' % (key)
        config = config_factory(raw_config=raw_config)

        option = getattr(config, key)
        self.assertFalse(option)

        setattr(config, key, True)

        option = getattr(config, key)
        self.assertIsTrue(option)

        setattr(config, key, False)

        option = getattr(config, key)
        self.assertIsFalse(option)

    def assertPropertyBooleanInherit(self, config_factory, key):
        """
        Helper for testing boolean properties which can be inherited.
        """
        raw_config = u'%s: Inherit\n' % (key)
        config = config_factory(raw_config=raw_config)

        option = getattr(config, key).lower()
        self.assertEqual(CONFIGURATION_INHERIT[0], option)

        setattr(config, key, True)

        option = getattr(config, key)
        self.assertIsTrue(option)

        setattr(config, key, False)

        option = getattr(config, key)
        self.assertIsFalse(option)

        setattr(config, key, 'Inherit')

        option = getattr(config, key).lower()
        self.assertEqual(CONFIGURATION_INHERIT[0], option)


class EventTestCase(ChevahTestCase):
    """
    A test case which checks that all emited events are tested.
    """

    def setUp(self):
        """
        Catch all emited events.
        """
        super(EventTestCase, self).setUp()

        def emitEvent_test(event):
            """
            Push the logging message into the log testing queue.
            """
            self._queue.append(event)

        self._queue = deque([])
        self.emitEvent_good = events_handler.emitEvent
        events_handler.emitEvent = emitEvent_test

    def tearDown(self):
        """
        Revert patching done to the event handler.
        """
        try:
            self.assertEventsQueueIsEmpty(tear_down=True)
            events_handler.emitEvent = self.emitEvent_good
            super(EventTestCase, self).tearDown()
        finally:
            self.clearEvents()

    def assertEvent(self, event_id, data=None, message=None, tear_down=False):
        '''Check that the system have issues and log with `log_id`.

        If `regex` is not None, the log text is checked agains the
        specified regular expression.
        '''
        if tear_down and not self._caller_success_member:
            return

        if data is None:
            data = {}

        try:
            first_entry = self._queue.popleft()
        except IndexError:
            self.fail(
                u'Events queue is empty. No sign of event with id=%s' % (
                event_id))

        if message:
            if message != first_entry.message:
                self.fail(
                    u'Event with d="%s" does not contains message "%s" '
                    u'but rather "%s"' % (
                        event_id, message, first_entry.message))

        if event_id != first_entry.id:
            self.fail(
                u'Top of the event queue does not contain the event with '
                u'id="%s" but rather "%s"' % (
                    event_id, unicode(first_entry)))

        self._checkData(
            kind=u'Event',
            kind_id=event_id,
            expected_data=data,
            current_data=first_entry.data,
            )

    def popEvent(self):
        """
        Extract and return the log from the queue.
        """
        return self._queue.popleft()

    def clearEvents(self):
        """
        Remove all current entries from the events queue.
        """
        self._queue.clear()

    def assertEventsQueueIsEmpty(self, tear_down=False):
        """
        Check that events queue is empty.
        """
        if tear_down and not self._caller_success_member:
            # When called from tearDown, only check for log if the
            # test was succesful. This prevent raising multiple failures
            # for a single error.
            return

        if len(self._queue) > 0:
            self.fail(u'Events queue is _not_ empty. %s' % repr(self._queue))

    def loadJSON(self, content):
        """
        Return the dictionary for encoded JSON.
        """
        return json.loads(content)

    def dumpJSON(self, content):
        """
        Return the serialized version of JSON content.
        """
        return json.dumps(content)


class LogTestCase(ChevahTestCase):
    '''A test factory which checks that all log messages were tested.'''

    def setUp(self):
        '''Redirect logging messages to local logging stack.'''
        super(LogTestCase, self).setUp()

        def log_test(message_id, text, avatar=None, peer=None, data=None):
            '''Push the logging message into the log testing queue.'''
            self.log_queue.append((message_id, text, avatar, peer, data))

        self.log_queue = deque([])
        self.log_method_good = Logger._log_helper
        self._patched_method = log_test
        Logger._log_helper = self._patched_method

    def tearDown(self):
        '''Revert monkey patching done to the Logger.'''
        try:
            self.assertLogIsEmpty(tear_down=True)
            Logger._log_helper = self.log_method_good
            super(LogTestCase, self).tearDown()
        finally:
            self.clearLog()

    def assertLog(self, log_id, regex=None, tear_down=False):
        '''Check that the system have issues and log with `log_id`.

        If `regex` is not None, the log text is checked against the
        specified regular expression.
        '''
        if tear_down and not self._caller_success_member:
            return

        first_log_entry = (0, '', '')
        try:
            first_log_entry = self.log_queue[0]
        except IndexError:
            self.fail(u'Log queue is empty. No sign of message with id=%d' % (
                log_id))

        queue_log_id = first_log_entry[0]
        queue_log_text = first_log_entry[1]
        if not log_id == queue_log_id:
            self.fail(
                u'Top of the queue does not contain the message with '
                u'id="%d" but rather "%s"' % (
                    log_id, unicode(first_log_entry)))
        elif regex and re.search(regex, queue_log_text) is None:
            self.fail(
                u'Top of the queue does not contain the message with '
                u'regex="%s" but rather text="%s"' % (
                    regex, unicode(first_log_entry)))
        else:
            # Everthing looks fine so we remove the log from the queue
            self.log_queue.popleft()

    def popLog(self):
        '''Return and extract the log from the queue.'''
        return self.log_queue.popleft()

    def clearLog(self):
        '''Remove all current entries from the log queue.'''
        self.log_queue.clear()

    def assertLogIsEmpty(self, tear_down=False):
        '''Check that the log queue is empty.'''
        if tear_down and not self._caller_success_member:
            # When called from tearDown, only check for log if the
            # test was succesful. This prevent raising multiple failures
            # for a single error.
            return

        if len(self.log_queue) > 0:
            self.fail(u'Log queue is _not_ empty. %s' % repr(self.log_queue))


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


class ChevahWebTestCase(ChevahTestCase):
    '''A test case to integrate well with SeleniumTestCast.'''

    def setUp(self):
        super(ChevahTestCase, self).setUp()

    def tearDown(self):
        try:
            super(ChevahTestCase, self).tearDown()
        finally:
            self.cleanReactor()


def setup_os(users, groups):
    '''Create testing environemnt

    Add users, groups, create temporary folders and other things required
    by the testing system.
    '''
    from chevah.compat.platform import OSAdministration

    os_administration = OSAdministration()
    for group in groups:
        os_administration.addGroup(group)

    for user in users:
        os_administration.addUser(user)

    for group in groups:
        os_administration.addUsersToGroup(group, group.members)


def teardown_os(users, groups):
    '''Revert changes from setUpOS.'''

    from chevah.compat.platform import OSAdministration

    os_administration = OSAdministration()

    for group in groups:
        os_administration.deleteGroup(group)

    for user in users:
        os_administration.deleteUser(user)