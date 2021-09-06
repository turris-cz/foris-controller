#
# foris-controller
# Copyright (C) 2018-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from functools import wraps

logger = logging.getLogger(__name__)


def decorate_guest_net(pos):
    """Handle guest net on position"""
    def decorate(func):
        @wraps(func)
        def wrapper(*args):
            if args[pos] == "guest":
                args = [*args]
                args[pos] = "guest_turris"
            func(*args)
        return wrapper
    return decorate


class NetworksUci(object):
    def _prepare_network(self, data, section, ports_map):
        # TODO: once `ifname` not required, refactor
        interfaces = get_option_named(data, "network", section, "ifname", [])
        interfaces = interfaces if isinstance(interfaces, (tuple, list)) else interfaces.split(" ")
        device = get_option_named(data, "network", section, "device", "")

        devices = get_option_named(data,"network", device.replace("-", "_"), "ports", [])

        # by default migrated "br-lan" is anonymous
        if section == "lan" and len(devices) < 1 and not interfaces:
            devs = get_sections_by_type(data, "network", "device")
            lan_bridge = [
                i for i in devs
                if i["name"].startswith("cfg") and i["data"].get("name") == "br-lan"
            ]
            devices = lan_bridge[0]["data"].get("ports", [])
        res = []

        # ensure ports are in port_map
        if devices:
            for port in devices:
                if port in ports_map:
                    res.append(ports_map.pop(port))
        else:
            try:
                res.append(ports_map.pop(device))
            except KeyError:
                pass

        # TODO: once old uci not supported delete, see above
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
            if section["data"].get("device") == ifname and section["data"].get("device")
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
                v["configurable"] = True
                if v["type"] == "wifi":
                    v["configurable"] = False
                    res_wireless.append(v)
                else:
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
        # Return only first interface asigned to wan to make it compatible with bridges for wan,
        # so the json message will still pass validation.
        # Note: remove this little workaround when multiple interfaces on wan are supported
        if wan_network:
            wan_network = [wan_network[0]]

        lan_network = self._prepare_network(network_data, "lan", iface_map)
        guest_network = self._prepare_network(network_data, "guest_turris", iface_map)
        none_network = [e for e in iface_map.values()]  # reduced in _prepare_network using pop()

        for record in wifi_ifaces:
            networks_and_ssids = self._find_enabled_networks_by_ifname(wireless_data, record["id"])
            macaddr = record.get("macaddr")
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

        @decorate_guest_net(1)
        def _create_bridge(backend: UciBackend, net: str, ifs: typing.List[str], mac=None):
            """Create bridge device and set its interfaces"""
            backend.add_section("network", "device", f"br_{net}")
            backend.set_option("network", f"br_{net}", "name", f"br-{net}")
            backend.set_option("network", f"br_{net}", "type", "bridge")
            backend.replace_list("network", f"br_{net}", "ports", ifs)
            backend.set_option("network", net, "device", f"br-{net}")
            backend.del_option("network", net, "bridge_empty", fail_on_error=False)
            if mac:
                backend.set_option("network", f"br_{net}", "macaddr", mac)

        @decorate_guest_net(2)
        def _del_bridge(backend: UciBackend, data, net: str, devices: typing.List[str]):
            """Delete bridge and set the interface device to device"""
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

        @decorate_guest_net(1)
        def _set_bridge_ports(backend, net, ifs):
            """Set bridge ports to provided interfaces"""
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
