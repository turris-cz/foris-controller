#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import json
import logging
import turrishw
import typing

from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    store_bool,
    parse_bool,
    get_sections_by_type,
)
from foris_controller_backends.cmdline import BaseCmdLine

from foris_controller.exceptions import UciException, UciRecordNotFound

logger = logging.getLogger(__name__)


class NetworksUci(object):
    def _prepare_network(self, data, section, ports_map):
        interfaces = get_option_named(data, "network", section, "ifname", [])
        interfaces = interfaces if isinstance(interfaces, (tuple, list)) else interfaces.split(" ")
        res = []
        for interface in interfaces:
            if interface in ports_map:
                res.append(ports_map.pop(interface))
        return res

    def _find_enabled_networks_by_ifname(self, wireless_data, ifname):
        """
        :returns: None if no valid iterface section found, or list of (network, ssid) (can be empty)
        """
        iface_sections = [
            section
            for section in get_sections_by_type(wireless_data, "wireless", "wifi-iface")
            if section["data"].get("ifname") == ifname and section["data"].get("device")
        ]
        if not iface_sections:
            return None
        # iterate over sections
        result = []
        for iface_section in iface_sections:
            # checke whether interface is enabled
            if parse_bool(iface_section["data"].get("disabled", "0")):
                continue
            # check whether the device is enabled
            device_name = iface_section["data"]["device"]
            try:
                if parse_bool(
                    get_option_named(wireless_data, "wireless", device_name, "disabled", "0")
                ):
                    continue  # device section disabled
            except UciRecordNotFound:
                continue  # section not found

            # finally add network and its ssid
            network = iface_section["data"].get("network")
            if network:
                result.append((network, iface_section["data"].get("ssid", "")))

        return result

    def _find_enabled_networks_by_macaddr(self, wireless_data, macaddr, ifname):
        """
        :returns: None if no valid device section found, or list of (network, ssid) (can be empty)
        """
        device_sections = [
            section
            for section in get_sections_by_type(wireless_data, "wireless", "wifi-device")
            if section["data"].get("macaddr") == macaddr
        ]
        if not device_sections:
            return None
        result = []
        for device_section in device_sections:
            if parse_bool(device_section["data"].get("disabled", "0")):
                continue
            interface_sections = [
                section
                for section in get_sections_by_type(wireless_data, "wireless", "wifi-iface")
                if section["data"].get("device") == device_section["name"]
                and not parse_bool(section["data"].get("disabled", "0"))
                and (
                    section["data"].get("ifname") == ifname or section["data"].get("ifname") is None
                )
            ]
            for interface_section in interface_sections:
                network = interface_section["data"].get("network", None)
                if network:
                    result.append((network, interface_section["data"].get("ssid", "")))

        return result

    @staticmethod
    def detect_interfaces():
        res = []
        res_wireless = []

        interfaces = turrishw.get_ifaces()
        logger.debug("interfaces from turrishw: %s", interfaces)
        try:
            for k, v in interfaces.items():
                v["id"] = k
                v["configurable"] = False if v["type"] == "wifi" else True
                if v["type"] == "wifi":
                    v["configurable"] = False
                    res_wireless.append(v)
                else:
                    v["configurable"] = True
                    del v["macaddr"]
                    res.append(v)
        except Exception:
            res = [], []  # when turrishw get fail -> return empty dict
        return sorted(res, key=lambda x: x["id"]), sorted(res_wireless, key=lambda x: x["id"])

    @staticmethod
    def get_interface_count(network_data, wireless_data, network_name, up_only=False):
        """ returns a count of iterfaces corresponding to the network
        """
        # convert guest name
        network_name = "guest_turris" if network_name == "guest" else network_name

        wifi_iface_count = 0
        try:
            enabled_radios = {
                e["name"]
                for e in get_sections_by_type(wireless_data, "wireless", "wifi-device")
                if not parse_bool(e["data"].get("disabled", "0"))
            }

            for section in get_sections_by_type(wireless_data, "wireless", "wifi-iface"):
                if (
                    not parse_bool(section["data"].get("disabled", "0"))
                    and section["data"].get("device", "") in enabled_radios
                    and section["data"].get("network", "") == network_name
                ):
                    wifi_iface_count += 1

        except UciRecordNotFound:
            pass

        try:
            if up_only:
                hw_interfaces = [k for k, v in turrishw.get_ifaces().items() if v["state"] == "up"]
            else:
                hw_interfaces = [e for e in turrishw.get_ifaces().keys()]
        except Exception:
            hw_interfaces = []
        config_interfaces = get_option_named(network_data, "network", network_name, "ifname", [])
        config_interfaces = (
            config_interfaces
            if isinstance(config_interfaces, (list, tuple))
            else [config_interfaces]
        )
        return len(set(hw_interfaces).intersection(config_interfaces)) + wifi_iface_count

    def get_settings(self):
        """ Get current wifi settings
        :returns: {"device": {}, "networks": [{...},]}
        "rtype: dict
        """

        ifaces, wifi_ifaces = self.detect_interfaces()
        iface_map = {e["id"]: e for e in ifaces}

        with UciBackend() as backend:
            network_data = backend.read("network")
            firewall_data = backend.read("firewall")
            try:
                wireless_data = backend.read("wireless")
            except UciException:
                wireless_data = {}  # wireless config missing

        wan_network = self._prepare_network(network_data, "wan", iface_map)
        lan_network = self._prepare_network(network_data, "lan", iface_map)
        guest_network = self._prepare_network(network_data, "guest_turris", iface_map)
        none_network = [e for e in iface_map.values()]  # reduced in _prepare_network using pop()

        for record in wifi_ifaces:
            networks_and_ssids = self._find_enabled_networks_by_ifname(wireless_data, record["id"])
            macaddr = record.pop("macaddr")
            if networks_and_ssids is None:
                networks_and_ssids = self._find_enabled_networks_by_macaddr(
                    wireless_data, macaddr, record["id"]
                )

            # always set undefined
            networks_and_ssids = [] if networks_and_ssids is None else networks_and_ssids

            for network, ssid in networks_and_ssids:
                record["ssid"] = ssid
                if network == "lan":
                    lan_network.append(record)
                elif network == "guest_turris":
                    guest_network.append(record)
                elif network == "wan":
                    wan_network.append(record)

            if len(networks_and_ssids) == 0:
                record["ssid"] = ""
                none_network.append(record)

        # parse firewall options
        ssh_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_ssh_turris_rule", "enabled", "0")
        )
        http_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_http_turris_rule", "enabled", "0")
        )
        https_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_https_turris_rule", "enabled", "0")
        )

        return {
            "device": {
                "model": SystemInfoFiles().get_model(),
                "version": SystemInfoFiles().get_os_version(),
            },
            "firewall": {
                "ssh_on_wan": ssh_on_wan,
                "http_on_wan": http_on_wan,
                "https_on_wan": https_on_wan,
            },
            "networks": {
                "wan": wan_network,
                "lan": lan_network,
                "guest": guest_network,
                "none": none_network,
            },
        }

    def update_settings(self, firewall, networks):
        system_files = SystemInfoFiles()

        if system_files.get_model() == "turris":
            return False  # Networks module can't be set for old turris

        if int(system_files.get_os_version().split(".", 1)[0]) < 4:
            return False  # Networks module can't be set for older versions

        wan_ifs = networks["wan"]
        lan_ifs = networks["lan"]
        guest_ifs = networks["guest"]
        none_ifs = networks["none"]
        ports, _ = self.detect_interfaces()
        ports = [e for e in ports if e["configurable"]]

        # check valid ports
        if {e["id"] for e in ports} != {e for e in wan_ifs + lan_ifs + guest_ifs + none_ifs}:
            # current ports doesn't match the one that are being set
            return False

        with UciBackend() as backend:
            GuestUci.enable_guest_network(backend)
            backend.set_option("network", "wan", "ifname", "" if len(wan_ifs) == 0 else wan_ifs[0])
            backend.set_option("network", "lan", "bridge_empty", store_bool(True))
            backend.set_option("network", "lan", "type", "bridge")
            backend.replace_list("network", "lan", "ifname", lan_ifs)
            backend.replace_list("network", "guest_turris", "ifname", guest_ifs)

            def set_firewall_rule(name, enabled, port):
                # update firewall rules
                backend.add_section("firewall", "rule", name)
                backend.set_option("firewall", name, "name", name)
                backend.set_option("firewall", name, "enabled", store_bool(enabled))
                backend.set_option("firewall", name, "target", "ACCEPT")
                backend.set_option("firewall", name, "dest_port", port)
                backend.set_option("firewall", name, "proto", "tcp")
                backend.set_option("firewall", name, "src", "wan")

            set_firewall_rule("wan_ssh_turris_rule", firewall["ssh_on_wan"], 22)
            set_firewall_rule("wan_http_turris_rule", firewall["http_on_wan"], 80)
            set_firewall_rule("wan_https_turris_rule", firewall["https_on_wan"], 443)

        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands

            WebUciCommands.update_passed("networks")
        except UciException:
            pass

        MaintainCommands().restart_network()

        return True


class NetworksCmd(BaseCmdLine):
    def get_network_info(self, network_name: str) -> typing.Optional[dict]:

        retval, stdout, stderr = BaseCmdLine._run_command("/sbin/ifstatus", network_name)
        if retval != 0:
            return None
        try:
            data = json.loads(stdout.strip())
        except ValueError:
            logger.error("Failed to parse output from `ifstatus`")
            logger.debug(stdout)
            return None
        try:
            ipv4 = [e["address"] for e in data.get("ipv4-address", [])]
            ipv6 = [e["address"] for e in data.get("ipv6-address", [])]
            up = data.get("up", False)
            device = data.get("device", "")
            proto = data.get("proto", "")

            return {
                "name": network_name,
                "ipv4": ipv4,
                "ipv6": ipv6,
                "up": up,
                "device": device,
                "proto": proto,
            }
        except KeyError:
            logger.error("can't deal with json structure of `ifstatus`")
            logger.debug(stdout)

        return None
