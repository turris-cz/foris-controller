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


class WebModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_data(self, data):
        """ Get data required by the the web gui
        :param data: supposed to be {}
        :type data: dict
        :returns: current data {'language': '..'}
        :rtype: dict
        """
        return {
            'language': self.handler.get_language(),
            'reboot_required': self.handler.reboot_required(),
            'updater_running': self.handler.updater_running(),
            'notification_count': self.handler.get_notification_count(),
            'guide': self.handler.get_guide(),
            'password_ready': self.handler.is_password_set(),
        }

    def action_set_language(self, data):
        """ Sets language of the web gui
        :param data: supposed to be {'language': '..'}
        :type data: dict
        :returns: current language {'result': true}
        :rtype: dict
        """
        res = self.handler.set_language(data['language'])
        if res:
            self.notify("set_language", data)
        return {'result': res}

    def action_list_languages(self, data):
        """ Returns a list of available languages
        :param data: supposed to be {}
        :type data: dict
        :returns: current language {'languages': ['en', 'cs', ..]}
        :rtype: dict
        """
        return {'languages': self.handler.list_languages()}

    def action_update_guide(self, data):
        """ Update current guide settings
        :param data: supposed to be {"enabled": True/False, "workflow": "standard"}
        :type data: dict
        :returns: {'result': true}
        :rtype: dict
        """
        return {"result": self.handler.update_guide(**data)}


@wrap_required_functions([
    'get_language',
    'set_language',
    'list_languages',
    'reboot_required',
    'updater_running',
    'get_notification_count',
    'update_guide',
    'get_guide',
    'is_password_set',
])
class Handler(object):
    pass
