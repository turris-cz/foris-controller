#
# foris-controller
# Copyright (C) 2020-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from enum import Enum
import logging

from foris_controller.exceptions import GenericError, UciException
from foris_controller.utils import parse_to_list, unwrap_list
from foris_controller_backends.cmdline import AsyncCommand, BaseCmdLine
from foris_controller_backends.files import BaseFile
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.networks import NetworksCmd, NetworksUci
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    parse_bool,
    section_exists,
    store_bool,
)

logger = logging.getLogger(__name__)


class WanUci:
    _LNAME = "wan_limit_turris"

    def get_settings(self):
        with UciBackend() as backend:
            network_data = backend.read("network")
            sqm_data = backend.read("sqm")
            try:
                wireless_data = backend.read("wireless")
            except UciException:
                wireless_data = {}

        # WAN
        wan_settings = {}
        wan_settings["wan_type"] = get_option_named(network_data, "network", "wan", "proto")
        if wan_settings["wan_type"] == "dhcp":
            hostname = get_option_named(network_data, "network", "wan", "hostname", "")
            wan_settings["wan_dhcp"] = {"hostname": hostname} if hostname else {}
        elif wan_settings["wan_type"] == "static":
            wan_settings["wan_static"] = {
                "ip": get_option_named(network_data, "network", "wan", "ipaddr"),
                "netmask": get_option_named(network_data, "network", "wan", "netmask"),
                "gateway": get_option_named(network_data, "network", "wan", "gateway"),
            }
            dns = get_option_named(network_data, "network", "wan", "dns", [])
            dns = dns if isinstance(dns, (list, tuple)) else [e for e in dns.split(" ") if e]
            dns = reversed(dns)  # dns with higher priority should be added last
            wan_settings["wan_static"].update(zip(("dns1", "dns2"), dns))
        elif wan_settings["wan_type"] == "pppoe":
            wan_settings["wan_pppoe"] = {
                "username": get_option_named(network_data, "network", "wan", "username", ""),
                "password": get_option_named(network_data, "network", "wan", "password", ""),
            }

        # WAN6
        wan6_settings = {}
        wan6_settings["wan6_type"] = get_option_named(
            network_data, "network", "wan6", "proto", "dhcpv6"
        )
        if wan6_settings["wan6_type"] == "static":
            wan6_settings["wan6_static"] = {
                "ip": get_option_named(network_data, "network", "wan6", "ip6addr", ""),
                "network": unwrap_list(get_option_named(network_data, "network", "wan6", "ip6prefix", "")),
                "gateway": get_option_named(network_data, "network", "wan6", "ip6gw", ""),
            }
            dns = get_option_named(network_data, "network", "wan6", "dns", [])
            dns = dns if isinstance(dns, (list, tuple)) else [e for e in dns.split(" ") if e]
            dns = reversed(dns)  # dns with higher priority should be last
            wan6_settings["wan6_static"].update(zip(("dns1", "dns2"), dns))
        elif wan6_settings["wan6_type"] == "dhcpv6":
            wan6_settings["wan6_dhcpv6"] = {
                "duid": get_option_named(network_data, "network", "wan6", "clientid", "")
            }
        elif wan6_settings["wan6_type"] == "6to4":
            wan6_settings["wan6_6to4"] = {
                "ipv4_address": get_option_named(network_data, "network", "wan6", "ipaddr", "")
            }
        elif wan6_settings["wan6_type"] == "6in4":
            wan6_settings["wan6_6in4"] = {
                "ipv6_prefix": unwrap_list(get_option_named(network_data, "network", "wan6", "ip6prefix", "")),
                "mtu": int(get_option_named(network_data, "network", "wan6", "mtu", "1480")),
                "server_ipv4": get_option_named(network_data, "network", "wan6", "peeraddr", ""),
                "ipv6_address": unwrap_list(get_option_named(network_data, "network", "wan6", "ip6addr", ""))
            }
            tunnel_id = get_option_named(network_data, "network", "wan6", "tunnelid", "")
            username = get_option_named(network_data, "network", "wan6", "username", "")
            password = get_option_named(network_data, "network", "wan6", "password", "")
            wan6_settings["wan6_6in4"]["dynamic_ipv4"] = {}
            if tunnel_id and username and password:
                wan6_settings["wan6_6in4"]["dynamic_ipv4"]["enabled"] = True
                wan6_settings["wan6_6in4"]["dynamic_ipv4"]["tunnel_id"] = tunnel_id
                wan6_settings["wan6_6in4"]["dynamic_ipv4"]["username"] = username
                wan6_settings["wan6_6in4"]["dynamic_ipv4"]["password_or_key"] = password
            else:
                wan6_settings["wan6_6in4"]["dynamic_ipv4"]["enabled"] = False

        custom_mac = WanUci._fetch_mac_address(network_data)

        networks = NetworksUci()
        networks_settings = networks.get_settings()
        wan = networks_settings["networks"]["wan"]

        mac_address = ""
        try:
            mac_address = wan[0]["macaddr"]
        except IndexError:
            logger.error("Device cannot detect wan interface.")

        mac_settings = {"custom_mac_enabled": False, "mac_address": mac_address}

        if custom_mac:
            mac_settings.update({"custom_mac_enabled": True, "custom_mac": custom_mac})

        # Try to get VLAN ID of wan device.
        # Note: use this little workaround to get wan interface device without the need of changing turrishw
        # to be able to detect devices with VLAN ID set (e.g. eth0.100).
        # Fetch the device directly from uci config - for now.
        wan_device = get_option_named(network_data, "network", "wan", "device", "")

        # TODO: Let the `turrishw` fetch the wan device (regardless of presence of VLAN ID) and use that.

        vlan_settings = {}
        vlan_id = None
        if "." in wan_device:
            vlan_id = wan_device.rsplit(".")[-1]

        if vlan_id is not None:
            vlan_settings["enabled"] = True
            vlan_settings["vlan_id"] = int(vlan_id)
        else:
            vlan_settings["enabled"] = False

        qos = {}
        qos["enabled"] = parse_bool(
            get_option_named(sqm_data, "sqm", WanUci._LNAME, "enabled", "0")
        )
        qos["upload"] = int(
            get_option_named(sqm_data, "sqm", WanUci._LNAME, "upload", 1024)
        )
        qos["download"] = int(
            get_option_named(sqm_data, "sqm", WanUci._LNAME, "download", 1024)
        )
        return {
            "wan_settings": wan_settings,
            "wan6_settings": wan6_settings,
            "mac_settings": mac_settings,
            "interface_count": NetworksUci.get_interface_count(network_data, wireless_data, "wan"),
            "interface_up_count": NetworksUci.get_interface_count(
                network_data, wireless_data, "wan", True
            ),
            "qos": qos,
            "vlan_settings": vlan_settings,
        }

    @staticmethod
    def _fetch_mac_address(network_data: dict) -> str:
        """Backward compatible reading of both OpenWrt 19.07 and 21.02 config style.

        Prefer the new way (21.02) and try that first.
        """
        if section_exists(network_data, "network", "dev_wan"):
            return get_option_named(network_data, "network", "dev_wan", "macaddr", "")

        # try to fallback on `interface 'wan'`, i.e. OpenWrt 19.07 style config syntax
        return get_option_named(network_data, "network", "wan", "macaddr", "")

    def update_settings(self, wan_settings, wan6_settings, mac_settings, qos=None, vlan_settings=None):
        with UciBackend() as backend:

            # WAN
            wan_type = wan_settings["wan_type"]
            backend.add_section("network", "interface", "wan")
            backend.set_option("network", "wan", "proto", wan_type)
            if wan_type == "dhcp":
                if "hostname" in wan_settings["wan_dhcp"]:
                    backend.set_option(
                        "network", "wan", "hostname", wan_settings["wan_dhcp"]["hostname"]
                    )
                else:
                    backend.del_option("network", "wan", "hostname", fail_on_error=False)

            elif wan_type == "static":
                backend.set_option("network", "wan", "ipaddr", wan_settings["wan_static"]["ip"])
                backend.set_option(
                    "network", "wan", "netmask", wan_settings["wan_static"]["netmask"]
                )
                backend.set_option(
                    "network", "wan", "gateway", wan_settings["wan_static"]["gateway"]
                )
                dns = [
                    wan_settings["wan_static"][name]
                    for name in ("dns2", "dns1")
                    if name in wan_settings["wan_static"]
                ]  # dns with higher priority should be added last
                backend.replace_list("network", "wan", "dns", dns)

            elif wan_type == "pppoe":
                backend.set_option(
                    "network", "wan", "username", wan_settings["wan_pppoe"]["username"]
                )
                backend.set_option(
                    "network", "wan", "password", wan_settings["wan_pppoe"]["password"]
                )

            # WAN6
            wan6_type = wan6_settings["wan6_type"]
            backend.add_section("network", "interface", "wan6")
            backend.set_option("network", "wan6", "device", "@wan")
            backend.set_option("network", "wan6", "proto", wan6_type)

            backend.del_option("network", "wan6", "ip6prefix", fail_on_error=False)

            # disable rule for 6in4 + cleanup
            if not wan6_type == "6in4":
                for item in ["tunnelid", "username", "password", "peeraddr", "mtu", "ip6addr"]:
                    backend.del_option("network", "wan6", item, fail_on_error=False)
                backend.add_section("firewall", "rule", "turris_wan_6in4_rule")
                backend.set_option("firewall", "turris_wan_6in4_rule", "enabled", store_bool(False))

            # disable rule for 6to4 + cleanup
            if not wan6_type == "6to4":
                backend.add_section("firewall", "rule", "turris_wan_6to4_rule")
                backend.set_option("firewall", "turris_wan_6to4_rule", "enabled", store_bool(False))

            if wan6_type == "static":
                backend.set_option("network", "wan6", "ip6addr", wan6_settings["wan6_static"]["ip"])
                backend.add_to_list(
                    "network", "wan6", "ip6prefix", parse_to_list(wan6_settings["wan6_static"]["network"])
                )
                backend.set_option(
                    "network", "wan6", "ip6gw", wan6_settings["wan6_static"]["gateway"]
                )
                dns = [
                    wan6_settings["wan6_static"][name]
                    for name in ("dns2", "dns1")
                    if name in wan6_settings["wan6_static"]
                ]  # dns with higher priority should be added last
                backend.replace_list("network", "wan6", "dns", dns)
            elif wan6_type == "dhcpv6":
                new_duid = wan6_settings["wan6_dhcpv6"]["duid"]
                if new_duid:
                    backend.set_option("network", "wan6", "clientid", new_duid)
                else:
                    backend.del_option("network", "wan6", "clientid", fail_on_error=False)
            elif wan6_type == "6to4":
                mapped_ipv4 = wan6_settings["wan6_6to4"]["ipv4_address"]
                backend.set_option("network", "lan", "ip6assign", "60")
                if mapped_ipv4:
                    backend.set_option("network", "wan6", "ipaddr", mapped_ipv4)
                else:
                    backend.del_option("network", "wan6", "ipaddr", fail_on_error=False)

                backend.add_section("firewall", "rule", "turris_wan_6to4_rule")
                backend.set_option("firewall", "turris_wan_6to4_rule", "enabled", store_bool(True))
                backend.set_option("firewall", "turris_wan_6to4_rule", "proto", "ipv6")
                backend.set_option("firewall", "turris_wan_6to4_rule", "src_ip", "192.88.99.1")
                backend.set_option("firewall", "turris_wan_6to4_rule", "target", "ACCEPT")
                backend.set_option("firewall", "turris_wan_6to4_rule", "src", "wan")

            elif wan6_type == "6in4":
                backend.set_option("network", "wan6", "mtu", wan6_settings["wan6_6in4"]["mtu"])
                backend.set_option(
                    "network", "wan6", "peeraddr", wan6_settings["wan6_6in4"]["server_ipv4"]
                )
                backend.replace_list("network", "wan6", "ip6addr", parse_to_list(
                    wan6_settings["wan6_6in4"].get("ipv6_address", "")
                ))

                if wan6_settings["wan6_6in4"]["ipv6_prefix"]:
                    backend.add_to_list(
                        "network", "wan6", "ip6prefix", parse_to_list(wan6_settings["wan6_6in4"]["ipv6_prefix"])
                    )
                else:
                    backend.del_option("network", "wan6", "ip6prefix", fail_on_error=False)

                if wan6_settings["wan6_6in4"]["dynamic_ipv4"]["enabled"]:
                    backend.set_option(
                        "network",
                        "wan6",
                        "tunnelid",
                        wan6_settings["wan6_6in4"]["dynamic_ipv4"]["tunnel_id"],
                    )
                    backend.set_option(
                        "network",
                        "wan6",
                        "username",
                        wan6_settings["wan6_6in4"]["dynamic_ipv4"]["username"],
                    )
                    backend.set_option(
                        "network",
                        "wan6",
                        "password",
                        wan6_settings["wan6_6in4"]["dynamic_ipv4"]["password_or_key"],
                    )
                else:
                    for item in ["tunnelid", "username", "password"]:
                        backend.del_option("network", "wan6", item, fail_on_error=False)

                backend.add_section("firewall", "rule", "turris_wan_6in4_rule")
                backend.set_option("firewall", "turris_wan_6in4_rule", "enabled", store_bool(True))
                backend.set_option("firewall", "turris_wan_6in4_rule", "family", "ipv4")
                backend.set_option("firewall", "turris_wan_6in4_rule", "proto", "41")
                backend.set_option("firewall", "turris_wan_6in4_rule", "target", "ACCEPT")
                backend.set_option("firewall", "turris_wan_6in4_rule", "src", "wan")
                backend.set_option(
                    "firewall",
                    "turris_wan_6in4_rule",
                    "src_ip",
                    wan6_settings["wan6_6in4"]["server_ipv4"],
                )
            else:
                # remove extra fields (otherwise it will mess with other settings)
                for field in ["ip6prefix", "ip6addr", "ip6gw"]:
                    backend.del_option("network", "wan6", field, fail_on_error=False)

            # disable/enable ipv6 on wan interface
            if wan6_type == "none":
                backend.set_option("network", "wan", "ipv6", store_bool(False))
                backend.set_option("resolver", "common", "net_ipv6", store_bool(False))
            else:
                backend.set_option("network", "wan", "ipv6", store_bool(True))
                backend.set_option("resolver", "common", "net_ipv6", store_bool(True))

            # create new `device dev_wan` section in case there is none and wasn't created through migration
            network_data = backend.read("network")
            wan_device = get_option_named(network_data, "network", "wan", "device")
            backend.add_section("network", "device", "dev_wan")
            backend.set_option("network", "dev_wan", "name", wan_device)

            # MAC
            if mac_settings["custom_mac_enabled"]:
                backend.set_option("network", "dev_wan", "macaddr", mac_settings["custom_mac"])
            else:
                backend.del_option("network", "dev_wan", "macaddr", fail_on_error=False)

            # handle VLAN ID
            if vlan_settings:
                WanUci._update_vlan_id(backend, wan_device, vlan_settings)

            if qos:
                try:
                    if qos.get("enabled"):
                        backend.add_section("sqm", "queue", WanUci._LNAME)
                        backend.set_option("sqm", WanUci._LNAME, "interface", wan_device)
                        backend.set_option("sqm", WanUci._LNAME, "download", qos["download"])
                        backend.set_option("sqm", WanUci._LNAME, "upload", qos["upload"])
                        backend.set_option("sqm", WanUci._LNAME, "script", "piece_of_cake.qos")
                    backend.set_option("sqm", WanUci._LNAME, "enabled", store_bool(qos["enabled"]))
                except UciException:
                    logger.error("Unable to create sqm record for WAN")
        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands

            WebUciCommands.update_passed("wan")
        except UciException:
            pass

        MaintainCommands().restart_network()

        return True

    @staticmethod
    def _update_vlan_id(backend: UciBackend, wan_device: str, vlan_settings: dict) -> None:
        """Update VLAN ID of WAN interface."""
        # Strip the vlan id from device and reuse only the base device
        # E.g.: eth0.100 => eth0
        base_wan_device = wan_device.split(".", maxsplit=1)[0]

        try:
            if vlan_settings.get("enabled"):
                wan_dev_with_vlan_id = f"{base_wan_device}.{vlan_settings['vlan_id']}"
                backend.set_option("network", "wan", "device", wan_dev_with_vlan_id)
                backend.set_option("network", "dev_wan", "name", wan_dev_with_vlan_id)
            else:
                # clear the vlan id
                backend.set_option("network", "wan", "device", base_wan_device)
                backend.set_option("network", "dev_wan", "name", base_wan_device)
        except UciException:
            logger.error("Failed to change VLAN ID for WAN device '%s'.", base_wan_device)

    def update_unconfigured_wan_to_default(self) -> bool:
        """
        Updates wan if it was not configured to get IP address via DHCP

        :returns: True if wan configuration was changed
        """
        with UciBackend() as backend:
            network_data = backend.read("network")
            wan_proto = get_option_named(network_data, "network", "wan", "proto")
            wan_device = get_option_named(network_data, "network", "wan", "device", "")

        if wan_proto == "none" and wan_device:
            self.update_settings(
                wan_settings={"wan_type": "dhcp", "wan_dhcp": {}},
                wan6_settings={"wan6_type": "dhcpv6", "wan6_dhcpv6": {"duid": ""}},
                mac_settings={"custom_mac_enabled": False},
            )
            return True
        return False


