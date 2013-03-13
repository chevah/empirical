# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for ChevahTestCase.
"""
from __future__ import with_statement

from twisted.internet.defer import Deferred
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
        deferred = Deferred()

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
        deferred = Deferred()
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
        from twisted.internet import reactor
        deferred_1 = Deferred()
        deferred_2 = Deferred()
        deferred_2.callback('start')
        deferred_2.addCallback(lambda d: deferred_1)
        reactor.callLater(0.1, lambda d: d.callback('ok'), deferred_1)

        self.runDeferred(deferred_2, timeout=0.3)

        self.assertEqual('ok', deferred_2.result)
