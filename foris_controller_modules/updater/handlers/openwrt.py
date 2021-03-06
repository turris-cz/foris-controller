#
# foris-controller
# Copyright (C) 2017-2020, 2022 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import typing

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.updater import svupdater_approvals
from foris_controller.utils import logger_wrapper
from foris_controller_backends.updater import Updater, UpdaterUci

from .. import Handler
from ..datatypes import ApprovalNotPresent

logger = logging.getLogger(__name__)


class OpenwrtUpdaterHandler(Handler, BaseOpenwrtHandler):
    uci = UpdaterUci()
    updater = Updater()

    @logger_wrapper(logger)
    def get_settings(self, lang="en"):
        """ get updater settings

        :returns: current updater settings
        :rtype: dict
        """
        return OpenwrtUpdaterHandler.uci.get_settings(lang)

    @logger_wrapper(logger)
    def update_settings(self, user_lists, languages, approvals_settings, enabled):
        """ update updater settings

        :param user_lists: new user-list set
        :type user_lists: dictionary
        :param languages: languages which will be installed
        :type languages: list
        :param approvals_settings: new approval settings
        :type approvals_settings: dict
        :param enabled: is updater enabled indicator
        :type enabled: bool
        :returns: True on success False otherwise
        :rtype: bool
        """
        approvals_status = approvals_settings["status"] if approvals_settings else None
        approvals_delay = approvals_settings.get("delay", None) if approvals_settings else None

        # user_list are silently dropped as we don't use it anymore here
        # function signature remains for backward compatibility
        return OpenwrtUpdaterHandler.uci.update_settings(
            languages, approvals_status, approvals_delay, enabled
        )

    @logger_wrapper(logger)
    def get_package_lists(self, lang):
        """ Returns package lists with their options
        :param lang: language en/cs/de
        :returns: [{"name": "..", "enabled": True, "title": "..", "description": "..", "options": [], "labels": []]
        :rtype: dict
        """
        return self.updater.get_package_lists(lang)

    @logger_wrapper(logger)
    def update_package_lists(self, package_lists):
        """ Update package lists

        :param package_lists: new package-lists set
        :type package_lists: dictionary
        """
        return OpenwrtUpdaterHandler.uci.update_package_lists(package_lists)

    @logger_wrapper(logger)
    def get_approval(self) -> typing.Union[svupdater_approvals.ApprovalRequest, ApprovalNotPresent]:
        """ Returns current approval
        :returns: current approval or {"present": False}
        :rtype: dict
        """
        return self.updater.get_approval()

    @logger_wrapper(logger)
    def resolve_approval(self, hash, solution):
        """ Resolv current approval
        :param hash: approval hash
        :type hash: str
        :param solution: what to do with the approval grant/deny
        :type solution: str

        :returns: True on success False otherwise
        :rtype: bool
        """
        return self.updater.resolve_approval(hash, solution)

    @logger_wrapper(logger)
    def get_languages(self):
        """ Returns language list and indicator whether the language is enabled

        :returns: [{"code": "cs", "enabled": True}, {"code": "de", "enabled": True}, ...]
        :rtype: dict
        """
        return self.updater.get_languages()

    def update_languages(self, languages):
        """ Update installed languages

        :param languages: languages
        :type languages: list

        :returns: True on success
        :rtype: bool
        """
        return self.updater.update_languages(languages)

    def query_installed_packages(self, packages: typing.List[str]) -> typing.List[str]:
        """ Query whether packages are installed or provided by another packages """
        return self.updater.query_installed_packages(packages)

    @logger_wrapper(logger)
    def run(self, set_reboot_indicator):
        """ Start updater run
        :param set_reboot_indicator: should reboot indicator be set after updater finishes
        :type set_reboot_indicator: bool
        :returns: True if updater started
        :rtype: bool
        """
        return self.updater.run(set_reboot_indicator)

    @logger_wrapper(logger)
    def get_enabled(self):
        """ Get info whether updater is enabled
        """
        return self.uci.get_enabled()

    @logger_wrapper(logger)
    def get_running(self):
        """ Get info whether updater is running
        """
        return self.updater.updater_running()
