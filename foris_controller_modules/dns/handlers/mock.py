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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockDnsHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    forwarding_enabled = True
    forwarder = ""
    available_forwarders = [
        {"name": "", "description": ""},
        {"name": "odvr-nic-dns", "description": "CZ.NIC"},
        {"name": "quad9-normal", "description": "Quad9"},
    ]
    dnssec_enabled = True
    dns_from_dhcp_enabled = False
    dns_from_dhcp_domain = None

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get dns settings

        :returns: current dns settiongs
        :rtype: str
        """
        result = {
            "forwarding_enabled": MockDnsHandler.forwarding_enabled,
            "forwarder": MockDnsHandler.forwarder,
            "available_forwarders": MockDnsHandler.available_forwarders,
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
            if forwarder in [e["name"] for e in MockDnsHandler.available_forwarders]:
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
