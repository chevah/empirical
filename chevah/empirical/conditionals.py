# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Decorators used for testing.
"""
from nose import SkipTest
from functools import wraps

from chevah.compat import process_capabilities


def onOSFamily(family):
    """
    Run test only if current os is from `family`.
    """
    def inner(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            if process_capabilities.os_family != family.lower():
                raise SkipTest()
            return method(*args, **kwargs)
        return wrapper

    return inner


def onOSName(name):
    """
    Run test only if current os is `name` or is in one from `name` list.
    """
    if not isinstance(name, list) and not isinstance(name, tuple):
        name = [name.lower()]
    else:
        name = [item.lower() for item in name]

    def inner(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            if process_capabilities.os_name not in name:
                raise SkipTest()
            return method(*args, **kwargs)
        return wrapper

    return inner
