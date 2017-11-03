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

from foris_controller_backends.uci import (
    UciBackend, get_option_anonymous, get_option_named, parse_bool, store_bool
)
from foris_controller_backends.services import OpenwrtServices
from foris_controller_backends.cmdline import AsyncCommand
from foris_controller.exceptions import UciRecordNotFound

logger = logging.getLogger(__name__)


class DnsUciCommands(object):

    def get_settings(self):

        with UciBackend() as backend:
            resolver_data = backend.read("resolver")
            dhcp_data = backend.read("dhcp")

        forwarding_enabled = parse_bool(
            get_option_named(resolver_data, "resolver", "common", "forward_upstream"))
        dnssec_enabled = not parse_bool(
            get_option_named(resolver_data, "resolver", "common", "ignore_root_key"))
        dns_from_dhcp_enabled = parse_bool(
            get_option_named(resolver_data, "resolver", "common", "dynamic_domains"))
        res = {
            "forwarding_enabled": forwarding_enabled, "dnssec_enabled": dnssec_enabled,
            "dns_from_dhcp_enabled": dns_from_dhcp_enabled
        }
        try:
            dns_from_dhcp_domain = get_option_anonymous(
                dhcp_data, "dhcp", "dnsmasq", 0, "local")
            res["dns_from_dhcp_domain"] = dns_from_dhcp_domain.strip("/")
        except UciRecordNotFound:
            pass
        return res

    def update_settings(
            self, forwarding_enabled, dnssec_enabled, dns_from_dhcp_enabled,
            dns_from_dhcp_domain=None):

        with UciBackend() as backend:
            backend.set_option(
                "resolver", "common", "forward_upstream", store_bool(forwarding_enabled))
            backend.set_option(
                "resolver", "common", "ignore_root_key", store_bool(not dnssec_enabled))
            backend.set_option(
                "resolver", "common", "dynamic_domains", store_bool(dns_from_dhcp_enabled))
            if dns_from_dhcp_domain:
                backend.set_option(
                    "dhcp", "@dnsmasq[0]", "local", "/%s/" % dns_from_dhcp_domain.strip("/"))

        with OpenwrtServices() as services:
            services.restart("resolver")

        return True


class DnsTestCommands(AsyncCommand):

    FIELDS = ("ipv6", "ipv6_gateway", "ipv4", "ipv4_gateway", "dns", "dnssec")

    def connection_test_status(self, process_id):
        """ Get the status of some connection test
        :param process_id: test process identifier
        :type process_id: str
        :returns: data about test process
        :rtype: dict
        """

        with self.lock.readlock:
            if process_id not in self.processes:
                return {'status': 'not_found'}
            process_data = self.processes[process_id]

        exitted = process_data.get_exitted()

        data = {e: False for e in DnsTestCommands.FIELDS if e not in ['dnssec']} \
            if exitted else {}
        for record in process_data.read_all_data():
            for option, res in record["data"].items():
                data[option] = res or data.get(option, False)

        if exitted and "dnssec" not in data:
            data["dnssec"] = True

        return {'status': "finished" if process_data.get_exitted() else "running", "data": data}

    def connection_test_trigger(
            self, notify_function, exit_notify_function, reset_notify_function):
        """ Executes connection test in asyncronous mode

        This means that we don't wait for the test results. Only a test id is returned.
        This id can be used in other queries.

        :param notify_function: function which is used to send notifications back to client
        :type notify_function: callable
        :param exit_notify_function: function which is used to send notifications back to client
                                     when test exits
        :type exit_notify_function: callable
        :param reset_notify_function: function which resets notification connection
        :type reset_notify_function: callable
        :returns: test id
        :rtype: str

        """
        logger.debug("Starting connection test.")

        # generate a notification handler
        def handler_gen(regex, option, result):
            def handler(matched, process_data):
                res = {"test_id": process_data.id, "data": {option: result}}
                process_data.append_data(res)
                notify_function(res)

            return regex, handler

        # handler which will be called when the test exits
        def handler_exit(process_data):
            data = {e: False for e in DnsTestCommands.FIELDS if e not in ['dnssec']}
            for record in process_data.read_all_data():
                for option, res in record["data"].items():
                    data[option] = res or data.get(option, False)
            data["dnssec"] = data.get("dnssec", True)
            exit_notify_function({
                "test_id": process_data.id, "data": data,
                "passed": process_data.get_retval() == 0}
            )
            logger.debug("Connection test finished: (retval=%d)" % process_data.get_retval())

        process_id = self.start_process(
            ["/usr/bin/nuci-helper-checkconn"],
            [
                handler_gen(r"V6", "ipv6", True),
                handler_gen(r"GATE6", "ipv6_gateway", True),
                handler_gen(r"V4", "ipv4", True),
                handler_gen(r"GATE4", "ipv4_gateway", True),
                handler_gen(r"DNS", "dns", True),
                handler_gen(r"BADSEC", "dnssec", False),
            ],
            handler_exit,
            reset_notify_function
        )

        logger.debug("Connection test started '%s'." % process_id)
        return process_id
