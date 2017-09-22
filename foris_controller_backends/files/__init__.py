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
from foris_controller.utils import RWLock

logger = logging.getLogger(__name__)

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
