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
import random
import uuid

from datetime import datetime

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper


from .. import Handler

logger = logging.getLogger(__name__)


class MockUpdaterHandler(Handler, BaseMockHandler):
    user_lists = []
    required_languages = []
    branch = ""
    approvals_delay = None
    enabled = True
    approvals_status = "off"
    updater_running = False

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get updater settings

        :returns: current updater settings
        :rtype: dict
        """
        result = {
            "user_lists": self.user_lists,
            "required_languages": self.required_languages,
            "approval_settings": {"status": self.approvals_status},
            "enabled": self.enabled,
            "branch": self.branch,
        }
        if self.approvals_delay:
            result["approval_settings"]["delay"] = self.approvals_delay
        return result

    @logger_wrapper(logger)
    def update_settings(self, user_lists, required_languages, approvals_settings, enabled, branch):
        """ Mocks update updater settings

        :param user_lists: new user-list set
        :type user_lists: list
        :param required_languages: languages which will be installed
        :type required_languages: list
        :param approvals_settings: new approval settings
        :type approvals_settings: dict
        :param enable: is updater enabled indicator
        :type enable: bool
        :param branch: which branch is updater using default("" == "stable")
        :type enable: string
        :returns: True on success False otherwise
        :rtype: bool
        """
        MockUpdaterHandler.user_lists = user_lists
        MockUpdaterHandler.required_languages = required_languages
        MockUpdaterHandler.approvals_delay = approvals_settings.get("delay", None)
        MockUpdaterHandler.approvals_status = approvals_settings["status"]
        MockUpdaterHandler.enabled = enabled
        MockUpdaterHandler.branch = branch

        return True

    @logger_wrapper(logger)
    def get_approval(self):
        """ Mocks return of current approval
        :returns: current approval or {"present": False}
        :rtype: dict
        """
        return random.choice([
            {"present": False},
            {
                "present": True,
                "id": str(uuid.uuid4()),
                "status": random.choice(["asked", "granted", "denied"]),
                "time": datetime.now().isoformat(),
                "install_list": ["package1", "package2"],
                "remove_list": ["package3", "package4"],
                "reboot": random.choice([True, False]),
            }
        ])

    @logger_wrapper(logger)
    def resolve_approval(self, id, solution):
        """ Mocks resovling of the current approval
        """
        return random.choice([True, False])

    @logger_wrapper(logger)
    def run(self, set_reboot_indicator):
        """ Mocks updater start
        :param set_reboot_indicator: should reboot indicator be set after updater finishes
        :type set_reboot_indicator: bool
        """
        return True
