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


class RouterNotificationsModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_list(self, data):
        """ Displays current notifications

        :param data: input data (supposed to be {"lang": "en/cs/.."})
        :type data: dict
        :returns: response to request
        :rtype: dict
        """
        return {"notifications": self.handler.list(data["lang"])}


@wrap_required_functions([
    'list',
])
class Handler(object):
    pass
