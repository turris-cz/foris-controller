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
import os

import pytest
from foris_controller_testtools.fixtures import (
    UCI_CONFIG_DIR_PATH,
    file_root_init,
    infrastructure,
    init_script_result,
    network_restart_command,
    only_backends,
    uci_configs_init,
)
from foris_controller_testtools.utils import (
    get_uci_module,
    match_subdict,
    network_restart_was_called,
)

from foris_controller.exceptions import UciRecordNotFound

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")


DEFAULT_CONFIG = [
    {
        "id": 0,
        "enabled": False,
        "SSID": "Turris",
        "hidden": False,
        "channel": 36,
        "htmode": "VHT160",
        "hwmode": "11a",
        "encryption": "WPA2/3",
        "password": "",
        "guest_wifi": {
            "enabled": False,
            "SSID": "Turris-guest",
            "password": "",
            "encryption": "WPA2/3",  # guest-wifi is disabled and turris defaults are used
        },
        "available_bands": [
            {
                "hwmode": "11g",
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
            },
            {
                "hwmode": "11a",
                "available_htmodes": ["NOHT", "HT20", "HT40", "VHT20", "VHT40", "VHT80", "VHT160"],
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
                    {"number": 181, "frequency": 5905, "radar": False}
                ],
            },
        ],
    },
    {
        "id": 1,
        "enabled": False,
        "SSID": "Turris",
        "hidden": False,
        "channel": 11,
        "htmode": "HT20",
        "hwmode": "11g",
        "password": "",
        "encryption": "WPA2/3",
        "guest_wifi": {
            "enabled": False,
            "SSID": "Turris-guest",
            "password": "",
            "encryption": "WPA2/3",  # guest-wifi is disabled and turris defaults are used
        },
        "available_bands": [
            {
                "hwmode": "11g",
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
            }
        ],
    },
]

# example data for update setting action
DEFAULT_UPDATE_DATA = [
    {
        "id": 0,
        "enabled": True,
        "SSID": "TurrisY",
        "hidden": True,
        "channel": 0,
        "htmode": "VHT20",
        "hwmode": "11a",
        "encryption": "WPA3",
        "password": "passpass",
        "guest_wifi": {"enabled": False},
    },
    {
        "id": 1,
        "enabled": True,
        "SSID": "TurrisX",
        "hidden": True,
        "channel": 0,
        "htmode": "NOHT",
        "hwmode": "11g",
        "encryption": "WPA2/3",
        "password": "passpass",
        "guest_wifi": {
            "enabled": True,
            "SSID": "Turris-testik",
            "password": "ssapssap",
            "encryption": "WPA2/3",
        },
    },
]


@pytest.fixture(scope="function", params=["config"])
def wifi_opt(request):
    WIFI_OPT_PATH = "/tmp/foris-controller-tests-wifi-detect-opt"
    with open(WIFI_OPT_PATH, "w") as f:
        f.write(request.param)
        f.flush()

    yield request.param

    os.unlink(WIFI_OPT_PATH)


def cut_out_htdata(data):
    """Cut out htmodes from other wifi data"""
    out = []
    for item in data:
        bands = []
        for band in item["available_bands"]:
            bands.append(
                {
                    "hwmode": band["hwmode"],
                    "available_htmodes": set(band.pop("available_htmodes"))
                }
            )
        out.append({
            "id": item["id"],
            "available_bands": bands,
        })

    return out