class WanTestCommands(AsyncCommand):
    class TestResult(str, Enum):
        UNKNOWN = "UNKNOWN"
        FAILED = "FAILED"
        OK = "OK"

        @classmethod
        def _missing_(cls, value):
            return cls.FAILED

    FIELDS = ("ipv6", "ipv6_gateway", "ipv4", "ipv4_gateway", "dns", "dnssec")
    TEST_KIND_MAP = {
        "ipv4": ["IP4GATE", "IP4"],
        "ipv6": ["IP6GATE", "IP6"],
        "dns": ["IP4GATE", "IP4", "IP6GATE", "IP6", "DNS", "DNSSEC"],  # IP has to be working
    }

    def connection_test_status(self, process_id):
        """ Get the status of some connection test
        :param process_id: test process identifier
        :type process_id: str
        :returns: data about test process
        :rtype: dict
        """

        with self.lock.readlock:
            if process_id not in self.processes:
                return {"status": "not_found"}
            process_data = self.processes[process_id]

        exited = process_data.get_exited()

        data = {e: False for e in WanTestCommands.FIELDS} if exited else {}
        for record in process_data.read_all_data():
            for option, res in record["data"].items():
                data[option] = res or data.get(option, False)

        return {"status": "finished" if process_data.get_exited() else "running", "data": data}

    def connection_test_trigger(
        self, test_kinds, notify_function, exit_notify_function, reset_notify_function
    ):
        """ Executes connection test in asyncronous mode

        This means that we don't wait for the test results. Only a test id is returned.
        This id can be used in other queries.

        :param test_kinds: which kinds of tests should be run (ipv4, ipv6, dns)
        :type test_kinds: array of str
        :param notify_function: function which is used to send notifications back to client
        :type notify_function: callable
        :param exit_notify_function: function which is used to send notifications back to client
                                     when test exits
        :type exit_notify_function: callable
        :param reset_notify_function: function which resets notification connection
        :type reset_notify_function: callable
        :returns: test id
        :rtype: str

        """
        logger.debug("Starting connection test.")

        # generate a notification handler
        def handler_gen(regex, option):
            def handler(matched, process_data):
                status = WanTestCommands.TestResult(matched.group(1))
                res = {"test_id": process_data.id, "data": {option: status}}
                process_data.append_data(res)
                notify_function(res)

            return regex, handler

        # handler which will be called when the test exits
        def handler_exit(exit_data):
            processed_data = exit_data.read_all_data()

            data = {e: "UNKNOWN" for e in WanTestCommands.FIELDS}

            for record in processed_data:
                for option, res in record["data"].items():
                    data[option] = WanTestCommands.TestResult(res)

            exit_notify_function(
                {"test_id": exit_data.id, "data": data, "passed": exit_data.get_retval() == 0}
            )
            logger.debug("Connection test finished: (retval=%d)" % exit_data.get_retval())

        # prepare test kinds
        cmd_line_kinds = []
        for kind in test_kinds:
            cmd_line_kinds.extend(self.TEST_KIND_MAP[kind])

        process_id = self.start_process(
            ["/sbin/check_connection"] + list(set(cmd_line_kinds)),
            [
                handler_gen(r"^IPv6: (\w+)", "ipv6"),
                handler_gen(r"^IPv6 Gateway: (\w+)", "ipv6_gateway"),
                handler_gen(r"^IPv4: (\w+)", "ipv4"),
                handler_gen(r"^IPv4 Gateway: (\w+)", "ipv4_gateway"),
                handler_gen(r"DNS: (\w+)", "dns"),
                handler_gen(r"DNSSEC: (\w+)", "dnssec"),
            ],
            handler_exit,
            reset_notify_function,
        )

        logger.debug("Connection test started '%s'." % process_id)
        return process_id


class WanStatusCommands(BaseCmdLine, BaseFile):
    DUID_STATUS_FILE = "/var/run/odhcp6c-duid"

    def get_status(self):
        """ network info enriched by DUID """
        network_info = NetworksCmd().get_network_info("wan")
        if not network_info:
            logger.error("Failed to obtain network info")
            raise GenericError("Failed to obtain network info")

        # try to figure out duid (best effort)
        device = network_info.get("device", None)
        network_info["duid"] = ""
        if device:
            duid_path = "%s.%s" % (WanStatusCommands.DUID_STATUS_FILE, device)
            try:
                network_info["duid"] = self._file_content(duid_path).strip()
            except (OSError, IOError):
                pass

        return network_info
