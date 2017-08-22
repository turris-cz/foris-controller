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

from foris_controller.handler_base import logger_wrapper, writelock, BaseOpenwrtHandler
from foris_controller.app import app_info
from foris_controller.utils import RWLock

from foris_controller.backends.cmdline import AtshaCmds, SystemInfoCmds, TemperatureCmds
from foris_controller.backends.files import SendingFiles, SystemInfoFiles

from .. import Handler

logger = logging.getLogger("backends.mock")


class OpenwrtAboutHandler(Handler, BaseOpenwrtHandler):
    i2c_lock = RWLock(app_info["lock_backend"])

    atsha_cmds = AtshaCmds()
    temperature_cmds = TemperatureCmds()
    sending_files = SendingFiles()
    system_info_cmds = SystemInfoCmds()
    system_info_files = SystemInfoFiles()

    @logger_wrapper(logger)
    def get_device_info(self):
        return {
            "model": self.system_info_files.get_model(),
            "board_name": self.system_info_files.get_board_name(),
            "kernel": self.system_info_cmds.get_kernel_version(),
            "os_version": self.system_info_files.get_os_version(),
        }

    @writelock(i2c_lock)
    @logger_wrapper(logger)
    def get_serial(self):
        return {"serial": self.atsha_cmds.get_serial()}

    @writelock(i2c_lock)
    @logger_wrapper(logger)
    def get_temperature(self):
        return {
            "temperature": {"CPU": self.temperature_cmds.get_cpu_temperature()},
        }

    @logger_wrapper(logger)
    def get_sending_info(self):
        return self.sending_files.get_sending_info()
