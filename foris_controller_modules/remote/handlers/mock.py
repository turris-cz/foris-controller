#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import random
import base64
import typing


from foris_controller.app import app_info
from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockRemoteHandler(Handler, BaseMockHandler):
    ca_generated = False
    tokens: typing.List[dict] = []
    current_id = 2
    settings = {
        "enabled": False,
        "wan_access": False,
        "port": 11884,
    }

    @logger_wrapper(logger)
    def generate_ca(self, notify, exit_notify, reset_notify):
        MockRemoteHandler.ca_generated = True
        return "%08X" % random.randrange(2**32)

    @logger_wrapper(logger)
    def get_status(self):
        return {
            "status": "ready" if MockRemoteHandler.ca_generated else "missing",
            "tokens": MockRemoteHandler.tokens,
        }

    @logger_wrapper(logger)
    def generate_token(self, name, notify, exit_notify, reset_notify):
        MockRemoteHandler.tokens.append({
            "id": "%02X" % MockRemoteHandler.current_id,
            "name": name,
            "status": "valid",
        })
        MockRemoteHandler.current_id += 1

        return "%08X" % random.randrange(2**32)

    @logger_wrapper(logger)
    def revoke(self, cert_id):
        for token in MockRemoteHandler.tokens:
            if token["id"] == cert_id:
                token["status"] = "revoked"
                return True
        return False

    @logger_wrapper(logger)
    def delete_ca(self):
        MockRemoteHandler.ca_generated = False
        MockRemoteHandler.tokens = []
        MockRemoteHandler.current_id = 2
        return True

    @logger_wrapper(logger)
    def get_settings(self):
        return MockRemoteHandler.settings

    @logger_wrapper(logger)
    def update_settings(
        self, enabled, wan_access=None, port=None,
    ):
        if app_info["bus"] != "mqtt":
            MockRemoteHandler.settings["enabled"] = False
            return False

        MockRemoteHandler.settings["enabled"] = enabled
        if enabled:
            MockRemoteHandler.settings["wan_access"] = wan_access
            MockRemoteHandler.settings["port"] = port

        return True

    @logger_wrapper(logger)
    def get_token(self, id):
        filtered = [e for e in MockRemoteHandler.tokens if e["id"] == id]
        if not filtered:
            return {"status": "not_found"}
        if filtered[0]["status"] == "revoked":
            return {"status": "revoked"}
        return {"status": "valid", "token": base64.b64encode(b'some data').decode()}
