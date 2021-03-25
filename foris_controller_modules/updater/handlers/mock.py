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
import typing

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
        "3g": {
            "title": {
                "en": "Extensions of network protocols for 3G/LTE"
            },
            "description": {
                "en": "Support for Turris Omnia and Turris MOX LTE pack."
            },
            "url": "https://wiki.turris.cz/doc/en/howto/lte_modem_install",
            "enabled": False
        },
        "datacollect": {
            "title": {
                "en": "Data Collection"
            },
            "description": {
                "en": "Software for participation in data collection and distributed adaptive firewall."
            },
            "url": "https://docs.turris.cz/basics/collect/",
            "options": {
                "survey": {
                    "title": "Usage Survey",
                    "description": "Collect data about router usage (installed packages, Internet connection type and etc.).",
                    "default": True
                },
                "dynfw": {
                    "title": "Dynamic Firewall",
                    "description": "Add firewall rules to block attackers detected by Turris collection network.",
                    "default": True
                },
                "nikola": {
                    "title": "Firewall Logs",
                    "description": "Collect logs from firewall for attempted connections.",
                    "default": True
                },
                "minipot": {
                    "title": "Minipots",
                    "description": "Minimal honeypots to catch attackers for various protocols.",
                    "default": True
                },
                "haas": {
                    "title": "SSH Honeypot",
                    "description": "SSH honeypot using Honeypot as a Service (haas.nic.cz)."
                }
            },
            "enabled": False
        },
        "atlas": {
            "title": {
                "en": "RIPE Atlas SW Probe"
            },
            "description": {
                "en": "Global platform, which measures Internet connectivity and reachability."
            },
            "url": "https://wiki.turris.cz/doc/en/howto/atlas-probe",
            "labels": [
                "community"
            ],
            "enabled": False
        },
        "dvb": {
            "title": {
                "en": "DVB tuner"
            },
            "description": {
                "en": "Software for sharing television received by a DVB tuner on Turris. Does not include device drivers."
            },
            "url": "https://wiki.turris.cz/doc/en/howto/dvb",
            "labels": [
                "community",
                "advanced"
            ],
            "enabled": False
        },
        "hardening": {
            "title": {
                "en": "Hardening"
            },
            "description": {
                "en": "Seccomp tools for system hardening."
            },
            "options": {
                "common_passwords": {
                    "title": "Common passwords filter",
                    "description": "Compare new password you are about to set to access router with list of common passwords used by robots trapped in Turris honeypots.",
                    "default": True
                },
                "ujail": {
                    "title": "OpenWrt's process jail",
                    "description": "ujail allows to limit processes by limiting syscalls and file-system access",
                    "labels": [
                        "community",
                        "experimental"
                    ]
                },
                "seccomp": {
                    "title": "Secure Computing Mode (seccomp)",
                    "description": "Optional support for seccomp allowing processes to isolate from them self",
                    "labels": [
                        "community",
                        "experimental"
                    ]
                }
            },
            "enabled": False
        },
        "luci_controls": {
            "title": {
                "en": "LuCI extensions"
            },
            "description": {
                "en": "Several additional tabs and controls for the advanced LuCI interface."
            },
            "options": {
                "adblock": {
                    "title": "AdBlock",
                    "description": "Script to block ad/abuse domains."
                },
                "sqm": {
                    "title": "SQM",
                    "description": "Active Queue Management to boost performance on heavily loaded network."
                },
                "tinyproxy": {
                    "title": "Tinyproxy",
                    "description": "HTTP(S) proxy."
                },
                "upnp": {
                    "title": "UPnP",
                    "description": "Universal Plug and Play service."
                },
                "printserver": {
                    "title": "Print server (p910nd)",
                    "description": "Services allowing to connect a printer to the router and use it for remote printing."
                },
                "statistics": {
                    "title": "Statistics",
                    "description": "Gather and render diagrams for system statistics by using collectd."
                },
                "wireguard": {
                    "title": "WireGuard",
                    "description": "Alternative to OpenVPN, it provides fast, modern and secure VPN tunnel.",
                    "url": "https://openwrt.org/docs/guide-user/services/vpn/wireguard/start",
                    "labels": [
                        "advanced"
                    ]
                }
            },
            "labels": [
                "community"
            ],
            "enabled": False
        },
        "lxc": {
            "title": {
                "en": "LXC utilities"
            },
            "description": {
                "en": "Set of utilities to manage Linux Containers (lightweight virtualization technology)."
            },
            "url": "https://docs.turris.cz/geek/lxc/lxc/",
            "labels": [
                "storage",
                "high_memory",
                "advanced"
            ],
            "enabled": False
        },
        "nas": {
            "title": {
                "en": "NAS"
            },
            "description": {
                "en": "Services allowing to connect a disk to the router and use it as network data store."
            },
            "url": "https://wiki.turris.cz/doc/en/howto/nas",
            "options": {
                "samba": {
                    "title": "Samba",
                    "description": "Implementation of SMB network protocol."
                },
                "dlna": {
                    "title": "DLNA",
                    "description": "Digital media sharing server."
                },
                "transmission": {
                    "title": "Transmission",
                    "description": "BitTorrent client."
                },
                "raid": {
                    "title": "mdadm",
                    "description": "Software RAID storage support using mdadm.",
                    "labels": [
                        "advanced"
                    ]
                },
                "encrypt": {
                    "title": "Encrypted Storage",
                    "description": "Add support to access encrypted storage devices using dm-crypt.",
                    "labels": [
                        "advanced"
                    ]
                }
            },
            "labels": [
                "community"
            ],
            "enabled": False
        },
        "net_monitoring": {
            "title": {
                "en": "Network monitoring and parental control"
            },
            "description": {
                "en": "Tools to monitor local network and users on it."
            },
            "options": {
                "netmetr": {
                    "title": "Internet connection speed measurement",
                    "description": "Actively measures speed of Internet connection using netmetr.cz service.",
                    "url": "https://docs.turris.cz/basics/apps/netmetr/"
                },
                "dev_detect": {
                    "title": "New devices detection",
                    "description": "Software for detecting new devices on local network.",
                    "labels": [
                        "experimental"
                    ]
                },
                "pakon": {
                    "title": "Pakon",
                    "description": "Software for in depth monitoring of your traffic using Suricata.",
                    "url": "https://docs.turris.cz/basics/apps/pakon/",
                    "labels": [
                        "experimental",
                        "netload",
                        "high_memory",
                        "storage"
                    ]
                }
            },
            "enabled": False
        },
        "netboot": {
            "title": {
                "en": "Turris MOX network boot"
            },
            "description": {
                "en": "Server-side for Turris MOX without microSD card used as Wi-Fi access point."
            },
            "url": "https://docs.turris.cz/basics/apps/netboot",
            "labels": [
                "high_storage",
                "experimental"
            ],
            "enabled": False
        },
        "netdata": {
            "title": {
                "en": "Netdata"
            },
            "description": {
                "en": "Real-time perfomance and health monitoring options."
            },
            "labels": [
                "community",
                "high_memory"
            ],
            "enabled": False
        },
        "nextcloud": {
            "title": {
                "en": "Nextcloud"
            },
            "description": {
                "en": "Self-hosted files hosting and productivity platform that keeps you in control. Alternative to services such as Dropbox or Google Drive."
            },
            "url": "https://docs.turris.cz/geek/nextcloud/nextcloud/",
            "labels": [
                "experimental",
                "storage"
            ],
            "enabled": False
        },
        "openvpn": {
            "title": {
                "en": "OpenVPN"
            },
            "description": {
                "en": "Easy setup of the OpenVPN server from Foris."
            },
            "url": "https://docs.turris.cz/basics/apps/openvpn/openvpn/",
            "enabled": False
        },
        "tor": {
            "title": {
                "en": "Tor"
            },
            "description": {
                "en": "Service to increase anonymity on the Internet."
            },
            "labels": [
                "advanced",
                "community"
            ],
            "enabled": False
        },
        "drivers": {
            "title": {
                "en": "Alternative core drivers"
            },
            "description": {
                "en": "These options allow you to use alternative drivers over those available in default installation. You can try to enable these if you encounter some problems with default ones."
            },
            "options": {
                "ath10k_ct": {
                    "title": "Candela Technologies Wi-Fi drivers for Qualcomm Atheros QCA988x",
                    "description": "Alternative driver from Candela Technologies.",
                    "boards": [
                        "omnia",
                        "turris1x"
                    ]
                },
                "ath10k_ct_htt": {
                    "title": "Candela Technologies Wi-Fi drivers for Qualcomm Atheros QCA988x with improved stability in busy networks",
                    "description": "Alternative driver from Candela Technologies. It uses HTT TX data path for management frames, which improves stability in busy networks."
                }
            },
            "labels": [
                "advanced",
                "community"
            ],
            "enabled": False
        }
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

    INSTALLED_PACKAGES = ["foo-alternative", "turris-version"]
    PROVIDING_PACKAGES = {
        "foo-alternative": "foo"
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

    @staticmethod
    def query_installed_packages(packages: typing.List[str]) -> typing.List[str]:
        """ Query whether packages are installed or provided by another packages """
        ret = set()
        for package in packages:
            if package in MockUpdaterHandler.INSTALLED_PACKAGES:
                ret.add(package)

            if package in MockUpdaterHandler.PROVIDING_PACKAGES.values():
                ret.add(package)

        return sorted(ret)

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
