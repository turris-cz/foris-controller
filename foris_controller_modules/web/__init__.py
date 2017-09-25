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

    def action_get_language(self, data):
        """ Get current language of the web gui
        :param data: supposed to be {}
        :type data: dict
        :returns: current language {'language': '..'}
        :rtype: dict
        """
        return {'language': self.handler.get_language()}

    def action_set_language(self, data):
        """ Sets language of the web gui
        :param data: supposed to be {'language': '..'}
        :type data: dict
        :returns: current language {'result': true}
        :rtype: dict
        """
        return {'result': self.handler.set_language(data['language'])}

    def action_list_languages(self, data):
        """ Returns a list of available languages
        :param data: supposed to be {}
        :type data: dict
        :returns: current language {'languages': ['en', 'cs', ..]}
        :rtype: dict
        """
        return {'languages': self.handler.list_languages()}


Class = WebModule


@wrap_required_functions([
    'get_language',
    'set_language',
    'list_languages',
])
class Handler(object):
    pass
