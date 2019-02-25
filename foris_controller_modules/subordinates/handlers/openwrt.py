#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.subordinates import (
    SubordinatesUci, SubordinatesComplex, SubordinatesService
)

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtSubordinatesHandler(Handler, BaseOpenwrtHandler):

    uci = SubordinatesUci()
    complex = SubordinatesComplex()
    service = SubordinatesService()

    @logger_wrapper(logger)
    def list_subordinates(self):
        return OpenwrtSubordinatesHandler.uci.list_subordinates()

    @logger_wrapper(logger)
    def add_subordinate(self, token):
        return OpenwrtSubordinatesHandler.complex.add_subordinate(token)

    @logger_wrapper(logger)
    def del_subordinate(self, controller_id):
        return OpenwrtSubordinatesHandler.complex.del_subordinate(controller_id)

    @logger_wrapper(logger)
    def set_subordinate(self, controller_id, enabled, custom_name):
        return OpenwrtSubordinatesHandler.uci.set_subordinate(controller_id, enabled, custom_name)

    @logger_wrapper(logger)
    def add_subsubordinate(self, controller_id: str, via: str) -> bool:
        return OpenwrtSubordinatesHandler.uci.add_subsubordinate(controller_id, via)

    @logger_wrapper(logger)
    def set_subsubordinate(self, controller_id, enabled, custom_name) -> bool:
        return OpenwrtSubordinatesHandler.uci.set_subsubordinate(
            controller_id, enabled, custom_name
        )

    @logger_wrapper(logger)
    def del_subsubordinate(self, controller_id) -> bool:
        return OpenwrtSubordinatesHandler.uci.del_subsubordinate(controller_id)

    @logger_wrapper(logger)
    def restart_mqtt(self):
        OpenwrtSubordinatesHandler.service.restart()
