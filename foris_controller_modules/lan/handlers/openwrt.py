#
# foris-controller
# Copyright (C) 2017-2024 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper
from foris_controller_backends.lan import LanUci

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtLanHandler(Handler, BaseOpenwrtHandler):
    uci = LanUci()

    @logger_wrapper(logger)
    def get_settings(self):
        """ get lan settings

        :returns: current lan settings
        :rtype: dict
        """
        return self.uci.get_settings()

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ updates current lan settings

        :param new_settings: new settings dictionary
        :type new_settings: dict

        :return: True if update passes
        :rtype: boolean
        """
        return self.uci.update_settings(**new_settings)

    @logger_wrapper(logger)
    def set_dhcp_client(self, ip: str, mac: str, hostname: str) -> dict:
        """ Sets configuration of a single dhcp client
        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: {"result": True} if update passes {"result": False, "reason": "..."} otherwise
        """
        err = self.uci.set_dhcp_client(ip, mac, hostname)
        if err:
            return {"result": False, "reason": err}

        return {"result": True}

    @logger_wrapper(logger)
    def update_dhcp_client(self, ip: str, old_mac: str, mac: str, hostname: str) -> dict:
        """Update configuration of a single dhcp client
        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: {"result": True} if update passes {"result": False, "reason": "..."} otherwise
        """
        err = self.uci.update_dhcp_client(ip, old_mac, mac, hostname)
        if err:
            return {"result": False, "reason": err}

        return {"result": True}

    @logger_wrapper(logger)
    def delete_dhcp_client(self, mac: str) -> dict:
        """Delete configuration of a single dhcp client """
        err = self.uci.delete_dhcp_client(mac)
        if err:
            return {"result": False, "reason": err}

        return {"result": True}

    @logger_wrapper(logger)
    def get_forwardings(self) -> list:
        """ Returns all current forwardings
        :rtype: List[dict]
        """
        return self.uci.get_forwardings()

    @logger_wrapper(logger)
    def update_forwardings(self, data) -> dict:
        """ Updates lan forwarding rules
        :param data: new forwarding settings
        :returns: {'result': True} or {'result': False, 'reason': [...]}
        """
        err = self.uci.update_forwardings(**data)
        if len(err) > 0:
            return {"result": False, "reason": err}
        else:
            return {"result": True}
