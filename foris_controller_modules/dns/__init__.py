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

    def action_connection_test_trigger(self, data):
        """ Triggers connectio test
        :param data: supposed to be {}
        :type data: dict
        :returns: dict containing test id {'test_id': 'xxxx'}
        :rtype: dict
        """

        # wrap action into notify function
        def notify(msg):
            self.notify("connection_test", msg)

        def exit_notify(msg):
            self.notify("connection_test_finished", msg)

        return {
            "test_id": self.handler.connection_test_trigger(
                notify, exit_notify, self.reset_notify)
        }

    def action_connection_test_status(self, data):
        """ Reads connectio test data
        :param data: supposed to be {'test_id': 'xxxx'}
        :type data: dict
        :returns: data about connection test {'status': 'xxxx', 'data': {...}}
        :rtype: dict
        """
        return self.handler.connection_test_status(data['test_id'])


@wrap_required_functions([
    'get_settings',
    'update_settings',
    'connection_test_trigger',
    'connection_test_status',
])
class Handler(object):
    pass
