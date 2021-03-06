#
# foris-controller
# Copyright (C) 2017-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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


class AboutModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get(self, data):
        """ Performs get action to obtain data from the device

        :param data: input data (supposed to be {})
        :type data: dict
        :returns: response to request
        :rtype: dict
        """
        res = {}
        res.update(self.handler.get_device_info())
        res.update(self.handler.get_serial())
        customization = self.handler.get_customization()
        if customization:
            res["customization"] = customization

        return res

    def action_get_registration_number(self, data):
        """ Obtains registration number

        :param data: input data (supposed to be {})
        :type data: dict
        :returns: registration_number or False
        :rtype: dict
        """
        return self.handler.get_registration_number()


@wrap_required_functions(["get_device_info", "get_serial", "get_registration_number"])
class Handler(object):
    pass
