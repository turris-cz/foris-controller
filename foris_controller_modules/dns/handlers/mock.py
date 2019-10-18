#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockDnsHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    forwarding_enabled = True
    forwarder = ""
    available_forwarders = [
        {
            "name": "99_google",
            "ipaddresses": {"ipv4": "8.8.8.8", "ipv6": "2001:4860:4860::8888"},
            "description": "Google",
            "editable": False,
            "tls_type": "no",
            "tls_hostname": "",
            "tls_pin": "",
        },
        {
            "name": "99_cloudflare",
            "description": "Cloudflare (TLS)",
            "ipaddresses": {"ipv4": "1.1.1.1", "ipv6": "2606:4700:4700::1111"},
            "editable": False,
            "tls_type": "pin",
            "tls_hostname": "",
            "tls_pin": "yioEpqeR4WtDwE9YxNVnCEkTxIjx6EEIwFSQW+lJsbc=",
        },
        {
            "name": "99_quad9",
            "description": "Quad9 (TLS)",
            "ipaddresses": {"ipv4": "9.9.9.10", "ipv6": "2620:fe::10"},
            "editable": False,
            "tls_type": "hostname",
            "tls_hostname": "dns.quad9.net",
            "tls_pin": "",
        },
    ]
    dnssec_enabled = True
    dns_from_dhcp_enabled = False
    dns_from_dhcp_domain = None

    def get_converted_forwarders(self):
        return [{"name": "", "description": "", "editable": False}] + [
            {"name": e["name"], "description": e["description"], "editable": e["editable"]}
            for e in MockDnsHandler.available_forwarders
        ]

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get dns settings

        :returns: current dns settings
        :rtype: str
        """
        result = {
            "forwarding_enabled": MockDnsHandler.forwarding_enabled,
            "forwarder": MockDnsHandler.forwarder,
            "available_forwarders": self.get_converted_forwarders(),
            "dnssec_enabled": MockDnsHandler.dnssec_enabled,
            "dns_from_dhcp_enabled": MockDnsHandler.dns_from_dhcp_enabled,
        }
        if MockDnsHandler.dns_from_dhcp_domain:
            result["dns_from_dhcp_domain"] = MockDnsHandler.dns_from_dhcp_domain
        return result

    @logger_wrapper(logger)
    def update_settings(
        self,
        forwarding_enabled,
        dnssec_enabled,
        dns_from_dhcp_enabled,
        forwarder=None,
        dns_from_dhcp_domain=None,
    ):
        """ Mocks updates current dns settings

        :param forwarding_enabled: set whether the forwarding is enabled
        :type forwarding_enabled: bool
        :param forwarder: which forwarder will be used
        :type forwarder: str
        :param dnssec_enabled: set whether dnssec is enabled
        :type dnssec_enabled: bool
        :param dns_from_dhcp_enabled: set whether dns from dhcp is enabled
        :type dns_from_dhcp_enabled: bool
        :param dns_from_dhcp_domain: set whether dns from dhcp is enabled
        :type dns_from_dhcp_domain: str
        :returns: True if update passes
        :rtype: bool
        """
        if forwarding_enabled:
            if forwarder in [e["name"] for e in self.get_converted_forwarders()]:
                MockDnsHandler.forwarder = forwarder
            else:
                return False

        MockDnsHandler.forwarding_enabled = forwarding_enabled
        MockDnsHandler.dnssec_enabled = dnssec_enabled
        MockDnsHandler.dns_from_dhcp_enabled = dns_from_dhcp_enabled
        if dns_from_dhcp_domain is not None:
            MockDnsHandler.dns_from_dhcp_domain = dns_from_dhcp_domain
        MockDnsHandler.guide_set.set(True)
        return True

    @logger_wrapper(logger)
    def list_forwarders(self):
        return MockDnsHandler.available_forwarders

    @logger_wrapper(logger)
    def add_forwarder(
        self,
        description: str,
        ipaddresses: dict,
        tls_type: str,
        tls_hostname: str = "",
        tls_pin: str = "",
    ) -> bool:
        def update_record(record: dict):
            record["name"] = description
            record["description"] = description
            record["ipaddresses"] = ipaddresses
            record["tls_type"] = tls_type
            record["tls_hostname"] = tls_hostname
            record["tls_pin"] = tls_pin
            record["editable"] = True

        record = {}
        update_record(record)
        MockDnsHandler.available_forwarders.append(record)
        return True

    @logger_wrapper(logger)
    def set_forwarder(
        self,
        name: str,
        description: str,
        ipaddresses: dict,
        tls_type: str,
        tls_hostname: str = "",
        tls_pin: str = "",
    ) -> bool:
        def update_record(record: dict):
            record["name"] = name
            record["description"] = description
            record["ipaddresses"] = ipaddresses
            record["tls_type"] = tls_type
            record["tls_hostname"] = tls_hostname
            record["tls_pin"] = tls_pin
            record["editable"] = True

        for e in MockDnsHandler.available_forwarders:
            if e["name"] == name:
                if e["editable"]:
                    update_record(e)
                    return True
        return False

    @logger_wrapper(logger)
    def del_forwarder(self, name: str) -> bool:
        for (idx, record) in enumerate(MockDnsHandler.available_forwarders):
            if record["name"] == name:
                if record["editable"]:
                    del MockDnsHandler.available_forwarders[idx]
                    return True
                else:
                    return False
        return False
