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

import copy
import logging

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockLanHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    mode = "managed"
    mode_managed = {
        "router_ip": "192.168.1.1",
        "netmask": "255.255.255.0",
        "dhcp": {
            "enabled": False,
            "start": 100,
            "limit": 150,
            "lease_time": 120,
        }
    }
    mode_unmanaged = {
        "lan_type": "none",
        "lan_dhcp": {
            "hostname": None,
        },
        "lan_static": {
            "ip": "192.168.1.10",
            "netmask": "255.255.255.0",
            "gateway": "192.168.1.1",
            "dns1": None,
            "dns2": None,
        },
    }

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get lan settings

        :returns: current lan settiongs
        :rtype: str
        """
        mode_unmanaged = copy.deepcopy(MockLanHandler.mode_unmanaged)

        if not mode_unmanaged["lan_dhcp"]["hostname"]:
            del mode_unmanaged["lan_dhcp"]["hostname"]
        if not mode_unmanaged["lan_static"]["dns1"]:
            del mode_unmanaged["lan_static"]["dns1"]
        if not mode_unmanaged["lan_static"]["dns2"]:
            del mode_unmanaged["lan_static"]["dns2"]

        from foris_controller_modules.networks.handlers.mock import MockNetworksHandler

        result = {
            "mode": MockLanHandler.mode,
            "mode_managed": MockLanHandler.mode_managed,
            "mode_unmanaged": mode_unmanaged,
            "interface_count": len(MockNetworksHandler.networks["lan"])
        }
        return result

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current lan settings
        :returns: True if update passes
        :rtype: bool
        """
        MockLanHandler.mode = new_settings["mode"]
        if new_settings["mode"] == "managed":
            mode = new_settings["mode_managed"]
            self.mode_managed["router_ip"] = mode["router_ip"]
            self.mode_managed["netmask"] = mode["netmask"]
            self.mode_managed["dhcp"]["enabled"] = mode["dhcp"]["enabled"]
            self.mode_managed["dhcp"]["start"] = mode["dhcp"].get(
                "start", self.mode_managed["dhcp"]["start"])
            self.mode_managed["dhcp"]["limit"] = mode["dhcp"].get(
                "limit", self.mode_managed["dhcp"]["limit"])
            self.mode_managed["dhcp"]["lease_time"] = mode["dhcp"].get(
                "lease_time", self.mode_managed["dhcp"]["lease_time"])
        elif new_settings["mode"] == "unmanaged":
            self.mode_unmanaged["lan_type"] = new_settings["mode_unmanaged"]["lan_type"]
            if new_settings["mode_unmanaged"]["lan_type"] == "dhcp":
                hostname = new_settings["mode_unmanaged"]["lan_dhcp"].get("hostname")
                if hostname:
                    self.mode_unmanaged["lan_dhcp"]["hostname"] = hostname
            elif new_settings["mode_unmanaged"]["lan_type"] == "static":
                self.mode_unmanaged["lan_static"] = {
                    "ip": new_settings["mode_unmanaged"]["lan_static"]["ip"],
                    "netmask": new_settings["mode_unmanaged"]["lan_static"]["netmask"],
                    "gateway": new_settings["mode_unmanaged"]["lan_static"]["gateway"],
                }
                dns1 = new_settings["mode_unmanaged"]["lan_static"].get("dns1")
                self.mode_unmanaged["lan_static"]["dns1"] = dns1
                dns2 = new_settings["mode_unmanaged"]["lan_static"].get("dns2")
                self.mode_unmanaged["lan_static"]["dns2"] = dns2

            elif new_settings["mode_unmanaged"]["lan_type"] == "none":
                pass

        MockLanHandler.guide_set.set(True)
        return True
