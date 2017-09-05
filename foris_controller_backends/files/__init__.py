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

server_uplink_lock = RWLock(app_info["lock_backend"])


class BaseFile(object):
    def _file_content(self, path):
        """ Returns a content of a file

        :param path: path to the file
        :type path: str

        :returns: file content
        :rtype: str
        """
        logger.debug("Trying to read file '%s'" % path)
        with open(path) as f:
            content = f.read()
        logger.debug("File '%s' was successfully read." % path)
        logger.debug("content: %s" % content)
        return content

    def _read_and_parse(self, path, regex, groups=(1, )):
        """ Reads and parses a content of the file by regex,
            raises an exception when the output doesn't match regex

        :param path: path to the file
        :type path: str
        :param regex: regular expression to match
        :type regex: str
        :param groups: groups which will be returned from the matching regex
        :type groups: tuple of int
        :returns: matching strings
        :rtype: tuple
        """
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
    STATE_ONLINE = "online"
    STATE_OFFLINE = "offline"
    STATE_UNKNOWN = "unknown"

    @readlock(file_lock, logger)
    def get_sending_info(self):
        """ Returns sending info

        :returns: sending info
        :rtype: dict
        """
        result = {
            'firewall_status': {"state": SendingFiles.STATE_UNKNOWN, "last_check": 0},
            'ucollect_status': {"state": SendingFiles.STATE_UNKNOWN, "last_check": 0},
        }
        try:
            content = self._file_content(SendingFiles.FW_PATH)
            if re.search(r"turris firewall working: yes", content):
                result['firewall_status']["state"] = SendingFiles.STATE_ONLINE
            else:
                result['firewall_status']["state"] = SendingFiles.STATE_OFFLINE
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
                if match.group(1) == "online":
                    result['ucollect_status']["state"] = SendingFiles.STATE_ONLINE
                else:
                    result['ucollect_status']["state"] = SendingFiles.STATE_OFFLINE
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
        """ Returns turris os version

        :returns: os version
        :rtype: str
        """
        return self._read_and_parse(SystemInfoFiles.OS_RELEASE_PATH, r'^([0-9]+\.[0-9]+)$', (1, ))

    @readlock(file_lock, logger)
    def get_model(self):
        """ Returns model of the device

        :returns: model
        :rtype: str
        """
        return self._read_and_parse(SystemInfoFiles.MODEL_PATH, r'^(\w+ \w+).*$', (1, ))

    @readlock(file_lock, logger)
    def get_board_name(self):
        """ Returns board name

        :returns: board name
        :rtype: str
        """
        return self._read_and_parse(SystemInfoFiles.BOARD_NAME_PATH, r'^(\w+).*$', (1, ))


class ServerUplinkFiles(BaseFile):
    REGNUM_PATH = "/usr/share/server-uplink/registration_code"
    CONTRACT_PATH = "/usr/share/server-uplink/contract_valid"

    @readlock(server_uplink_lock, logger)
    def get_registration_number(self):
        """ Returns registration number

        :returns: registration number
        :rtype: str
        """
        try:
            res = self._read_and_parse(ServerUplinkFiles.REGNUM_PATH, r'^([a-zA-Z0-9]{16})$', (1, ))
        except:
            # failed to read file -> return False
            res = False

        return res

    @readlock(server_uplink_lock, logger)
    def get_contract_status(self):
        """ Returns contract status

        :returns: contract status
        :rtype: str
        """
        try:
            res = self._read_and_parse(ServerUplinkFiles.CONTRACT_PATH, r'^(\w+)$', (1, ))
            res = "not_valid" if res != "valid" else "valid"
        except:
            # failed to read file -> return None
            res = "unknown"
        return res
