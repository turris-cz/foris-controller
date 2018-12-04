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
from foris_controller.utils import logger_wrapper, IPv4

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
            "clients": [
                {
                    "ip": "192.168.1.1", "mac": "11:22:33:44:55:66",
                    "expires": 1539350186, "active": True, "hostname": "prvni"
                },
                {
                    "ip": "192.168.2.1", "mac": "99:88:77:66:55:44",
                    "expires": 1539350188, "active": False, "hostname": "*"
                }
            ]
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
            "interface_count": len(MockNetworksHandler.networks["lan"]),
            "interface_up_count": len([
                e for e in MockNetworksHandler.networks["lan"] if e["state"] == "up"])
        }
        return result

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current lan settings
        :returns: True if update passes
        :rtype: bool
        """

        # test new_settings
        if new_settings["mode"] == "managed" and new_settings["mode_managed"]["dhcp"]["enabled"]:
            netmask = new_settings["mode_managed"]["netmask"]
            ip = new_settings["mode_managed"]["router_ip"]
            ip_norm = IPv4.normalize_subnet(ip, netmask)
            start = new_settings["mode_managed"]["dhcp"]["start"]
            limit = new_settings["mode_managed"]["dhcp"]["limit"]
            last_ip_num = IPv4.str_to_num(ip_norm) + start + limit
            if last_ip_num >= 2 ** 32:  # ip overflow
                return False
            last_ip_norm = IPv4.normalize_subnet(IPv4.num_to_str(last_ip_num), netmask)
            if last_ip_norm != ip_norm:
                return False

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
