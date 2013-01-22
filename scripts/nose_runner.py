# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Helper for executing nose as a separate process.

This is needed since on Unix the tests are executed using sudo.
'''
import sys

from nose.core import main as nose_main

from chevah.empirical.nose_test_timer import TestTimer
from chevah.empirical.nose_run_reporter import RunReporter
from chevah.empirical.testcase import ChevahTestCase

if __name__ == '__main__':
    '''Execute the nose test runner.

    Drop privileges and alter the system argument to remove the
    userid and group id arguments that are only required for the test.
    '''
    if len(sys.argv) < 2:
        print (
            u'Run the test suite using drop privilges username as first '
            u'arguments. Use "-" if you do not want elevated mode.')
        sys.exit(1)

    ChevahTestCase.initialize(drop_user=sys.argv[1])
    ChevahTestCase.dropPrivileges()

    new_argv = ['chevah-test-runner']
    new_argv.extend(sys.argv[2:])
    sys.argv = new_argv
    nose_main(addplugins=[
        TestTimer(),
        RunReporter(),
        ])
