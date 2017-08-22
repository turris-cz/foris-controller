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


class RWLock(object):

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
        self._counter = 0
        self._writer_lock = lock_module.Lock()
        self._new_readers = lock_module.Lock()
        self._counter_lock = lock_module.Condition(lock_module.Lock())
        self.readlock = RWLock.ReadLock(self)
        self.writelock = RWLock.WriteLock(self)


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


def readlock(lock, logger):
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
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            logger.debug("Acquiring write lock for '%s'" % (func.__name__))
            with lock.writelock:
                return func(*args, **kwargs)
            logger.debug("Releasing write lock for '%s'" % (func.__name__))
        return inner
    return outer
