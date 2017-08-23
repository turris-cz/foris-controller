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
import re


from foris_controller.app import app_info
from foris_controller.exceptions import FailedToParseFileContent
from foris_controller.utils import readlock, RWLock

logger = logging.getLogger("backends.files")


class BaseFile(object):
    def _file_content(self, path):
        logger.debug("Trying to read file '%s'" % path)
        with open(path) as f:
            content = f.read()
        logger.debug("File '%s' was successfully read." % path)
        logger.debug("content: %s" % content)
        return content

    def _read_and_parse(self, path, regex, groups=(1, )):
        content = self._file_content(path)
        match = re.search(regex, content)
        if not match:
            logger.error("Failed to parse content of '%s'." % path)
            raise FailedToParseFileContent(path, content)
        return match.group(*groups)


class SendingFiles(BaseFile):
    FW_PATH = "/tmp/firewall-turris-status.txt"
    UC_PATH = "/tmp/ucollect-status"
    file_lock = RWLock(app_info["lock_backend"])

    @readlock(file_lock, logger)
    def get_sending_info(self):
        result = {
            'firewall_status': {"working": False, "last_check": 0},
            'ucollect_status': {"working": False, "last_check": 0},
        }
        try:
            content = self._file_content(SendingFiles.FW_PATH)
            if re.search(r"turris firewall working: yes", content):
                result['firewall_status']["working"] = True
            match = re.search(r"last working timestamp: ([0-9]+)", content)
            if match:
                result['firewall_status']["last_check"] = int(match.group(1))
        except IOError:
            # file doesn't probably exists yet
            logger.warning("Failed to read file '%s'." % SendingFiles.FW_PATH)

        try:
            content = self._file_content(SendingFiles.UC_PATH)
            match = re.search(r"^(\w+)\s+([0-9]+)$", content)
            if not match:
                logger.error("Wrong format of file '%s'." % SendingFiles.UC_PATH)
            else:
                result['ucollect_status']["working"] = "online" == match.group(1)
                result['ucollect_status']["last_check"] = int(match.group(2))

        except IOError:
            # file doesn't probably exists yet
            logger.warning("Failed to read file '%s'." % SendingFiles.UC_PATH)

        return result


class SystemInfoFiles(BaseFile):
    OS_RELEASE_PATH = "/etc/turris-version"
    MODEL_PATH = "/tmp/sysinfo/model"
    BOARD_NAME_PATH = "/tmp/sysinfo/board_name"
    file_lock = RWLock(app_info["lock_backend"])

    @readlock(file_lock, logger)
    def get_os_version(self):
        return self._read_and_parse(SystemInfoFiles.OS_RELEASE_PATH, r'^([0-9]+\.[0-9]+)$', (1, ))

    @readlock(file_lock, logger)
    def get_model(self):
        return self._read_and_parse(SystemInfoFiles.MODEL_PATH, r'^(\w+ \w+).*$', (1, ))

    @readlock(file_lock, logger)
    def get_board_name(self):
        return self._read_and_parse(SystemInfoFiles.BOARD_NAME_PATH, r'^(\w+).*$', (1, ))