def match_default_openwrt_config(result_data):
    default_data = copy.deepcopy(DEFAULT_CONFIG)

    default_htmodes = cut_out_htdata(default_data)
    result_htmodes = cut_out_htdata(result_data)

    assert result_htmodes == default_htmodes
    assert result_data == default_data


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_settings(file_root_init, uci_configs_init, infrastructure):
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert res.keys() == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_custom_encryption(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):
    """Test that detection of custom encryption configuration is correct
    Foris-controller should handle any unexpected values of 'encryption' as 'custom'
    """
    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("wireless", "@wifi-iface[0]", "encryption", "psk+mixed")
        # "none" should be considered as "custom" only if is intentionally configured that way
        # If encryption is "none", but interface is disabled, consider this as default OpenWrt settings,
        # i.e. not configured yet
        backend.set_option("wireless", "@wifi-device[1]", "disabled", "0")
        backend.set_option("wireless", "@wifi-iface[1]", "disabled", "0")
        backend.set_option("wireless", "@wifi-iface[1]", "encryption", "none")

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )

    assert "devices" in res["data"].keys()
    devices = res["data"]["devices"]
    assert devices[0]["encryption"] == "custom"
    assert devices[1]["encryption"] == "custom"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_initial_tos_config(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):
    """In general Foris-controller should handle any unexpected values of 'encryption' as 'custom'

    However there is special case when default settings of unconfigured wifi or settings after wifi reset
    should return TOS default encryption mode.
    Intention is that user should initially see our preferred encryption mode in reForis for first time setup
    and once wifi is configured, then respect user choice and treat it as custom configuration.

    * encryption none && interface disabled => WPA2/3 (TOS preferred)
    * encryption none && interface enabled => custom (user wants it that way)
    """
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )

    assert "devices" in res["data"].keys()
    devices = res["data"]["devices"]
    assert devices[0]["encryption"] == "WPA2/3"
    assert devices[1]["encryption"] == "WPA2/3"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_without_encryption_set(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):
    """Test that default encryption values are returned in case the option is missing"""
    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # clear the encryption options
        backend.del_option("wireless", "@wifi-iface[0]", "encryption")
        backend.del_option("wireless", "@wifi-iface[1]", "encryption")

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )

    assert "devices" in res["data"].keys()
    devices = res["data"]["devices"]
    assert devices[0]["encryption"] == "WPA2/3"
    assert devices[1]["encryption"] == "WPA2/3"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_update_settings(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):
    filters = [("wifi", "update_settings")]

    def update(result, *devices):
        devices = list(devices)
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": devices},
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": result},
            "kind": "reply",
            "module": "wifi",
        }

        if not result:
            return

        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1] == {
            "module": "wifi",
            "action": "update_settings",
            "kind": "notification",
            "data": {"devices": devices},
        }

        res = infrastructure.process_message(
            {"module": "wifi", "action": "get_settings", "kind": "request"}
        )

        assert res["module"] == "wifi"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert "devices" in res["data"]
        for device in devices:
            obtained = [e for e in res["data"]["devices"] if e["id"] == device["id"]]
            assert len(obtained) == 1
            assert match_subdict(device, obtained[0])

    update(True)  # empty list
    update(
        True,
        {
            "id": 0,
            "enabled": True,
            "SSID": "Turris",
            "hidden": False,
            "channel": 11,
            "htmode": "HT20",
            "hwmode": "11g",
            "encryption": "WPA2",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {"id": 1, "enabled": False},
    )
    update(
        True,
        {
            "id": 0,
            "enabled": True,
            "SSID": "TurrisY",
            "hidden": True,
            "channel": 40,
            "htmode": "VHT20",
            "hwmode": "11a",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "TurrisX",
            "hidden": True,
            "channel": 6,
            "htmode": "NOHT",
            "hwmode": "11g",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {
                "enabled": True,
                "SSID": "Turris-testik",
                "password": "ssapssap",
                "encryption": "WPA2",
            },
        },
    )

    # test auto channels
    update(
        True,
        {
            "id": 0,
            "enabled": True,
            "SSID": "TurrisY",
            "hidden": True,
            "channel": 0,
            "htmode": "VHT20",
            "hwmode": "11a",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "TurrisX",
            "hidden": True,
            "channel": 0,
            "htmode": "NOHT",
            "hwmode": "11g",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {
                "enabled": True,
                "SSID": "Turris-testik",
                "password": "ssapssap",
                "encryption": "WPA2/3",
            },
        },
    )

    # more records than devices
    update(
        False,
        {
            "id": 0,
            "enabled": True,
            "SSID": "Turris",
            "hidden": False,
            "channel": 11,
            "htmode": "HT20",
            "hwmode": "11g",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "Turris",
            "hidden": False,
            "channel": 11,
            "htmode": "HT20",
            "hwmode": "11g",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 2,
            "enabled": True,
            "SSID": "Turris",
            "hidden": False,
            "channel": 11,
            "htmode": "HT20",
            "hwmode": "11g",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
    )

    # unsupported mode
    update(
        False,
        {
            "id": 0,
            "enabled": True,
            "SSID": "TurrisYY",
            "hidden": True,
            "channel": 40,
            "htmode": "VHT20",
            "hwmode": "11a",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "TurrisXX",
            "hidden": True,
            "channel": 44,
            "htmode": "NOHT",
            "hwmode": "11a",
            "encryption": "WPA3",
            "password": "passpass",
            "guest_wifi": {
                "enabled": True,
                "SSID": "Turris-testik",
                "password": "ssapssap",
                "encryption": "WPA2/3",
            },
        },
    )


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("wpa2_mode", ["psk2", "psk2+aes", "psk2+tkip+ccmp"])
def test_update_and_get_wpa2_modes(
    init_script_result,
    file_root_init,
    uci_configs_init,
    infrastructure,
    network_restart_command,
    wpa2_mode,
):
    """
    Set WPA2 encryption for both regular and guest wifi
    Change "psk2+ccmp" to alternative psk2 mode
    Then check compatibility with many different WPA2 mode names that are allowed in OpenWrt
    i.e.: "psk2*" -> WPA2
    """
    devices = [
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev111",
            "hidden": True,
            "channel": 0,
            "htmode": "NOHT",
            "hwmode": "11a",
            "encryption": "WPA2",
            "password": "passpass",
            "guest_wifi": {"enabled": True, "password": "passpassg", "SSID": "Dev111G", "encryption": "WPA2"},
        },
        {"id": 1, "enabled": False},
    ]

    res = infrastructure.process_message(
        {
            "module": "wifi",
            "action": "update_settings",
            "kind": "request",
            "data": {"devices": devices},
        }
    )

    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }

    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("wireless", "default_radio0", "encryption", wpa2_mode)
        backend.set_option("wireless", "guest_iface_0", "encryption", wpa2_mode)

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )

    wifi_dev = res["data"]["devices"][0]
    assert wifi_dev["encryption"] == "WPA2"
    assert wifi_dev["guest_wifi"]["encryption"] == "WPA2"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_uci(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):

    uci = get_uci_module(infrastructure.name)

    def update(*devices):
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": devices},
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wifi",
        }
        network_restart_was_called([])
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            data = backend.read()
        return data

    def get_sections(data, radio_name):
        # get sections where device is radioX
        real_section = [
            e
            for e in uci.get_sections_by_type(data, "wireless", "wifi-iface")
            if e["data"].get("device") == radio_name
            and not e.get("name", "").startswith("guest_iface_")
        ][0]["name"]
        guest_section = [
            e
            for e in uci.get_sections_by_type(data, "wireless", "wifi-iface")
            if e["data"].get("device") == radio_name
            and e.get("name", "").startswith("guest_iface_")
        ][0]["name"]
        return real_section, guest_section

    data = update(
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev1",
            "hidden": False,
            "channel": 36,
            "htmode": "VHT80",
            "hwmode": "11a",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "Dev2",
            "hidden": False,
            "channel": 11,
            "htmode": "HT20",
            "hwmode": "11g",
            "encryption": "WPA3",
            "password": "ssapssap",
            "guest_wifi": {"enabled": False},
        },
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "36"
    assert uci.get_option_named(data, "wireless", "radio0", "band") == "5g"
    assert uci.get_option_named(data, "wireless", "radio0", "htmode") == "VHT80"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", "radio0", "disabled", "0")) is False
    )
    real_section, guest_section = get_sections(data, "radio0")
    assert uci.get_option_named(data, "wireless", real_section, "ssid") == "Dev1"
    assert uci.get_option_named(data, "wireless", real_section, "key") == "passpass"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is False
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "hidden", "0")) is False
    )
    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "sae-mixed"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    assert uci.get_option_named(data, "wireless", "radio1", "channel") == "11"
    assert uci.get_option_named(data, "wireless", "radio1", "band") == "2g"
    assert uci.get_option_named(data, "wireless", "radio1", "htmode") == "HT20"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", "radio1", "disabled", "0")) is False
    )
    real_section, guest_section = get_sections(data, "radio1")
    assert uci.get_option_named(data, "wireless", real_section, "ssid") == "Dev2"
    assert uci.get_option_named(data, "wireless", real_section, "key") == "ssapssap"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is False
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "hidden", "0")) is False
    )
    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "sae"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    data = update(
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev11",
            "hidden": False,
            "channel": 40,
            "htmode": "VHT40",
            "hwmode": "11a",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "Dev22",
            "hidden": True,
            "channel": 12,
            "htmode": "HT40",
            "hwmode": "11g",
            "encryption": "WPA3",
            "password": "ssapssap",
            "guest_wifi": {"enabled": True, "SSID": "Dev22G", "password": "ssapssapg", "encryption": "WPA2"},
        },
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "40"
    assert uci.get_option_named(data, "wireless", "radio0", "band") == "5g"
    assert uci.get_option_named(data, "wireless", "radio0", "htmode") == "VHT40"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", "radio0", "disabled", "0")) is False
    )
    real_section, guest_section = get_sections(data, "radio0")
    assert uci.get_option_named(data, "wireless", real_section, "ssid") == "Dev11"
    assert uci.get_option_named(data, "wireless", real_section, "key") == "passpass"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is False
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "hidden", "0")) is False
    )
    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "sae-mixed"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    assert uci.get_option_named(data, "wireless", "radio1", "channel") == "12"
    assert uci.get_option_named(data, "wireless", "radio1", "band") == "2g"
    assert uci.get_option_named(data, "wireless", "radio1", "htmode") == "HT40"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", "radio1", "disabled", "0")) is False
    )
    real_section, guest_section = get_sections(data, "radio1")
    assert uci.get_option_named(data, "wireless", real_section, "ssid") == "Dev22"
    assert uci.get_option_named(data, "wireless", real_section, "key") == "ssapssap"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is False
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "hidden", "0")) is True
    )

    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "sae"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is False
    )
    assert uci.get_option_named(data, "wireless", guest_section, "ssid") == "Dev22G"
    assert uci.get_option_named(data, "wireless", guest_section, "key") == "ssapssapg"
    assert uci.get_option_named(data, "wireless", guest_section, "encryption") == "psk2+ccmp"
    assert uci.get_option_named(data, "wireless", guest_section, "wpa_group_rekey") == "86400"
    assert uci.get_option_named(data, "wireless", guest_section, "mode") == "ap"
    assert uci.get_option_named(data, "wireless", guest_section, "network") == "guest_turris"

    assert (
        uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled", "0"))
        is True
    )

    # test setting auto frequency
    data = update(
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev111",
            "hidden": True,
            "channel": 0,
            "htmode": "NOHT",
            "hwmode": "11a",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {"enabled": True, "password": "passpassg", "SSID": "Dev111G", "encryption": "WPA2"},
        },
        {"id": 1, "enabled": False},
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "auto"
    assert uci.get_option_named(data, "wireless", "radio0", "band") == "5g"
    assert uci.get_option_named(data, "wireless", "radio0", "htmode") == "NOHT"
    real_section, guest_section = get_sections(data, "radio0")
    assert uci.get_option_named(data, "wireless", guest_section, "encryption") == "psk2+ccmp"
    assert uci.get_option_named(data, "wireless", guest_section, "wpa_group_rekey") == "86400"

    assert uci.parse_bool(uci.get_option_named(data, "wireless", "radio1", "disabled", "0")) is True
    real_section, guest_section = get_sections(data, "radio1")
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is True
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )
    assert uci.get_option_named(data, "wireless", guest_section, "encryption") == "psk2+ccmp"
    assert (
        uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled", "0"))
        is True
    )

    data = update({"id": 0, "enabled": False}, {"id": 1, "enabled": False})

    assert uci.parse_bool(uci.get_option_named(data, "wireless", "radio0", "disabled", "0")) is True
    real_section, guest_section = get_sections(data, "radio0")
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is True
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    assert uci.parse_bool(uci.get_option_named(data, "wireless", "radio1", "disabled", "0")) is True
    real_section, guest_section = get_sections(data, "radio1")
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", real_section, "disabled", "0"))
        is True
    )
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )


