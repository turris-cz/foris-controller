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

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions
from foris_controller.utils import check_dynamic_ranges


class GuestModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        """ Get current guest settings
        :param data: supposed to be {}
        :type data: dict
        :returns: current guest settings
        :rtype: dict
        """
        return self.handler.get_settings()

    def action_update_settings(self, data):
        """ Updates guest settings
        :param data: new guest settings
        :type data: dict
        :returns: result of the update {'result': True/False}
        :rtype: dict
        """
        if (
            data["enabled"]
            and data["dhcp"]["enabled"]
            and not check_dynamic_ranges(
                data["ip"], data["netmask"], data["dhcp"]["start"], data["dhcp"]["limit"]
            )
        ):
            res = False
        else:
            res = self.handler.update_settings(data)
            if res:
                self.notify("update_settings", data)
        return {"result": res}


@wrap_required_functions(["get_settings", "update_settings"])
class Handler(object):
    pass
