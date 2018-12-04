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
from foris_controller.utils import logger_wrapper, IPv4

from .. import Handler

logger = logging.getLogger(__name__)


class MockGuestHandler(Handler, BaseMockHandler):
    enabled = False
    router_ip = "192.168.1.1"
    netmask = "255.255.255.0"
    dhcp = {
        "enabled": False,
        "start": 100,
        "limit": 150,
        "lease_time": 12 * 60 * 60,
        "clients": [
            {
                "ip": "10.10.2.1", "mac": "16:25:34:43:52:61",
                "expires": 1539350286, "active": True, "hostname": "first"
            },
            {
                "ip": "10.10.1.1", "mac": "94:85:76:67:58:49",
                "expires": 1539350388, "active": False, "hostname": ""
            }
        ]
    }
    qos = {
        "enabled": False,
        "download": 1200,
        "upload": 1200,
    }

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get guest settings

        :returns: current guest settiongs
        :rtype: str
        """
        from foris_controller_modules.networks.handlers.mock import MockNetworksHandler

        result = {
            "enabled": MockGuestHandler.enabled,
            "ip": MockGuestHandler.router_ip,
            "netmask": MockGuestHandler.netmask,
            "dhcp": MockGuestHandler.dhcp,
            "qos": MockGuestHandler.qos,
            "interface_count": len(MockNetworksHandler.networks["guest"]),
            "interface_up_count": len(
                [e for e in MockNetworksHandler.networks["guest"] if e["state"] == "up"])
        }
        return result

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current guest settings
        :returns: True if update passes
        :rtype: bool
        """

        if new_settings["enabled"] and new_settings["dhcp"]["enabled"]:
            ip_norm = IPv4.normalize_subnet(new_settings["ip"], new_settings["netmask"])
            start, limit = new_settings["dhcp"]["start"], new_settings["dhcp"]["limit"]
            last_ip_num = IPv4.str_to_num(ip_norm) + start + limit
            if last_ip_num >= 2 ** 32:  # ip overflow
                return False
            last_ip_norm = IPv4.normalize_subnet(
                IPv4.num_to_str(last_ip_num), new_settings["netmask"])
            if last_ip_norm != ip_norm:
                return False

        MockGuestHandler.enabled = new_settings["enabled"]
        if MockGuestHandler.enabled:
            MockGuestHandler.router_ip = new_settings["ip"]
            MockGuestHandler.netmask = new_settings["netmask"]
            MockGuestHandler.dhcp["enabled"] = new_settings["dhcp"]["enabled"]
            MockGuestHandler.dhcp["start"] = new_settings["dhcp"].get(
                "start", MockGuestHandler.dhcp["start"])
            MockGuestHandler.dhcp["limit"] = new_settings["dhcp"].get(
                "limit", MockGuestHandler.dhcp["limit"])
            MockGuestHandler.dhcp["lease_time"] = new_settings["dhcp"].get(
                "lease_time", MockGuestHandler.dhcp["lease_time"])
            MockGuestHandler.qos["enabled"] = new_settings["qos"]["enabled"]
            if MockGuestHandler.qos["enabled"]:
                MockGuestHandler.qos["download"] = new_settings["qos"]["download"]
                MockGuestHandler.qos["upload"] = new_settings["qos"]["upload"]

        return True
