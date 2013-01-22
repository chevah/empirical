"""
Helpers for running tests for which Twisted reactor in execcuted in a
separate thread.

This code is under based on nose/twistedtools.py which is under LGPL license.
"""
from threading import Thread

from twisted.python import threadable
threadable.registerAsIOThread()

_twisted_thread = None


def threaded_reactor():
    """
    Start the Twisted reactor in a separate thread, if not already done.
    Returns the reactor.
    The thread will automatically be destroyed when all the tests are done.
    """
    global _twisted_thread
    try:
        from twisted.internet import reactor
    except ImportError:
        return None, None
    if not _twisted_thread:

        _twisted_thread = Thread(target=lambda: reactor.run( \
                installSignalHandlers=False))
        _twisted_thread.setDaemon(True)
        _twisted_thread.start()
    return reactor, _twisted_thread


def stop_reactor():
    """
    Stop the reactor and join the reactor thread until it stops.
    Call this function in teardown at the module or package level to
    reset the twisted system after your tests. You *must* do this if
    you mix tests using these tools and tests using twisted.trial.
    """
    global _twisted_thread

    def stop_reactor():
        '''Helper for calling stop from withing the thread.'''
        reactor.stop()
        for p in reactor.getDelayedCalls():
            if p.active():
                p.cancel()

    reactor.callFromThread(stop_reactor)
    reactor_thread.join()
    _twisted_thread = None


# Export global reactor variable, as Twisted does
reactor, reactor_thread = threaded_reactor()
