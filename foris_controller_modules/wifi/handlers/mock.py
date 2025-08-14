#
# foris-controller
# Copyright (C) 2018-2022 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)

DEFAULT_WIFI_ENCRYPTION = "WPA2/3"
# Note: default OpenWrt config has "encryption none" and interface disabled
# However we treat this config as not configured wifi yet and return TOS preferred mode instead
DEFAULT_CONFIG = [
    {
        "id": 0,
        "enabled": False,
        "SSID": "Turris",
        "hidden": False,
        "channel": 36,
        "htmode": "HE80",
        "band": "5g",
        "encryption": DEFAULT_WIFI_ENCRYPTION,
        "ieee80211w_disabled": False,
        "password": "",
        "guest_wifi": {
            "enabled": False,
            "SSID": "Turris-guest",
            "password": "",
            "encryption": DEFAULT_WIFI_ENCRYPTION,
        },
        "available_bands": [
            {
                "band": "2g",
                "available_htmodes": ["NOHT", "HT20", "HT40", "HE20", "HE40", "HE80", "HE160"],
                "available_channels": [
                    {"number": 1, "frequency": 2412, "radar": False},
                    {"number": 2, "frequency": 2417, "radar": False},
                    {"number": 3, "frequency": 2422, "radar": False},
                    {"number": 4, "frequency": 2427, "radar": False},
                    {"number": 5, "frequency": 2432, "radar": False},
                    {"number": 6, "frequency": 2437, "radar": False},
                    {"number": 7, "frequency": 2442, "radar": False},
                    {"number": 8, "frequency": 2447, "radar": False},
                    {"number": 9, "frequency": 2452, "radar": False},
                    {"number": 10, "frequency": 2457, "radar": False},
                    {"number": 11, "frequency": 2462, "radar": False},
                    {"number": 12, "frequency": 2467, "radar": False},
                    {"number": 13, "frequency": 2472, "radar": False},
                ],
                "available_multilink": False,
            },
            {
                "band": "5g",
                "available_htmodes": [
                    "NOHT",
                    "HT20", "HT40",
                    "VHT20", "VHT40", "VHT80", "VHT160",
                    "HE20", "HE40", "HE80", "HE160",
                ],
                "available_channels": [
                    {"number": 36, "frequency": 5180, "radar": False},
                    {"number": 40, "frequency": 5200, "radar": False},
                    {"number": 44, "frequency": 5220, "radar": False},
                    {"number": 48, "frequency": 5240, "radar": False},
                    {"number": 52, "frequency": 5260, "radar": False},
                    {"number": 56, "frequency": 5280, "radar": False},
                    {"number": 60, "frequency": 5300, "radar": False},
                    {"number": 64, "frequency": 5320, "radar": False},
                    {"number": 68, "frequency": 5340, "radar": False},
                    {"number": 72, "frequency": 5360, "radar": False},
                    {"number": 76, "frequency": 5380, "radar": False},
                    {"number": 80, "frequency": 5400, "radar": False},
                    {"number": 84, "frequency": 5420, "radar": False},
                    {"number": 88, "frequency": 5440, "radar": False},
                    {"number": 92, "frequency": 5460, "radar": False},
                    {"number": 96, "frequency": 5480, "radar": False},
                    {"number": 100, "frequency": 5500, "radar": False},
                    {"number": 104, "frequency": 5520, "radar": False},
                    {"number": 108, "frequency": 5540, "radar": False},
                    {"number": 112, "frequency": 5560, "radar": False},
                    {"number": 116, "frequency": 5580, "radar": False},
                    {"number": 120, "frequency": 5600, "radar": False},
                    {"number": 124, "frequency": 5620, "radar": False},
                    {"number": 128, "frequency": 5640, "radar": False},
                    {"number": 132, "frequency": 5660, "radar": False},
                    {"number": 136, "frequency": 5680, "radar": False},
                    {"number": 140, "frequency": 5700, "radar": False},
                    {"number": 144, "frequency": 5720, "radar": False},
                    {"number": 149, "frequency": 5745, "radar": False},
                    {"number": 153, "frequency": 5765, "radar": False},
                    {"number": 157, "frequency": 5785, "radar": False},
                    {"number": 161, "frequency": 5805, "radar": False},
                    {"number": 165, "frequency": 5825, "radar": False},
                    {"number": 169, "frequency": 5845, "radar": False},
                    {"number": 173, "frequency": 5865, "radar": False},
                    {"number": 177, "frequency": 5885, "radar": False},
                ],
                "available_multilink": False,
            },
        ],
    },
    {
        "id": 1,
        "enabled": False,
        "SSID": "Turris",
        "hidden": False,
        "channel": 1,
        "htmode": "HT20",
        "band": "2g",
        "encryption": DEFAULT_WIFI_ENCRYPTION,
        "ieee80211w_disabled": False,
        "password": "",
        "guest_wifi": {
            "enabled": False,
            "SSID": "Turris-guest",
            "password": "",
            "encryption": DEFAULT_WIFI_ENCRYPTION,
        },
        "available_bands": [
            {
                "band": "2g",
                "available_htmodes": ["NOHT", "HT20", "HT40"],
                "available_channels": [
                    {"number": 1, "frequency": 2412, "radar": False},
                    {"number": 2, "frequency": 2417, "radar": False},
                    {"number": 3, "frequency": 2422, "radar": False},
                    {"number": 4, "frequency": 2427, "radar": False},
                    {"number": 5, "frequency": 2432, "radar": False},
                    {"number": 6, "frequency": 2437, "radar": False},
                    {"number": 7, "frequency": 2442, "radar": False},
                    {"number": 8, "frequency": 2447, "radar": False},
                    {"number": 9, "frequency": 2452, "radar": False},
                    {"number": 10, "frequency": 2457, "radar": False},
                    {"number": 11, "frequency": 2462, "radar": False},
                    {"number": 12, "frequency": 2467, "radar": False},
                    {"number": 13, "frequency": 2472, "radar": False},
                ],
                "available_multilink": True,
            }
        ],
    },
]


