"""This plugin provides test timings to identify which tests might be
taking the most. From this information, it might be useful to couple
individual tests nose's `--with-profile` option to profile problematic
tests.

This plugin is heavily influenced by nose's `xunit` plugin.

Add this command to the way you execute nose::

    --with-test-timer

After all tests are executed, they will be sorted in ascending order.

(c) 2011 - Mahmoud Abdelkader (http://github.com/mahmoudimus)

LICENSE:
            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                    Version 2, December 2004

 Copyright (C) 2004 Sam Hocevar <sam@hocevar.net>

 Everyone is permitted to copy and distribute verbatim or modified
 copies of this license document, and changing it is allowed as long
 as the name is changed.

            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. You just DO WHAT THE FUCK YOU WANT TO.

"""

import operator
from time import time

import nose
from nose.plugins.base import Plugin

# Number of tests to show in final report.
TOP_COUNT = 10
# Ideal execution time in seconds.
IDEAL_TIME = 0.009


class TestTimer(Plugin):
    '''This plugin reporting time execution for each test.

    It reports the 10 most slow tests.
    'inner' time is the time while the only the test code is executed.
    'outer' time is the setup, test and teardown execution time.
    '''

    name = 'timer'
    score = 1

    def _timeTaken(self, time_now, kind):
        if hasattr(self, '_timer'):
            taken = time_now - self._timer[kind]
        else:
            # test died before it ran (probably error in setup())
            # or success/failure added before test started probably
            # due to custom TestResult munging
            taken = 0.0
        return taken

    def _set_start_time(self, kind):
        '''Set final time for only the test code.'''
        self._timer[kind] = time()

    def _set_end_time(self, test, time_now, kind):
        '''Set final time for only the test code.'''
        self._timed_tests[kind][test.id()] = self._timeTaken(time_now, kind)

    def options(self, parser, env):
        """Sets additional command line options."""
        super(TestTimer, self).options(parser, env)

    def configure(self, options, config):
        """Configures the test timer plugin."""
        super(TestTimer, self).configure(options, config)
        self.config = config
        self._timed_tests = {'inner': {}, 'outer': {}}
        self._timer = {'inner': 0, 'outer': 0}

    def startTest(self, test):
        '''Initializes a timer before starting a test.

        We wrap the actual testing method to have a more accurate
        measurement.
        '''
        self._timer = {'inner': 0, 'outer': 0}
        self._initial_target_test = getattr(
                test.test, test.test._testMethodName)

        def wrapped_test():
            self._set_start_time(kind='inner')
            self._initial_target_test()
            self._set_end_time(test=test, time_now=time(), kind='inner')

        setattr(test.test, test.test._testMethodName, wrapped_test)

        self._set_start_time(kind='outer')

    def stopTest(self, test):
        self._set_end_time(test=test, time_now=time(), kind='outer')
        try:
            self._timed_tests['inner'][test.id()]
        except KeyError:
            self._set_end_time(test=test, time_now=time(), kind='inner')

    def report(self, stream):
        """Report the test times"""
        if not self.enabled:
            return

        inner_time_list = sorted(
            self._timed_tests['inner'].iteritems(),
            key=operator.itemgetter(1),
            )

        total_time = {'inner': 0, 'outer': 0}
        tests_count = 0

        for test, time_inner in inner_time_list:
            tests_count += 1
            total_time['inner'] += time_inner
            total_time['outer'] += self._timed_tests['outer'][test]

        if tests_count == 0:
            stream.writeln('-' * 70)
            stream.writeln('No tests were executed.')
            return

        test_start = tests_count - TOP_COUNT
        if test_start < 0:
            test_start = 0

        for index in xrange(test_start, tests_count):
            test, time_taken = inner_time_list[index]
            outer_time = self._timed_tests['outer'][test]
            stream.writeln("%0.4f:%0.4f: %s" % (time_taken, outer_time, test))

        def get_status(average):
            if average > IDEAL_TIME:
                status = 'bad job - above %0.4f' % IDEAL_TIME
            else:
                status = 'excellent job'
            return status

        a_inner = total_time['inner'] / tests_count
        a_outer = total_time['outer'] / tests_count
        s_inner = get_status(a_inner)
        s_outer = get_status(a_outer)

        stream.writeln('-' * 70)
        stream.writeln("Average inner: %0.4f (%s)" % (a_inner, s_inner))
        stream.writeln("Average outer: %0.4f (%s)" % (a_outer, s_outer))
        stream.writeln("Total inner  : %0.4f" % total_time['inner'])
        stream.writeln("Total outer  : %0.4f" % total_time['outer'])


if __name__ == '__main__':
    nose.main(addplugins=[TestTimer()])