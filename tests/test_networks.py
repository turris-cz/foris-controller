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

from foris_controller_testtools.fixtures import (
    uci_configs_init, infrastructure, ubusd_test
)


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "networks",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "device" in res["data"].keys()
    assert "networks" in res["data"].keys()


def test_update_settings(uci_configs_init, infrastructure, ubusd_test):
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


def test_update_settings_wrong_wan(uci_configs_init, infrastructure, ubusd_test):
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

def test_update_settings_missing_assign(uci_configs_init, infrastructure, ubusd_test):
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


def test_update_settings_unknown_assign(uci_configs_init, infrastructure, ubusd_test):
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
    assert res["data"]["networks"]["none"] == orig_none
