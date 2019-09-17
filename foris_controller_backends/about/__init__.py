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

from foris_controller.app import app_info
from foris_controller.utils import writelock, readlock, RWLock
from foris_controller_backends.cmdline import BaseCmdLine, i2c_lock
from foris_controller_backends.files import server_uplink_lock, BaseFile
from foris_controller_backends.uci import UciBackend, get_option_named

logger = logging.getLogger(__name__)


class CryptoWrapperCmds(BaseCmdLine):
    @writelock(i2c_lock, logger)
    def get_serial(self):
        """ Obrains serial number

        :returns: serial number
        :rtype: str
        """
        return self._trigger_and_parse(
            ("/usr/bin/crypto-wrapper", "serial-number"), r"^([0-9a-fA-F]{16})$", (1,)
        )


class SystemInfoCmds(BaseCmdLine):
    def get_kernel_version(self):
        """ Obtains kernel version

        :returns: kernel version
        :rtype: str
        """
        return self._trigger_and_parse(("/bin/uname", "-r"), r"^([^\s]+)$", (1,))


class SystemInfoFiles(BaseFile):
    OS_RELEASE_PATH = "/etc/turris-version"
    MODEL_PATH = "/tmp/sysinfo/model"
    file_lock = RWLock(app_info["lock_backend"])

    @readlock(file_lock, logger)
    def get_os_version(self):
        """ Returns turris os version

        :returns: os version
        :rtype: str
        """
        return self._read_and_parse(SystemInfoFiles.OS_RELEASE_PATH, r"^([0-9]+(\.[0-9]+)*)$", (1,))

    def get_os_branch(self):
        """ Returns turris os branch

        :returns: os branch or version
        :rtype: dict
        """
        with UciBackend() as backend:
            updater_data = backend.read("updater")

        mode = get_option_named(updater_data, "updater", "turris", "mode")
        value = get_option_named(updater_data, "updater", "turris", mode, "unknown")

        return {"mode": mode, "value": value}

    @readlock(file_lock, logger)
    def get_model_name(self):
        """ Returns model of the device

        :returns: model
        :rtype: str
        """
        return self._read_and_parse(SystemInfoFiles.MODEL_PATH, r"^(\w+.*)$", (1,))

    def get_model(self):
        """ display standartized model name (omnia/mox/turris)
        """
        repr_model = self.get_model_name()
        if "Omnia" in repr_model:
            return "omnia"
        elif "Mox" in repr_model:
            return "mox"
        return "turris"


class ServerUplinkFiles(BaseFile):
    REGNUM_PATH = "/usr/share/server-uplink/registration_code"

    @readlock(server_uplink_lock, logger)
    def get_registration_number(self):
        """ Returns registration number

        :returns: registration number
        :rtype: str
        """
        try:
            res = self._read_and_parse(ServerUplinkFiles.REGNUM_PATH, r"^([a-zA-Z0-9]{16})$", (1,))
        except:
            # failed to read file -> return False
            res = False

        return res
