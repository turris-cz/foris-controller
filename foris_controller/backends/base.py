#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

from functools import wraps

REQUIRED_FUNCTIONS = [
    'get_device_info',
    'get_serial',
    'get_temperature',
    'get_sending_info',
]


def logger_wrapper(logger):
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            logger.debug("Starting to perform '%s' (%s, %s)" % (func.__name__, args[1:], kwargs))
            res = func(*args, **kwargs)
            logger.debug("Performing '%s' finished (%s)." % (func.__name__, res))
            return res

        return inner

    return outer


class BackendFunctionNotImplemented(BaseException):
    pass


class MetaBackend(type):
    def __init__(cls, name, bases, dct):
        # Check presence of REQUIRED_FUNCTIONS for all instances except for BaseBackend
        if name != "BaseBackend":
            for function_name in REQUIRED_FUNCTIONS:
                if function_name not in dct:
                    raise BackendFunctionNotImplemented(function_name)

        super(MetaBackend, cls).__init__(name, bases, dct)


class BaseBackend(object):
    pass


BaseBackend = MetaBackend(BaseBackend.__name__, BaseBackend.__bases__, {})
