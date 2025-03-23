#
# foris-controller
# Copyright (C) 2018-2019, 2021-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.exceptions import UciException, UciRecordNotFound
from foris_controller_backends.lan import LanFiles, LanUci
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.services import OpenwrtServices
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    parse_bool,
    store_bool,
)

logger = logging.getLogger(__name__)


class GuestUci:
    DEFAULT_GUEST_ADDRESS = "10.111.222.1"
    DEFAULT_GUEST_NETMASK = "255.255.255.0"
    DEFAULT_GUEST_DHCP_LEASE_TIME = 60 * 60

    @staticmethod
    def get_guest_enabled(network_data, firewall_data, dhcp_data):
        def test(data, config, section, value, default=False):
            try:
                return parse_bool(get_option_named(data, config, section, value))
            except UciRecordNotFound:
                return default

        return (
            test(network_data, "network", "guest_turris", "enabled")
            and test(firewall_data, "firewall", "guest_turris", "enabled")
            and test(firewall_data, "firewall", "guest_turris_forward_wan", "enabled")
            and test(firewall_data, "firewall", "guest_turris_dhcp_rule", "enabled")
            and test(firewall_data, "firewall", "guest_turris_dns_rule", "enabled")
        )

    @staticmethod
    def get_guest_network_settings(network_data, firewall_data, dhcp_data, sqm_data, wireless_data):
        guest = {}
        guest["enabled"] = GuestUci.get_guest_enabled(network_data, firewall_data, dhcp_data)

        guest["ip"] = get_option_named(
            network_data, "network", "guest_turris", "ipaddr", GuestUci.DEFAULT_GUEST_ADDRESS
        )
        guest["netmask"] = get_option_named(
            network_data, "network", "guest_turris", "netmask", GuestUci.DEFAULT_GUEST_NETMASK
        )

        guest["qos"] = {}
        guest["qos"]["enabled"] = parse_bool(
            get_option_named(sqm_data, "sqm", "guest_limit_turris", "enabled", "0")
        )
        # upload is actually download limit nad vice versa
        guest["qos"]["upload"] = int(
            get_option_named(sqm_data, "sqm", "guest_limit_turris", "download", 1024)
        )
        guest["qos"]["download"] = int(
            get_option_named(sqm_data, "sqm", "guest_limit_turris", "upload", 1024)
        )

        guest["dhcp"] = {}
        guest["dhcp"]["enabled"] = not parse_bool(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "ignore", "0")
        )
        guest["dhcp"]["start"] = int(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "start", LanUci.DEFAULT_DHCP_START)
        )
        guest["dhcp"]["limit"] = int(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "limit", LanUci.DEFAULT_DHCP_LIMIT)
        )
        guest["dhcp"]["lease_time"] = LanUci._normalize_lease(
            get_option_named(
                dhcp_data,
                "dhcp",
                "guest_turris",
                "leasetime",
                GuestUci.DEFAULT_GUEST_DHCP_LEASE_TIME,
            )
        )
        guest["dhcp"]["clients"] = (
            LanFiles().get_dhcp_clients(guest["ip"], guest["netmask"])
            if guest["dhcp"]["enabled"]
            else []
        )

        from foris_controller_backends.networks import NetworksUci

        guest["interface_count"] = NetworksUci.get_interface_count(
            network_data, wireless_data, "guest"
        )
        guest["interface_up_count"] = NetworksUci.get_interface_count(
            network_data, wireless_data, "guest", True
        )

        return guest

    @staticmethod
    def set_guest_network(backend, guest_network):
        """
        :returns: None or "enable" or "disable" to set sqm service
        :rtype: NoneType or str
        """

        enabled = store_bool(guest_network["enabled"])
        # On OpenWrt >=21.02 firewall zone name is limited to max 11 chars
        guest_zone_name = "tr_guest"
        guest_net_bridge_name = "br-guest-turris"

        # update network interface list
        backend.add_section("network", "interface", "guest_turris")
        backend.set_option("network", "guest_turris", "enabled", enabled)
        backend.set_option("network", "guest_turris", "proto", "static")
        backend.add_section("network", "device", "br_guest_turris")
        backend.set_option("network", "br_guest_turris", "name", guest_net_bridge_name)
        backend.set_option("network", "br_guest_turris", "type", "bridge")
        backend.set_option("network", "guest_turris", "device", guest_net_bridge_name)
        if guest_network["enabled"]:
            backend.set_option("network", "guest_turris", "ipaddr", guest_network["ip"])
            backend.set_option("network", "guest_turris", "netmask", guest_network["netmask"])
        backend.set_option("network", "br_guest_turris", "bridge_empty", store_bool(True))
        backend.set_option("network", "guest_turris", "ip6assign", "64")

        # update firewall config
        backend.add_section("firewall", "zone", "guest_turris")
        backend.set_option("firewall", "guest_turris", "enabled", enabled)
        backend.set_option("firewall", "guest_turris", "name", guest_zone_name)
        backend.replace_list("firewall", "guest_turris", "network", ["guest_turris"])
        backend.set_option("firewall", "guest_turris", "input", "REJECT")
        backend.set_option("firewall", "guest_turris", "forward", "REJECT")
        backend.set_option("firewall", "guest_turris", "output", "ACCEPT")

        backend.add_section("firewall", "forwarding", "guest_turris_forward_wan")
        backend.set_option("firewall", "guest_turris_forward_wan", "enabled", enabled)
        backend.set_option("firewall", "guest_turris_forward_wan", "name", "guest to wan forward")
        backend.set_option("firewall", "guest_turris_forward_wan", "src", guest_zone_name)
        backend.set_option("firewall", "guest_turris_forward_wan", "dest", "wan")

        backend.add_section("firewall", "rule", "guest_turris_dns_rule")
        backend.set_option("firewall", "guest_turris_dns_rule", "enabled", enabled)
        backend.set_option("firewall", "guest_turris_dns_rule", "name", "guest dns rule")
        backend.set_option("firewall", "guest_turris_dns_rule", "src", guest_zone_name)
        backend.replace_list("firewall", "guest_turris_dns_rule", "proto", ["TCP", "UDP"])
        backend.set_option("firewall", "guest_turris_dns_rule", "dest_port", "53")
        backend.set_option("firewall", "guest_turris_dns_rule", "target", "ACCEPT")

        backend.add_section("firewall", "rule", "guest_turris_dhcp_rule")
        backend.set_option("firewall", "guest_turris_dhcp_rule", "enabled", enabled)
        backend.set_option("firewall", "guest_turris_dhcp_rule", "name", "guest dhcp rule")
        backend.set_option("firewall", "guest_turris_dhcp_rule", "src", guest_zone_name)
        backend.set_option("firewall", "guest_turris_dhcp_rule", "proto", "udp")
        backend.set_option("firewall", "guest_turris_dhcp_rule", "src_port", "68")
        backend.set_option("firewall", "guest_turris_dhcp_rule", "dest_port", "67")
        backend.set_option("firewall", "guest_turris_dhcp_rule", "target", "ACCEPT")

        backend.add_section("firewall", "rule", "guest_turris_Allow_DHCPv6")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "src", guest_zone_name)
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "proto", "udp")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "src_ip", "fe80::/10")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "src_port", "546")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "dest_ip", "ff02::1:2")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "dest_port", "547")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "family", "ipv6")
        backend.set_option("firewall", "guest_turris_Allow_DHCPv6", "target", "ACCEPT")

        backend.add_section("firewall", "rule", "guest_turris_Allow_MLD")
        backend.set_option("firewall", "guest_turris_Allow_MLD", "src", guest_zone_name)
        backend.set_option("firewall", "guest_turris_Allow_MLD", "proto", "icmp")
        backend.set_option("firewall", "guest_turris_Allow_MLD", "src_ip", "fe80::/10")
        backend.set_option("firewall", "guest_turris_Allow_MLD", "family", "ipv6")
        backend.set_option("firewall", "guest_turris_Allow_MLD", "target", "ACCEPT")
        backend.replace_list("firewall", "guest_turris_Allow_MLD", "icmp_type", ['130/0', '131/0', '132/0', '143/0'])

        backend.add_section("firewall", "rule", "guest_turris_Allow_ICMPv6_Input")
        backend.set_option("firewall", "guest_turris_Allow_ICMPv6_Input", "src", guest_zone_name)
        backend.set_option("firewall", "guest_turris_Allow_ICMPv6_Input", "proto", "icmp")
        backend.set_option("firewall", "guest_turris_Allow_ICMPv6_Input", "limit", "1000/sec")
        backend.set_option("firewall", "guest_turris_Allow_ICMPv6_Input", "family", "ipv6")
        backend.set_option("firewall", "guest_turris_Allow_ICMPv6_Input", "target", "ACCEPT")
        backend.replace_list("firewall", "guest_turris_Allow_ICMPv6_Input", "icmp_type", [
            'echo-request', 'echo-reply', 'destination-unreachable', 'packet-too-big', 'time-exceeded', 'bad-header',
            'unknown-header-type', 'router-solicitation', 'neighbour-solicitation', 'router-advertisement', 'neighbour-advertisement'
        ]
        )
        # update dhcp config
        backend.add_section("dhcp", "dhcp", "guest_turris")
        backend.set_option("dhcp", "guest_turris", "interface", "guest_turris")
        if guest_network["enabled"]:
            dhcp_ignored = store_bool(not guest_network["dhcp"]["enabled"])
            backend.set_option("dhcp", "guest_turris", "ignore", dhcp_ignored)
            if guest_network["dhcp"]["enabled"]:
                backend.set_option("dhcp", "guest_turris", "start", guest_network["dhcp"]["start"])
                backend.set_option("dhcp", "guest_turris", "limit", guest_network["dhcp"]["limit"])
                backend.set_option(
                    "dhcp",
                    "guest_turris",
                    "leasetime",
                    "infinite"
                    if guest_network["dhcp"]["lease_time"] == 0
                    else guest_network["dhcp"]["lease_time"],
                )
                # dhcpv6
                backend.set_option("dhcp", "guest_turris", "dhcpv6", "server")
                backend.set_option("dhcp", "guest_turris", "ra", "server")
            if guest_network.get("ip", False):
                backend.replace_list(
                    "dhcp", "guest_turris", "dhcp_option", ["6,%s" % guest_network["ip"]]
                )

        # qos part (replaces whole sqm section)
        try:
            # cleanup section
            backend.del_section("sqm", "guest_limit_turris")
        except UciException:
            pass  # section might not exist

        def set_if_exists(backend, config, section, option, data, key):
            if key in data:
                backend.set_option(config, section, option, data[key])

        try:
            if (
                guest_network["enabled"]
                and "qos" in guest_network
                and guest_network["qos"]["enabled"]
            ):
                backend.add_section("sqm", "queue", "guest_limit_turris")
                backend.set_option("sqm", "guest_limit_turris", "enabled", enabled)
                backend.set_option("sqm", "guest_limit_turris", "interface", guest_net_bridge_name)
                backend.set_option("sqm", "guest_limit_turris", "qdisc", "fq_codel")
                backend.set_option("sqm", "guest_limit_turris", "script", "simple.qos")
                backend.set_option("sqm", "guest_limit_turris", "link_layer", "none")
                backend.set_option("sqm", "guest_limit_turris", "verbosity", "5")
                backend.set_option("sqm", "guest_limit_turris", "debug_logging", "1")
                # We need to swap dowload and upload
                # "upload" means upload to the guest network
                # "download" means dowload from the guest network
                set_if_exists(
                    backend, "sqm", "guest_limit_turris", "upload", guest_network["qos"], "download"
                )
                set_if_exists(
                    backend, "sqm", "guest_limit_turris", "download", guest_network["qos"], "upload"
                )
                return "enable"
            else:
                return "disable"
        except UciException:
            pass  # sqm might not be installed -> set at least the rest and don't fail

    @staticmethod
    def enable_guest_network(backend):
        """ Enables guest network. If guest network is not preset it is created
        """

        network_data = backend.read("network")
        dhcp_data = backend.read("dhcp")

        dhcp_enabled = not parse_bool(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "ignore", "0")
        )
        dhcp_start = int(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "start", LanUci.DEFAULT_DHCP_START)
        )
        dhcp_limit = int(
            get_option_named(dhcp_data, "dhcp", "guest_turris", "limit", LanUci.DEFAULT_DHCP_LIMIT)
        )
        router_ip = get_option_named(
            network_data, "network", "guest_turris", "ipaddr", GuestUci.DEFAULT_GUEST_ADDRESS
        )
        netmask = get_option_named(
            network_data, "network", "guest_turris", "netmask", GuestUci.DEFAULT_GUEST_NETMASK
        )
        dhcp_lease_time = LanUci._normalize_lease(
            get_option_named(
                dhcp_data,
                "dhcp",
                "guest_turris",
                "leasetime",
                GuestUci.DEFAULT_GUEST_DHCP_LEASE_TIME,
            )
        )

        try:
            get_option_named(network_data, "network", "guest_turris", "proto", None)
            # guest network present
            GuestUci.set_guest_network(
                backend,
                {
                    "enabled": True,
                    "ip": router_ip,
                    "netmask": netmask,
                    "dhcp": {
                        "enabled": dhcp_enabled,
                        "start": dhcp_start,
                        "limit": dhcp_limit,
                        "lease_time": dhcp_lease_time,
                    },
                },
            )
        except (UciException, UciRecordNotFound):
            # guest network missing - try to create initial configuration
            GuestUci.set_guest_network(
                backend,
                {
                    "enabled": True,
                    "ip": router_ip,
                    "netmask": netmask,
                    "dhcp": {
                        "enabled": dhcp_enabled,
                        "start": dhcp_start,
                        "limit": dhcp_limit,
                        "lease_time": dhcp_lease_time,
                    },
                },
            )

    def get_settings(self):

        with UciBackend() as backend:
            firewall = backend.read("firewall")
            network = backend.read("network")
            sqm = backend.read("sqm")
            dhcp = backend.read("dhcp")
            try:
                wireless = backend.read("wireless")
            except UciException:
                wireless = {}
        return GuestUci.get_guest_network_settings(network, firewall, dhcp, sqm, wireless)

    def update_settings(self, **new_settings):
        with UciBackend() as backend:
            from foris_controller_backends.wifi import WifiUci

            # disable guest wifi when guest network is not enabled
            if not new_settings["enabled"]:
                WifiUci.set_guest_wifi_disabled(backend)
            sqm_cmd = GuestUci.set_guest_network(backend, new_settings)

        with OpenwrtServices() as services:
            # try to restart sqm (best effort) in might not be installed yet
            # note that sqm will be restarted when the network is restarted
            if sqm_cmd == "enable":
                services.enable("sqm", fail_on_error=False)
            elif sqm_cmd == "disable":
                services.disable("sqm", fail_on_error=False)

        MaintainCommands().restart_network()
        return True
