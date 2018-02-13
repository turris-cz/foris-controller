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

from foris_controller_backends.uci import (
    UciBackend, get_option_named
)
from foris_controller.exceptions import UciException
from foris_controller_backends.services import OpenwrtServices


logger = logging.getLogger(__name__)


class WanUci(object):

    def get_settings(self):

        with UciBackend() as backend:
            network_data = backend.read("network")

        # WAN
        wan_settings = {}
        wan_settings["wan_type"] = get_option_named(network_data, "network", "wan", "proto")
        if wan_settings["wan_type"] == "dhcp":
            client_id = get_option_named(network_data, "network", "wan", "clientid", "")
            wan_settings["wan_dhcp"] = {"client_id": client_id} if client_id else {}
        elif wan_settings["wan_type"] == "static":
            wan_settings["wan_static"] = {
                "ip": get_option_named(network_data, "network", "wan", "ipaddr"),
                "netmask": get_option_named(network_data, "network", "wan", "netmask"),
                "gateway": get_option_named(network_data, "network", "wan", "gateway"),
            }
            dns = get_option_named(network_data, "network", "wan", "dns", [])
            dns = reversed(dns)  # dns with higher priority should be added last
            wan_settings["wan_static"].update(zip(("dns1", "dns2"), dns))
        elif wan_settings["wan_type"] == "pppoe":
            wan_settings["wan_pppoe"] = {
                "username": get_option_named(network_data, "network", "wan", "username"),
                "password": get_option_named(network_data, "network", "wan", "password"),
            }

        # WAN6
        wan6_settings = {}
        wan6_settings["wan6_type"] = get_option_named(network_data, "network", "wan6", "proto")
        if wan6_settings["wan6_type"] == "static":
            wan6_settings["wan6_static"] = {
                "ip": get_option_named(network_data, "network", "wan6", "ip6addr"),
                "network": get_option_named(network_data, "network", "wan6", "ip6prefix"),
                "gateway": get_option_named(network_data, "network", "wan6", "ip6gw"),
            }
            dns = get_option_named(network_data, "network", "wan6", "dns", [])
            dns = reversed(dns)  # dns with higher priority should be last
            wan6_settings["wan6_static"].update(zip(("dns1", "dns2"), dns))

        # MAC
        custom_mac = get_option_named(network_data, "network", "wan", "macaddr", "")
        mac_settings = {"custom_mac_enabled": True, "custom_mac": custom_mac} if custom_mac \
            else {"custom_mac_enabled": False}

        return {
            "wan_settings": wan_settings,
            "wan6_settings": wan6_settings,
            "mac_settings": mac_settings,
        }

    def update_settings(self, wan_settings, wan6_settings, mac_settings):
        with UciBackend() as backend:
            # WAN
            wan_type = wan_settings["wan_type"]
            backend.add_section("network", "interface", "wan")
            backend.set_option("network", "wan", "proto", wan_type)
            if wan_type == "dhcp":
                if "client_id" in wan_settings["wan_dhcp"]:
                    backend.set_option(
                        "network", "wan", "clientid", wan_settings["wan_dhcp"]["client_id"])
                else:
                    try:
                        backend.del_option("network", "wan", "clientid")
                    except UciException:
                        pass

            elif wan_type == "static":
                backend.set_option("network", "wan", "ipaddr", wan_settings["wan_static"]["ip"])
                backend.set_option(
                    "network", "wan", "netmask", wan_settings["wan_static"]["netmask"])
                backend.set_option(
                    "network", "wan", "gateway", wan_settings["wan_static"]["gateway"])
                dns = [
                    wan_settings["wan_static"][name] for name in ("dns2", "dns1")
                    if name in wan_settings["wan_static"]
                ]  # dns with higher priority should be added last
                backend.replace_list("network", "wan", "dns", dns)

            elif wan_type == "pppoe":
                backend.set_option(
                    "network", "wan", "username", wan_settings["wan_pppoe"]["username"])
                backend.set_option(
                    "network", "wan", "password", wan_settings["wan_pppoe"]["password"])

            # WAN6
            wan6_type = wan6_settings["wan6_type"]
            backend.set_option("network", "wan6", "proto", wan6_type)
            if wan6_type == "static":
                backend.set_option("network", "wan6", "ip6addr", wan6_settings["wan6_static"]["ip"])
                backend.set_option(
                    "network", "wan6", "ip6prefix", wan6_settings["wan6_static"]["network"])
                backend.set_option(
                    "network", "wan6", "ip6gw", wan6_settings["wan6_static"]["gateway"])
                dns = [
                    wan6_settings["wan6_static"][name] for name in ("dns2", "dns1")
                    if name in wan6_settings["wan6_static"]
                ]  # dns with higher priority should be added last
                backend.replace_list("network", "wan6", "dns", dns)

            # MAC
            if mac_settings["custom_mac_enabled"]:
                backend.set_option("network", "wan", "macaddr", mac_settings["custom_mac"])
            else:
                try:
                    backend.del_option("network", "wan", "macaddr")
                except UciException:
                    pass

        with OpenwrtServices() as services:
            services.restart("network", delay=2)

        return True
