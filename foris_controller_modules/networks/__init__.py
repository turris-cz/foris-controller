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

import copy
import logging

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class NetworksModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        """ Get current networks settings
        :param data: supposed to be {}
        :type data: dict
        :returns: current networks settings
        :rtype: dict
        """
        return self.handler.get_settings()

    def action_update_settings(self, data):
        """ Updates networks settings
        :param data: new networks settings
        :type data: dict
        :returns: result of the update {'result': True/False}
        :rtype: dict
        """
        orig_data = copy.deepcopy(data)
        res = self.handler.update_settings(data)
        if res:
            self.notify("update_settings", orig_data)
        return {"result": res}


@wrap_required_functions(["get_settings", "update_settings"])
class Handler(object):
    pass
