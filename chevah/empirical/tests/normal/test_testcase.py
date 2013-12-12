# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for ChevahTestCase.
"""
import sys

from twisted.internet import defer, reactor
from twisted.internet.task import Clock

from chevah.empirical import EmpiricalTestCase, mk


class Dummy(object):
    """
    Dummy class to help with testing.
    """
    _value = mk.string()

    def method(self):
        return self._value


class TestEmpiricalTestCase(EmpiricalTestCase):
    """
    General tests for EmpiricalTestCase.
    """

    def test_runDeferred_non_deferred(self):
        """
        An assertion error is raised when runDeferred is called for
        something which is not an deferred.
        Ex. a delayedCall
        """
        scheduler = Clock()
        delayed_call = scheduler.callLater(0, lambda: None)

        with self.assertRaises(AssertionError) as context:
            self.runDeferred(delayed_call)

        self.assertEqual(
            'This is not a deferred.', context.exception.message)

    def test_runDeferred_timeout(self):
        """
        runDeferred will execute the reactor and raise a timeout
        if deferred got no result after the timeout.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError) as context:
            self.runDeferred(deferred, timeout=0)

        self.assertEqual(
            'Deferred took more than 0 to execute.',
            context.exception.message
            )

        # Restore order order messing with internal timeout state in
        # previous state.
        self._reactor_timeout_failure = None

    def test_runDeferred_non_recursive(self):
        """
        runDeferred will execute the reactor and wait for deferred
        tu return a result.
        """
        deferred = defer.Deferred()
        reactor.callLater(0.001, lambda d: d.callback('ok'), deferred)

        self.runDeferred(deferred, timeout=0.3)

        self.assertEqual('ok', deferred.result)

    def test_runDeferred_callbacks_list(self):
        """
        runDeferred will execute the reactor and wait for deferred
        to return a non-deferred result from the deferrers callbacks list.
        """
        # We use an uncalled deferred, to make sure that callbacks are not
        # executed when we call addCallback.
        deferred = defer.Deferred()
        two_deferred = defer.Deferred()
        three_deferred = defer.Deferred()
        four_deferred = defer.Deferred()
        deferred.addCallback(lambda result: two_deferred)
        deferred.addCallback(lambda result: three_deferred)
        deferred.addCallback(lambda result: four_deferred)
        reactor.callLater(0.001, lambda d: d.callback('one'), deferred)
        reactor.callLater(0.001, lambda d: d.callback('two'), two_deferred)
        reactor.callLater(
            0.002, lambda d: d.callback('three'), three_deferred)
        reactor.callLater(0.003, lambda d: d.callback('four'), four_deferred)

        self.runDeferred(deferred, timeout=0.3)

        self.assertEqual('four', deferred.result)

    def test_runDeferred_cleanup(self):
        """
        runDeferred will execute the reactor and will leave the reactor
        stopped.
        """
        deferred = defer.succeed(True)

        # Make sure we have a threadpool before calling runDeferred.
        threadpool = reactor.getThreadPool()
        self.assertIsNotNone(threadpool)
        self.assertIsNotNone(reactor.threadpool)

        self.runDeferred(deferred, timeout=0.3)

        self.assertIsTrue(deferred.result)
        self.assertIsNone(reactor.threadpool)
        self.assertFalse(reactor.running)

    def test_runDeferred_prevent_stop(self):
        """
        When called with `prevent_stop=True` runDeferred will not
        stop the reactor at exit.

        In this way, threadpool and other shared reactor resources can be
        reused between multiple calls of runDeferred.
        """
        deferred = defer.succeed(True)
        # Force the reactor to create an internal threadpool, in
        # case it was removed by previous calls.
        initial_pool = reactor.getThreadPool()

        with self.patchObject(reactor, 'stop') as mock_stop:
            self.runDeferred(deferred, timeout=0.3, prevent_stop=True)

        # reactor.stop() is not called
        self.assertIsFalse(mock_stop.called)
        self.assertIsTrue(reactor._started)
        self.assertIsTrue(deferred.result)
        self.assertIsNotNone(reactor.threadpool)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again and we should still have the same pool.
        with self.patchObject(reactor, 'startRunning') as mock_start:
            self.runDeferred(
                defer.succeed(True), timeout=0.3, prevent_stop=True)

        # reactor.start() is not called if reactor was not previously
        # stopped.
        self.assertIsFalse(mock_start.called)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again but this time call reactor.stop.
        self.runDeferred(
            defer.succeed(True), timeout=0.3, prevent_stop=False)

        self.assertIsFalse(reactor._started)
        self.assertIsNone(reactor.threadpool)

    def test_assertNoResult_good(self):
        """
        assertNoResult will not fail if deferred has no result yet.
        """
        deferred = defer.Deferred()
        self.assertNoResult(deferred)

    def test_assertNoResult_fail(self):
        """
        assertNoResult will fail if deferred has a result.
        """
        deferred = defer.Deferred()
        deferred.callback(None)

        with self.assertRaises(AssertionError):
            self.assertNoResult(deferred)

    def test_successResultOf_ok(self):
        """
        successResultOf will not fail if deferred has a result.
        """
        value = object()
        deferred = defer.succeed(value)

        result = self.successResultOf(deferred)

        self.assertEqual(value, result)

    def test_successResultOf_no_result(self):
        """
        successResultOf will fail if deferred has no result.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError):
            self.successResultOf(deferred)

    def test_successResultOf_failure(self):
        """
        successResultOf will fail if deferred has a failure.
        """
        deferred = defer.fail(AssertionError())

        with self.assertRaises(AssertionError):
            self.successResultOf(deferred)

    def test_failureResultOf_good_any(self):
        """
        failureResultOf will return the failure.
        """
        error = AssertionError(u'bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_good_type(self):
        """
        failureResultOf will return the failure of a specific type.
        """
        error = NotImplementedError(u'bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred, NotImplementedError)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_bad_type(self):
        """
        failureResultOf will fail if failure is not of the specified type.
        """
        error = NotImplementedError(u'bla')
        deferred = defer.fail(error)

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred, SystemExit)

    def test_failureResultOf_no_result(self):
        """
        failureResultOf will fail if deferred got no result.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred)

    def test_failureResultOf_no_failure(self):
        """
        failureResultOf will fail if deferred is not a failure.
        """
        deferred = defer.succeed(None)

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred)

    def test_cleanTemporaryFolder_empty(self):
        """
        Empty list is returned if temporary folder does not contain test
        files for folders.
        """
        result = self.cleanTemporaryFolder()

        self.assertIsEmpty(result)

    def test_cleanTemporaryFolder_content(self):
        """
        The list of members is returned if temporary folder contains test
        files for folders.

        Only root members are returned and folders are removed recursively.
        """
        file1 = mk.fs.createFileInTemp()
        folder1 = mk.fs.createFolderInTemp()
        folder1_file2 = folder1[:]
        folder1_file2.append(mk.makeFilename())

        result = self.cleanTemporaryFolder()

        self.assertEqual(2, len(result))
        self.assertContains(file1[-1], result)
        self.assertContains(folder1[-1], result)

    def test_assertTempIsClean_clean_temp(self):
        """
        No error is raised if temp folder is clean.
        """
        self.assertTempIsClean()

    def test_assertTempIsClean_dirty(self):
        """
        If temp is not clean an error is raised and then temp folders
        is cleaned.
        """
        temp_segments = mk.fs.createFileInTemp()

        with self.assertRaises(AssertionError) as context:
            self.assertTempIsClean()

        self.assertStartsWith(
            u'Temporary folder is not clean. [', context.exception.message)

        self.assertFalse(mk.fs.exists(temp_segments))

    def test_patch(self):
        """
        It can be used for patching classes.
        """
        value = mk.string()

        with self.patch(
                'chevah.empirical.tests.normal.test_testcase.Dummy.method',
                return_value=value,
            ):
            instance = Dummy()
            self.assertEqual(value, instance.method())

        # After exiting the context, the value is restored.
        instance = Dummy()
        self.assertEqual(Dummy._value, instance.method())

    def test_patchObject(self):
        """
        It can be used for patching an instance of an object.
        """
        value = mk.string()
        one_instance = Dummy()

        with self.patchObject(
                one_instance, 'method', return_value=value):
            self.assertEqual(value, one_instance.method())

            # All other instances are not affected.
            new_instance = Dummy()
            self.assertEqual(Dummy._value, new_instance.method())

        # After exiting the context, the value is restored.
        self.assertEqual(Dummy._value, one_instance.method())

    def test_Mock(self):
        """
        It creates a generic mock object.
        """
        value = mk.string()

        mock = self.Mock(return_value=value)

        self.assertEqual(value, mock())

    def test_skipped_test(self):
        """
        Just a test to check that everything works ok with skipped tests
        in a normal testcase.
        """
        raise self.skipTest()

    def test_listenPort(self):
        """
        It can be used for listening a dummy connection on a port and address.
        """
        address = '127.0.0.1'
        port = 10000

        with self.listenPort(address, port):

            self.assertIsListening(address, port)

    def test_listenPort_on_loopback_alias(self):
        """
        Integration test to check that we can listen on loopback alias.

        This is a system test, but socket operations are light.
        """
        if sys.platform.startswith('aix'):
            # On AIX and probably on other Unixes we can only bind on
            # existing fixed IP addressed like 127.0.0.1.
            raise self.skipTest()

        # This is just a test to make sure that the server can listen to
        # 127.0.0.10 as this IP is used in other tests.
        address = '127.0.0.10'
        port = 10070

        with self.listenPort(address, port):

            self.assertIsListening(address, port)


class TestEmpiricalTestCaseSkipSetup(EmpiricalTestCase):
    """
    Test skipped test at setup level.
    """

    def setUp(self):
        """
        Skip the test, after initializing parent.

        This will prevent calling of tearDown.
        """
        super(TestEmpiricalTestCaseSkipSetup, self).setUp()

        raise self.skipTest()

    def tearDown(self):
        raise AssertionError('Should not be called.')

    def test_skipped_test(self):
        """
        Just a test to check that everything works ok with skipped tests.
        """
        raise AssertionError('Should not be called')
