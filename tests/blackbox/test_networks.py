#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import pytest
import os

from foris_controller_testtools.fixtures import (
    only_backends,
    uci_configs_init,
    infrastructure,
    lock_backend,
    init_script_result,
    network_restart_command,
    device,
    turris_os_version,
    notify_api,
    UCI_CONFIG_DIR_PATH,
    start_buses,
    ubusd_test,
    mosquitto_test,
)

from foris_controller_testtools.utils import (
    get_uci_module,
    network_restart_was_called,
    TURRISHW_ROOT,
    prepare_turrishw_root,
    prepare_turrishw,
)


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0")], indirect=True
)
def test_get_settings(uci_configs_init, infrastructure, start_buses, device, turris_os_version):

    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "device" in res["data"].keys()
    assert "networks" in res["data"].keys()
    assert "firewall" in res["data"].keys()
    assert set(res["data"]["firewall"]) == {"ssh_on_wan", "http_on_wan", "https_on_wan"}


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0")], indirect=True
)
def test_update_settings(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    filters = [("networks", "update_settings")]
    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    non_configurable = [e["id"] for e in ports if not e["configurable"]]
    ports = [e for e in ports if e["configurable"]]

    wan_port = ports.pop()["id"]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": True, "http_on_wan": False, "https_on_wan": True},
                "networks": {
                    "wan": [wan_port],
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert res["data"] == {"result": True}
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "networks",
        "action": "update_settings",
        "kind": "notification",
        "data": {
            "firewall": {"ssh_on_wan": True, "http_on_wan": False, "https_on_wan": True},
            "networks": {
                "wan": [wan_port],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            },
        },
    }

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"][0]["id"] == wan_port
    assert {e["id"] for e in res["data"]["networks"]["lan"]} == set(lan_ports)
    assert {e["id"] for e in res["data"]["networks"]["guest"]} == set(guest_ports)
    assert {e["id"] for e in res["data"]["networks"]["none"]} == set(none_ports + non_configurable)
    assert res["data"]["firewall"] == {
        "ssh_on_wan": True,
        "http_on_wan": False,
        "https_on_wan": True,
    }


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0")], indirect=True
)
def test_update_settings_empty_wan(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    filters = [("networks", "update_settings")]
    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    non_configurable = [e["id"] for e in ports if not e["configurable"]]
    ports = [e for e in ports if e["configurable"]]

    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": False, "http_on_wan": True, "https_on_wan": False},
                "networks": {"wan": [], "lan": lan_ports, "guest": guest_ports, "none": none_ports},
            },
        }
    )
    assert res["data"] == {"result": True}
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "networks",
        "action": "update_settings",
        "kind": "notification",
        "data": {
            "firewall": {"ssh_on_wan": False, "http_on_wan": True, "https_on_wan": False},
            "networks": {"wan": [], "lan": lan_ports, "guest": guest_ports, "none": none_ports},
        },
    }

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"] == []
    assert {e["id"] for e in res["data"]["networks"]["lan"]} == set(lan_ports)
    assert {e["id"] for e in res["data"]["networks"]["guest"]} == set(guest_ports)
    assert {e["id"] for e in res["data"]["networks"]["none"]} == set(none_ports + non_configurable)
    assert res["data"]["firewall"] == {
        "ssh_on_wan": False,
        "http_on_wan": True,
        "https_on_wan": False,
    }


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "4.0")], indirect=True)
def test_update_settings_more_wans(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    orig_firewall = res["data"]["firewall"]
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    ports = [e for e in ports if e["configurable"]]

    assert len(list(ports)) > 2

    wan_ports = [ports.pop()["id"], ports.pop()["id"]]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": orig_firewall,
                "networks": {
                    "wan": wan_ports,
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert "errors" in res

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none
    assert res["data"]["firewall"] == orig_firewall


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_missing_assign(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    orig_firewall = res["data"]["firewall"]
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    ports = [e for e in ports if e["configurable"]]

    assert len(list(ports)) > 1
    ports.pop()

    wan_ports = [ports.pop()["id"]]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": orig_firewall,
                "networks": {
                    "wan": wan_ports,
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert res["data"] == {"result": False}

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none
    assert res["data"]["firewall"] == orig_firewall


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_unknown_assign(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    orig_firewall = res["data"]["firewall"]
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    ports = [e for e in ports if e["configurable"]]

    assert len(list(ports)) > 0

    wan_ports = [ports.pop()["id"]]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    lan_ports.append("eth-0-9")

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": orig_firewall,
                "networks": {
                    "wan": wan_ports,
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert res["data"] == {"result": False}

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none
    assert res["data"]["firewall"] == orig_firewall


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "4.0")], indirect=True)
def test_update_settings_set_non_configurable(
    uci_configs_init,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    orig_firewall = res["data"]["firewall"]
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    assert len(list(ports)) > 0

    wan_ports = [ports.pop()["id"]]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": orig_firewall,
                "networks": {
                    "wan": wan_ports,
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert res["data"] == {"result": False}

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none
    assert res["data"]["firewall"] == orig_firewall


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0")], indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    uci_configs_init,
    lock_backend,
    init_script_result,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(lock_backend)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )

    # filter non-configurable ports
    ports = [e for e in ports if e["configurable"]]

    wan_port = ports.pop()["id"]
    ports = reversed(ports)
    lan_ports, guest_ports, none_ports = [], [], []
    for i, port in enumerate(ports):
        if i % 3 == 0:
            lan_ports.append(port["id"])
        elif i % 3 == 1:
            guest_ports.append(port["id"])
        elif i % 3 == 2:
            none_ports.append(port["id"])

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": True, "http_on_wan": True, "https_on_wan": False},
                "networks": {
                    "wan": [wan_port],
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
    )
    assert res["data"] == {"result": True}

    assert network_restart_was_called([])

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert wan_port == uci.get_option_named(data, "network", "wan", "ifname")

    assert "bridge" == uci.get_option_named(data, "network", "lan", "type")
    assert uci.parse_bool(uci.get_option_named(data, "network", "lan", "bridge_empty"))
    assert lan_ports == uci.get_option_named(data, "network", "lan", "ifname", [])

    assert "bridge" == uci.get_option_named(data, "network", "guest_turris", "type")
    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "bridge_empty"))
    assert guest_ports == uci.get_option_named(data, "network", "guest_turris", "ifname", [])

    # test firewall rules
    assert (
        uci.parse_bool(uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "enabled"))
        is True
    )
    assert (
        uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "name")
        == "wan_ssh_turris_rule"
    )
    assert uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "proto") == "tcp"
    assert uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "src") == "wan"
    assert uci.get_option_named(data, "firewall", "wan_ssh_turris_rule", "dest_port") == "22"

    assert (
        uci.parse_bool(uci.get_option_named(data, "firewall", "wan_http_turris_rule", "enabled"))
        is True
    )
    assert (
        uci.get_option_named(data, "firewall", "wan_http_turris_rule", "name")
        == "wan_http_turris_rule"
    )
    assert uci.get_option_named(data, "firewall", "wan_http_turris_rule", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "wan_http_turris_rule", "proto") == "tcp"
    assert uci.get_option_named(data, "firewall", "wan_http_turris_rule", "src") == "wan"
    assert uci.get_option_named(data, "firewall", "wan_http_turris_rule", "dest_port") == "80"

    assert (
        uci.parse_bool(uci.get_option_named(data, "firewall", "wan_https_turris_rule", "enabled"))
        is False
    )
    assert (
        uci.get_option_named(data, "firewall", "wan_https_turris_rule", "name")
        == "wan_https_turris_rule"
    )
    assert uci.get_option_named(data, "firewall", "wan_https_turris_rule", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "wan_https_turris_rule", "proto") == "tcp"
    assert uci.get_option_named(data, "firewall", "wan_https_turris_rule", "src") == "wan"
    assert uci.get_option_named(data, "firewall", "wan_https_turris_rule", "dest_port") == "443"


