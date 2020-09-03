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

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper
from foris_controller_backends.system import SystemUciCommands

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtSystemHandler(Handler, BaseOpenwrtHandler):
    uci = SystemUciCommands()

    @logger_wrapper(logger)
    def get_hostname(self) -> str:
        return self.uci.get_hostname()

    @logger_wrapper(logger)
    def set_hostname(self, hostname: str) -> bool:
        return self.uci.set_hostname(hostname)
