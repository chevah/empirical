# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-empirical.
"""
from __future__ import with_statement
import sys

# Marker for paver.sh.
# This value is pavers by bash. Use a strict format.
BRINK_VERSION = '0.7.1'

EXTRA_PACKAGES = [
    'chevah-compat==0.2.0',
    'chevah-utils==0.3.0',
    ]

from brink.pavement_commons import (
    _p,
    buildbot_list,
    buildbot_try,
    default,
    harness,
    help,
    lint,
    pave,
    SETUP,
    test,
    test_remote,
    test_normal,
    test_super,
    )
from paver.easy import task

# Make pylint shut up.
buildbot_list
buildbot_try
default
harness
help
lint
test
test_remote
test_normal
test_super

SETUP['product']['name'] = 'chevah-empirical'
SETUP['folders']['source'] = u'chevah/empirical'
SETUP['repository']['name'] = u'empirical'
SETUP['pocket-lint']['include_files'] = ['pavement.py']
SETUP['pocket-lint']['include_folders'] = ['chevah/empirical']
SETUP['pocket-lint']['exclude_files'] = []
SETUP['test']['package'] = 'chevah.empirical.tests'


@task
def deps():
    """
    Copy external dependencies.
    """
    print('Installing dependencies to %s...' % (pave.path.build))
    pave.installRunDependencies(extra_packages=EXTRA_PACKAGES)
    pave.installBuildDependencies()


@task
def build():
    """
    Copy new source code to build folder.
    """
    build_target = _p([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', 'build', '--build-base', build_target]
    print "Building in " + build_target
    import setup
    setup.distribution.run_command('install')