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

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class LanModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data: dict) -> dict:
        """ Get current lan settings
        :param data: supposed to be {}
        :returns: current lan settings
        """
        return self.handler.get_settings()

    def action_update_settings(self, data: dict) -> dict:
        """ Updates lan settings
        :param data: new lan settings
        :returns: result of the update {'result': True/False}
        """
        res = self.handler.update_settings(data)
        if res:
            self.notify("update_settings", data)
        return {"result": res}

    def action_set_dhcp_client(self, data: dict) -> dict:
        """ Updates configuration of a single dhcp client
        :param: data: client data to be set
        :returns: result of the update {'result': True/False}
        """
        res = self.handler.set_dhcp_client(**data)
        if res["result"]:
            self.notify("set_dhcp_client", data)
        return res


@wrap_required_functions(["get_settings", "update_settings", "set_dhcp_client"])
class Handler(object):
    pass
