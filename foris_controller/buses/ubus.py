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
import inspect
import prctl
import signal
import multiprocessing

logger = logging.getLogger(__name__)

from foris_controller.message_router import Router
from foris_controller.app import app_info
from foris_controller.utils import get_modules, get_module_class


def _get_method_names_from_module(module):
    """ Reads python module, checks for a valid foris-controller module class
        and reads all names of class functions which starts with action_*

    :param module: module to be examine
    :type module: module
    :returns: list of action names
    :rtype: list of str
    """

    module_class = get_module_class(module)

    if not module_class:
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
    """ Transfers a module to an object which is registered on ubus

    :param module_name: the name of the module
    :type module_name: str
    :param module: the module to be registered
    :type module: module
    """
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
    """ This function is used after a fork() to register a separate object based on the module

    :param socket_path: path to ubus socket
    :type socket_path: str
    :param module_name: the name of the module
    :type module_name: str
    :param module: the module which will be handled in this function
    :type module: module
    """
    if not ubus.get_connected():
        logger.debug("Connecting to ubus.")
        ubus.connect(socket_path)

    prctl.set_pdeathsig(signal.SIGKILL)
    _register_object(module_name, module)
    try:
        while True:
            ubus.loop(500)
    finally:
        ubus.disconnect()


def ubus_all_in_one_worker(socket_path, modules_list):
    """ This function is used after fork() to register all obects on ubus in a separate process

    :param socket_path: path to ubus socket
    :type socket_path: str
    :param modules_list: list of module_name and module
    :type modules_list: list of (str, module)
    """
    if not ubus.get_connected():
        logger.debug("Connecting to ubus.")
        ubus.connect(socket_path)
    prctl.set_pdeathsig(signal.SIGKILL)
    for module_name, module in modules_list:
        _register_object(module_name, module)
    try:
        while True:
            ubus.loop(500)
    finally:
        ubus.disconnect()


class UbusListener(object):

    def __init__(self, socket_path):
        """ Inits object which handle listening on ubus

        :param socket_path: path to ubus socket
        :type socket_path: str
        """

        logger.debug("Starting to create workers for ubus.")

        self.workers = []
        if app_info["ubus_single_process"]:
            worker = multiprocessing.Process(
                name="all-in-one", target=ubus_all_in_one_worker,
                args=(socket_path, get_modules(app_info["filter_modules"]), )
            )
            self.workers.append(worker)
        else:
            for module_name, module in get_modules(app_info["filter_modules"]):
                worker = multiprocessing.Process(
                    name=module_name, target=ubus_listener_worker,
                    args=(socket_path, module_name, module)
                )
                self.workers.append(worker)

        logger.debug("Ubus workers successfully initialized.")

    def serve_forever(self):
        """ Start listening on ubus (for all worker processes)
        """
        logger.debug("Starting to run workers.")

        for worker in self.workers:
            worker.start()

        logger.debug("All workers started.")

        # wait for all processes to finish
        for worker in self.workers:
            worker.join()

        logger.warning("All workers finished.")


class UbusNotificationSender(object):

    def __init__(self, socket_path):
        """ Inits object which handles sending notification via ubus

        :param socket_path: path to ubus socket
        :type socket_path: str
        """
        self.socket_path = socket_path

    def _validate(self, msg, validator):
        logger.debug("Starting to validate notification.")
        from jsonschema import ValidationError
        try:
            validator.validate(msg)
        except ValidationError:
            validator.validate_verbose(msg)
        logger.debug("Notification validation passed.")

    def notify(self, module, action, data, validator=None):
        if not ubus.get_connected():
            logger.debug("Connecting to ubus.")
            ubus.connect(self.socket_path)

        object_name = 'foris-controller-%s' % module
        logger.debug(
            "Sending notificaton (module='%s', action='%s', data='%s')" % (module, action, data))

        if validator:
            self._validate(
                {
                    "module": module,
                    "kind": "notification",
                    "action": action,
                    "data": data,
                },
                validator,
            )

        ubus.send(object_name, {"action": action, "data": data})