class MockWifiHandler(Handler, BaseMockHandler):
    devices = copy.deepcopy(DEFAULT_CONFIG)

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get wifi settings

        :returns: current wifi settings
        :rtype: str
        """
        return {"devices": copy.deepcopy(MockWifiHandler.devices)}

    @classmethod
    def _update_device(
        cls,
        id,
        enabled,
        SSID=None,
        hidden=None,
        channel=None,
        htmode=None,
        band=None,
        encryption=None,
        ieee80211w_disabled=None,
        password=None,
        guest_wifi=None,
    ):
        # try to find the device
        dev = None
        for device in cls.devices:
            if id == device["id"]:
                dev = device

        # device not found
        if not dev:
            return False

        dev["enabled"] = enabled
        if not enabled:
            # don't need to check furhter input is only {"enabled": True, "id": X}
            return True

        # find corresponding band
        corresponding_bands = [e for e in dev["available_bands"] if e["band"] == band]
        if len(corresponding_bands) != 1:
            return False
        band_o = corresponding_bands[0]

        # wrong channel
        if channel not in [e["number"] for e in band_o["available_channels"]] and channel != 0:
            return False

        # from htmode
        if htmode not in band_o["available_htmodes"]:
            return False

        dev["SSID"] = SSID
        dev["hidden"] = hidden
        dev["channel"] = channel
        dev["htmode"] = htmode
        dev["band"] = band
        dev["encryption"] = encryption if encryption is not None else DEFAULT_WIFI_ENCRYPTION

        # handle optional ieee80211w based on encryption type
        if encryption in ("WPA2/3", "WPA3"):
            dev["ieee80211w_disabled"] = ieee80211w_disabled
        elif encryption == "WPA2":
            dev["ieee80211w_disabled"] = False  # ignore ieee80211w value for WPA2
        else:
            return False

        dev["password"] = password
        if guest_wifi["enabled"]:
            dev["guest_wifi"] = copy.deepcopy(guest_wifi)
        else:
            dev["guest_wifi"]["enabled"] = False

        return True

    @logger_wrapper(logger)
    def update_settings(self, new_settings):
        """ Mocks updates current wifi settings
        :returns: True if update passes
        :rtype: bool
        """
        orig = copy.deepcopy(MockWifiHandler.devices)
        for device in new_settings["devices"]:
            if not self._update_device(**device):
                MockWifiHandler.devices = orig
                return False
        return True

    @logger_wrapper(logger)
    def reset(self):
        """ Mocks reset of wifi settings
        :returns: True if reset passes False otherwise
        :rtype: bool
        """
        MockWifiHandler.devices = copy.deepcopy(DEFAULT_CONFIG)
        return True
