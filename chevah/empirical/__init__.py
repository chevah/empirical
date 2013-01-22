# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''
Package with code that helps with testing.

Here are a few import shortcuts.
'''

from chevah.empirical.testcase import (
    ChevahTestCase,
    EventTestCase,
    )
from chevah.empirical.mockup import factory

# Silence the linter.
ChevahTestCase
EventTestCase
factory
