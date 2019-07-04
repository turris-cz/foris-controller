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


class DnsModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        """ Get current dns settings
        :param data: supposed to be {}
        :type data: dict
        :returns: current dns settings {'forwarding_enabled': '..'}
        :rtype: dict
        """
        return self.handler.get_settings()

    def action_update_settings(self, data):
        """ Updates dns settings
        :param data: new dns settings {'forwarding_enabled': '..'}
        :type data: dict
        :returns: result of the update {'result': '..'}
        :rtype: dict
        """
        res = self.handler.update_settings(**data)
        if res:
            self.notify("update_settings", data)
        return {"result": res}

    def action_list_forwarders(self, data):
        """ lists forwarders
        :param data: new dns settings {}
        :type data: dict
        :returns: result of the update {"forwarders": [{"name": "00_nic", ...}, ...]}
        :rtype: dict
        """
        return {"forwarders": self.handler.list_forwarders()}

    def action_set_forwarder(self, data):
        """ set forwarder
        :param data: forwarder settings {"name": "XXX", ...}
        :type data: dict
        :returns: result of the update {"result": True/False}
        :rtype: dict
        """
        res = self.handler.set_forwarder(**data)
        if res:
            self.notify("set_forwarder", data)
        return {"result": res}

    def action_del_forwarder(self, data):
        """ del forwarder
        :param data: forwarder settings {"name": "XXX"}
        :type data: dict
        :returns: result of the update {"result": True/False}
        :rtype: dict
        """
        res = self.handler.del_forwarder(**data)
        if res:
            self.notify("del_forwarder", data)
        return {"result": res}


@wrap_required_functions(
    ["get_settings", "update_settings", "list_forwarders", "set_forwarder", "del_forwarder"]
)
class Handler(object):
    pass
