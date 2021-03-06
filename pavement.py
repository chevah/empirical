# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-empirical.
"""
import os
import sys
import warnings

from brink.pavement_commons import (
    buildbot_list,
    buildbot_try,
    coverage_prepare,
    coverage_publish,
    default,
    github,
    harness,
    help,
    lint,
    merge_init,
    merge_commit,
    pave,
    pqm,
    SETUP,
    test_coverage,
    test_os_dependent,
    test_os_independent,
    test_python,
    test_remote,
    test_normal,
    test_review,
    test_super,
    )
from paver.easy import call_task, consume_args, needs, task

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile
    tempfile.tempdir = "c:\\temp"

RUN_PACKAGES = [
    'twisted==15.5.0.chevah4',
    'chevah-compat==0.24.0',
    # Py3 compat.
    'future',
    # Required for compat testing.
    'unidecode',
    # We install wmi everywhere even though it is only used on Windows.
    'wmi==1.4.9',
    ]

BUILD_PACKAGES = [
    # Buildbot is used for try scheduler
    'buildbot==0.8.11.c7',

    # For PQM
    'smmap==0.8.2',
    'async==0.6.1',
    'gitdb==0.6.4',
    'gitpython==1.0.1',
    'pygithub==1.10.0',
    ]


TEST_PACKAGES = [
    'pyflakes==0.8.1',
    'closure_linter==2.3.9',
    'pocketlint==1.4.4.c4',

    # Used for py3 porting and other checks.
    'pylint==1.4.3',
    'pep8 >= 1.6.2',

    # Never version of nose, hangs on closing some tests
    # due to some thread handling.
    'nose==1.3.6',
    'mock',

    'coverage==4.0.3',
    'codecov==2.0.3',

    # Used to test HTTPServerContext
    'requests==2.5.3',

    'bunch',
    ]

# Make pylint shut up.
buildbot_list
buildbot_try
coverage_prepare
coverage_publish
default
github
harness
help
lint
merge_init
merge_commit
pqm
test_coverage
test_os_dependent
test_os_independent
test_python
test_remote
test_normal
test_review
test_super

SETUP['product']['name'] = 'chevah-empirical'
SETUP['folders']['source'] = pave.fs.join([u'chevah', 'empirical'])
SETUP['repository']['name'] = u'empirical'
SETUP['repository']['github'] = u'https://github.com/chevah/empirical'
SETUP['pocket-lint']['include_files'] = [
    'pavement.py',
    'release-notes.rst',
    ]
SETUP['buildbot']['server'] = 'buildbot.chevah.com'
SETUP['buildbot']['web_url'] = 'http://buildbot.chevah.com:10433'
SETUP['pypi']['index_url'] = 'http://pypi.chevah.com/simple'
SETUP['pocket-lint']['include_folders'] = ['chevah/empirical']
SETUP['pocket-lint']['exclude_files'] = []
SETUP['test']['package'] = 'chevah.empirical.tests'
SETUP['test']['elevated'] = 'elevated'


@task
def update_setup():
    """
    Does nothing.
    """


@task
def deps():
    """
    Install all dependencies.
    """
    print('Installing  dependencies to %s...' % (pave.path.build))
    pave.pip(
        command='install',
        arguments=RUN_PACKAGES + TEST_PACKAGES + BUILD_PACKAGES,
        silent=False,
        )


@task
@needs('coverage_prepare')
def build(platform=None, python_version=None):
    """
    Copy new source code to build folder.
    """
    # Clean previous files.
    install_folder = [
        pave.path.build,
        pave.getPythonLibPath(python_version=python_version),
        'chevah',
        'empirical',
        ]
    pave.fs.deleteFolder(install_folder)
    pave.fs.deleteFolder([pave.path.build, 'setup-build'])
    build_target = pave.fs.join([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', 'build', '--build-base', build_target]
    print "Building in " + build_target
    import setup
    setup.distribution.run_command('install')


@task
def test_documentation():
    """
    Does nothing.
    """


@consume_args
@needs('test_python')
def test(args):
    """
    Run all python tests.
    """


@task
# It needs consume_args to initialize the paver environment.
@consume_args
def test_ci(args):
    """
    Run tests in continuous integration environment.
    """
    env = os.environ.copy()
    args = env.get('TEST_ARGUMENTS', '')
    if not args:
        args = []
    else:
        args = [args]
    test_type = env.get('TEST_TYPE', 'normal')

    if test_type == 'os-independent':
        return call_task('test_os_independent')

    if test_type == 'py3':
        return call_task('test_py3', args=args)

    call_task('test_os_dependent', args=args)

    # Only publish coverage for os dependent tests and if coverage is enabled
    # and we have a token.
    codecov_token = os.environ.get('CODECOV_TOKEN', '')
    if codecov_token:
        call_task('coverage_publish')


@task
def test_py3():
    """
    Run checks for py3 compatibility.
    """
    from pylint.lint import Run
    from nose.core import main as nose_main
    arguments = ['--py3k', SETUP['folders']['source']]
    linter = Run(arguments, exit=False)
    stats = linter.linter.stats
    errors = (
        stats['info'] + stats['error'] + stats['refactor'] +
        stats['fatal'] + stats['convention'] + stats['warning']
        )
    if errors:
        print 'Pylint failed'
        sys.exit(1)

    print 'Compiling in Py3 ...',
    command = ['python3', '-m', 'compileall', '-q', 'chevah']
    pave.execute(command, output=sys.stdout)
    print 'done'

    sys.argv = sys.argv[:1]
    pave.python_command_normal.extend(['-3'])

    warnings.filterwarnings('always', module='chevah.empirical')
    captured_warnings = []

    def capture_warning(
        message, category, filename,
        lineno=None, file=None, line=None
            ):
        if not filename.startswith('chevah'):
            # Not our code.
            return
        line = (message.message, filename, lineno)
        if line in captured_warnings:
            # Don't include duplicate warnings.
            return
        captured_warnings.append(line)

    warnings.showwarning = capture_warning

    sys.args = ['nose', 'chevah.empirical.tests.normal']
    runner = nose_main(exit=False)
    if not runner.success:
        print 'Test failed'
        sys.exit(1)
    if not captured_warnings:
        sys.exit(0)

    print '\nCaptured warnings\n'
    for warning, filename, line in captured_warnings:
        print '%s:%s %s' % (filename, line, warning)
    sys.exit(1)
