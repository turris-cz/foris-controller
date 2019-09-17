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

from foris_controller_backends.about import (
    SystemInfoCmds,
    SystemInfoFiles,
    ServerUplinkFiles,
    CryptoWrapperCmds,
)

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtAboutHandler(Handler, BaseOpenwrtHandler):

    crypto_cmds = CryptoWrapperCmds()
    system_info_cmds = SystemInfoCmds()
    system_info_files = SystemInfoFiles()
    server_uplink_files = ServerUplinkFiles()

    @logger_wrapper(logger)
    def get_device_info(self):
        """ Obtains info about the device

        :returns: result
        :rtype: dict
        """
        return {
            "model": self.system_info_files.get_model_name(),
            "kernel": self.system_info_cmds.get_kernel_version(),
            "os_version": self.system_info_files.get_os_version(),
            "os_branch": self.system_info_files.get_os_branch(),
        }

    @logger_wrapper(logger)
    def get_serial(self):
        """ Obtains serial number

        :returns: result
        :rtype: dict
        """
        return {"serial": self.crypto_cmds.get_serial()}

    @logger_wrapper(logger)
    def get_registration_number(self):
        """ Obtains registration number

        :returns: result
        :rtype: dict
        """
        return {"registration_number": self.server_uplink_files.get_registration_number()}
