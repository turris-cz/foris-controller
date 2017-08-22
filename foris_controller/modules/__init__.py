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


import importlib
import inspect
import os
import pkgutil


def get_modules():
    res = []
    for _, mod_name, _ in pkgutil.iter_modules(__path__):
        module = importlib.import_module("foris_controller.modules.%s" % mod_name)
        if hasattr(module, "Class"):
            res.append((mod_name, module))
    return res


def get_handler(module, base_handler_class):
    handlers_path = os.path.join(module.__path__[0], "handlers")
    for _, handler_name, _ in pkgutil.iter_modules([handlers_path]):
        # load <module>.handlers module
        handler_mod = importlib.import_module(
            ".".join([module.__name__, "handlers", handler_name]))

        # find subclass of base_handler (Mock/Openwrt)
        for _, handler_class in inspect.getmembers(handler_mod, inspect.isclass):
            if handler_class is not base_handler_class and \
                    issubclass(handler_class, base_handler_class):
                return handler_class()
