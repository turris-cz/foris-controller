#
# foris-controller
# Copyright (C) 2019-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import typing
import ipaddress

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockLanHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    mode: str = "managed"
    mode_managed: typing.Dict[str, typing.Any] = {
        "router_ip": "192.168.1.1",
        "netmask": "255.255.255.0",
        "dhcp": {
            "enabled": False,
            "start": 100,
            "limit": 150,
            "lease_time": 120,
            "clients": [
                {
                    "ip": "192.168.1.1",
                    "mac": "11:22:33:44:55:66",
                    "expires": 1539350186,
                    "active": True,
                    "hostname": "prvni",
                },
                {
                    "ip": "192.168.2.1",
                    "mac": "99:88:77:66:55:44",
                    "expires": 1539350188,
                    "active": False,
                    "hostname": "*",
                },
            ],
            "ipv6clients": [
                {
                    "ipv6": "fd52:ad42:a6c9::64fe",
                    "duid": "00010003d8e63397f73ed8cd7cda",
                    "expires": 1539350186,
                    "active": True,
                    "hostname": "prvni"
                },
                {
                    "ipv6": "fd52:ad42:a6c9::64fa",
                    "duid": "00020000df167896750a08ce0782",
                    "expires": 1539350186,
                    "active": False,
                    "hostname": "*"
                },
            ]
        },
    }
    mode_unmanaged: typing.Dict[str, typing.Any] = {
        "lan_type": "none",
        "lan_dhcp": {"hostname": None},
        "lan_static": {
            "ip": "192.168.1.10",
            "netmask": "255.255.255.0",
            "gateway": "192.168.1.1",
            "dns1": None,
            "dns2": None,
        },
    }
    lan_redirect = True

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
            "interface_up_count": len(
                [e for e in MockNetworksHandler.networks["lan"] if e["state"] == "up"]
            ),
            "lan_redirect": MockLanHandler.lan_redirect,
        }
        return result

    @logger_wrapper(logger)
    def update_settings(self, new_settings: dict):
        """ Mocks updates current lan settings
        :returns: True if update passes
        :rtype: bool
        """

        if "lan_redirect" in new_settings:
            MockLanHandler.lan_redirect = new_settings["lan_redirect"]

        MockLanHandler.mode = new_settings["mode"]
        if new_settings["mode"] == "managed":
            mode = new_settings["mode_managed"]
            self.mode_managed["router_ip"] = mode["router_ip"]
            self.mode_managed["netmask"] = mode["netmask"]
            self.mode_managed["dhcp"]["enabled"] = mode["dhcp"]["enabled"]
            self.mode_managed["dhcp"]["start"] = mode["dhcp"].get(
                "start", self.mode_managed["dhcp"]["start"]
            )
            self.mode_managed["dhcp"]["limit"] = mode["dhcp"].get(
                "limit", self.mode_managed["dhcp"]["limit"]
            )
            self.mode_managed["dhcp"]["lease_time"] = mode["dhcp"].get(
                "lease_time", self.mode_managed["dhcp"]["lease_time"]
            )

            # remove clients by its ip
            self.mode_managed["dhcp"]["clients"] = [
                e
                for e in self.mode_managed["dhcp"]["clients"]
                if e["ip"] == "ignore"
                or (
                    not MockLanHandler.in_range(
                        e["ip"],
                        self.mode_managed["router_ip"],
                        self.mode_managed["dhcp"]["start"],
                        self.mode_managed["dhcp"]["limit"],
                    )
                    and MockLanHandler.in_network(
                        e["ip"], self.mode_managed["router_ip"], self.mode_managed["netmask"]
                    )
                )
            ]

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

    @staticmethod
    def in_range(ip: str, router_ip: str, start: int, limit: int) -> bool:
        dynamic_first = ipaddress.ip_address(router_ip) + start
        dynamic_last = dynamic_first + limit
        return dynamic_first <= ipaddress.ip_address(ip) <= dynamic_last

    @staticmethod
    def in_network(ip: str, ip_root: str, netmask: str) -> bool:
        network = ipaddress.ip_network(f"{ip_root}/{netmask}", strict=False)
        return ipaddress.ip_address(ip) in network

    @logger_wrapper(logger)
    def set_dhcp_client(self, ip: str, mac: str, hostname: str) -> dict:
        """ Mocks updating configuration of a single dhcp client
        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: {"result": True} if update passes {"result": False, "reason": "..."} otherwise
        """
        if MockLanHandler.mode != "managed" or not MockLanHandler.mode_managed["dhcp"]["enabled"]:
            return {"result": False, "reason": "disabled"}

        # convert to upper case
        mac = mac.upper()

        if ip != "ignore":

            # not match into network
            if not MockLanHandler.in_network(
                ip, MockLanHandler.mode_managed["router_ip"], MockLanHandler.mode_managed["netmask"]
            ):
                return {"result": False, "reason": "out-of-network"}

            # in dynamic range
            if MockLanHandler.in_range(
                ip,
                MockLanHandler.mode_managed["router_ip"],
                MockLanHandler.mode_managed["dhcp"]["start"],
                MockLanHandler.mode_managed["dhcp"]["limit"],
            ):
                return {"result": False, "reason": "in-dynamic"}

        # modify or add ip
        mac_to_client_map = {e["mac"]: e for e in MockLanHandler.mode_managed["dhcp"]["clients"]}
        record = mac_to_client_map.get(
            mac, {"ip": "", "mac": "", "expires": 0, "active": False, "hostname": ""}
        )
        record["ip"] = ip
        record["mac"] = mac
        record["hostname"] = hostname

        # add new record if not present
        if mac not in mac_to_client_map:
            MockLanHandler.mode_managed["dhcp"]["clients"].append(record)

        return {"result": True}
