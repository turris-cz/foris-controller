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
import os

from foris_controller.app import app_info
from foris_controller.exceptions import ServiceCmdFailed
from foris_controller.utils import RWLock

from foris_controller_backends.cmdline import handle_command


logger = logging.getLogger(__name__)


class OpenwrtServices(object):
    DEFAUL_SERVICE_SCRIPTS_PATH = '/etc/init.d/'

    services_lock = RWLock(app_info["lock_backend"])

    def __init__(self, service_scripts_path=DEFAUL_SERVICE_SCRIPTS_PATH):
        self.service_scripts_path = service_scripts_path

    def __enter__(self):
        logger.debug("Starting interaction with OpenWRT services.")
        OpenwrtServices.services_lock.writelock.acquire()
        logger.debug("Service lock obtained.")
        return self

    def __exit__(self, exc_type, value, traceback):
        OpenwrtServices.services_lock.writelock.release()
        logger.debug("Service lock released.")

    def _run_service_command(self, service_name, cmd, fail_on_error=True):
        """ Executes a service task and waits till it's finished

        :param service_name: the name of the service
        :type service_name: str
        :param cmd: service command
        :type cmd: str
        """
        script_path = os.path.join(self.service_scripts_path, service_name)
        logger.debug("Starting to call '%s %s'" % (script_path, cmd))
        try:
            retval, stdout, stderr = handle_command(script_path, cmd)

        except OSError as e:
            raise ServiceCmdFailed(
                service_name, cmd, "unable to call '%s %s'" % (script_path, cmd))
        logger.debug("'%s %s' was finished" % (script_path, cmd))
        logger.debug("retcode: %d" % retval)
        logger.debug("stdout: %s" % stdout)
        logger.debug("stderr: %s" % stderr)

        if fail_on_error and retval != 0:
            raise ServiceCmdFailed(service_name, cmd)

    def start(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "start", fail_on_error)

    def stop(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "stop", fail_on_error)

    def restart(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "restart", fail_on_error)

    def reload(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "reload", fail_on_error)

    def enable(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "enable", fail_on_error)

    def disable(self, service_name, fail_on_error=True):
        self._run_service_command(service_name, "disable", fail_on_error)
