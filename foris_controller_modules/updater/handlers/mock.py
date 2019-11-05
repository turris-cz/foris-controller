# -*- coding: utf-8 -*-

#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import copy
import logging
import random
import uuid

from datetime import datetime

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper


from .. import Handler

logger = logging.getLogger(__name__)


class MockUpdaterHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)

    # Enabled flag in option is there only for testing purposes
    # On real system enabled/disabled status will be written in uci config file
    DEFAULT_USERLISTS = {
        "api-token": {
            "description": {
                "en": u"A Foris plugin allowing to manage remote API access tokens"
                " (for example for use in Spectator or Android application).",
                "cs": "Správa tokenů pro vzdálený API přístup"
                " (např. pro Spectator, nebo Android aplikaci) ve Forisu.",
                "de": "Ein Plugin für Foris, welcher Management von Tokens für das"
                " Fernzugriff-API (z. B. für Anwendung in Spectator oder Android"
                " Applikationen) erlaubt.",
            },
            "title": {"en": "Access tokens", "cs": "Přístupové tokeny", "de": "Zugangsverwaltung"},
            "enabled": False,
            "hidden": False,
        },
        "automation": {
            "description": {
                "cs": "Software pro ovládání domácí automatizace, včetně Turris Gadgets.",
                "de": "Steuerungssoftware für die Hausautomation, einschließlich Turris "
                "Gadgets.",
                "en": "Control software for home automation, including Turris Gadgets.",
            },
            "title": {"cs": "Domácí automatizace", "de": "Hausautomation", "en": "Home automation"},
            "enabled": False,
            "hidden": False,
        },
        "dev-detect": {
            "description": {
                "cs": "Software pro detekci nově připojených zařízení na lokální síti"
                " (EXPERIMENTÁLNÍ).",
                "de": "Software für die Erkennung neuer Geräte im lokalen Netzwerk"
                " (EXPERIMENTELL).",
                "en": "Software for detecting new devices on local network (EXPERIMENTAL).",
            },
            "title": {
                "cs": "Detekce připojených zařízení",
                "de": "Geräterkennung",
                "en": "Device detection",
            },
            "enabled": False,
            "hidden": False,
        },
        "dvb": {
            "description": {
                "cs": "Software na sdílení televizního vysílání přijímaného Turrisem."
                " Neobsahuje ovladače pro zařízení.",
                "de": "Software für die Weiterleitung von Fernsehsignal, welcher mittels"
                " DVB-Tuner vom Turris empfangen wird. Gerätetreiber sind nicht enthalten.",
                "en": "Software for sharing television received by a DVB tuner on Turris."
                " Does not include device drivers.",
            },
            "title": {"cs": "Televizní tuner", "de": "DVB-Tuner", "en": "DVB tuner"},
            "enabled": False,
            "hidden": False,
        },
        "i_agree_honeypot": {
            "description": {
                "cs": "Past na roboty zkoušející hesla na SSH.",
                "de": "Falle für Roboter, die das Kennwort für den SSH-Zugriff zu erraten"
                " versuchen.",
                "en": "Trap for password-guessing robots on SSH.",
            },
            "title": {"cs": "SSH Honeypot", "de": "SSH-Honigtopf", "en": "SSH Honeypot"},
            "enabled": False,
            "hidden": False,
            "options": {
                "minipot": {
                    "title": "Minipots",
                    "description": "Minimal honeypots to catch attackers for various protocols.",
                    "default": True,
                },
                "haas": {
                    "title": "SSH Honeypot",
                    "description": "SSH honeypot using Honeypot as a Service (haas.nic.cz).",
                }
            }
        },
        "i_agree_datacollect": {
            "description": {"cs": "", "de": "", "en": ""},
            "title": {"cs": "", "de": "", "en": ""},
            "enabled": False,
            "hidden": False,
        },
    }

    # actual stored user lists
    USER_LISTS = {}

    languages = [
        {"code": "cs", "enabled": True},
        {"code": "de", "enabled": True},
        {"code": "da", "enabled": False},
        {"code": "fr", "enabled": False},
        {"code": "lt", "enabled": False},
        {"code": "pl", "enabled": False},
        {"code": "ru", "enabled": False},
        {"code": "sk", "enabled": False},
        {"code": "hu", "enabled": False},
        {"code": "it", "enabled": False},
        {"code": "nb_NO", "enabled": True},
    ]
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
        result = {"approval_settings": {"status": self.approvals_status}, "enabled": self.enabled}
        if self.approvals_delay:
            result["approval_settings"]["delay"] = self.approvals_delay
        return result

    @staticmethod
    @logger_wrapper(logger)
    def update_settings(user_lists, languages, approvals_settings, enabled):
        """ Mocks update updater settings

        :param user_lists: new user-list set
        :type user_lists: list of dictionaries
        :param languages: languages which will be installed
        :type languages: list
        :param approvals_settings: new approval settings
        :type approvals_settings: dict
        :param enabled: is updater enabled indicator
        :type enabled: bool
        :returns: True on success False otherwise
        :rtype: bool
        """

        if user_lists is not None:
            MockUpdaterHandler.USER_LISTS = {}
            for lst in user_lists:
                list_name = lst["name"]
                MockUpdaterHandler.USER_LISTS[list_name] = copy.deepcopy(MockUpdaterHandler.DEFAULT_USERLISTS[list_name])
                MockUpdaterHandler.USER_LISTS[list_name]["enabled"] = True

                default_list_options = MockUpdaterHandler.USER_LISTS[list_name].get("options", {})
                opts = {}
                for opt in lst.get("options", {}):
                    if opt["name"] in default_list_options:
                        opts[opt["name"]] = default_list_options[opt["name"]]
                        opts[opt["name"]]["enabled"] = opt["enabled"]

                MockUpdaterHandler.USER_LISTS[list_name]["options"] = opts

        if languages is not None:
            for record in MockUpdaterHandler.languages:
                record["enabled"] = record["code"] in languages
        if approvals_settings is not None:
            MockUpdaterHandler.approvals_delay = approvals_settings.get("delay", None)
            MockUpdaterHandler.approvals_status = approvals_settings["status"]
        MockUpdaterHandler.enabled = enabled
        MockUpdaterHandler.guide_set.set(True)

        return True

    @logger_wrapper(logger)
    def get_approval(self):
        """ Mocks return of current approval
        :returns: current approval or {"present": False}
        :rtype: dict
        """
        return random.choice(
            [
                {"present": False},
                {
                    "present": True,
                    "hash": str(uuid.uuid4()),
                    "status": random.choice(["asked", "granted", "denied"]),
                    "time": datetime.now().isoformat(),
                    "plan": [
                        {"name": "package1", "op": "install", "new_ver": "1.0"},
                        {"name": "package2", "op": "remove", "cur_ver": "2.0"},
                        {"name": "package3", "op": "upgrade", "cur_ver": "1.0", "new_ver": "1.1"},
                        {"name": "package4", "op": "downgrade", "cur_ver": "2.1", "new_ver": "2.0"},
                    ],
                    "reboot": random.choice([True, False]),
                },
            ]
        )

    @staticmethod
    @logger_wrapper(logger)
    def get_user_lists(lang):
        """ Mocks getting user lists
        :param lang: language en/cs/de
        :returns: [{"name": "..", "enabled": True, "title": "..", "description": "..", "hidden": True}, ...]
        :rtype: dict
        """
        exported = []
        for list_name, lst in MockUpdaterHandler.DEFAULT_USERLISTS.items():
            opts = [
                {
                    "name": opt_name,
                    "title": data["title"],
                    "description": data["description"],
                    "enabled": (MockUpdaterHandler.USER_LISTS[list_name]["options"][opt_name]["enabled"]
                                if (list_name in MockUpdaterHandler.USER_LISTS and
                                    opt_name in MockUpdaterHandler.USER_LISTS[list_name]["options"])
                                else data.get("default", False)),
                }
                for opt_name, data in lst.get("options", {}).items()
            ]
            exported.append(
                {
                    "name": list_name,
                    "hidden": lst["hidden"],
                    "enabled": (MockUpdaterHandler.USER_LISTS[list_name]["enabled"]
                                if list_name in MockUpdaterHandler.USER_LISTS else lst["enabled"]),
                    "description": lst["description"].get(lang, lst["description"]["en"]),
                    "title": lst["title"].get(lang, lst["title"]["en"]),
                    "options": opts,
                }
            )

        return exported

    @logger_wrapper(logger)
    def get_languages(self):
        """ Mocks getting languages

        :returns: [{"code": "cs", "enabled": True}, {"code": "de", "enabled": True}, ...]
        :rtype: dict
        """
        return MockUpdaterHandler.languages

    @logger_wrapper(logger)
    def resolve_approval(self, hash, solution):
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

    @logger_wrapper(logger)
    def get_enabled(self):
        """ Mocks get info whether updater is enabled
        """
        return self.enabled
