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