@pytest.mark.parametrize(
    "device,turris_os_version",
    [("omnia", "3.10.7"), ("turris", "3.10.7"), ("turris", "4.0")],
    indirect=True,
)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_openwrt_unsupported(
    uci_configs_init, lock_backend, infrastructure, start_buses, device, turris_os_version
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    # get ports
    ports = (
        res["data"]["networks"]["wan"]
        + res["data"]["networks"]["lan"]
        + res["data"]["networks"]["guest"]
        + res["data"]["networks"]["none"]
    )
    assert len(ports) == 0


@pytest.mark.parametrize(
    "device,turris_os_version",
    [("omnia", "3.10.7"), ("turris", "3.10.7"), ("turris", "4.0")],
    indirect=True,
)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt_unsupported(
    uci_configs_init, lock_backend, infrastructure, start_buses, device, turris_os_version
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": False, "http_on_wan": True, "https_on_wan": True},
                "networks": {"wan": [], "lan": [], "guest": [], "none": []},
            },
        }
    )
    assert res["data"] == {"result": False}


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_wifi_devices(
    uci_configs_init,
    lock_backend,
    init_script_result,
    infrastructure,
    start_buses,
    network_restart_command,
    device,
    turris_os_version,
):
    prepare_turrishw("mox+ALL")
    uci = get_uci_module(lock_backend)
    os.environ["TURRISHW_ROOT"] = TURRISHW_ROOT
    import turrishw

    interfaces = turrishw.get_ifaces()
    macaddr = [e["macaddr"] for e in interfaces.values() if e["type"] == "wifi"]
    assert len(macaddr) == 1
    macaddr = macaddr[0]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # override wireless
        backend.import_data(
            """\
config wifi-device 'radio0'
	option type 'mac80211'
	option macaddr '00:00:00:00:00:00'
	option disabled '1'
	option channel 'auto'
	option hwmode '11g'
	option htmode 'NOHT'

config wifi-iface 'default_radio0'
	option device 'radio0'
	option network 'lan'
	option mode 'ap'
	option hidden '0'
	option encryption 'psk2+ccmp'
	option wpa_group_rekey '86400'
	option key 'testtest'
	option disabled '0'
	option ssid 'Turris'

config wifi-iface 'guest_iface_0'
	option device 'radio0'
	option mode 'ap'
	option ssid 'Turris-guest'
	option network 'guest_turris'
	option encryption 'psk2+ccmp'
	option wpa_group_rekey '86400'
	option key 'testtest'
	option ifname 'guest_turris_0'
	option isolate '1'
	option disabled '0'""",
            "wireless",
        )
        backend.set_option("wireless", "radio0", "macaddr", macaddr)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert len([e["id"] for e in res["data"]["networks"]["none"] if e["type"] == "wifi"]) == 1
    assert [e["ssid"] for e in res["data"]["networks"]["none"] if e["type"] == "wifi"] == [""]
    assert len([e["id"] for e in res["data"]["networks"]["lan"] if e["type"] == "wifi"]) == 0

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("wireless", "radio0", "disabled", uci.store_bool(False))

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert len([e["id"] for e in res["data"]["networks"]["none"] if e["type"] == "wifi"]) == 0
    assert len([e["id"] for e in res["data"]["networks"]["lan"] if e["type"] == "wifi"]) == 1
    assert [e["ssid"] for e in res["data"]["networks"]["lan"] if e["type"] == "wifi"] == ["Turris"]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("wireless", "default_radio0", "disabled", uci.store_bool(True))

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )

    assert len([e["id"] for e in res["data"]["networks"]["none"] if e["type"] == "wifi"]) == 1
    assert len([e["id"] for e in res["data"]["networks"]["lan"] if e["type"] == "wifi"]) == 0


def test_network_change_notification(uci_configs_init, infrastructure, start_buses, notify_api):
    filters = [("networks", "network_change")]

    def check_notification(dev, network, action):
        notifications = infrastructure.get_notifications(filters=filters)
        notify_api(
            "networks",
            "network_change",
            {"device": dev, "network": network, "action": action},
            True,
        )
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1] == {
            "module": "networks",
            "action": "network_change",
            "kind": "notification",
            "data": {"device": dev, "network": network, "action": action},
        }

    check_notification("eth0", "lan", "ifup")
    check_notification("", "wan", "ifdown")
    check_notification("guest_turris", "wan", "ifupdate")
