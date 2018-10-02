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
        "model": "omnia",
        "version": "2G no GPIO",
    }
    firewall = {
        "ssh_on_wan": False,
        "http_on_wan": False,
        "https_on_wan": False,
    }
    DEFAULT_NETWORKS = {
        "wan": [
            {"id": "eth2", "kind": "eth", "description": "WAN", "state": "up", "link_speed": 1000},
        ],
        "lan": [
            {"id": "lan0", "kind": "eth", "description": "LAN0", "state": "down", "link_speed": 0},
            {"id": "lan1", "kind": "eth", "description": "LAN1", "state": "down", "link_speed": 0},
            {"id": "lan2", "kind": "eth", "description": "LAN2", "state": "up", "link_speed": 100},
            {"id": "lan3", "kind": "eth", "description": "LAN3", "state": "down", "link_speed": 0},
            {"id": "lan4", "kind": "eth", "description": "LAN4", "state": "down", "link_speed": 0},
        ],
        "guest": [
            {"id": "eth3", "kind": "usb", "description": "USB-0", "state": "down", "link_speed": 0},
        ],
        "none": [
            {"id": "wwan0", "kind": "4g", "description": "MPCI1", "state": "down", "link_speed": 0},
            {"id": "wwan1", "kind": "3g", "description": "MPCI1", "state": "down", "link_speed": 0},
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
            "firewall": MockNetworksHandler.firewall,
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
        MockNetworksHandler.firewall = new_settings["firewall"]

        return True
