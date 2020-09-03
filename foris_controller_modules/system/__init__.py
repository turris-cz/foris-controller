#
# foris-controller
# Copyright (C) 2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
from typing import Dict

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class SystemModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_hostname(self, data: dict) -> Dict[str, str]:
        """ Get hostname setting. """
        hostname = self.handler.get_hostname()
        return {"hostname": hostname}

    def action_set_hostname(self, data: dict) -> object:
        """ Set hostname setting. """
        res = self.handler.set_hostname(data['hostname'])
        return {"result": res}


@wrap_required_functions(["get_hostname", "set_hostname"])
class Handler:
    pass
