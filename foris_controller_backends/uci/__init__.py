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

import collections
import logging
import os
import re
import subprocess

from foris_controller.utils import RWLock

from foris_controller.app import app_info
from foris_controller.exceptions import UciException, UciTypeException

logger = logging.getLogger(__name__)


def parse_bool(value):
    if value in ("1", "on", "true", "yes", "enabled"):
        return True
    elif value in ("0", "off", "false", "no", "disabled"):
        return False
    raise UciTypeException(value, ['bool'])


class UciBackend(object):
    CHANGES_DIR = "/tmp/.uci-foris-controller"
    DEFAULT_CONFIG_DIR = "/etc/config/"
    uci_lock = RWLock(app_info["lock_backend"])

    def __init__(self, config_dir=DEFAULT_CONFIG_DIR):
        self.affected_configs = set()
        self.config_dir = config_dir

    def _cleanup(self):
        logger.debug("Clearing %s." % UciBackend.CHANGES_DIR)
        try:
            os.makedirs(UciBackend.CHANGES_DIR)
        except OSError:
            pass
        for file_path in os.listdir(UciBackend.CHANGES_DIR):
            os.remove(os.path.join(UciBackend.CHANGES_DIR, file_path))

    def __enter__(self):
        logger.debug("Starting uci transaction.")
        UciBackend.uci_lock.writelock.acquire()
        logger.debug("UCI lock obtained.")
        self._cleanup()
        return self

    def __exit__(self, exc_type, value, traceback):
        logger.debug("UCI lock released.")
        if exc_type is None:
            if self.affected_configs:
                self.commit()
            logger.debug("Uci transaction ended.")
        else:
            logger.error("Uci transaction terminated.")
        UciBackend.uci_lock.writelock.release()

    def _run_uci_command(self, *args, **kwargs):
        """
        :return: command output
        :rtype: str
        """
        fail_on_error = kwargs['fail_on_error'] if 'fail_on_error' in kwargs else True
        changes_path_option = "-p" if args[0] == "commit" else "-P"
        cmdline_args = [
            "uci", "-c", self.config_dir, changes_path_option, UciBackend.CHANGES_DIR
        ] + list(args)
        logger.debug("uci cmd '%s'" % str(args))
        process = subprocess.Popen(cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        logger.debug("retcode: %d" % process.returncode)
        logger.debug("stdout: %s" % stdout)
        logger.debug("stderr: %s" % stderr)
        if fail_on_error and process.returncode:
            raise UciException(cmdline_args, stderr)
        return stdout

    def add_section(self, config, section_type, section_name=None):
        """
        :param section_name: for anonymous leave
        :returns: section name if section is anonymous
        """
        retval = None
        if section_name is None:
            retval = self._run_uci_command("add", config, section_type, fail_on_error=False)
        else:
            self._run_uci_command(
                "set", "%s.%s=%s" % (config, section_name, section_type))

        self.affected_configs.add(config)
        return retval
        # return section name if anonymous

    def del_section(self, config, section_name):
        """
        :param section_name: anonymous or named (@anonymous[1], named)
        """
        self._run_uci_command("delete", "%s.%s" % (config, section_name))
        self.affected_configs.add(config)

    def set_option(self, config, section_name, option_name, value):
        self._run_uci_command("set", "%s.%s.%s=%s" % (config, section_name, option_name, value))
        self.affected_configs.add(config)

    def del_option(self, config, section_name, option_name):
        self._run_uci_command("delete", "%s.%s.%s" % (config, section_name, option_name))
        self.affected_configs.add(config)

    def add_to_list(self, config, section_name, list_name, values):
        """
        merges with previous values
        """
        for value in values:
            self._run_uci_command(
                "add_list", "%s.%s.%s=%s" % (config, section_name, list_name, value))

        self.affected_configs.add(config)

    def del_from_list(self, config, section_name, list_name, values=None):
        """
        deletes values from the list if values is set else delete whole list
        """
        if values:
            for value in values:
                self._run_uci_command(
                    "del_list", "%s.%s.%s=%s" % (config, section_name, list_name, value))
        else:
            self._run_uci_command("delete", "%s.%s.%s" % (config, section_name, list_name))
        self.affected_configs.add(config)

    def commit(self):
        logger.debug("Preparing commit for configs %s" % ", ".join(self.affected_configs))
        for config in self.affected_configs:
            self._run_uci_command("commit", config)
            # This revert should clean the changes directory
            self._run_uci_command("revert", config)
        logger.debug("Uci configs updates were commited.")

    def _parse_section(self, lines):
        result = collections.OrderedDict()
        try:
            while True:
                if lines[0].startswith("package") or lines[0].startswith("config"):
                    break

                match = re.match(r"^\s*option ([^\s]+) '([^']+)'$", lines[0])
                if match:
                    result[match.group(1)] = match.group(2)
                else:
                    match = re.match(r"^\s*list ([^\s]+) '([^']+)'$", lines[0])
                    if match:
                        list_name, value = match.group(1, 2)
                        result[list_name] = result.get(list_name, [])
                        result[list_name].append(value)
                lines.pop(0)

        except IndexError:
            pass

        return result

    def _parse_package(self, lines):
        result = []
        try:
            while True:
                if lines[0].startswith("config"):
                    line = lines.pop(0)
                    section_name = None
                    section_type = None
                    matched = re.match(r"^config ([^\s]+) '([^\s]+)'$", line)
                    if matched:
                        section_type, section_name = matched.group(1, 2)
                    else:
                        matched = re.match(r"^config ([^\s]+)$", line)
                        section_type = matched.group(1)
                    section = {
                        "type": section_type, "name": section_name,
                        "data": self._parse_section(lines),
                    }
                    result.append(section)
                elif lines[0].startswith("package"):
                    # next package
                    break
                else:
                    line = lines.pop(0)
        except IndexError:
            pass

        return result

    def _parse_packages(self, lines):
        """
        :param lines: lines of the export output
        :type lines: list
        """
        result = {}
        if not lines:
            return result
        try:
            while True:
                package_line = lines.pop(0)
                while not package_line.startswith("package"):
                    package_line = lines.pop(0)
                result[re.match(r"^package ([^\s]+)$", package_line).group(1)] = \
                    self._parse_package(lines)

        except IndexError:
            pass

        return result

    def read(self, config=None):
        output = self._run_uci_command("export", config) if config \
            else self._run_uci_command("export")
        lines = output.splitlines()
        return self._parse_packages(lines)
