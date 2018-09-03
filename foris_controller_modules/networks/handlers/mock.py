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
import copy

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockNetworksHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    device = {
        "type": "omnia",
        "version": "2G no GPIO",
    }
    DEFAULT_NETWORKS = {
        "wan": [
            {"id": "eth2", "kind": "eth", "module_index": 0, "index": 0},
        ],
        "lan": [
            {"id": "eth0", "kind": "eth", "module_index": 0, "index": 1},
            {"id": "lan0", "kind": "eth", "module_index": 0, "index": 1},
            {"id": "lan1", "kind": "eth", "module_index": 0, "index": 2},
            {"id": "lan2", "kind": "eth", "module_index": 0, "index": 3},
            {"id": "lan3", "kind": "eth", "module_index": 0, "index": 4},
        ],
        "guest": [
            {"id": "eth3", "kind": "usb", "module_index": 0, "index": 5},
        ],
        "none": [
            {"id": "wwan0", "kind": "4g", "module_index": 0, "index": 0},
            {"id": "wwan1", "kind": "3g", "module_index": 0, "index": 1},
        ],
    }
    networks = copy.deepcopy(DEFAULT_NETWORKS)

    def _cleanup(self):
        self.networks = copy.deepcopy(MockNetworksHandler.DEFAULT_NETWORKS)

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get networks settings

        :returns: current networks settiongs
        :rtype: str
        """
        res = {
            "device": MockNetworksHandler.device,
            "networks": MockNetworksHandler.networks,
        }
        return copy.deepcopy(res)

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current wan settings

        :returns: True if update passes
        :rtype: bool
        """
        MockNetworksHandler.guide_set.set(True)
        ports = []
        for net_name in MockNetworksHandler.networks:
            ports += MockNetworksHandler.networks[net_name]
        ports_map = {e["id"]: e for e in ports}

        new_nets = {e: [] for e in MockNetworksHandler.networks}
        try:
            for net_name in MockNetworksHandler.networks:
                for port_id in new_settings["networks"][net_name]:
                    new_nets[net_name].append(ports_map.pop(port_id))
        except KeyError:
            return False

        if ports_map:  # some ports were not assigned
            return False

        MockNetworksHandler.networks = new_nets

        return True
