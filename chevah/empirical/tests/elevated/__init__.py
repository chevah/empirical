# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for empirical package executed under elevated accounts.
"""
from chevah.compat import process_capabilities
from chevah.compat.testing import (
    TEST_GROUPS,
    TEST_USERS,
    )

from chevah.empirical.testcase import (
    setup_os,
    teardown_os,
    )
from chevah.empirical import EmpiricalTestCase


def should_run_elevated_test():
    """
    Return true if we can access privileged OS operations.
    """
    if not process_capabilities.impersonate_local_account:
        return False

    if not process_capabilities.get_home_folder:
        return False

    return True


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not should_run_elevated_test():
        raise EmpiricalTestCase.skipTest()

    # Initialize the testing OS.
    try:
        setup_os(users=TEST_USERS, groups=TEST_GROUPS)
    except:
        import traceback
        error = traceback.format_exc()
        try:
            teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
        except:
            pass
        raise AssertionError(
            'Failed to initialize system accounts.\n\n%s' % (error))


def teardown_package():
    teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
