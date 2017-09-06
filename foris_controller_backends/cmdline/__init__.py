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

import subprocess

from foris_controller.app import app_info
from foris_controller.exceptions import BackendCommandFailed, FailedToParseCommandOutput
from foris_controller.utils import RWLock, writelock
from foris_controller_backends.files import server_uplink_lock


logger = logging.getLogger(__name__)

i2c_lock = RWLock(app_info["lock_backend"])


class BaseCmdLine(object):

    def _run_command_in_background(self, *args):
        """ Executes command in background

        :param args: cmd and its arguments
        :type args: tuple
        """
        logger.debug("Starting Command '%s' is starting." % str(args))
        subprocess.Popen(args)

    def _run_command(self, *args):
        """ Executes command and waits till it's finished

        :param args: cmd and its arguments
        :type args: tuple

        :returns: (retcode, stdout, stderr)
        :rtype: (int, str, str)
        """

        logger.debug("Command '%s' is starting." % str(args))
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        logger.debug("Command '%s' finished." % str(args))
        logger.debug("retcode: %d" % process.returncode)
        logger.debug("stdout: %s" % stdout)
        logger.debug("stderr: %s" % stderr)
        return process.returncode, stdout, stderr

    def _trigger_and_parse(self, args, regex, groups=(1, )):
        """ Runs command and parses the output by regex,
            raises an exception when the output doesn't match regex

        :param args: command and arguments
        :type args: tuple
        :param regex: regular expression to match
        :type regex: str
        :param groups: groups which will be returned from the matching regex
        :type groups: tuple of int
        :returns: matching strings
        :rtype: tuple
        """
        retval, stdout, _ = self._run_command(*args)
        if not retval == 0:
            logger.error("Command %s failed." % str(args))
            raise BackendCommandFailed(retval, args)
        match = re.search(regex, stdout)
        if not match:
            logger.error("Failed to parse output of %s." % str(args))
            raise FailedToParseCommandOutput(args, stdout)
        return match.group(*groups)


class AtshaCmds(BaseCmdLine):
    @writelock(i2c_lock, logger)
    def get_serial(self):
        """ Obrains serial number

        :returns: serial number
        :rtype: str
        """
        return self._trigger_and_parse(
            ("atsha204cmd", "serial-number"), r'^([0-9a-fA-F]{16})$', (1, ))


class TemperatureCmds(BaseCmdLine):
    @writelock(i2c_lock, logger)
    def get_cpu_temperature(self):
        """ Obtains temperature from the cpu

        :returns: temperature of cpu
        :rtype: int
        """
        return int(self._trigger_and_parse(
            ("thermometer", ), r'^CPU:\s+([0-9]+)$', (1, )))


class SystemInfoCmds(BaseCmdLine):
    def get_kernel_version(self):
        """ Obtains kernel version

        :returns: kernel version
        :rtype: str
        """
        return self._trigger_and_parse(("uname", "-r"), r'^([^\s]+)$', (1, ))


class ServerUplinkCmds(BaseCmdLine):
    @writelock(server_uplink_lock, logger)
    def update_contract_status(self):
        """ Updates contract status
        """
        self._run_command_in_background("/usr/share/server-uplink/contract_valid.sh")


class RegisteredCmds(BaseCmdLine):

    def get_registered(self, email, language):
        """ Returns registration status
        :param email: email which will be used in the server query
        :type email: str
        :param language: language which will be used in the server query (en/cs)
        :type language: str

        :returns: registration status and sometimes registration url
        :rtype: dict
        """

        # get registration code
        from foris_controller_backends.files import ServerUplinkFiles
        registration_code = ServerUplinkFiles().get_registration_number()
        if not registration_code:
            # failed to obtain registration code
            return {"status": "unknown"}
        retcode, stdout, _ = self._run_command(
            "/usr/share/server-uplink/registered.sh",
            email, language
        )
        if not retcode == 0:
            # cmd failed (e.g. connection failed)
            return {"status": "unknown"}

        # code field should be present
        code_re = re.search(r"code: ([0-9]+)", stdout)
        http_code = int(code_re.group(1))
        if http_code != 200:
            return {"status": "not_found"}

        # status should be present
        status_re = re.search(r"status: (\w+)", stdout)
        status = status_re.group(1)

        if status == "owned":
            return {"status": status}
        elif status in ["free", "foreign"]:
            url_re = re.search(r"url: ([^\s]+)", stdout)
            url = url_re.group(1)
            return {
                "status": status, "url": url,
                "registration_number": registration_code,
            }

        return {"status": "unknown"}
