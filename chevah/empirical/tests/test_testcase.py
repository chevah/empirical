# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for ChevahTestCase.
"""
from __future__ import with_statement

from twisted.internet import defer, reactor
from twisted.internet.task import Clock

from chevah.empirical.testcase import ChevahTestCase


class TestChevahTestCase(ChevahTestCase):
    """
    General tests for ChevahTestCase.
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
        from twisted.internet import reactor
        deferred = defer.Deferred()
        reactor.callLater(0.1, lambda d: d.callback('ok'), deferred)

        self.runDeferred(deferred, timeout=0.3)

        self.assertEqual('ok', deferred.result)

    def test_runDeferred_recursive(self):
        """
        runDeferred will execute the reactor and wait for deferred
        to return a final result.

        When a deferred is a returned, it will do a chained execution.
        """
        # Here is a bit of brain attack.
        # We wait for deferred_2, which already got a result, but
        # it also has a callback which returns deferred_1.
        # deferred_1 will get the result at some point, and will pass it
        # to deferred_2
        # deferred.callback() can not be called directly with a deferred.
        deferred_1 = defer.Deferred()
        deferred_2 = defer.Deferred()
        deferred_2.callback('start')
        deferred_2.addCallback(lambda d: deferred_1)
        reactor.callLater(0.1, lambda d: d.callback('ok'), deferred_1)

        self.runDeferred(deferred_2, timeout=0.3)

        self.assertEqual('ok', deferred_2.result)

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

        self.runDeferred(deferred, timeout=0.3, prevent_stop=True)

        self.assertIsTrue(deferred.result)
        self.assertIsNotNone(reactor.threadpool)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again and we should still have the same pool.
        self.runDeferred(
            defer.succeed(True), timeout=0.3, prevent_stop=True)

        self.assertIs(initial_pool, reactor.threadpool)

        # Run again but this time call reactor.stop.
        self.runDeferred(
            defer.succeed(True), timeout=0.3, prevent_stop=False)

        self.assertIsNone(reactor.threadpool)
