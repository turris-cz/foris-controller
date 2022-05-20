#
# foris-controller
# Copyright (C) 2017, 2021-2022 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import imp
import importlib
import inspect
import ipaddress
import os
import pkgutil
import re
import signal
import typing
from functools import wraps
from multiprocessing.managers import SyncManager

import prctl

from .module_base import BaseModule

IPAddress = typing.TypeVar("IPAddress", ipaddress.IPv4Address, ipaddress.IPv6Address)
ListOrString = typing.NewType('ListOrString', typing.Union[str, typing.List[str]])

LOGGER_MAX_LEN = 10000


class RWLock(object):
    """ Custom implementation of RWLock
        it can use lock for Processes as well as lock for threads
    """

    class ReadLock(object):
        def __init__(self, parent):
            self.parent = parent

        def __enter__(self):
            self.acquire()

        def __exit__(self, *args, **kwargs):
            self.release()

        def acquire(self):
            with self.parent._new_readers:
                with self.parent._counter_lock:
                    self.parent._counter += 1
                    self.parent._counter_lock.notify()

        def release(self):
            with self.parent._counter_lock:
                self.parent._counter -= 1
                self.parent._counter_lock.notify()

    class WriteLock(object):
        def __init__(self, parent):
            self.parent = parent

        def __enter__(self):
            self.acquire()

        def __exit__(self, *args, **kwargs):
            self.release()

        def acquire(self):
            self.parent._writer_lock.acquire()
            self.parent._new_readers.acquire()
            with self.parent._counter_lock:
                while self.parent._counter != 0:
                    self.parent._counter_lock.wait()

        def release(self):
            self.parent._new_readers.release()
            self.parent._writer_lock.release()

    def __init__(self, lock_module):
        """ Initializes RWLock

        :param lock_module: module which is used as locking backend - multiprocessing/threading
        """
        self._counter = 0
        self._writer_lock = lock_module.Lock()
        self._new_readers = lock_module.Lock()
        self._counter_lock = lock_module.Condition(lock_module.Lock())
        self.readlock = RWLock.ReadLock(self)
        self.writelock = RWLock.WriteLock(self)


def logger_wrapper(logger):
    """ Wraps funcion with some debug outputs of the logger

    :param logger: logger which will be used to trigger debug outputs
    :type logger: logging.Logger
    """

    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            logger.debug("Starting to perform '%s' (%s, %s)" % (func.__name__, args[1:], kwargs))
            res = func(*args, **kwargs)
            logger.debug("Performing '%s' finished (%s)." % (func.__name__, res))
            return res

        return inner

    return outer


def readlock(lock, logger):
    """ Make sure that this fuction is called after the read lock is obtained and
        wraps funcion with some debug outputs

    :param lock: lock which will be used
    :type lock: foris_controller.utils.RWLock
    :param logger: logger which will be used to trigger debug outputs
    :type logger: logging.Logger
    """

    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            logger.debug("Acquiring read lock for '%s'" % (func.__name__))
            with lock.readlock:
                return func(*args, **kwargs)
            logger.debug("Releasing read lock for '%s'" % (func.__name__))

        return inner

    return outer


def writelock(lock, logger):
    """ Make sure that this fuction is called after the write lock is obtained and
        wraps funcion with some debug outputs

    :param lock: lock which will be used
    :type lock: foris_controller.utils.RWLock
    :param logger: logger which will be used to trigger debug outputs
    :type logger: logging.Logger
    """

    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            logger.debug("Acquiring write lock for '%s'" % (func.__name__))
            with lock.writelock:
                return func(*args, **kwargs)
            logger.debug("Releasing write lock for '%s'" % (func.__name__))

        return inner

    return outer


def get_modules(filter_modules, module_paths=[]):
    """ Returns a list of modules that can be used

    :param filter_modules: use only modules which names are specified in this list
    :param module_paths: extra paths to dir containing modules
    :type filter_modules: list of str
    :returns: list of (module_name, module)
    """
    res = []

    modules = importlib.import_module("foris_controller_modules")

    for _, mod_name, _ in pkgutil.iter_modules(modules.__path__):
        if filter_modules and mod_name not in filter_modules:
            continue
        module = importlib.import_module("foris_controller_modules.%s" % mod_name)
        res.append((mod_name, module))

    for modules_path in module_paths:
        # dir base name will be module name
        modules_path = modules_path.rstrip("/")
        name = os.path.basename(modules_path)
        fp, pathname, description = imp.find_module(name, [os.path.dirname(modules_path)])
        try:
            res.append(
                (
                    name,
                    imp.load_module(
                        "foris_controller_modules.%s" % name, fp, pathname, description
                    ),
                )
            )
        finally:
            if fp:
                fp.close()

    return res


