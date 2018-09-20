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

from foris_controller import profiles

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.updater import Updater
from foris_controller_backends.web import WebUciCommands, Languages
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.router_notifications import RouterNotificationsCmds
from foris_controller_backends.password import ForisPasswordUci

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtWebHandler(Handler, BaseOpenwrtHandler):
    sys_info_files = SystemInfoFiles()
    web_uci_cmds = WebUciCommands()
    password_uci = ForisPasswordUci()
    langs = Languages()
    maintain_cmds = MaintainCommands()
    notifications_cmds = RouterNotificationsCmds()
    updater = Updater()

    @logger_wrapper(logger)
    def set_language(self, language):
        """ Sets language

         :returns: True
        :rtype: bool
        """
        return self.web_uci_cmds.set_language(language)

    @logger_wrapper(logger)
    def list_languages(self):
        """ Lists languages

        :returns: available languages
        :rtype: list
        """
        return self.langs.list_languages()

    def update_guide(self, enabled, workflow):
        """ Updates guide settings
        :param enabled: is guide mode enabled
        :type enabled: bool
        :param workflow: which guide workflow is used
        :type workflow: str
        :returns: True on success, False otherwise
        :rtype: bool
        """
        return self.web_uci_cmds.update_guide(enabled, workflow)

    @logger_wrapper(logger)
    def get_data(self):
        data = self.web_uci_cmds.get_data()
        data["updater_running"] = self.updater.updater_running()
        data["notification_count"] = self.notifications_cmds.active_count()
        data["reboot_required"] = self.maintain_cmds.reboot_required()
        data["guide"]["workflow_steps"] = profiles.WORKFLOWS[data["guide"]["workflow"]]
        data["device"] = self.sys_info_files.get_model()
        data["turris_os_version"] = self.sys_info_files.get_os_version()

        return data

    @logger_wrapper(logger)
    def get_guide(self):
        return self.web_uci_cmds.get_guide()

    @logger_wrapper(logger)
    def reset_guide(self, new_workflow=None):
        return self.web_uci_cmds.reset_guide(new_workflow)
