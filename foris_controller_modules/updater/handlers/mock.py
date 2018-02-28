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
            "approvals": {"status": self.approvals_status},
            "enabled": self.enabled,
            "branch": self.branch,
        }
        if self.approvals_delay:
            result["approvals"]["delay"] = self.approvals_delay
        return result
