from setuptools import Command, find_packages, setup
import os

VERSION = '0.26.4'


class PublishCommand(Command):
    """
    Publish the source distribution to remote Chevah PyPi server.
    """

    description = 'Publish package to Chevah PyPi server.'
    user_options = []

    def initialize_options(self):
        self.cwd = None

    def finalize_options(self):
        self.cwd = os.getcwd()

    def run(self):
        assert os.getcwd() == self.cwd, (
            'Must be in package root: %s' % self.cwd)
        self.run_command('sdist')
        self.distribution.get_command_obj('sdist')
        # Upload package to Chevah PyPi server.
        upload_command = self.distribution.get_command_obj('upload')
        upload_command.repository = u'chevah'
        self.run_command('upload')


distribution = setup(
    name="chevah-empirical",
    version=VERSION,
    maintainer='Adi Roiban',
    maintainer_email='adi.roiban@chevah.com',
    license='BSD 3-Clause',
    platforms='any',
    description="Chevah Testing Helpers.",
    long_description=open('README.rst').read(),
    url='http://www.chevah.com',
    namespace_packages=['chevah'],
    packages=find_packages("."),
    scripts=['scripts/nose_runner.py'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        ],
    cmdclass={
        'publish': PublishCommand,
        },
    )
