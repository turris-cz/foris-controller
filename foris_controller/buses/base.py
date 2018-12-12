#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import logging
import inspect


logger = logging.getLogger(__name__)

from foris_controller.utils import get_modules, get_module_class


class BaseNotificationSender(object):

    def _validate(self, msg, validator):
        logger.debug("Starting to validate notification.")
        validator.validate(msg)
        logger.debug("Notification validation passed.")

    def _prepare_msg(self, module, action, data=None):
        msg = {
            "module": module,
            "kind": "notification",
            "action": action,
        }
        if data is not None:
            msg["data"] = data
        return msg

    def notify(self, module, action, data=None, validator=None):
        """ Send a notification on a message bus
        """
        msg = self._prepare_msg(module, action, data)
        if validator:
            self._validate(msg, validator)

        return self._send_message(msg, module, action, data)

    def _send_message(self, msg, module, action, data=None):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()


class BaseSocketListener(object):

    def serve_forever(self):
        raise NotImplementedError()


def get_method_names_from_module(module):
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
    return [e[len("action_"):] for e in res]
