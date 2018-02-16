#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import json
import logging

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller.exceptions import (
    BackendCommandFailed, FailedToParseCommandOutput
)

logger = logging.getLogger(__name__)


class RouterNotificationsCmds(BaseCmdLine):
    def list(self):
        """ Lists notifications

        :returns: list of notifications in following format
                [
                    {
                        "id": "1234567-1234",
                        "displayed": True/False,
                        "severity": "restart/news/error/update",
                        "messages": {
                            "cs": "msg in cs",
                            "en": "msg in en",
                        }
                    },
                    ...
                ]
        :rtype: list
        """
        args = ("/usr/bin/list_notifications", "-n")
        retval, stdout, _ = self._run_command(*args)
        if not retval == 0:
            logger.error("Command %s failed." % str(args))
            raise BackendCommandFailed(retval, args)

        try:
            parsed = json.loads(stdout.strip())
        except ValueError:
            raise FailedToParseCommandOutput(args, stdout)
        return parsed
