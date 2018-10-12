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

from foris_controller.exceptions import UciException
from foris_controller_backends.uci import (
    UciBackend, get_option_named, parse_bool, store_bool
)

from foris_controller_backends.maintain import MaintainCommands

logger = logging.getLogger(__name__)


class LanUci(object):
    DEFAULT_DHCP_START = 100
    DEFAULT_DHCP_LIMIT = 150
    DEFAULT_LEASE_TIME = 12 * 60 * 60

    @staticmethod
    def _normalize_lease(value):
        leasetime = str(value)
        if leasetime == "infinite":
            return 0
        elif leasetime.endswith("m"):
            return int(leasetime[:-1]) * 60
        elif leasetime.endswith("h"):
            return int(leasetime[:-1]) * 60 * 60
        else:
            return int(leasetime)

    def get_settings(self):

        with UciBackend() as backend:
            network_data = backend.read("network")
            dhcp_data = backend.read("dhcp")

        mode = get_option_named(network_data, "network", "lan", "_turris_mode", "managed")

        mode_managed = {"dhcp": {}}
        mode_managed["router_ip"] = get_option_named(network_data, "network", "lan", "ipaddr")
        mode_managed["netmask"] = get_option_named(network_data, "network", "lan", "netmask")
        mode_managed["dhcp"]["enabled"] = not parse_bool(
            get_option_named(dhcp_data, "dhcp", "lan", "ignore", "0"))
        mode_managed["dhcp"]["start"] = int(get_option_named(
            dhcp_data, "dhcp", "lan", "start", self.DEFAULT_DHCP_START))
        mode_managed["dhcp"]["limit"] = int(get_option_named(
            dhcp_data, "dhcp", "lan", "limit", self.DEFAULT_DHCP_LIMIT))
        mode_managed["dhcp"]["lease_time"] = LanUci._normalize_lease(
            get_option_named(dhcp_data, "dhcp", "lan", "leasetime", self.DEFAULT_LEASE_TIME)
        )

        mode_unmanaged = {}
        mode_unmanaged["lan_type"] = get_option_named(network_data, "network", "lan", "proto")
        hostname = get_option_named(network_data, "network", "lan", "hostname", "")
        mode_unmanaged["lan_dhcp"] = {"hostname": hostname} if hostname else {}
        mode_unmanaged["lan_static"] = {
            "ip": get_option_named(network_data, "network", "lan", "ipaddr"),
            "netmask": get_option_named(network_data, "network", "lan", "netmask"),
            "gateway": get_option_named(
                network_data, "network", "lan", "gateway",
                get_option_named(network_data, "network", "lan", "ipaddr"),
            ),
        }
        dns = get_option_named(network_data, "network", "lan", "dns", [])
        dns = reversed(dns)  # dns with higher priority should be added last
        mode_unmanaged["lan_static"].update(zip(("dns1", "dns2"), dns))

        from foris_controller_backends.networks import NetworksUci

        return {
            "mode": mode,
            "mode_managed": mode_managed,
            "mode_unmanaged": mode_unmanaged,
            "interface_count": NetworksUci.get_interface_count(network_data, "lan")
        }

    def update_settings(self, mode, mode_managed=None, mode_unmanaged=None):
        """  Updates the lan settings in uci

        :param mode: lan setting mode managed/unmanaged
        :type mode: str
        :param mode_managed: managed mode settings {"router_ip": ..., "netmask":..., "dhcp": ...}
        :type mode_managed: dict
        :param mode_unmanaged: {"lan_type": "none/dhcp/static", "lan_static": {}, ...}
        :type mode_unmanaged: dict
        """
        with UciBackend() as backend:
            backend.add_section("network", "interface", "lan")
            backend.set_option("network", "lan", "_turris_mode", mode)

            if mode == "managed":
                backend.set_option("network", "lan", "proto", "static")
                backend.set_option("network", "lan", "ipaddr", mode_managed["router_ip"])
                backend.set_option("network", "lan", "netmask", mode_managed["netmask"])

                backend.add_section("dhcp", "dhcp", "lan")
                dhcp = mode_managed["dhcp"]
                backend.set_option(
                    "dhcp", "lan", "ignore", store_bool(not dhcp["enabled"]))

                # set dhcp part (this device acts as a server here)
                if dhcp["enabled"]:
                    backend.set_option("dhcp", "lan", "start", dhcp["start"])
                    backend.set_option("dhcp", "lan", "limit", dhcp["limit"])
                    backend.set_option(
                        "dhcp", "lan", "leasetime",
                        "infinite" if dhcp["lease_time"] == 0 else dhcp["lease_time"]
                    )

                    # this will override all user dhcp options
                    # TODO we might want to preserve some options
                    backend.replace_list(
                        "dhcp", "lan", "dhcp_option", ["6,%s" % mode_managed["router_ip"]])

            elif mode == "unmanaged":
                backend.set_option("network", "lan", "proto", mode_unmanaged["lan_type"])
                # disable dhcp you are not managing this network...
                backend.add_section("dhcp", "dhcp", "lan")
                backend.set_option("dhcp", "lan", "ignore", store_bool(True))
                if mode_unmanaged["lan_type"] == "dhcp":
                    if "hostname" in mode_unmanaged["lan_dhcp"]:
                        backend.set_option(
                            "network", "lan", "hostname",
                            mode_unmanaged["lan_dhcp"]["hostname"])

                elif mode_unmanaged["lan_type"] == "static":
                    backend.set_option(
                        "network", "lan", "ipaddr", mode_unmanaged["lan_static"]["ip"])
                    backend.set_option(
                        "network", "lan", "netmask", mode_unmanaged["lan_static"]["netmask"])
                    backend.set_option(
                        "network", "lan", "gateway", mode_unmanaged["lan_static"]["gateway"])
                    dns = [
                        mode_unmanaged["lan_static"][name] for name in ("dns2", "dns1")
                        if name in mode_unmanaged["lan_static"]
                    ]  # dns with higher priority should be added last
                    backend.replace_list("network", "lan", "dns", dns)
                elif mode_unmanaged["lan_type"] == "none":
                    pass  # no need to handle

        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands
            WebUciCommands.update_passed("lan")
        except UciException:
            pass

        MaintainCommands().restart_network()

        return True
