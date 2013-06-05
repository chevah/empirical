# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''
Package with code that helps with testing.

Here are a few import shortcuts.
'''

from chevah.empirical.testcase import (
    ChevahTestCase,
    )
from chevah.empirical.mockup import factory

# Export to new names.
EmpiricalTestCase = ChevahTestCase
mk = factory
