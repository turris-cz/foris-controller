#
# foris-controller
# Copyright (C) 2018-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import typing

import turrishw

from foris_controller.exceptions import UciException, UciRecordNotFound
from foris_controller.utils import sort_by_natural_order
from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    get_sections_by_type,
    parse_bool,
    section_exists,
    store_bool,
)

logger = logging.getLogger(__name__)

NetworkAndSSIDs = typing.List[typing.Tuple[str, str]]


def convert_network_name(name: str) -> str:
    if name == "guest":
        return "guest_turris"
    return name


class NetworksUci():
    def _prepare_network(self, data: dict, section: str, ports_map: typing.Dict[str, dict]) -> typing.List[dict]:
        """Map detected interfaces to interfaces found in uci config file.

        Return only those that exist in uci configuration and ignore the rest.

        Sort interfaces by natural order by the port names

        For example with following config:
            list ports 'lan2'
            list ports 'lan11'
            list ports 'lan1'

        resulting interfaces should be return in order lan1, lan2, lan11.
        """
        # TODO: once `ifname` not required, refactor
        interfaces = get_option_named(data, "network", section, "ifname", [])
        interfaces = interfaces if isinstance(interfaces, (tuple, list)) else interfaces.split(" ")
        device = get_option_named(data, "network", section, "device", "")

        ports = get_option_named(data,"network", device.replace("-", "_"), "ports", [])

        # by default migrated "br-lan" and "br-guest_turris" is anonymous
        if section in ("lan", "guest_turris") and not ports and not interfaces:
            ports = NetworksUci._get_anonymous_bridge_ports(data, section)

        res = []

        # ensure ports are in port_map
        if ports:
            ports = sort_by_natural_order(ports)
            for port in ports:
                if prt := ports_map.pop(port, None):
                    res.append(prt)
        else:
            if prt := ports_map.pop(device, None):
                res.append(prt)

        interfaces = sort_by_natural_order(interfaces)

        # TODO: once old uci not supported delete, see above
        for interface in interfaces:
            if iface := ports_map.pop(interface, None):
                res.append(iface)
        return res

    def _prepare_wwan(self, data: dict, ports_map: typing.Dict[str, dict]) -> typing.List[dict]:
        """Detetmine if network in uci and return list of active devices."""

        res = []

        device_path = get_option_named(data, "network", "gsm", "device", "none")

        if device_path != "none":
            for id_, interface in ports_map.items():
                if id_.startswith("wwan") and interface["slot_path"] == device_path:
                    res.append(interface)

        return res

    @staticmethod
    def _get_anonymous_bridge_ports(uci_data: dict, section: str) -> typing.List[str]:
        """Get network bridges (lan, guest, ...) ports names of anonymous bridge config section.

        These config sections might exist after network config migration in TOS 6.x,
        or just be there from default configuration.
        """
        devs = get_sections_by_type(uci_data, "network", "device")
        bridge = [
            dev for dev in devs
            if dev["name"].startswith("cfg") and dev["data"].get("name") == f"br-{section}"
        ]

        if not bridge:
            logger.debug("No anonymous section 'br-%s' found among network devices.", section)
            return []

        return bridge[0]["data"].get("ports", [])

    def _find_enabled_networks_by_ifname(self, wireless_data, ifname: str) -> typing.Optional[NetworkAndSSIDs]:
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

    def _find_enabled_networks_by_macaddr(self, wireless_data, macaddr: typing.Optional[str], ifname: str) -> typing.Optional[NetworkAndSSIDs]:
        """
        :returns: None if no valid device section found, or list of (network, ssid) (can be empty)
        """
        if macaddr is None:
            return None

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

    def _find_enabled_networks_by_path(
        self,
        wireless_data,
        slot_path: typing.Optional[str],
        ifname: str
    ) -> typing.Optional[NetworkAndSSIDs]:
        """
        Return list of tuples with (network, ssid).
        Return None if no valid interface section is found.
        """
        if slot_path is None:
            return None

        device_sections = [
            section
            for section in get_sections_by_type(wireless_data, "wireless", "wifi-device")
            # Do not try to match the whole path, because `slot_path` value from turrishw might differ
            # from config value.
            # Substring match should be sufficient.
            if section["data"].get("path", "") in slot_path
        ]
        # For example:
        #     turrishw: "slot_path": "soc/d0070000.pcie/pci0000:00/0000:00:00.0/0000:01:00.0/net/wlan0"
        #     uci config: option path 'soc/d0070000.pcie/pci0000:00/0000:00:00.0/0000:01:00.0'

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
                if network := interface_section["data"].get("network", None):
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
                v["configurable"] = True
                if v["type"] in {"wifi","wwan"}:
                    v["configurable"] = False
                if v["type"] == "wifi":
                    res_wireless.append(v)
                else:
                    res.append(v)
        except Exception:
            res = [], []  # when turrishw get fail -> return empty dict
        return res, res_wireless

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
        if get_option_named(network_data, "network", network_name, "ifname", "") != "":
            config_interfaces = get_option_named(network_data, "network", network_name, "ifname")
        else:
            device = get_option_named(network_data, "network", network_name, "device", "").replace("-","_")
            if section_exists(network_data, "network", device):
                config_interfaces = get_option_named(network_data, "network", device, "ports", [])
            else:
                config_interfaces = get_option_named(network_data, "network", network_name, "device", [])
        config_interfaces = (
            config_interfaces
            if isinstance(config_interfaces, (list, tuple))
            else [config_interfaces]
        )
        return len(set(hw_interfaces).intersection(config_interfaces)) + wifi_iface_count

    def _find_enabled_wireless_networks(self, wireless_data: dict, record: dict) -> NetworkAndSSIDs:
        """Try to find configured wireless interfaces by different means.

        * by pci slot path
        * by macaddr
        * by ifname


        Return list of tuples (network, SSID) or empty list if nothing is found.
        """
        ifname = record["id"]

        # try to matched based on ifname
        if ssids := self._find_enabled_networks_by_ifname(wireless_data, ifname):
            return ssids

        # try to find it by pci slot path first
        slot_path = record.get("slot_path")
        if ssids := self._find_enabled_networks_by_path(wireless_data, slot_path, ifname):
            return ssids

        # try the macaddr as second choice
        macaddr = record.get("macaddr")
        if ssids := self._find_enabled_networks_by_macaddr(wireless_data, macaddr, ifname):
            return ssids

        return []  # None found

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

        # prepare wired intefaces...
        wan_network = self._prepare_network(network_data, "wan", iface_map)
        # Return only first interface asigned to wan to make it compatible with bridges for wan,
        # so the json message will still pass validation.
        # Note: remove this little workaround when multiple interfaces on wan are supported
        # TODO: add active "wwan" if exists
        wwan_network = self._prepare_wwan(network_data, iface_map)

        if wwan_network:
            wan_network.extend(wwan_network)
        else:
            if wan_network:
                wan_network = [wan_network[0]]

        lan_network = self._prepare_network(network_data, "lan", iface_map)
        guest_network = self._prepare_network(network_data, "guest_turris", iface_map)
        none_network = list(iface_map.values())  # reduced in _prepare_network using pop()
        # Note: none_network interfaces should be already sorted from turrishw

        network_groups_map = {
            "wan": wan_network,
            "lan": lan_network,
            "guest_turris": guest_network
        }

        # prepare wifi interfaces... something along this:
        # self._prepare_wireless_network(lan_network, guest_network, none_network)
        # hide code below to separate function?
        for record in wifi_ifaces:
            networks_and_ssids = self._find_enabled_wireless_networks(wireless_data, record)
            if not networks_and_ssids:
                record["ssid"] = ""
                none_network.append(record)

            for network_group, ssid in networks_and_ssids:
                record["ssid"] = ssid
                network_groups_map.get(network_group, none_network).append(record)

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

        def _create_bridge(backend: UciBackend, net: str, ifs: typing.List[str], mac=None):
            """Create bridge device and set its interfaces"""
            net = convert_network_name(net)
            backend.add_section("network", "device", f"br_{net}")
            backend.set_option("network", f"br_{net}", "name", f"br-{net}")
            backend.set_option("network", f"br_{net}", "type", "bridge")
            backend.replace_list("network", f"br_{net}", "ports", ifs)
            backend.set_option("network", net, "device", f"br-{net}")
            backend.del_option("network", net, "bridge_empty", fail_on_error=False)
            if mac:
                backend.set_option("network", f"br_{net}", "macaddr", mac)

        def _del_bridge(backend: UciBackend, data, net: str, devices: typing.List[str]):
            """Delete bridge and set the interface device to device"""
            net = convert_network_name(net)
            mac = get_option_named(data, "network", f"br_{net}", "macaddr", False)
            if section_exists(data, "network", f"br_{net}"):
                backend.del_section("network", f"br_{net}")
            if devices:
                backend.set_option("network", net, "device", devices[0])
                if mac:
                    backend.set_option("network", net, "macaddr", mac)
            else:
                backend.del_option("network", net, "device", fail_on_error=False)
                backend.set_option("network", net, "bridge_empty", store_bool(True))

        def _set_bridge_ports(backend, net, ifs):
            """Set bridge ports to provided interfaces"""
            net = convert_network_name(net)
            backend.replace_list("network", f"br_{net}", "ports", ifs)

        with UciBackend() as backend:
            # enable guest
            GuestUci.enable_guest_network(backend)
            data = backend.read("network")
            _set_bridge_ports(backend, "guest", guest_ifs)

            for net, ifs in zip(("wan", "lan"), (wan_ifs, lan_ifs)):
                # determine old config and delete it's keys and values
                if get_option_named(data, "network", net, "ifname", "") != "":
                    # this is old config, when "ifname" is present
                    backend.del_option("network", net, "ifname", fail_on_error=False)
                    if get_option_named(data, "network", net, "type", "") == "bridge":
                        # it also is of "bridge" type, which is reserved for "device" rather than "interface"
                        backend.del_option("network", net, "type", fail_on_error=False)

                # Check for anonymous bridge device (this actually applies only to lan)
                # this is here in case of migrated config with properly set bridge
                # but the bridge is anonymous.
                br_name = f"br-{net}"
                mac = None
                if get_option_named(data, "network", net, "device", "") == br_name:
                    for dev_section in get_sections_by_type(data, "network", "device"):
                        if dev_section["data"].get("name") == br_name:
                            mac = dev_section["data"].get("macaddr")
                            if dev_section["name"].startswith("cfg"):
                                backend.del_section("network", dev_section["name"])

                # new configuration
                if len(ifs) > 1 or net == "lan":
                    # more than one interface should have been used with bridge device
                    if section_exists(data, "network", f"br_{net}"):
                        # bridge already exists
                        _set_bridge_ports(backend, net, ifs)
                    else:
                        _create_bridge(backend, net, ifs, mac)
                else:
                    _del_bridge(backend, data, net, ifs)

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
