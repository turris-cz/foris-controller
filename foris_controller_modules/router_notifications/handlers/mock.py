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

import logging

from datetime import datetime

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockRouterNotificationsHandler(Handler, BaseMockHandler):
    notifications = [
        {
            "displayed": False,
            "id": "1518776436-2593",
            "severity": "restart",
            "messages": {
                "cs": "REBOOT1 CS",
                "en": "REBOOT1 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2598",
            "severity": "restart",
            "messages": {
                "cs": "REBOOT2 CS",
                "en": "REBOOT2 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2603",
            "severity": "news",
            "messages": {
                "cs": "NEWS1 CS",
                "en": "NEWS1 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2608",
            "severity": "news",
            "messages": {
                "cs": "NEWS2 CS",
                "en": "NEWS2 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2613",
            "severity": "error",
            "messages": {
                "cs": "ERROR1 CS",
                "en": "ERROR1 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2618",
            "severity": "error",
            "messages": {
                "cs": "ERROR2 CS",
                "en": "ERROR2 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2623",
            "severity": "update",
            "messages": {
                "cs": "UPDATE1 CS",
                "en": "UPDATE1 EN"
            }
        },
        {
            "displayed": False,
            "id": "1518776436-2628",
            "severity": "update",
            "messages": {
                "cs": "UPDATE2 CS",
                "en": "UPDATE2 EN"
            }
        }
    ]

    @logger_wrapper(logger)
    def list(self, lang):
        res = []
        for notification in self.notifications:
            new = {
                "id": notification["id"],
                "displayed": notification["displayed"],
                "severity": notification["severity"],
                "created_at": datetime.fromtimestamp(
                    int(notification['id'].split("-")[0])).isoformat()
            }
            msg = notification["messages"].get(lang, None)
            if msg:
                new["msg"] = msg
                new["lang"] = lang
            else:
                # english fallback
                msg = notification["messages"].get("en", None)
                if msg:
                    new["msg"] = msg
                    new["lang"] = "en"
                else:
                    raise KeyError(lang)  # this should not happen
            res.append(new)
        return res
