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
import updater

from foris_controller_backends.uci import (
    UciBackend, get_option_named, parse_bool
)
from foris_controller.exceptions import UciRecordNotFound

logger = logging.getLogger(__name__)


class UpdaterUci(object):

    def get_settings(self):

        with UciBackend() as backend:
            updater_data = backend.read("updater")

        res = {
            "enabled": not parse_bool(
                get_option_named(updater_data, "updater", "override", "disable", "0")
            ),
            "branch": get_option_named(updater_data, "updater", "override", "branch", ""),
            "user_lists": get_option_named(updater_data, "updater", "pkglists", "lists", []),
            "required_languages": get_option_named(updater_data, "updater", "l10n", "langs", []),
            "approvals": {
                "status": "on" if parse_bool(
                    get_option_named(updater_data, "updater", "approvals", "need", "0"),
                ) else "off"
            }
        }

        try:
            delay_seconds = int(get_option_named(
                updater_data, "updater", "approvals", "auto_grant_seconds"))
            delay_hours = delay_seconds / (60 * 60)
            res["approvals"]["delay"] = delay_hours
            if res["approvals"]["status"] == "on":
                res["approvals"]["status"] = "delayed"
        except UciRecordNotFound:
            pass

        return res


class Updater(object):
    def updater_running(self):
        """ Returns indicator whether the updater is running
        :returns: True if updater is running False otherwise
        :rtype: bool
        """
        return updater.is_running()
