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

from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.uci import UciBackend, get_option_named, store_bool
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.services import OpenwrtServices

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

    def _get_model(self):
        model_name = SystemInfoFiles().get_model()
        if "Omnia" in model_name:
            model = "omnia"
        elif "Mox" in model_name:
            model = "mox"
        else:
            model = "turris"
        return model

    def _fake_hwdetect(self):
        # TODO this should be done using hwdetect
        model = self._get_model()
        if model == "omnia":
            ports = [
                {"id": "eth2", "kind": "eth", "module_index": 0, "index": 0, "title": "WAN"},
                {"id": "lan0", "kind": "eth", "module_index": 0, "index": 1, "title": "LAN0"},
                {"id": "lan1", "kind": "eth", "module_index": 0, "index": 2, "title": "LAN1"},
                {"id": "lan2", "kind": "eth", "module_index": 0, "index": 3, "title": "LAN2"},
                {"id": "lan3", "kind": "eth", "module_index": 0, "index": 4, "title": "LAN3"},
                {"id": "lan4", "kind": "eth", "module_index": 0, "index": 5, "title": "LAN4"},
            ]
        elif model == "mox":
            ports = [
                {"id": "eth0", "kind": "eth", "module_index": 0, "index": 0, "title": "WAN"},
            ]
        else:
            ports = []
        return ports

    def get_settings(self):
        """ Get current wifi settings
        :returns: {"device": {}, "networks": [{...},]}
        "rtype: dict
        """
        model = self._get_model()

        ports = self._fake_hwdetect()
        ports_map = {e["id"]: e for e in ports}

        with UciBackend() as backend:
            data = backend.read("network")

        wan_network = self._prepare_network(data, "wan", ports_map)
        lan_network = self._prepare_network(data, "lan", ports_map)
        guest_network = self._prepare_network(data, "guest_turris", ports_map)
        none_network = [e for e in ports_map.values()]  # reduced in _prepare_network using pop()

        return {
            "device": {
                "model": model,
                "version": "??"
            },
            "networks": {
                "wan": wan_network,
                "lan": lan_network,
                "guest": guest_network,
                "none": none_network,
            }
        }

    def update_settings(self, networks):
        # check valid ports
        if self._get_model() == "turris":
            return False  # Networks module can't be used for old turris
        wan_ifs = networks["wan"]
        lan_ifs = networks["lan"]
        guest_ifs = networks["guest"]
        none_ifs = networks["none"]
        ports = self._fake_hwdetect()
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

        with OpenwrtServices() as services:
            services.restart("network", delay=2)

        return True
