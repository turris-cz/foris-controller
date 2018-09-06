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

from foris_controller_testtools.fixtures import (
    only_backends, uci_configs_init, infrastructure, ubusd_test, lock_backend, FILE_ROOT_PATH,
    init_script_result, network_restart_command,
)

from foris_controller_testtools.utils import (
    sh_was_called, get_uci_module, FileFaker, network_restart_was_called
)


@pytest.fixture(
    params=[
        ("mox", "CZ.NIC Turris Mox Board"),
        ("omnia", "Turris Omnia"),
    ],
    ids=["mox", "omnia"],
    scope="function"
)
def mox_and_omnia(request):
    device, device_str = request.param
    with FileFaker(FILE_ROOT_PATH, "/tmp/sysinfo/model", False, device_str + "\n"):
        yield device


@pytest.fixture(params=["Turris Omnia"], ids=["omnia"], scope="function")
def only_omnia(request):
    with FileFaker(FILE_ROOT_PATH, "/tmp/sysinfo/model", False, request.param + "\n"):
        yield "omnia"


@pytest.fixture(params=["Turris 1.X"], ids=["turris"], scope="function")
def only_turris(request):
    with FileFaker(FILE_ROOT_PATH, "/tmp/sysinfo/model", False, request.param + "\n"):
        yield "turris"


def test_get_settings(uci_configs_init, infrastructure, ubusd_test, mox_and_omnia):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "device" in res["data"].keys()
    assert "networks" in res["data"].keys()


def test_update_settings(
    uci_configs_init, infrastructure, ubusd_test, mox_and_omnia, network_restart_command
):
    filters = [("networks", "update_settings")]
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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
    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": [wan_port],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert res["data"] == {"result": True}
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "networks",
        "action": "update_settings",
        "kind": "notification",
        "data": {
            "networks": {
                "wan": [wan_port],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    }

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["networks"]["wan"][0]["id"] == wan_port
    assert [e["id"] for e in res["data"]["networks"]["lan"]] == lan_ports
    assert [e["id"] for e in res["data"]["networks"]["guest"]] == guest_ports
    assert [e["id"] for e in res["data"]["networks"]["none"]] == none_ports


def test_update_settings_empty_wan(
    uci_configs_init, infrastructure, ubusd_test, mox_and_omnia, network_restart_command
):
    filters = [("networks", "update_settings")]
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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
    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": [],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert res["data"] == {"result": True}
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "networks",
        "action": "update_settings",
        "kind": "notification",
        "data": {
            "networks": {
                "wan": [],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    }

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["networks"]["wan"] == []
    assert {e["id"] for e in res["data"]["networks"]["lan"]} == set(lan_ports)
    assert {e["id"] for e in res["data"]["networks"]["guest"]} == set(guest_ports)
    assert {e["id"] for e in res["data"]["networks"]["none"]} == set(none_ports)



def test_update_settings_more_wans(
    uci_configs_init, infrastructure, ubusd_test, only_omnia, network_restart_command
):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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

    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": wan_ports,
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert "errors" in res

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none


def test_update_settings_missing_assign(
    uci_configs_init, infrastructure, ubusd_test, only_omnia, network_restart_command
):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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

    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": wan_ports,
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert res["data"] == {"result": False}

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none


def test_update_settings_unknown_assign(
    uci_configs_init, infrastructure, ubusd_test, mox_and_omnia, network_restart_command
):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    orig_wan = res["data"]["networks"]["wan"]
    orig_lan = res["data"]["networks"]["lan"]
    orig_guest = res["data"]["networks"]["guest"]
    orig_none = res["data"]["networks"]["none"]
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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

    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": wan_ports,
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert res["data"] == {"result": False}

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["networks"]["wan"] == orig_wan
    assert res["data"]["networks"]["lan"] == orig_lan
    assert res["data"]["networks"]["guest"] == orig_guest
    assert res["data"]["networks"]["none"] == orig_none


@pytest.mark.only_backends(['openwrt'])
def test_update_settings_openwrt(
    uci_configs_init, lock_backend, init_script_result, infrastructure, ubusd_test, mox_and_omnia,
    network_restart_command
):
    uci = get_uci_module(lock_backend)

    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]

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

    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": [wan_port],
                "lan": lan_ports,
                "guest": guest_ports,
                "none": none_ports,
            }
        }
    })
    assert res["data"] == {"result": True}

    assert network_restart_was_called([])

    with uci.UciBackend() as backend:
        data = backend.read()

    assert wan_port == uci.get_option_named(data, "network", "wan", "ifname")

    assert "bridge" == uci.get_option_named(data, "network", "lan", "type")
    assert uci.parse_bool(uci.get_option_named(data, "network", "lan", "bridge_empty"))
    assert lan_ports == uci.get_option_named(data, "network", "lan", "ifname", [])

    assert "bridge" == uci.get_option_named(data, "network", "guest_turris", "type")
    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "bridge_empty"))
    assert guest_ports == uci.get_option_named(data, "network", "guest_turris", "ifname", [])


@pytest.mark.only_backends(['openwrt'])
def test_get_settings_openwrt_turris(
    uci_configs_init, lock_backend, infrastructure, ubusd_test, only_turris
):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    # get ports
    ports = res["data"]["networks"]["wan"] + res["data"]["networks"]["lan"] \
        + res["data"]["networks"]["guest"] + res["data"]["networks"]["none"]
    assert len(ports) == 0


@pytest.mark.only_backends(['openwrt'])
def test_update_settings_openwrt_turris(
    uci_configs_init, lock_backend, infrastructure, ubusd_test, only_turris
):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "networks": {
                "wan": [],
                "lan": [],
                "guest": [],
                "none": [],
            }
        }
    })
    assert res["data"] == {"result": False}
