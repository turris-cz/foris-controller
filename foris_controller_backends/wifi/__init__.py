#
# foris-controller
# Copyright (C) 2018-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.exceptions import UciException, UciRecordNotFound, BackendCommandFailed
from foris_controller_backends.uci import (
    UciBackend,
    get_sections_by_type,
    store_bool,
    parse_bool,
    get_option_anonymous,
)

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.guest import GuestUci
from foris_controller_backends.maintain import MaintainCommands

logger = logging.getLogger(__name__)


class WifiUci(object):
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
    def _get_device_bands(device_name):
        DEFAULT_HTMODES = {"NOHT"}
        HTMODES = {"HT20", "HT40"}
        VHTMODES = HTMODES | {"VHT20", "VHT40", "VHT80", "VHT160"}

        MODES_MAP = {
            "11g": "n",
            "11a": "ac",
        }

        request_msg = {"device": device_name}
        ht_data = WifiUci.call_ubus("iwinfo", "info", request_msg)
        if not ht_data:
            return []

        freq_data = WifiUci.call_ubus("iwinfo", "freqlist", request_msg)
        if not freq_data:
            return []

        htmodes = {}
        channels = {"11g": [], "11a": []}

        for freq in freq_data["results"]:
            channel = {
                "number": freq["channel"],
                "frequency": freq["mhz"],
                "radar": False,  # iwinfo/rpcd doesn't return DFS flags; use False for compatibility
            }
            channels["11a" if channel["frequency"] > 2484 else "11g"].append(channel)

        if "ac" in ht_data["hwmodes"]:
            htmodes["ac"] = list(DEFAULT_HTMODES | (set(ht_data["htmodes"]) & VHTMODES))

        if "n" in ht_data["hwmodes"]:
            htmodes["n"] = list(DEFAULT_HTMODES | (set(ht_data["htmodes"]) & HTMODES))

        return [
            {
                "available_channels": channels[hwmode],
                "available_htmodes": htmodes[MODES_MAP[hwmode]],
                "hwmode": hwmode,
            }
            for hwmode in ["11g", "11a"]
            if len(channels[hwmode]) > 0
        ]

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
        hwmode = device["data"].get("hwmode", "11g")
        htmode = device["data"].get("htmode", "NOHT")
        current_channel = device["data"].get("channel", "11" if hwmode == "11g" else "36")
        current_channel = 0 if current_channel == "auto" else int(current_channel)

        if guest_interface:
            derived_guest = "%s-guest" % ssid if len("%s-guest" % ssid) <= 32 else "Turris-guest"
            guest_enabled = not parse_bool(guest_interface["data"].get("disabled", "0"))
            guest_ssid = guest_interface["data"].get("ssid", derived_guest)
            guest_password = guest_interface["data"].get("key", "")
        else:
            guest_enabled = False
            guest_ssid = "%s-guest" % ssid
            guest_password = ""

        bands = WifiUci._get_device_bands(device_name)
        if not bands:
            # unable to determine wifi device name
            return None

        return {
            "id": device_id,
            "enabled": enabled,
            "SSID": ssid,
            "channel": current_channel,
            "hidden": hidden,
            "hwmode": hwmode,
            "htmode": htmode,
            "password": password,
            "guest_wifi": {
                "enabled": guest_enabled,
                "SSID": guest_ssid,
                "password": guest_password,
            },
            "available_bands": bands,
        }

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
        self, backend, settings, device_section, interface_section, guest_interface_section
    ):
        """
        :returns: Name of the guest interface if guest interface is enabled otherwise None
        :rtype: None or str
        """
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

        # device
        channel = "auto" if settings["channel"] == 0 else int(settings["channel"])
        backend.set_option("wireless", device_section["name"], "channel", channel)
        backend.set_option("wireless", device_section["name"], "hwmode", settings["hwmode"])
        backend.set_option("wireless", device_section["name"], "htmode", settings["htmode"])

        # interface
        backend.set_option("wireless", interface_section["name"], "ssid", settings["SSID"])
        backend.set_option("wireless", interface_section["name"], "network", "lan")
        backend.set_option("wireless", interface_section["name"], "mode", "ap")
        backend.set_option(
            "wireless", interface_section["name"], "hidden", store_bool(settings["hidden"])
        )
        if interface_section["data"].get("encryption", "none") == "none":
            backend.set_option("wireless", interface_section["name"], "encryption", "psk2+ccmp")
        backend.set_option("wireless", interface_section["name"], "wpa_group_rekey", "86400")
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
        if (
            not guest_interface_section
            or guest_interface_section["data"].get("encryption", "none") == "none"
        ):
            backend.set_option("wireless", guest_name, "encryption", "psk2+ccmp")
        backend.set_option("wireless", guest_name, "wpa_group_rekey", "86400")
        backend.set_option("wireless", guest_name, "key", settings["guest_wifi"]["password"])
        guest_ifname = "guest_turris_%d" % settings["id"]
        backend.set_option("wireless", guest_name, "ifname", guest_ifname)
        backend.set_option("wireless", guest_name, "isolate", store_bool(True))

        return True

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
