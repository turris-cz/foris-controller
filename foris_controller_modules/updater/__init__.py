#
# foris-controller
# Copyright (C) 2017-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class UpdaterModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_settings(self, data):
        """ Get current updater settings

        :param data: supposed to be {'lang': }
        :type data: dict
        :returns: current updater settings
        :rtype: dict
        """
        res = self.handler.get_settings(data["lang"])
        res["approval"] = self.handler.get_approval()
        res["languages"] = self.handler.get_languages()
        return res

    def action_update_settings(self, data):
        """ Updates updater settings

        :param data: data containing new updater settings
        :type data: dict
        :returns: {"result": True/False}
        :rtype: dict
        """
        return {
            "result": self.handler.update_settings(
                data.get("user_lists", None),
                data.get("languages", None),
                data.get("approval_settings", None),
                data["enabled"],
            )
        }

    def action_get_package_lists(self, data):
        """ Get current package lists settings

        :param data: supposed to be {'lang': }
        :type data: dict
        :returns: current package lists
        :rtype: dict

        """
        return {"package_lists": self.handler.get_package_lists(data["lang"])}

    def action_update_package_lists(self, data):
        """ Updates package lists settings

        :param data: data containing new package lists settings
        :type data: dict
        :returns: {"result": True/False}
        :rtype: dict
        """
        return {
            "result": self.handler.update_package_lists(data["package_lists"])
        }

    def action_get_languages(self, data):
        """ Get current language list

        :param data: supposed to be {}
        :type data: dict
        :returns: current language lists
        :rtype: dict
        """
        return {"languages": self.handler.get_languages()}

    def action_update_languages(self, data):
        """ Update current language list

        :param data: data containing list of locale strings
        :type data: dict
        :returns: {"result": True/False}
        :rtype: dict
        """
        return {"result": self.handler.update_languages(data["languages"])}

    def action_resolve_approval(self, data):
        """ Resolvs approval
        :param data: {"id": "...", "solution": "grant/deny"}
        :type data: dict

        :returns: {"result": True/False}
        :rtype: dict
        """
        res = self.handler.resolve_approval(**data)
        if res:
            self.notify("resolve_approval", data)
        return {"result": res}

    def action_run(self, data):
        """ Starts the updater

        :param data: {"set_reboot_indicator": True/False}
        :type data: dict
        :returns: {"result": True/False}
        :rtype: dict
        """
        return {"result": self.handler.run(**data)}

    def action_get_enabled(self, data):
        """ Get information whether updater is enabled
        :param data: supposed to be {}
        :type data: dict
        :returns: {"enabled": True/False}
        :rtype: dict
        """
        return {"enabled": self.handler.get_enabled()}

    def action_get_running(self, data):
        """ Get information whether updater is running
        :param data: supposed to be {}
        :type data: dict
        :returns: {"running": True/False}
        :rtype: dict
        """
        return {"running": self.handler.get_running()}

    def action_query_installed_packages(self, data):
        """ Query whether packages are installed or provided by another packages """
        return {"installed": self.handler.query_installed_packages(**data)}


@wrap_required_functions(
    [
        "get_settings",
        "update_settings",
        "get_package_lists",
        "update_package_lists",
        "get_approval",
        "get_languages",
        "update_languages",
        "resolve_approval",
        "run",
        "get_enabled",
        "get_running",
        "query_installed_packages",
    ]
)
class Handler(object):
    pass
