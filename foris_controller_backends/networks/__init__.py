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

import logging

import turrishw

from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.uci import UciBackend, get_option_named, store_bool, parse_bool

from foris_controller.exceptions import UciException

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

    def _detect_ports(self):
        res = []
        try:
            for k, v in turrishw.get_ifaces().items():
                v["id"] = k
                v["kind"] = "eth"  # TODO hw detect should return which bus is used
                res.append(v)
        except Exception:
            res = []  # when turrishw get fail -> return empty dict
        return sorted(res, key=lambda x: x["id"])

    def get_settings(self):
        """ Get current wifi settings
        :returns: {"device": {}, "networks": [{...},]}
        "rtype: dict
        """

        ports = self._detect_ports()
        ports_map = {e["id"]: e for e in ports}

        with UciBackend() as backend:
            network_data = backend.read("network")
            firewall_data = backend.read("firewall")

        wan_network = self._prepare_network(network_data, "wan", ports_map)
        lan_network = self._prepare_network(network_data, "lan", ports_map)
        guest_network = self._prepare_network(network_data, "guest_turris", ports_map)
        none_network = [e for e in ports_map.values()]  # reduced in _prepare_network using pop()
        # parse firewall options
        ssh_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_ssh_turris_rule", "enabled", "0"))
        http_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_http_turris_rule", "enabled", "0"))
        https_on_wan = parse_bool(
            get_option_named(firewall_data, "firewall", "wan_https_turris_rule", "enabled", "0"))

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
            }
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
        ports = self._detect_ports()

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
