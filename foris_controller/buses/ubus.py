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

from __future__ import absolute_import

import logging
import ubus
import importlib
import inspect
import pkgutil
import prctl
import signal
import multiprocessing

logger = logging.getLogger("buses.ubus")

from ..message_router import Router
from ..app import app_info


def _get_method_names_from_module(module):
    module_class = getattr(module, "Class", None)

    if not module_class:
        # Class not found
        return None

    # read all names fucntions which starts with action_
    res = [
        e[0] for e in inspect.getmembers(
            module_class, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        ) if e[0].startswith("action_")
    ]

    # remove action_ prefix
    return [e.lstrip("action_") for e in res]


def _register_object(module_name, module):
    methods = _get_method_names_from_module(module)
    if not methods:
        logger.warning("No suitable method found in '%s' module. Skipping" % module_name)

    object_name = 'foris-controller-%s' % module_name
    logger.debug("Trying to register '%s' object." % object_name)

    def handler_gen(module, action):
        def handler(handler, data):
            logger.debug("Handling request")
            logger.debug("Data received '%s'." % str(data))
            router = Router()
            data["module"] = module
            data["action"] = action
            data["kind"] = "request"
            if not data["data"]:
                del data["data"]
            response = router.process_message(data)
            logger.debug("Sending response %s" % str(response))
            logger.debug("Handling finished.")
            handler.reply(response)
        return handler

    ubus.add(
        object_name,
        {
            method_name: {"method": handler_gen(module_name, method_name), "signature": {
                "data": ubus.BLOBMSG_TYPE_TABLE
            }} for method_name in methods
        }
    )
    logger.debug("Object '%s' was successfully registered." % object_name)


def ubus_listener_worker(socket_path, module_name, module):
    ubus.connect(socket_path)
    prctl.set_pdeathsig(signal.SIGKILL)
    _register_object(module_name, module)
    try:
        while True:
            ubus.loop(500)
    finally:
        ubus.disconnect()


class UbusListener(object):

    def _get_modules(self):
        from .. import modules
        res = []
        for _, mod_name, _ in pkgutil.iter_modules(modules.__path__):
            module = importlib.import_module("foris_controller.modules.%s" % mod_name)
            if hasattr(module, "Class"):
                res.append((mod_name, module))
        return res

    def __init__(self, socket_path):
        if app_info["ubus_single_process"]:
            logger.debug("Starting ubus in single process mode.")
            ubus.connect(socket_path)
            for module_name, module in self._get_modules():
                _register_object(module_name, module)
            logger.debug("All object were successfully registered.")
        else:
            logger.debug("Starting to create workers for ubus.")

            self.workers = []
            for module_name, module in self._get_modules():
                worker = multiprocessing.Process(
                    name=module_name, target=ubus_listener_worker,
                    args=(socket_path, module_name, module)
                )
                self.workers.append(worker)

            logger.debug("Ubus workers successfully initialized.")

    def serve_forever(self):
        if app_info["ubus_single_process"]:
            logger.debug("Starting to listen on ubus.")
            try:
                while True:
                    ubus.loop(500)
            finally:
                ubus.disconnect()
                logger.warning("Disconnected from ubus.")
        else:
            logger.debug("Starting to run workers.")

            for worker in self.workers:
                worker.start()

            logger.debug("All workers started.")

            # wait for all processes to finish
            for worker in self.workers:
                worker.join()

            logger.warning("All workers finished.")
