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

from foris_controller_backends.guest import GuestUci
from foris_controller_backends.uci import (
    UciBackend, get_option_named, parse_bool, store_bool
)
from foris_controller_backends.wifi import WifiUci

from foris_controller_backends.services import OpenwrtServices
from foris_controller.exceptions import UciException

logger = logging.getLogger(__name__)


class LanUci(object):
    DEFAULT_DHCP_START = 100
    DEFAULT_DHCP_LIMIT = 150

    def get_settings(self):

        with UciBackend() as backend:
            network_data = backend.read("network")
            dhcp_data = backend.read("dhcp")
            try:
                sqm_data = backend.read("sqm")
            except UciException:
                sqm_data = {"sqm": {}}
            firewall_data = backend.read("firewall")

        router_ip = get_option_named(network_data, "network", "lan", "ipaddr")
        netmask = get_option_named(network_data, "network", "lan", "netmask")
        dhcp = {}
        dhcp["enabled"] = not parse_bool(
            get_option_named(dhcp_data, "dhcp", "lan", "ignore", "0"))
        dhcp["start"] = int(get_option_named(
            dhcp_data, "dhcp", "lan", "start", self.DEFAULT_DHCP_START))
        dhcp["limit"] = int(get_option_named(
            dhcp_data, "dhcp", "lan", "limit", self.DEFAULT_DHCP_LIMIT))

        guest = GuestUci.get_guest_network_settings(
            network_data, firewall_data, dhcp_data, sqm_data)

        return {
            "ip": router_ip,
            "netmask": netmask,
            "dhcp": dhcp,
            "guest_network": guest,
        }

    def update_settings(self, ip, netmask, dhcp, guest_network):
        """  Updates the lan settings in uci

        :param ip: new router ip
        :type ip: str
        :param netmask: network mask of lan
        :type netmask: str
        :param dhcp: {"enabled": True/False, ["start": 10, "max": 40]}
        :type dhpc: dict
        :param guest: {"enabled": True/False, ["ip": "192.168.1.1", ...]}
        :type guest: dict
        """
        with UciBackend() as backend:
            backend.add_section("network", "interface", "lan")
            backend.set_option("network", "lan", "ipaddr", ip)
            backend.set_option("network", "lan", "netmask", netmask)

            backend.add_section("dhcp", "dhcp", "lan")
            backend.set_option("dhcp", "lan", "ignore", store_bool(not dhcp["enabled"]))

            # set dhcp part
            if dhcp["enabled"]:
                backend.set_option(
                    "dhcp", "lan", "start", dhcp.get("start", self.DEFAULT_DHCP_START))
                backend.set_option(
                    "dhcp", "lan", "limit", dhcp.get("limit", self.DEFAULT_DHCP_LIMIT))

                # this will override all user dhcp options
                # TODO we might want to preserve some options
                backend.replace_list("dhcp", "lan", "dhcp_option", ["6,%s" % ip])

            # disable guest wifi when guest network is not enabled
            if not guest_network["enabled"]:
                WifiUci.set_guest_wifi_disabled(backend)

            # set guest network part
            sqm_cmd = GuestUci.set_guest_network(backend, guest_network)

        with OpenwrtServices() as services:
            # try to restart sqm (best effort) in might not be installed yet
            # note that sqm will be restarted when the network is restarted
            if sqm_cmd == "enable":
                services.enable("sqm", fail_on_error=False)
            elif sqm_cmd == "disable":
                services.disable("sqm", fail_on_error=False)

            services.restart("network", delay=2)
