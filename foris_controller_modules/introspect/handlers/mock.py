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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)

FORIS_CONTROLLER_MODULES = [
    "about",
    "diagnostics",
    "dns",
    "guest",
    "introspect",
    "lan",
    "maintain",
    "networks",
    "password",
    "remote",
    "router_notifications",
    "storage",
    "time",
    "updater",
    "wan",
    "web",
    "wifi"
]


class MockIntrospectHandler(Handler, BaseMockHandler):
    @staticmethod
    @logger_wrapper(logger)
    def list_modules():
        return FORIS_CONTROLLER_MODULES
