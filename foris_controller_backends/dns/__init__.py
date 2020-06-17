#
# foris-controller
# Copyright (C) 2019-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import hashlib
import json
import logging
import re
import pathlib
from slugify import slugify

from foris_controller.app import app_info
from foris_controller.utils import RWLock
from foris_controller_backends.uci import (
    UciBackend,
    get_option_anonymous,
    get_option_named,
    parse_bool,
    store_bool,
)
from foris_controller_backends.files import BaseMatch, BaseFile, path_exists
from foris_controller_backends.services import OpenwrtServices
from foris_controller.exceptions import UciRecordNotFound, UciException

logger = logging.getLogger(__name__)


class DnsFiles(BaseFile):
    file_lock = RWLock(app_info["lock_backend"])
    RESOLVERS_DIR = pathlib.Path("/etc/resolver/dns_servers/")

    @staticmethod
    def empty_forwarder():
        return {
            "name": "",
            "description": "",
            "editable": False,
        }  # default resolver -> forward to provider's dns

    def add_forwarder(
        self,
        description: str,
        ipaddresses: dict,
        tls_type: str,
        tls_hostname: str,
        tls_pin: str,
    ):
        forwarder = {
            "description": description,
            "ipaddresses": ipaddresses,
            "tls_type": tls_type,
            "tls_hostname": tls_hostname,
            "tls_pin": tls_pin,
        }
        forwarder_dump = json.dumps(forwarder).encode('utf-8')
        forwarder_hash = hashlib.md5(forwarder_dump).hexdigest()
        name = f'{slugify(description, separator="_")}_{forwarder_hash}'

        path = str(DnsFiles.RESOLVERS_DIR / f"{name}.conf")
        if path_exists(path):
            return False

        res = self._store_forwarder_to_file(
            name,
            description,
            ipaddresses,
            tls_type,
            tls_hostname,
            tls_pin,
        )

        if res:
            return name
        return False

    def set_forwarder(
        self,
        name: str,
        description: str,
        ipaddresses: dict,
        tls_type: str,
        tls_hostname: str,
        tls_pin: str,
    ) -> bool:
        path = str(DnsFiles.RESOLVERS_DIR / f"{name}.conf")
        if not path_exists(path):
            return False

        if name in [e["name"] for e in DnsFiles.get_available_forwarders() if not e["editable"]]:
            return False

        return self._store_forwarder_to_file(
            name,
            description,
            ipaddresses,
            tls_type,
            tls_hostname,
            tls_pin,
        )

    def _store_forwarder_to_file(
        self,
        name: str,
        description: str,
        ipaddresses: dict,
        tls_type: str,
        tls_hostname: str,
        tls_pin: str,
    ) -> bool:
        with DnsFiles.file_lock.readlock:
            escaped_description = description.replace('"', '\\"')
            content = f"""\
name="{name}.conf"
description="{escaped_description}"
ipv4="{" ".join(ipaddresses.get("ipv4", ""))}"
ipv6="{" ".join(ipaddresses.get("ipv6", ""))}"
editable="true"
"""
            if tls_type == "pin":
                content += f"""\
enable_tls="1"
port="853"
pin_sha256="{tls_pin}"
"""
            elif tls_type == "hostname":
                content += f"""\
enable_tls="1"
port="853"
hostname="{tls_hostname}"
ca_file="/etc/ssl/certs/ca-certificates.crt"

"""
            self._store_to_file(str(DnsFiles.RESOLVERS_DIR / f"{name}.conf"), content)

        return True

    def del_forwarder(self, name: str) -> bool:
        path = str(DnsFiles.RESOLVERS_DIR / f"{name}.conf")
        if not path_exists(path):
            return False
        if name in [e["name"] for e in DnsFiles.get_available_forwarders() if not e["editable"]]:
            return False

        print(dir(self))
        self.delete_file(path)
        return True

    @staticmethod
    def _split_ip_addresses_list(ip_addresses):
        return list(filter(None, ip_addresses.split(" ")))

    @staticmethod
    def get_available_forwarders():
        res = []
        with DnsFiles.file_lock.readlock:
            for e in BaseMatch.list_files([str(DnsFiles.RESOLVERS_DIR / "*.conf")]):
                name = pathlib.Path(e).name[: -len(".conf")]
                content = BaseFile()._file_content(str(DnsFiles.RESOLVERS_DIR / f"{name}.conf"))
                description = re.search(r'description="([^"]*)"', content, re.MULTILINE).group(1)
                editable = re.search(r'editable="([^"]*)"', content, re.MULTILINE)
                ipv4 = re.search(r'ipv4="([^"]*)"', content, re.MULTILINE).group(1)
                ipv6 = re.search(r'ipv6="([^"]*)"', content, re.MULTILINE).group(1)
                editable = re.search(r'editable="([^"]*)"', content, re.MULTILINE)
                if editable and editable.group(1).lower() == "true":
                    editable = True
                else:
                    editable = False

                record = {
                    "name": name,
                    "description": description,
                    "ipaddresses": {
                        "ipv4": DnsFiles._split_ip_addresses_list(ipv4),
                        "ipv6": DnsFiles._split_ip_addresses_list(ipv6),
                    },
                    "editable": editable,
                    "tls_type": "no",
                    "tls_hostname": "",
                    "tls_pin": "",
                }
                hostname = re.search(r'^hostname="([^"]*)"', content, re.MULTILINE)
                if hostname:
                    record["tls_type"] = "hostname"
                    record["tls_hostname"] = hostname.group(1)

                pin = re.search(r'^pin_sha256="([^"]*)"', content, re.MULTILINE)
                if pin:
                    record["tls_type"] = "pin"
                    record["tls_pin"] = pin.group(1)

                res.append(record)
        return res

    @staticmethod
    def get_available_forwarders_short():
        return [DnsFiles.empty_forwarder()] + [
            {"name": e["name"], "description": e["description"], "editable": e["editable"]}
            for e in DnsFiles.get_available_forwarders()
        ]


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
            "available_forwarders": DnsFiles.get_available_forwarders_short(),
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

        if forwarder and forwarder not in [
            e["name"] for e in DnsFiles.get_available_forwarders_short()
        ]:
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
