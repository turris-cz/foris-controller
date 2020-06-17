# -*- coding: utf-8 -*-

#
# foris-controller
# Copyright (C) 2019-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
    DEFAULT_PACKAGE_LISTS = {
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
            "labels": ["community"],
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
            "labels": ["experimental"],
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
            "url": "https://doc.turris.cz/doc/en/howto/dvb",
            "labels": ["community", "advanced"],
        },
        "i_agree_honeypot": {
            "description": {
                "cs": "Past na roboty zkoušející hesla na SSH.",
                "de": "Falle für Roboter, die das Kennwort für den SSH-Zugriff zu erraten"
                " versuchen.",
                "en": "Trap for password-guessing robots on SSH.",
            },
            "title": {"cs": "Honeypot", "de": "Honigtopf", "en": "Honeypot"},
            "enabled": False,
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
            },
            "labels": ["experimental"],
        },
        "i_agree_datacollect": {
            "description": {"cs": "", "de": "", "en": ""},
            "title": {"cs": "datacollect", "de": "datacollect", "en": "datacollect"},
            "enabled": False,
            "options": {
                "survey": {
                    "title": "Usage Survey",
                    "description": "Collect data about router usage (installed packages, Internet connection type and etc.).",
                },
                "dynfw": {
                    "title": "Dynamic Firewall",
                    "description": "Add firewall rules to block attackers detected by Turris collection network.",
                    "default": True,
                }
            },
        },
    }

    # actual stored user lists
    PACKAGE_LISTS = {}

    OPTION_LABELS = {
        "advanced": {
            "title": "Advanced users",
            "description": "This functionality is usable only for advanced users.",
            "severity": "secondary"
        },
        "community": {
            "title": "Community",
            "description": "This package list is not officially supported. Turris team has no responsibility for stability of software that is part of this list.",
            "severity": "success"
        },
        "experimental": {
            "title": "Experimental",
            "description": "Software that is part of this package list is considered experimental. Problems when using it can be expected.",
            "severity": "danger"
        },
        "deprecated": {
            "title": "Deprecated",
            "description": "This package list and/or software that provides are planned to be removed. It is advised to not use it.",
            "severity": "warning"
        },
        "storage": {
            "title": "External storage",
            "description": "External storage use is highly suggested for use of this package list",
            "severity": "primary"
        },
        "high_memory": {
            "title": "High memory usage",
            "description": "Software in this package list consumes possibly higher amount of memory to run. It is not suggested to use it with small memory.",
            "severity": "info"
        },
        "high_storage": {
            "title": "High storage usage",
            "description": "Software in this package list consumes possibly higher amount of storage space to install. It is not suggested to use it with small storages such as internal storage of Turris 1.x and SD cards with less than 1GB of storage.",
            "severity": "info"
        },
        "netload": {
            "title": "Network load",
            "description": "This functionality can decreases network performance. That can be felt only on faster uplinks but because of that it still can be decremental to some users.",
            "severity": "secondary"
        }
    }

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
    running = True
    approvals_status = "off"
    updater_running = False

    @logger_wrapper(logger)
    def get_settings(self, lang):
        """ Mocks get updater settings

        :returns: current updater settings
        :rtype: dict
        """
        result = {
            "approval_settings": {"status": self.approvals_status},
            "enabled": self.enabled,
            "user_lists": [],  # don't return package lists, return empty list for compatibility instead
        }
        if self.approvals_delay:
            result["approval_settings"]["delay"] = self.approvals_delay
        return result

    @staticmethod
    @logger_wrapper(logger)
    def update_settings(user_lists, languages, approvals_settings, enabled):
        """ Mocks update updater settings

        :param user_lists: new user-list set
        :type user_lists: list of dictionaries, deprecated and ignored here
        :param languages: languages which will be installed
        :type languages: list
        :param approvals_settings: new approval settings
        :type approvals_settings: dict
        :param enabled: is updater enabled indicator
        :type enabled: bool
        :returns: True on success False otherwise
        :rtype: bool
        """

        MockUpdaterHandler.update_languages(languages)
        if approvals_settings is not None:
            MockUpdaterHandler.approvals_delay = approvals_settings.get("delay", None)
            MockUpdaterHandler.approvals_status = approvals_settings["status"]
        MockUpdaterHandler.enabled = enabled
        MockUpdaterHandler.guide_set.set(True)

        return True

    @staticmethod
    @logger_wrapper(logger)
    def get_package_lists(lang):
        """ Mocks getting package lists

        :param lang: language en/cs/de
        :returns: [{"name": "..", "enabled": True, "title": "..", "description": "..", "options": [], "labels": []]
        :rtype: dict
        """
        exported = []
        for list_name, lst in MockUpdaterHandler.DEFAULT_PACKAGE_LISTS.items():
            opts = [
                {
                    "name": opt_name,
                    "title": data["title"],
                    "description": data["description"],
                    "enabled": MockUpdaterHandler._is_option_enabled(list_name, opt_name, data),
                    "labels": MockUpdaterHandler._get_labels(data.get("labels", [])),
                }
                for opt_name, data in lst.get("options", {}).items()
            ]
            item = {
                "name": list_name,
                "enabled": MockUpdaterHandler.PACKAGE_LISTS.get(list_name, lst)["enabled"],
                "description": lst["description"].get(lang, lst["description"]["en"]),
                "title": lst["title"].get(lang, lst["title"]["en"]),
                "options": opts,
                "labels": MockUpdaterHandler._get_labels(lst.get("labels", [])),
            }
            if lst.get("url") is not None:
                item["url"] = lst["url"]
            exported.append(item)

        return exported

    def update_package_lists(self, package_lists):
        """ Update package lists

        :param package_lists: new package list settings
        :type package_lists: list of dictionaries
        :returns: True on success False otherwise
        :rtype: bool
        """
        if package_lists is not None:
            MockUpdaterHandler.PACKAGE_LISTS = {}
            for lst in package_lists:
                list_name = lst["name"]
                MockUpdaterHandler.PACKAGE_LISTS[list_name] = copy.deepcopy(MockUpdaterHandler.DEFAULT_PACKAGE_LISTS[list_name])
                MockUpdaterHandler.PACKAGE_LISTS[list_name]["enabled"] = True

                default_list_options = MockUpdaterHandler.PACKAGE_LISTS[list_name].get("options", {})
                opts = {}
                # options are not mandatory, therefore the explicit get
                for opt in lst.get("options", {}):
                    if opt["name"] in default_list_options:
                        opts[opt["name"]] = default_list_options[opt["name"]]
                        opts[opt["name"]]["enabled"] = opt["enabled"]

                MockUpdaterHandler.PACKAGE_LISTS[list_name]["options"] = opts

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
    def _is_option_enabled(list_name, opt_name, opt_data):
        if (list_name in MockUpdaterHandler.PACKAGE_LISTS
                and opt_name in MockUpdaterHandler.PACKAGE_LISTS[list_name]["options"]):
            return MockUpdaterHandler.PACKAGE_LISTS[list_name]["options"][opt_name]["enabled"]

        return opt_data.get("default", False)

    @staticmethod
    def _get_labels(labels):
        desc = []
        for label in labels:
            if label in MockUpdaterHandler.OPTION_LABELS:
                data = MockUpdaterHandler.OPTION_LABELS[label]
                record = {
                    "name": label,
                    "title": data["title"],
                    "description": data["description"],
                    "severity": data.get("severity", "primary"),
                }
                desc.append(record)

        return desc

    @logger_wrapper(logger)
    def get_languages(self):
        """ Mocks getting languages

        :returns: [{"code": "cs", "enabled": True}, {"code": "de", "enabled": True}, ...]
        :rtype: dict
        """
        return MockUpdaterHandler.languages

    @staticmethod
    @logger_wrapper(logger)
    def update_languages(languages):
        if languages is not None:
            for record in MockUpdaterHandler.languages:
                record["enabled"] = record["code"] in languages
        return True

    @logger_wrapper(logger)
    def resolve_approval(self, hash, solution):
        """ Mocks resolving of the current approval
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

    @logger_wrapper(logger)
    def get_running(self):
        """ Mocks get info whether updater is running
        """
        return self.running
