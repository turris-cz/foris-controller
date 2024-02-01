#
# foris-controller
# Copyright (C) 2018-2021, 2023 CZ.NIC, z.s.p.o. (https://www.nic.cz/)
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
import logging

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockNetworksHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    device = {"model": "omnia", "version": "2G no GPIO"}
    firewall = {"ssh_on_wan": False, "http_on_wan": False, "https_on_wan": False}
    DEFAULT_NETWORKS = {
        "wan": [
            {
                "id": "eth2",
                "type": "eth",
                "slot": "WAN",
                "state": "up",
                "link_speed": 1000,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "04:f0:21:24:11:1f"
            },
            {
                "id": "wwan0",
                "type": "wwan",
                "slot": "MPCI1",
                "state": "down",
                "link_speed": 0,
                "bus": "pci",
                "module_id": 0,
                "configurable": True,
                "macaddr": "",
                'qmi_device': '/dev/cdc-wdm0',
                "slot_path": "/sys/devices/platform/soc/soc:internal-regs@d0000000/d005e000.usb/usb1/1-1"
            }
        ],
        "lan": [
            {
                "id": "lan0",
                "type": "eth",
                "slot": "LAN0",
                "state": "down",
                "link_speed": 0,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:91"
            },
            {
                "id": "lan1",
                "type": "eth",
                "slot": "LAN1",
                "state": "down",
                "link_speed": 0,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:92"
            },
            {
                "id": "lan2",
                "type": "eth",
                "slot": "LAN2",
                "state": "up",
                "link_speed": 100,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:9c"
            },
            {
                "id": "lan3",
                "type": "eth",
                "slot": "LAN3",
                "state": "down",
                "link_speed": 0,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:9d"
            },
            {
                "id": "lan4",
                "type": "eth",
                "slot": "LAN4",
                "state": "down",
                "link_speed": 0,
                "bus": "eth",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:9f"
            },
        ],
        "guest": [
            {
                "id": "eth3",
                "type": "eth",
                "slot": "0",
                "state": "down",
                "link_speed": 0,
                "bus": "usb",
                "module_id": 0,
                "configurable": True,
                "macaddr": "d8:58:d7:00:92:9d"
            }
        ],
        "none": [
            {
                "id": "wwan1",
                "type": "wwan",
                "slot": "MPCI2",
                "state": "down",
                "link_speed": 0,
                "bus": "pci",
                "module_id": 0,
                "configurable": True,
                "macaddr": "04:f0:21:24:11:be",
                'qmi_device': '/dev/cdc-wdm1',
                "slot_path": "/sys/devices/platform/soc/soc:internal-regs@d0000000/d0058000.usb/usb3/3-1"
            },
            {
                "id": "wlan0",
                "type": "wifi",
                "slot": "MPCI0",
                "state": "down",
                "link_speed": 0,
                "bus": "pci",
                "module_id": 0,
                "configurable": False,
                "ssid": "testing-ssid",
                "macaddr": "04:f0:21:23:22:dc",
                "slot_path": "soc/soc:pcie/pci0000:00/0000:00:02.0/0000:01:00.0"
            }
        ],
    }
    networks = BaseMockHandler._manager.dict(dict(copy.deepcopy(DEFAULT_NETWORKS)))
    networks_lock = BaseMockHandler._manager.Lock()

    def _cleanup(self):
        MockNetworksHandler.networks = BaseMockHandler._manager.dict(
            dict(copy.deepcopy(MockNetworksHandler))
        )

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get networks settings

        :returns: current networks settiongs
        :rtype: str
        """
        res = {
            "device": MockNetworksHandler.device,
            "firewall": MockNetworksHandler.firewall,
            "networks": dict(MockNetworksHandler.networks),
        }
        return copy.deepcopy(res)

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current wan settings

        :returns: True if update passes
        :rtype: bool
        """
        MockNetworksHandler.guide_set.set(True)

        with MockNetworksHandler.networks_lock:
            ports = []
            for net_name in MockNetworksHandler.networks.keys():
                ports += MockNetworksHandler.networks[net_name]
            ports_map = {e["id"]: e for e in ports}

            new_nets = {e: [] for e in MockNetworksHandler.networks.keys()}
            try:
                for net_name in MockNetworksHandler.networks.keys():
                    for port_id in new_settings["networks"][net_name]:
                        if not ports_map[port_id]["configurable"]:
                            return False
                        new_nets[net_name].append(ports_map.pop(port_id))
            except KeyError:
                return False

            if [True for _, v in ports_map.items() if v["configurable"]]:  # ports were not assigned
                return False

            for k, v in ports_map.items():
                new_nets["none"].append(v)

            for key in new_nets.keys():
                MockNetworksHandler.networks[key] = new_nets[key]

        MockNetworksHandler.firewall = new_settings["firewall"]

        return True
