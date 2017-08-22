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

from foris_controller.modules.base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class AboutModule(BaseModule):
    logger = logging.getLogger("modules.about")

    def action_get(self, data):
        res = {}
        res.update(self.handler.get_device_info())
        res.update(self.handler.get_serial())
        res.update(self.handler.get_temperature())
        res.update(self.handler.get_sending_info())
        return res


Class = AboutModule


@wrap_required_functions([
    'get_device_info',
    'get_serial',
    'get_temperature',
    'get_sending_info',
])
class Handler(object):
    pass