@pytest.mark.only_backends(["openwrt"])
def test_update_settings_migrate_old_syntax_uci(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):

    uci = get_uci_module(infrastructure.name)

    def update(*devices):
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": devices},
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wifi",
        }
        network_restart_was_called([])
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            data = backend.read()
        return data

    # init config first to look like OpenWrt 19.07
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("wireless", "radio0", "band", fail_on_error=False)
        backend.set_option("wireless", "radio0", "hwmode", "11a")
        backend.del_option("wireless", "radio1", "band", fail_on_error=False)
        backend.set_option("wireless", "radio1", "hwmode", "11g")

    data = update(
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev1",
            "hidden": False,
            "channel": 36,
            "htmode": "VHT80",
            "hwmode": "11a",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        },
        {
            "id": 1,
            "enabled": False,
        },
    )

    assert uci.get_option_named(data, "wireless", "radio0", "band") == "5g"
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "wireless", "radio0", "hwmode")

    assert uci.get_option_named(data, "wireless", "radio1", "hwmode") == "11g"
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "wireless", "radio1", "band")

    # enable second radio
    data = update(
        {
            "id": 0,
            "enabled": False,
        },
        {
            "id": 1,
            "enabled": True,
            "SSID": "Dev2",
            "hidden": False,
            "channel": 11,
            "htmode": "HT40",
            "hwmode": "11g",
            "encryption": "WPA2/3",
            "password": "passpass",
            "guest_wifi": {"enabled": False},
        }
    )

    assert uci.get_option_named(data, "wireless", "radio0", "band") == "5g"
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "wireless", "radio0", "hwmode")

    assert uci.get_option_named(data, "wireless", "radio1", "band") == "2g"
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "wireless", "radio1", "hwmode")


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_wrong_update(file_root_init, uci_configs_init, infrastructure):
    def update(*devices):
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": devices},
            }
        )
        assert "errors" in res

    # enabled false
    update(
        [
            {
                "id": 1,
                "enabled": False,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )

    # enabled wifi false
    update(
        [
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False, "SSID": "Turris-guest", "password": "passpass"},
            }
        ]
    )

    # wrong ht mode
    update(
        [
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "VTH20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )
    update(
        [
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "VTH40",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )
    update(
        [
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "VTH80",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )

    # mismatching frequences
    update(
        [
            {
                "id": 0,
                "enabled": False,
                "SSID": "Turris",
                "hidden": False,
                "channel": 40,
                "htmode": "HT20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )
    update(
        [
            {
                "id": 0,
                "enabled": False,
                "SSID": "Turris",
                "hidden": False,
                "channel": 10,
                "htmode": "HT20",
                "hwmode": "11a",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )

    # too long SSID
    update(
        [
            {
                "id": 0,
                "enabled": False,
                "SSID": "This SSID has more than 32 charac",
                "hidden": False,
                "channel": 10,
                "htmode": "HT20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            }
        ]
    )
    update(
        [
            {
                "id": 0,
                "enabled": False,
                "SSID": "Turris",
                "hidden": False,
                "channel": 40,
                "htmode": "HT20",
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "This SSID has more than 32 charac",
                    "password": "passpass",
                },
            }
        ]
    )


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_reset(wifi_opt, file_root_init, uci_configs_init, infrastructure, network_restart_command):
    res = infrastructure.process_message(
        {
            "module": "wifi",
            "action": "update_settings",
            "kind": "request",
            "data": {"devices": DEFAULT_UPDATE_DATA},
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }

    filters = [("wifi", "reset")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({"module": "wifi", "action": "reset", "kind": "request"})
    assert res == {
        "action": "reset",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {"module": "wifi", "action": "reset", "kind": "notification"}

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial openwrt situation (based on default omnia settings)
    match_default_openwrt_config(res["data"]["devices"])


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_reset_openwrt(wifi_opt, file_root_init, uci_configs_init, infrastructure, network_restart_command):
    res = infrastructure.process_message(
        {
            "module": "wifi",
            "action": "update_settings",
            "kind": "request",
            "data": {"devices": DEFAULT_UPDATE_DATA},
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }

    filters = [("wifi", "reset")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({"module": "wifi", "action": "reset", "kind": "request"})
    assert res == {
        "action": "reset",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {"module": "wifi", "action": "reset", "kind": "notification"}

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial openwrt situation (based on default omnia settings)
    match_default_openwrt_config(res["data"]["devices"])

    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        uci_data = backend.read()

    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-iface", 0, "encryption") == "none"
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-iface", 1, "encryption") == "none"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_too_long_generated_guest_ssid(
    file_root_init, uci_configs_init, infrastructure, network_restart_command
):
    res = infrastructure.process_message(
        {
            "module": "wifi",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "devices": [
                    {
                        "id": 0,
                        "enabled": True,
                        "SSID": "This SSID has less than 32 chars",
                        "hidden": False,
                        "channel": 10,
                        "htmode": "HT20",
                        "hwmode": "11g",
                        "encryption": "WPA2/3",
                        "password": "passpass",
                        "guest_wifi": {"enabled": False},
                    }
                ]
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "wifi",
    }
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["devices"][0]["guest_wifi"]["SSID"] == "Turris-guest"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_missing_wireless(file_root_init, uci_configs_init, infrastructure):
    os.unlink(os.path.join(uci_configs_init[0], "wireless"))
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}


@pytest.mark.only_backends(["openwrt"])
def test_get_hwmode_openwrt_19_07(infrastructure, uci_configs_init):
    """Test that we get correct hwmode from OpenWrt 19.07 config syntax

    OpenWrt 19.07 uses `option hwmode` for frequency band
    """
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("wireless", "radio0", "band")
        backend.set_option("wireless", "radio0", "hwmode", "11a")

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        uci_data = backend.read()

    assert uci.get_option_named(uci_data, "wireless", "radio0", "hwmode") == "11a"


@pytest.mark.only_backends(["openwrt"])
def test_get_hwmode_openwrt_21_02(infrastructure, uci_configs_init):
    """Test that we get correct hwmode from OpenWrt 21.02 config syntax

    OpenWrt 21.02 uses `option band` instead of `option hwmode`
    """
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # Make sure that `option hwmode` is not interfering
        backend.del_option("wireless", "radio0", "hwmode", fail_on_error=False)

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        uci_data = backend.read()

    assert uci.get_option_named(uci_data, "wireless", "radio0", "band") == "5g"


@pytest.mark.only_backends(["openwrt"])
def test_get_hwmode_fallback_openwrt(infrastructure, uci_configs_init):
    """Test that we get fallback hwmode even if options `band` or `hwmode` are missing

    In case both options are missing, we should fallback to "11g" (2.4 GHz)
    """
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("wireless", "radio0", "band", fail_on_error=False)
        backend.del_option("wireless", "radio0", "hwmode", fail_on_error=False)

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res
    assert res["data"]["devices"][0]["hwmode"] == "11g"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_uci_country(
    init_script_result, file_root_init, uci_configs_init, infrastructure, network_restart_command,
):

    uci = get_uci_module(infrastructure.name)

    def set_country(country):
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            backend.set_option("system", "@system[0]", "_country", country)

    def update():
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {
                    "devices": [
                        {
                            "id": 0,
                            "enabled": True,
                            "SSID": "Devxxx",
                            "hidden": True,
                            "channel": 0,
                            "htmode": "NOHT",
                            "hwmode": "11a",
                            "encryption": "WPA3",
                            "password": "passpass",
                            "guest_wifi": {
                                "enabled": True,
                                "password": "passpassg",
                                "SSID": "Dev111G",
                                "encryption": "WPA3",
                            },
                        },
                        {"id": 1, "enabled": False},
                    ]
                },
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wifi",
        }
        network_restart_was_called([])
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            data = backend.read()
        return data

    set_country("")  # unset _country
    uci_data = update()
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 0, "country") == "00"
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 1, "country") == "00"

    set_country("CZ")
    uci_data = update()
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 0, "country") == "CZ"
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 1, "country") == "CZ"

    set_country("UK")
    uci_data = update()
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 0, "country") == "UK"
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 1, "country") == "UK"

    set_country("")
    uci_data = update()
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 0, "country") == "00"
    assert uci.get_option_anonymous(uci_data, "wireless", "wifi-device", 1, "country") == "00"
