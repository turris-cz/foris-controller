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

import json
import logging
import re
import typing

from foris_controller.exceptions import (
    BackendCommandFailed,
    UciException,
    UciRecordNotFound,
)
from foris_controller.utils import sort_by_natural_order
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.uci import (
    UciBackend,
    get_option_anonymous,
    get_sections_by_type,
    parse_bool,
    store_bool,
)

logger = logging.getLogger(__name__)


class WifiUci:
    WIFI_ENC_MODES_TO_UCI = {
        "WPA2": "psk2+ccmp",
        "WPA3": "sae",
        "WPA2/3": "sae-mixed",
    }
    # reverse lookup of json schema values and uci config values
    WIFI_ENC_UCI_TO_MODES = {v:k for k, v in WIFI_ENC_MODES_TO_UCI.items()}
    WIFI_UCI_DEFAULT_ENC_MODE = "sae-mixed"

    @staticmethod
    def get_wifi_devices(backend):
        try:
            wifi_data = backend.read("wireless")
            return get_sections_by_type(wifi_data, "wireless", "wifi-device")
        except (UciException, UciRecordNotFound):
            return []  # no wifi sections -> no gest wifi is running -> we're done

    @staticmethod
    def set_guest_wifi_disabled(backend):
        """ Should disable all guest wifi networks
        :param backend: backend controller instance
        :type backend: foris_controller_backends.uci.UciBackend
        """
        for i, _ in enumerate(WifiUci.get_wifi_devices(backend), 0):
            section_name = "guest_iface_%d" % i
            backend.add_section("wireless", "wifi-iface", section_name)
            backend.set_option("wireless", section_name, "disabled", store_bool(True))

    @staticmethod
    def call_ubus(ubus_object, method, data):
        retval, stdout, stderr = BaseCmdLine._run_command(
            "/bin/ubus", "call", ubus_object, method, json.dumps(data)
        )
        if retval != 0:
            logger.warning("Failure during ubus call: %s", stderr)
            return None

        try:
            return json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("Failed to read result: %r", e)
            return None

    @staticmethod
    def _sort_htmodes(modes: typing.Set[str]) -> typing.List[str]:
        """Sort HT (HT, VHT, HE, ...) modes in natural order"""
        return sort_by_natural_order(modes)

    @staticmethod
    def _get_device_bands(device_name: str) -> list:
        DEFAULT_HTMODE = "NOHT"

        # map bands to compatible hwmodes values for reforis
        BANDS_MAP = {
            "2g": "11g",
            "5g": "11a",
        }
        BANDS_TO_MODES_MAP = {
            "2g": ("n", "ax"),
            "5g": ("n", "ac", "ax"),
        }

        request_msg = {"device": device_name}
        ht_data = WifiUci.call_ubus("iwinfo", "info", request_msg)
        if not ht_data:
            return []

        freq_data = WifiUci.call_ubus("iwinfo", "freqlist", request_msg)
        if not freq_data:
            return []

        channels = WifiUci._get_frequencies(freq_data, device_name)
        htmodes = WifiUci._get_htmodes(ht_data["htmodes"])

        # return frequencies and htmodes for each frequency band in separate objects
        res = []
        for band in ["2g", "5g"]:
            if len(channels[band]) > 0:
                record = {
                    "available_channels": channels[band],
                    "hwmode": BANDS_MAP[band],
                }
                band_htmodes = [DEFAULT_HTMODE]
                for htmode in BANDS_TO_MODES_MAP[band]:
                    # filter htmodes and keep them in order by BANDS_TO_MODES_MAP
                    if htmode in ht_data["hwmodes"]:
                        band_htmodes += htmodes.get(htmode, [])

                record["available_htmodes"] = band_htmodes
                res.append(record)
        return res

    @staticmethod
    def _get_frequencies(freq_data, device_name: str) -> typing.Dict[str, list]:
        """Get available frequencies sorted into frequency bands

        Return frequencies for both 2.4 GHz and 5 GHz.
        """
        channels = {"2g": [], "5g": []}

        for freq in freq_data["results"]:
            channel = {
                "number": freq["channel"],
                "frequency": freq["mhz"],
                "radar": False,  # iwinfo/rpcd doesn't return DFS flags; use False for compatibility
            }

            ch_freq = channel["frequency"]
            if 2412 <= ch_freq <= 2484:
                band = "2g"
            elif 5160 <= ch_freq <= 5980:
                band = "5g"
            else:
                logger.warning(
                    "%s: Frequency '%d MHz' does not fit supported bands (2.4 & 5 GHz)",
                    device_name, ch_freq
                )
                continue

            channels[band].append(channel)

        return channels

    @staticmethod
    def _get_htmodes(device_htmodes: typing.List[str]) -> typing.Dict[str, typing.List[str]]:
        """Get HT modes based on 802.11 standard (n, ac, ax, ...)

        Get intersection of valid HT modes by standard with modes advertised by device.
        Return list of HT modes sorted in natural order.
        """
        HWMODE_TO_HT = {
            "n": {"HT20", "HT40"},
            "ac": {"VHT20", "VHT40", "VHT80", "VHT160"},
            "ax": {"HE20", "HE40", "HE80", "HE160"},
        }

        device_htmodes_set = set(device_htmodes)
        res = {
            hwmode: WifiUci._sort_htmodes(device_htmodes_set & htmodes)
            for hwmode, htmodes in HWMODE_TO_HT.items()
        }

        # Skip empty lists, for example:
        # Do not return {"ac": []}, when device does not support any of "ac" htmodes
        return {hwmode: htmodes for hwmode, htmodes in res.items() if htmodes}

    def _prepare_wifi_device(self, device, interface, guest_interface):
        # read data from uci
        device_name = device["name"]
        device_no = re.search(r"radio(\d+)$", device_name)  # radioX -> X
        if not device_no:
            return None
        device_id = int(device_no.group(1))
        enabled = not (
            parse_bool(device["data"].get("disabled", "0"))
            or parse_bool(interface["data"].get("disabled", "0"))
        )
        ssid = interface["data"].get("ssid", "Turris")
        hidden = parse_bool(interface["data"].get("hidden", "0"))
        password = interface["data"].get("key", "")
        hwmode = WifiUci._get_hwmode(device)
        htmode = device["data"].get("htmode", "NOHT")
        current_channel = device["data"].get("channel", "11" if hwmode == "11g" else "36")
        current_channel = 0 if current_channel == "auto" else int(current_channel)
        wifi_encryption = interface["data"].get("encryption", self.WIFI_UCI_DEFAULT_ENC_MODE)
        ieee80211w = interface["data"].get("ieee80211w")
        ieee80211w_disabled = ieee80211w == "0"  # "1", "2" or unset means that ieee80211w will be enabled in some way

        # compatibility with many different WPA2 mode names that are allowed in OpenWrt
        # "psk2*" -> WPA2
        if wifi_encryption.startswith("psk2"):
            wifi_encryption = "psk2+ccmp"

        # Check whether we are reading initial OpenWrt (21.02) wifi config,
        # which means that either wifi is not configured yet or it was reset to OpenWrt defaults
        # defaults: disabled wifi and encryption is "none"
        if not enabled and wifi_encryption == "none":
            # In case we have default OpenWrt config, return Turris OS prefered encryption mode,
            # so it will be the initial choice in reForis for the first time wifi setup
            wifi_encryption = self.WIFI_UCI_DEFAULT_ENC_MODE

        if guest_interface:
            derived_guest = "%s-guest" % ssid if len("%s-guest" % ssid) <= 32 else "Turris-guest"
            guest_enabled = not parse_bool(guest_interface["data"].get("disabled", "0"))
            guest_ssid = guest_interface["data"].get("ssid", derived_guest)
            guest_password = guest_interface["data"].get("key", "")
            guest_wifi_encryption = guest_interface["data"].get("encryption", self.WIFI_UCI_DEFAULT_ENC_MODE)
            # compatibility with many different WPA2 mode names that are allowed in OpenWrt
            # "psk2*" -> WPA2
            if guest_wifi_encryption.startswith("psk2"):
                guest_wifi_encryption = "psk2+ccmp"
        else:
            guest_enabled = False
            guest_ssid = "%s-guest" % ssid
            guest_password = ""
            guest_wifi_encryption = self.WIFI_UCI_DEFAULT_ENC_MODE

        bands = WifiUci._get_device_bands(device_name)
        if not bands:
            # unable to determine wifi device name
            return None

        res = {
            "id": device_id,
            "enabled": enabled,
            "SSID": ssid,
            "channel": current_channel,
            "hidden": hidden,
            "hwmode": hwmode,
            "htmode": htmode,
            "encryption": self.WIFI_ENC_UCI_TO_MODES.get(wifi_encryption, "custom"),
            "ieee80211w_disabled": False,
            "password": password,
            "guest_wifi": {
                "enabled": guest_enabled,
                "SSID": guest_ssid,
                "password": guest_password,
                "encryption": self.WIFI_ENC_UCI_TO_MODES.get(guest_wifi_encryption, "custom"),
            },
            "available_bands": bands,
        }

        if res["encryption"] in ("WPA2/3", "WPA3"):  # we don't care about 802.11w outside of WPA3
            res["ieee80211w_disabled"] = ieee80211w_disabled

        return res

    @staticmethod
    def _get_hwmode(device) -> typing.Literal["11g", "11a"]:
        """Get device hwmode in compatible manner with OpenWrt 19.07

        OpenWrt 19.07 use `option hwmode` for setting frequency band
        OpenWrt 21.02 use `option band` instead

        Return either "11g" (2.4 GHz) or "11a" (5 Ghz)
        """
        BAND_HWMODE = {
            "2g": "11g",
            "5g": "11a",
        }
        FALLBACK_HWMODE = "11g"

        band = device["data"].get("band")
        if not band:
            hwmode = device["data"].get("hwmode", FALLBACK_HWMODE)
        else:
            hwmode = BAND_HWMODE.get(band, FALLBACK_HWMODE)

        return hwmode

    def _get_device_sections(self, data):
        return [
            e for e in get_sections_by_type(data, "wireless", "wifi-device") if not e["anonymous"]
        ]

    def _get_interface_sections_from_device_section(self, data, device_section):
        # first section is interface
        interface = [
            e
            for e in get_sections_by_type(data, "wireless", "wifi-iface")
            if e["data"].get("device") == device_section["name"]
            and (e["anonymous"] or not e["name"].startswith("guest_iface_"))
        ][0]
        # first non-anonymous section starting with 'guest_iface_' is guest wifi
        guest_interfaces = [
            e
            for e in get_sections_by_type(data, "wireless", "wifi-iface")
            if e["data"].get("device") == device_section["name"]
            and not e["anonymous"]
            and e["name"].startswith("guest_iface_")
        ]
        guest_interface = guest_interfaces[0] if guest_interfaces else None

        return interface, guest_interface

    def get_settings(self):
        """ Get current wifi settings
        :returns: {"devices": [{...}]}
        "rtype: dict
        """
        devices = []
        try:
            with UciBackend() as backend:
                data = backend.read("wireless")
            device_sections = self._get_device_sections(data)
            for device_section in device_sections:
                interface, guest_interface = self._get_interface_sections_from_device_section(
                    data, device_section
                )
                device = self._prepare_wifi_device(device_section, interface, guest_interface)
                if device:
                    devices.append(device)

        except (UciException, UciRecordNotFound):
            devices = []

        return {"devices": devices}

    def _update_wifi(
        self,
        backend: UciBackend,
        settings,
        device_section,
        interface_section,
        guest_interface_section,
    ) -> typing.Optional[bool]:
        """
        :param backend: instance of UciBackend
        :param settings: requested settings
        :param device_section: device configuration
        :param interface_section: regular wifi (i.e. non-guest) interface configuration
        :param guest_interface_section: guest wifi interface configuration
        :returns: True/False if guest interface is enabled/disabled or None if wifi is disabled
        :rtype: None or bool
        """
        DEFAULT_WIFI_ENC_MODE = "WPA2/3"
        HWMODE_BAND = {
            "11g": "2g",
            "11a": "5g",
        }
        # sections are supposed to exist so there is no need to create them

        if not settings["enabled"]:
            # disable everything
            backend.set_option("wireless", device_section["name"], "disabled", store_bool(True))
            backend.set_option("wireless", interface_section["name"], "disabled", store_bool(True))
            if guest_interface_section:
                backend.set_option(
                    "wireless", guest_interface_section["name"], "disabled", store_bool(True)
                )
            return None
        else:
            backend.set_option("wireless", device_section["name"], "disabled", store_bool(False))
            backend.set_option("wireless", interface_section["name"], "disabled", store_bool(False))
            # guest wifi is enabled elsewhere

        WifiUci._delete_old_config(backend, device_section["name"])

        # device
        channel = "auto" if settings["channel"] == 0 else int(settings["channel"])
        backend.set_option("wireless", device_section["name"], "channel", channel)
        backend.set_option("wireless", device_section["name"], "band", HWMODE_BAND[settings["hwmode"]])
        backend.set_option("wireless", device_section["name"], "htmode", settings["htmode"])

        # interface
        backend.set_option("wireless", interface_section["name"], "ssid", settings["SSID"])
        backend.set_option("wireless", interface_section["name"], "network", "lan")
        backend.set_option("wireless", interface_section["name"], "mode", "ap")
        backend.set_option(
            "wireless", interface_section["name"], "hidden", store_bool(settings["hidden"])
        )
        wifi_encryption = settings.get("encryption", DEFAULT_WIFI_ENC_MODE)
        ieee80211w_disabled = settings.get("ieee80211w_disabled", False)
        if wifi_encryption != "custom":  # custom == keep wifi encryption configuration intact
            self._set_wifi_encryption(backend, interface_section["name"], wifi_encryption, ieee80211w_disabled)
        backend.set_option("wireless", interface_section["name"], "key", settings["password"])

        # guest interface
        if not guest_interface_section:
            guest_name = "guest_iface_%d" % settings["id"]
            # prepare guest network if it doesn't exist
            backend.add_section("wireless", "wifi-iface", guest_name)
        else:
            guest_name = guest_interface_section["name"]

        if not settings["guest_wifi"]["enabled"]:
            # just add disabled and possibly update device if wifi-interface is newly created
            backend.set_option("wireless", guest_name, "disabled", store_bool(True))
            backend.set_option("wireless", guest_name, "device", device_section["name"])
            return False

        backend.set_option("wireless", guest_name, "disabled", store_bool(False))
        backend.set_option("wireless", guest_name, "device", device_section["name"])
        backend.set_option("wireless", guest_name, "mode", "ap")
        backend.set_option("wireless", guest_name, "ssid", settings["guest_wifi"]["SSID"])
        backend.set_option("wireless", guest_name, "network", "guest_turris")
        guest_wifi_encryption = settings["guest_wifi"].get("encryption", DEFAULT_WIFI_ENC_MODE)
        if guest_wifi_encryption != "custom":  # custom == keep wifi encryption configuration intact
            # apply the same encryption settings as main SSID to guest SSID
            self._set_wifi_encryption(backend, guest_name, guest_wifi_encryption, ieee80211w_disabled)
        backend.set_option("wireless", guest_name, "key", settings["guest_wifi"]["password"])
        guest_ifname = "guest_turris_%d" % settings["id"]
        backend.set_option("wireless", guest_name, "ifname", guest_ifname)
        backend.set_option("wireless", guest_name, "isolate", store_bool(True))

        return True

    @staticmethod
    def _delete_old_config(backend: UciBackend, device: str):
        """Delete OpenWrt 19.07 config options which are no longer used"""
        # OpenWrt 21.02 uses `option band` instead of `option hwmode`
        backend.del_option("wireless", device, "hwmode", fail_on_error=False)

    def _set_wifi_encryption(
        self,
        backend: UciBackend,
        if_name: str,
        wifi_encryption: str,
        ieee80211w_disabled: bool
    ) -> None:
        """Set wifi encryption mode and its related options
        :param backend: instance of UciBackend
        :param if_name: name of the interface (str)
        :param wifi_encryption: wifi encryption mode (str)
        """
        encryption_mode = self.WIFI_ENC_MODES_TO_UCI.get(wifi_encryption, self.WIFI_UCI_DEFAULT_ENC_MODE)
        backend.set_option("wireless", if_name, "encryption", encryption_mode)
        backend.set_option("wireless", if_name, "wpa_group_rekey", "86400")

        if encryption_mode in ("sae", "sae-mixed") and ieee80211w_disabled:
            # set ieee80211w only if WPA3 is used and ieee80211w is explicitly disabled
            backend.set_option("wireless", if_name, "ieee80211w", "0")
        else:
            backend.del_option("wireless", if_name, "ieee80211w", fail_on_error=False)

    @staticmethod
    def update_regulator_domain(data, backend, country_code):
        for section in get_sections_by_type(data, "wireless", "wifi-device"):
            backend.set_option("wireless", section["name"], "country", country_code)

    def update_settings(self, new_settings):
        """ Updates current wifi settings
        :param new_settings: {"devices": [{...}]}
        "type new_settings: dict
        :returns: True on success False otherwise
        "rtype: bool
        """
        try:
            with UciBackend() as backend:
                data = backend.read("wireless")  # data were read to find corresponding sections
                device_sections = self._get_device_sections(data)

                enable_guest_network = False

                for device in new_settings["devices"]:
                    device_section = [
                        e for e in device_sections if e["name"] == "radio%d" % device["id"]
                    ][0]

                    if device["enabled"]:
                        # test configuration

                        # find corresponding band
                        bands = [
                            e
                            for e in WifiUci._get_device_bands(device_section["name"])
                            if e and e["hwmode"] == device["hwmode"]
                        ]
                        if len(bands) != 1:
                            raise ValueError()
                        band = bands[0]

                        # test channels (0 means auto)
                        if device["channel"] not in [0] + [
                            e["number"] for e in band["available_channels"]
                        ]:
                            raise ValueError()
                        if device["htmode"] not in band["available_htmodes"]:
                            raise ValueError()

                    interface, guest_interface = self._get_interface_sections_from_device_section(
                        data, device_section
                    )

                    if self._update_wifi(
                        backend, device, device_section, interface, guest_interface
                    ):
                        enable_guest_network = True

                if enable_guest_network:
                    GuestUci.enable_guest_network(backend)

                # update regulatory according to _country
                system_data = backend.read("system")  # _country stored by time.update_settings
                country_code = get_option_anonymous(
                    system_data, "system", "system", 0, "_country", "00"
                )
                WifiUci.update_regulator_domain(data, backend, country_code)

        except (IndexError, ValueError):
            return False  # device not found changes were not commited - no partial changes passed

        MaintainCommands().restart_network()

        return True


class WifiCmds(BaseCmdLine):
    def set_regulatory_domain(self, country: typing.Optional[str]) -> bool:
        """ Sets regulatry domain for wifi cards
        :param country: country to be set or None, the None will cause that default 00 is set
        """
        country = country if country else "00"
        try:
            self._run_command_and_check_retval(["/usr/sbin/iw", "reg", "set", country], 0)
        except BackendCommandFailed:
            return False

        return True

    def reset(self):
        # export wireless config in case of any error
        with UciBackend() as backend:
            try:
                backup = backend.export_data("wireless")
            except UciException:
                backup = ""  # in case the wireless config is missing

        try:
            # clear wireless config
            with UciBackend() as backend:
                # detection can be performed only when empty wireless is present
                # import_data write to final conf immediatelly (not affected by commits)
                backend.import_data("", "wireless")
                # wifi config creates /etc/config/wireless and does not print output to stdout
                self._run_command_and_check_retval(["/sbin/wifi", "config"], 0)

        except Exception as e:
            logger.error("Exception occured during the reset '%r'", e)
            # try to restore the backup
            with UciBackend() as backend:
                backend.import_data(backup, "wireless")
            return False

        return True
