#
# foris-controller
# Copyright (C) 2019-2024 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import ipaddress
import logging
import typing

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
                    "static": False,
                },
                {
                    "ip": "192.168.2.1",
                    "mac": "99:88:77:66:55:44",
                    "expires": 1539350188,
                    "active": False,
                    "hostname": "*",
                    "static": True,
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

    qos = {'download': 1024, 'enabled': False, 'upload': 1024}

    lan_redirect = True

    forwarding = []

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

        from foris_controller_modules.networks.handlers.mock import (
            MockNetworksHandler,
        )

        result = {
            "mode": MockLanHandler.mode,
            "mode_managed": MockLanHandler.mode_managed,
            "mode_unmanaged": mode_unmanaged,
            "interface_count": len(MockNetworksHandler.networks["lan"]),
            "interface_up_count": len(
                [e for e in MockNetworksHandler.networks["lan"] if e["state"] == "up"]
            ),
            "lan_redirect": MockLanHandler.lan_redirect,
            "qos": MockLanHandler.qos
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

        if "qos" in new_settings:
            MockLanHandler.qos = new_settings["qos"]

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

    @staticmethod
    def client_exists(mac: str) -> bool:
        """Check whether MAC address is not already used"""
        for client in MockLanHandler.mode_managed["dhcp"]["clients"]:
            if client["mac"] == mac:
                return True

        return False

    @staticmethod
    def is_dhcp_managed() -> bool:
        """Check whether dhcp is managed and enabled"""
        if MockLanHandler.mode != "managed" or not MockLanHandler.mode_managed["dhcp"]["enabled"]:
            return False

        return True

    @staticmethod
    def is_hostname_unique(hostname: str) -> bool:
        """Check whether hostname is unique among DHCP hosts"""
        for client in MockLanHandler.mode_managed["dhcp"]["clients"]:
            if client["hostname"] == hostname:
                return False

        return True

    @staticmethod
    def validate_dhcp_host_ip(ip: str) -> typing.Optional[str]:
        """Validate DHCP host IP address

        Check whether it fits the target network or doesn't overlap with DHCP pool range

        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :returns: error message (disabled, out-of-network, ...) on error, None otherwise
        """
        if not MockLanHandler.is_dhcp_managed():
            return "disabled"

        if ip != "ignore":
            # does not fit into network range
            if not MockLanHandler.in_network(
                ip, MockLanHandler.mode_managed["router_ip"], MockLanHandler.mode_managed["netmask"]
            ):
                return "out-of-network"

            # ip address is already taken by another host
            for client in MockLanHandler.mode_managed["dhcp"]["clients"]:
                if client["ip"] == ip:
                    return "ip-exists"

        return None  # data looks OK

    @logger_wrapper(logger)
    def set_dhcp_client(self, ip: str, mac: str, hostname: str) -> dict:
        """ Mocks setting configuration of a single dhcp client

        It shouldn't allow overwriting existing configuration

        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: {"result": True} if update passes {"result": False, "reason": "..."} otherwise
        """
        # convert to upper case
        mac = mac.upper()
        if MockLanHandler.client_exists(mac):
            return {"result": False, "reason": "mac-exists"}

        err = MockLanHandler.validate_dhcp_host_ip(ip)
        if err:
            return {"result": False, "reason": err}

        if not MockLanHandler.is_hostname_unique(hostname):
            return {"result": False, "reason": "hostname-exists"}

        record = {
            "ip": ip,
            "mac": mac,
            "expires": 0,
            "active": False,
            "hostname": hostname,
            "static": True,
        }

        MockLanHandler.mode_managed["dhcp"]["clients"].append(record)

        return {"result": True}

    @logger_wrapper(logger)
    def update_dhcp_client(self, ip: str, old_mac: str, mac: str, hostname: str) -> dict:
        """ Mocks updating configuration of a single dhcp client

        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param old_mac: previous mac address of the client
        :param new_mac: new mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: {"result": True} if update passes {"result": False, "reason": "..."} otherwise
        """
        # convert to upper case
        old_mac = old_mac.upper()
        new_mac = mac.upper()

        if not MockLanHandler.client_exists(old_mac):
            # cannot update non-existing host
            return {"result": False, "reason": "mac-not-exists"}

        clients = MockLanHandler.mode_managed["dhcp"]["clients"]
        for cl in clients:
            if cl["mac"] == old_mac:
                current_client_config = cl

        if MockLanHandler.client_exists(new_mac) and current_client_config["mac"] != new_mac:
            return {"result": False, "reason": "mac-exists"}

        # ip is unique or the same on the same host
        err = MockLanHandler.validate_dhcp_host_ip(ip)
        if err == "ip-exists" and current_client_config["ip"] != ip:
            return {"result": False, "reason": err}
        elif err is not None:
            return {"result": False, "reason": err}

        unique_hostname = MockLanHandler.is_hostname_unique(hostname)
        if not unique_hostname and current_client_config["hostname"] != hostname:
            return {"result": False, "reason": "hostname-exists"}

        current_client_config["ip"] = ip
        current_client_config["mac"] = new_mac
        current_client_config["hostname"] = hostname

        return {"result": True}

    @logger_wrapper(logger)
    def delete_dhcp_client(self, mac: str) -> dict:
        if not MockLanHandler.is_dhcp_managed():
            return {"result": False, "reason": "disabled"}

        if not MockLanHandler.client_exists(mac):
            return {"result": False, "reason": "mac-not-exists"}

        clients = MockLanHandler.mode_managed["dhcp"]["clients"]
        MockLanHandler.mode_managed["dhcp"]["clients"] = [c for c in clients if c["mac"] != mac]
        return {"result": True}

    def update_forwardings(self, data) -> dict:
        # delete the updates also and replace those in next step
        deletes = {e["name"] for e in data.get("deletions", []) + data.get("updates", [])}
        self.forwarding = [e for e in self.forwarding if e["name"] not in deletes]

        self.forwarding.extend(data.get("updates", []))
        return {"result": True}

    def get_forwardings(self):
        return {"rules" : self.forwarding}
