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
import random

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockAboutHandler(Handler, BaseMockHandler):
    @logger_wrapper(logger)
    def get_device_info(self):
        """ Returns fake info about the device

        :returns: Mocked result
        :rtype: dict
        """
        return {
            "model": "Turris Omnia",
            "kernel": "4.4.77-967673b9d511e4292e3bcb76c9e064bc-0",
            "os_version": "3.7",
            "os_branch": {
                "mode": "branch",
                "value": "hbk",
            },
        }

    @logger_wrapper(logger)
    def get_serial(self):
        """ Returns fake serial number

        :returns: Mocked result
        :rtype: dict
        """
        return {"serial": "0000000B00009CD6"}

    @logger_wrapper(logger)
    def get_registration_number(self):
        """ Returns fake registration number

        :returns: Mocked result
        :rtype: dict
        """
        return {"registration_number": "%016X" % random.randrange(2 ** 16)}
