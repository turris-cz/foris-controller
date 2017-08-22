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

import logging

from jsonschema import ValidationError

from foris_controller.app import app_info

logger = logging.getLogger("message_router")


class Router(object):
    def _build_error_msg(self, orig_msg, errors):
        return {
            "module": orig_msg.get("module", "?"),
            "kind": orig_msg.get("kind", "?"),
            "action": orig_msg.get("action", "?"),
            "data": {"errors": errors},
        }

    def validate(self, message, module=None, idx=None):
        app_info["validator"].validate(message, module, idx)

    def process_message(self, message):
        # validate input message
        logger.debug("Starting to validate input message.")
        try:
            self.validate(message)
        except ValidationError:
            logger.warning("Failed to validate input message.")
            return self._build_error_msg(message, ["Incorrect input."])
        logger.debug("Input message validated.")

        if message["kind"] != "request":
            logger.warning("Wrong message kind (only requests allowed) (=%s)." % message["kind"])
            return self._build_error_msg(
                message, ["Wrong message kind (only request are allowed)."])

        # check whether the module is loaded
        if message["module"] not in app_info["modules"]:
            logger.error(
                "Module not found '%s'" % message["module"])
            return self._build_error_msg(
                message, [
                    "Internal error (module not found '%s')." % message["module"]
                ]
            )

        module_instance = app_info["modules"][message["module"]]
        try:
            data = module_instance.perform_action(message["action"], message.get("data", {}))
        except Exception as e:
            logger.error("Internal error occured %s('%s')" % (type(e), str(e)))
            return self._build_error_msg(
                message, [
                    "Internal error %s('%s')" % (type(e), str(e))
                ]
            )

        reply = {
            "kind": "reply",
            "module": message["module"],
            "action": message["action"],
            "data": data,
        }

        logger.debug("Starting to validate output message.")
        try:
            self.validate(reply)
        except ValidationError:
            logger.error("Failed to validate output message.")
            return self._build_error_msg(message, ["Incorrect output %s." % str(reply)])

        logger.debug("Output message validated.")
        return reply
