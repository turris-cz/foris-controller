#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import os

from foris_controller_backends.uci import (
    UciBackend,
    get_option_anonymous,
    get_option_named,
    parse_bool,
    store_bool,
)
from foris_controller_backends.files import BaseMatch, BaseFile
from foris_controller_backends.services import OpenwrtServices
from foris_controller.exceptions import UciRecordNotFound, UciException

logger = logging.getLogger(__name__)


class DnsFiles(object):
    RESOLVERS_DIR = "/etc/resolver/dns_servers/"

    @staticmethod
    def get_available_resolvers():
        res = [{"name": "", "description": ""}]  # default resovler -> forward to provider's dns
        for e in BaseMatch.list_files([os.path.join(DnsFiles.RESOLVERS_DIR, "*.conf")]):
            name = os.path.basename(e)[: -len(".conf")]
            description = BaseFile()._read_and_parse(
                os.path.join(DnsFiles.RESOLVERS_DIR, name + ".conf"), r'description="([^"]*)"', (1,)
            )
            res.append({"name": name, "description": description})
        return res


class DnsUciCommands(object):
    def get_settings(self):

        with UciBackend() as backend:
            resolver_data = backend.read("resolver")
            dhcp_data = backend.read("dhcp")

        forwarding_enabled = parse_bool(
            get_option_named(resolver_data, "resolver", "common", "forward_upstream")
        )
        forwarder = get_option_named(resolver_data, "resolver", "common", "forward_custom", "")
        dnssec_enabled = not parse_bool(
            get_option_named(resolver_data, "resolver", "common", "ignore_root_key", "0")
        )
        dns_from_dhcp_enabled = parse_bool(
            get_option_named(resolver_data, "resolver", "common", "dynamic_domains", "0")
        )
        res = {
            "forwarding_enabled": forwarding_enabled,
            "forwarder": forwarder,
            "available_forwarders": DnsFiles.get_available_resolvers(),
            "dnssec_enabled": dnssec_enabled,
            "dns_from_dhcp_enabled": dns_from_dhcp_enabled,
        }
        try:
            dns_from_dhcp_domain = get_option_anonymous(dhcp_data, "dhcp", "dnsmasq", 0, "local")
            res["dns_from_dhcp_domain"] = dns_from_dhcp_domain.strip("/")
        except UciRecordNotFound:
            pass
        return res

    def update_settings(
        self,
        forwarding_enabled,
        dnssec_enabled,
        dns_from_dhcp_enabled,
        forwarder=None,
        dns_from_dhcp_domain=None,
    ):

        if forwarder and forwarder not in [e["name"] for e in DnsFiles.get_available_resolvers()]:
            return False

        with UciBackend() as backend:
            backend.set_option(
                "resolver", "common", "forward_upstream", store_bool(forwarding_enabled)
            )
            backend.set_option(
                "resolver", "common", "ignore_root_key", store_bool(not dnssec_enabled)
            )
            backend.set_option(
                "resolver", "common", "dynamic_domains", store_bool(dns_from_dhcp_enabled)
            )
            if dns_from_dhcp_domain:
                backend.set_option(
                    "dhcp", "@dnsmasq[0]", "local", "/%s/" % dns_from_dhcp_domain.strip("/")
                )
            if forwarder is not None:
                backend.set_option("resolver", "common", "forward_custom", forwarder)

        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands

            WebUciCommands.update_passed("dns")
        except UciException:
            pass

        with OpenwrtServices() as services:
            services.restart("resolver")

        return True
