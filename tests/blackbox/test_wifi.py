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

import os
import pytest

from foris_controller_testtools.fixtures import (
    only_backends,
    uci_configs_init,
    infrastructure,
    file_root_init,
    init_script_result,
    network_restart_command,
    UCI_CONFIG_DIR_PATH,
    start_buses,
    ubusd_test,
    mosquitto_test,
)
from foris_controller_testtools.utils import (
    match_subdict,
    get_uci_module,
    network_restart_was_called,
)


FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")


DEFAULT_CONFIG = [
    {
        u"id": 0,
        u"enabled": False,
        u"SSID": u"Turris",
        u"hidden": False,
        u"channel": 36,
        u"htmode": u"VHT80",
        u"hwmode": u"11a",
        u"password": u"",
        u"guest_wifi": {u"enabled": False, u"SSID": u"Turris-guest", u"password": u""},
        u"available_bands": [
            {
                u"hwmode": "11g",
                u"available_htmodes": [u"NOHT", u"HT20", u"HT40"],
                u"available_channels": [
                    {u"number": 1, u"frequency": 2412, u"radar": False},
                    {u"number": 2, u"frequency": 2417, u"radar": False},
                    {u"number": 3, u"frequency": 2422, u"radar": False},
                    {u"number": 4, u"frequency": 2427, u"radar": False},
                    {u"number": 5, u"frequency": 2432, u"radar": False},
                    {u"number": 6, u"frequency": 2437, u"radar": False},
                    {u"number": 7, u"frequency": 2442, u"radar": False},
                    {u"number": 8, u"frequency": 2447, u"radar": False},
                    {u"number": 9, u"frequency": 2452, u"radar": False},
                    {u"number": 10, u"frequency": 2457, u"radar": False},
                    {u"number": 11, u"frequency": 2462, u"radar": False},
                    {u"number": 12, u"frequency": 2467, u"radar": False},
                    {u"number": 13, u"frequency": 2472, u"radar": False},
                ],
            },
            {
                u"hwmode": "11a",
                u"available_htmodes": [u"NOHT", u"HT20", u"HT40", u"VHT20", u"VHT40", u"VHT80"],
                u"available_channels": [
                    {u"number": 36, u"frequency": 5180, u"radar": False},
                    {u"number": 40, u"frequency": 5200, u"radar": False},
                    {u"number": 44, u"frequency": 5220, u"radar": False},
                    {u"number": 48, u"frequency": 5240, u"radar": False},
                    {u"number": 52, u"frequency": 5260, u"radar": True},
                    {u"number": 56, u"frequency": 5280, u"radar": True},
                    {u"number": 60, u"frequency": 5300, u"radar": True},
                    {u"number": 64, u"frequency": 5320, u"radar": True},
                    {u"number": 100, u"frequency": 5500, u"radar": True},
                    {u"number": 104, u"frequency": 5520, u"radar": True},
                    {u"number": 108, u"frequency": 5540, u"radar": True},
                    {u"number": 112, u"frequency": 5560, u"radar": True},
                    {u"number": 116, u"frequency": 5580, u"radar": True},
                    {u"number": 120, u"frequency": 5600, u"radar": True},
                    {u"number": 124, u"frequency": 5620, u"radar": True},
                    {u"number": 128, u"frequency": 5640, u"radar": True},
                    {u"number": 132, u"frequency": 5660, u"radar": True},
                    {u"number": 136, u"frequency": 5680, u"radar": True},
                    {u"number": 140, u"frequency": 5700, u"radar": True},
                ],
            },
        ],
    },
    {
        u"id": 1,
        u"enabled": False,
        u"SSID": u"Turris",
        u"hidden": False,
        u"channel": 11,
        u"htmode": u"HT20",
        u"hwmode": u"11g",
        u"password": u"",
        u"guest_wifi": {u"enabled": False, u"SSID": u"Turris-guest", u"password": u""},
        u"available_bands": [
            {
                u"hwmode": "11g",
                u"available_htmodes": [u"NOHT", u"HT20", u"HT40"],
                u"available_channels": [
                    {u"number": 1, u"frequency": 2412, u"radar": False},
                    {u"number": 2, u"frequency": 2417, u"radar": False},
                    {u"number": 3, u"frequency": 2422, u"radar": False},
                    {u"number": 4, u"frequency": 2427, u"radar": False},
                    {u"number": 5, u"frequency": 2432, u"radar": False},
                    {u"number": 6, u"frequency": 2437, u"radar": False},
                    {u"number": 7, u"frequency": 2442, u"radar": False},
                    {u"number": 8, u"frequency": 2447, u"radar": False},
                    {u"number": 9, u"frequency": 2452, u"radar": False},
                    {u"number": 10, u"frequency": 2457, u"radar": False},
                    {u"number": 11, u"frequency": 2462, u"radar": False},
                    {u"number": 12, u"frequency": 2467, u"radar": False},
                    {u"number": 13, u"frequency": 2472, u"radar": False},
                ],
            }
        ],
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


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_settings(file_root_init, uci_configs_init, infrastructure, start_buses):
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial situation (based on default omnia settings)
    assert res["data"]["devices"] == DEFAULT_CONFIG


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_update_settings(
    init_script_result,
    file_root_init,
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
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
            u"action": u"update_settings",
            u"data": {u"result": result},
            u"kind": u"reply",
            u"module": u"wifi",
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
            "password": "passpass",
            "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
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
            "password": "passpass",
            "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
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
            "password": "passpass",
            "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
        },
    )


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_uci(
    init_script_result,
    file_root_init,
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
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
            u"action": u"update_settings",
            u"data": {u"result": True},
            u"kind": u"reply",
            u"module": u"wifi",
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
            "password": "ssapssap",
            "guest_wifi": {"enabled": False},
        },
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "36"
    assert uci.get_option_named(data, "wireless", "radio0", "hwmode") == "11a"
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
    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "psk2+ccmp"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    assert uci.get_option_named(data, "wireless", "radio1", "channel") == "11"
    assert uci.get_option_named(data, "wireless", "radio1", "hwmode") == "11g"
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
            "password": "ssapssap",
            "guest_wifi": {"enabled": True, "SSID": "Dev22G", "password": "ssapssapg"},
        },
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "40"
    assert uci.get_option_named(data, "wireless", "radio0", "hwmode") == "11a"
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
    assert uci.get_option_named(data, "wireless", real_section, "encryption") == "psk2+ccmp"
    assert uci.get_option_named(data, "wireless", real_section, "wpa_group_rekey") == "86400"
    assert (
        uci.parse_bool(uci.get_option_named(data, "wireless", guest_section, "disabled", "0"))
        is True
    )

    assert uci.get_option_named(data, "wireless", "radio1", "channel") == "12"
    assert uci.get_option_named(data, "wireless", "radio1", "hwmode") == "11g"
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

    data = update(
        {
            "id": 0,
            "enabled": True,
            "SSID": "Dev111",
            "hidden": True,
            "channel": 0,
            "htmode": "NOHT",
            "hwmode": "11a",
            "password": "passpass",
            "guest_wifi": {"enabled": True, "password": "passpassg", "SSID": "Dev111G"},
        },
        {"id": 1, "enabled": False},
    )

    assert uci.get_option_named(data, "wireless", "radio0", "channel") == "auto"
    assert uci.get_option_named(data, "wireless", "radio0", "hwmode") == "11a"
    assert uci.get_option_named(data, "wireless", "radio0", "htmode") == "NOHT"
    real_section, guest_section = get_sections(data, "radio0")

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


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_wrong_update(file_root_init, uci_configs_init, infrastructure, start_buses):
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
def test_reset(
    wifi_opt, file_root_init, uci_configs_init, infrastructure, start_buses, network_restart_command
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
                        "SSID": "TurrisY",
                        "hidden": True,
                        "channel": 0,
                        "htmode": "VHT20",
                        "hwmode": "11a",
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
                        "password": "passpass",
                        "guest_wifi": {
                            "enabled": True,
                            "SSID": "Turris-testik",
                            "password": "ssapssap",
                        },
                    },
                ]
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }

    filters = [("wifi", "reset")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({"module": "wifi", "action": "reset", "kind": "request"})
    assert res == {
        u"action": u"reset",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {u"module": u"wifi", u"action": u"reset", u"kind": u"notification"}

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial situation (based on default omnia settings)

    assert res["data"]["devices"] == DEFAULT_CONFIG


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_too_long_generated_guest_ssid(
    file_root_init, uci_configs_init, infrastructure, start_buses, network_restart_command
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
                        "password": "passpass",
                        "guest_wifi": {"enabled": False},
                    }
                ]
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["devices"][0]["guest_wifi"]["SSID"] == "Turris-guest"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_modify_encryption_only_if_none(
    init_script_result,
    file_root_init,
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
):
    uci = get_uci_module(infrastructure.name)

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
                        "SSID": "Turris",
                        "hidden": False,
                        "channel": 10,
                        "htmode": "HT20",
                        "hwmode": "11g",
                        "password": "passpass",
                        "guest_wifi": {
                            "SSID": "Turris-guest",
                            "enabled": True,
                            "password": "passpass",
                        },
                    }
                ]
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert uci.get_option_anonymous(data, "wireless", "wifi-iface", 0, "encryption") == "psk2+ccmp"
    assert uci.get_option_named(data, "wireless", "guest_iface_0", "encryption") == "psk2+ccmp"

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("wireless", "@wifi-iface[0]", "encryption", "psk2+tkip+ccmp")
        backend.set_option("wireless", "guest_iface_0", "encryption", "psk2+tkip+ccmp")

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
                        "SSID": "Turris",
                        "hidden": False,
                        "channel": 10,
                        "htmode": "HT20",
                        "hwmode": "11g",
                        "password": "passpass",
                        "guest_wifi": {
                            "SSID": "Turris-guest",
                            "enabled": True,
                            "password": "passpass",
                        },
                    }
                ]
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert (
        uci.get_option_anonymous(data, "wireless", "wifi-iface", 0, "encryption")
        == "psk2+tkip+ccmp"
    )
    assert uci.get_option_named(data, "wireless", "guest_iface_0", "encryption") == "psk2+tkip+ccmp"


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_settings_and_reset(
    wifi_opt, file_root_init, uci_configs_init, infrastructure, start_buses
):
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial situation (based on default omnia settings)
    assert res["data"]["devices"] == DEFAULT_CONFIG

    res = infrastructure.process_message({"module": "wifi", "action": "reset", "kind": "request"})
    assert res == {
        u"action": u"reset",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"wifi",
    }

    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "devices" in res["data"].keys()
    # test initial situation (based on default omnia settings)
    assert res["data"]["devices"] == DEFAULT_CONFIG


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_missing_wireless(
    file_root_init, uci_configs_init, infrastructure, start_buses
):
    os.unlink(os.path.join(uci_configs_init[0], "wireless"))
    res = infrastructure.process_message(
        {"module": "wifi", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_uci_country(
    init_script_result,
    file_root_init,
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
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
                            "password": "passpass",
                            "guest_wifi": {
                                "enabled": True,
                                "password": "passpassg",
                                "SSID": "Dev111G",
                            },
                        },
                        {"id": 1, "enabled": False},
                    ]
                },
            }
        )
        assert res == {
            u"action": u"update_settings",
            u"data": {u"result": True},
            u"kind": u"reply",
            u"module": u"wifi",
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