def get_handler(module, base_handler_class):
    """ Instanciates a specific handler based on the module and base_handler class
    :param module: module which should be used
    :type module: module
    :param base_handler_class: base of the class which should be Openwrt/Mock/...
    :type base_handler_class: class
    :returns: handler instace or None
    """
    handlers_path = os.path.join(module.__path__[0], "handlers")
    for _, handler_name, _ in pkgutil.iter_modules([handlers_path]):
        # load <module>.handlers module
        handler_mod = importlib.import_module(".".join([module.__name__, "handlers", handler_name]))

        # find subclass of base_handler (Mock/Openwrt)
        for _, handler_class in inspect.getmembers(handler_mod, inspect.isclass):
            if handler_class is not base_handler_class and issubclass(
                handler_class, base_handler_class
            ):
                return handler_class()


def get_module_class(module):
    """ Returns class of the foris-controller module.
        When a multiple suitable classes are present the first one is returned

    :param module: module which should be examined
    """
    for _, module_class in inspect.getmembers(module, inspect.isclass):
        if module_class is not BaseModule and issubclass(module_class, BaseModule):
            return module_class


def get_validator_dirs(filter_modules, module_paths=[]):
    """ Returns schema and definition dirs for validator
    :param filter_modules: use only modules present in this list
    :param module_paths: extra paths to dir containing modules
    """

    # and global definitions
    definition_dirs = [
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "schemas", "definitions")
    ]

    schema_dirs = []
    # load modules dirs
    for module_name, module in get_modules(filter_modules, module_paths):
        schema_dirs.append(os.path.join(module.__path__[0], "schema"))

    return schema_dirs, definition_dirs


def make_multiprocessing_manager():
    """ Prepares multiprocessing manager which can serve to exchange data between
    different processes (see pythons multiprocessing doc)

    :returns: newly create instance of multiprocessing manager
    :rtype: multiprocessing.managers.SyncManager
    """
    manager = SyncManager()
    manager.start(initializer=lambda: prctl.set_pdeathsig(signal.SIGKILL))
    return manager


def read_passwd_file(path: str) -> typing.Tuple[str]:
    """ Returns username and password from passwd file
    """
    with open(path, "r") as f:
        return re.match(r"^([^:]+):(.*)$", f.readlines()[0][:-1]).groups()


def check_dynamic_ranges(router_ip: str, netmask: str, start: int, limit: int) -> bool:
    """ Test whether combination of router_ip, netmask, start, limit is a valid
        dynamic dhcp range / ip combination
        :returns: True if configuration is valid False otherwise
    """
    # test new_settings
    ip = ipaddress.ip_address(router_ip)
    network = ipaddress.ip_network(f"{ip}/{netmask}", strict=False)
    try:
        start_ip = network.network_address + start
        last_ip = start_ip + limit
    except ipaddress.AddressValueError:  # IP overflow
        return False

    if start_ip not in network or last_ip not in network:  # not in dynamic range
        return False

    if start_ip <= ip <= last_ip:  # router ip within dynamic range
        return False

    return True


def ip_network_address(ip: IPAddress, netmask: str) -> IPAddress:
    """ Get network address of given network
        Accepts netmask as string, e.g. 255.255.255.0
    """
    return ipaddress.ip_network(f"{ip}/{netmask}", strict=False).network_address


def unwrap_list(option: ListOrString) -> str:
    """ Test whether passed value is list and return only string of first item
        or original string."""
    if not option:
        return ""
    if isinstance(option, list):
        return option[0]
    return option


def parse_to_list(option: ListOrString) -> typing.List[str]:
    """ Test whether passed value is already list, convert if string."""
    if not option:
        return [""]
    if not isinstance(option, list):
        return [option]
    return option


def sort_by_natural_order(items: typing.List[str]) -> typing.List[str]:
    """Sort strings in collection by natural order"""
    return sorted(
        items,
        key=lambda l: [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", l)]
    )
