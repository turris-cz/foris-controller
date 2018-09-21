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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockLanHandler(Handler, BaseMockHandler):
    router_ip = "192.168.1.1"
    netmask = "255.255.255.0"
    dhcp = {
        "enabled": False,
        "start": 100,
        "limit": 150,
        "lease_time": 120,
    }

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get lan settings

        :returns: current lan settiongs
        :rtype: str
        """
        result = {
            "ip": self.router_ip,
            "netmask": self.netmask,
            "dhcp": self.dhcp,
        }
        return result

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current lan settings
        :returns: True if update passes
        :rtype: bool
        """
        self.router_ip = new_settings["ip"]
        self.netmask = new_settings["netmask"]
        self.dhcp["enabled"] = new_settings["dhcp"]["enabled"]
        self.dhcp["start"] = new_settings["dhcp"].get("start", self.dhcp["start"])
        self.dhcp["limit"] = new_settings["dhcp"].get("limit", self.dhcp["limit"])
        self.dhcp["lease_time"] = new_settings["dhcp"].get("lease_time", self.dhcp["lease_time"])
        return True
