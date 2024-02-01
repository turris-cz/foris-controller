#
# foris-controller
# Copyright (C) 2020-2022 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
from foris_controller_testtools.fixtures import UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import (
    TURRISHW_ROOT,
    get_uci_module,
    network_restart_was_called,
    prepare_turrishw,
    prepare_turrishw_root,
)


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0"), ("turris", "6.0")], indirect=True
)
def test_get_settings(uci_configs_init, fix_mox_wan, infrastructure, device, turris_os_version):

    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"].keys() == {"device", "networks", "firewall"}
    assert set(res["data"]["firewall"]) == {"ssh_on_wan", "http_on_wan", "https_on_wan"}


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("device,turris_os_version", [("omnia","7.0"), ("mox","7.0"), ("turris","7.0")], indirect=True)
def test_get_settings_wwan(uci_configs_init, fix_mox_wan, infrastructure, device, turris_os_version):
    """Test networks return in case of wwan interface existing"""

    prepare_turrishw(f"{device}-wwan-{turris_os_version}")

    DEVICE_PATH_MAP = {
        "omnia": "/sys/devices/platform/soc/soc:internal-regs/f1058000.usb/usb1/1-1",
        "mox": "/sys/devices/platform/soc/soc:internal-regs@d0000000/d005e000.usb/usb1/1-1",
        "turris": "/sys/devices/platform/ffe08000.pcie/pci0002:00/0002:00:00.0/0002:01:00.0/usb2/2-2"
    }

    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.add_section("network", "interface", "gsm")
        backend.set_option("network", "gsm", "apn", "internet")
        backend.set_option("network", "gsm", "proto", "modemanager")
        backend.set_option("network", "gsm", "iptype", "ipv4v6")
        backend.set_option("network", "gsm", "metric", "2048")
        backend.set_option("network", "gsm", "device", DEVICE_PATH_MAP.get(device))

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize(
    "device,turris_os_version", [("mox", "5.2")], indirect=True
)
def test_get_settings_more_wans(
    fix_mox_wan, infrastructure, device, turris_os_version
):
    """Check that even with multiple interfaces assigned to wan, only one is returned"""
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # detach lan4 from br-lan
        backend.set_option("network", "lan", "ifname", "lan1 lan2 lan3")
        # attach it to br-wan
        backend.set_option("network", "wan", "type", "bridge")
        backend.set_option("network", "wan", "ifname", "eth0 lan4")

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"].keys() == {"device", "networks", "firewall"}
    assert set(res["data"]["firewall"]) == {"ssh_on_wan", "http_on_wan", "https_on_wan"}
    assert len(res["data"]["networks"]["wan"]) == 1


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("device,turris_os_version", [("mox", "6.0")], indirect=True)
def test_get_settings_interfaces_in_order(uci_configs_init, fix_mox_wan, infrastructure, device, turris_os_version):
    """Test that interfaces defined in uci config are returned in natural sort order.

    For example:
        config device
            option name 'br-lan'
            list ports 'lan4'
            list ports 'lan1'
            list ports 'lan11'
            list ports 'lan7'
            list ports 'lan2'

    Should return interfaces data in order 'lan1', 'lan2', 'lan4', 'lan7', 'lan11'.
    """
    # Config for Mox AEEC => lan1..20
    ifaces_in_config = {
        "lan": ["lan4", "lan1", "lan11", "lan7", "lan2"],
        "guest": ["lan5", "lan6", "lan10", "lan20", "lan8", "lan15", "lan9"],
    }
    ifaces_sorted = {
        "lan": ["lan1", "lan2", "lan4", "lan7", "lan11"],
        "guest": ["lan5", "lan6", "lan8", "lan9", "lan10", "lan15", "lan20"],
        "none": ["lan3", "lan12", "lan13", "lan14", "lan16", "lan17", "lan18", "lan19"],
    }

    # Note: Only one wan interface is supported at the moment, so don't check sorting on wan

    prepare_turrishw_root(device, turris_os_version)
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # lan bridge
        backend.replace_list("network", "@device[0]", "ports", ifaces_in_config["lan"])
        # guest bridge
        backend.replace_list("network", "@device[1]", "ports", ifaces_in_config["guest"])

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert "networks" in res["data"]

    # check lan net ports sorting
    assert "lan" in res["data"]["networks"]
    lan_ports = res["data"]["networks"]["lan"]
    lan_ports_ids = [e["id"] for e in lan_ports]
    assert ifaces_sorted["lan"] == lan_ports_ids

    # check guest net ports sorting
    assert "guest" in res["data"]["networks"]
    guest_ports = res["data"]["networks"]["guest"]
    guest_ports_ids = [e["id"] for e in guest_ports]
    assert ifaces_sorted["guest"] == guest_ports_ids

    # check none interfaces ports sorting
    assert "none" in res["data"]["networks"]
    none_ports = res["data"]["networks"]["none"]
    none_ports_ids = [e["id"] for e in none_ports]
    assert ifaces_sorted["none"] == none_ports_ids


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("device,turris_os_version", [("mox", "6.0")], indirect=True)
def test_get_settings_interfaces_in_order_mixed_ifaces(
    uci_configs_init,
    fix_mox_wan,
    infrastructure,
    device,
    turris_os_version,
):
    """Test mixed interfaces names, not just lans, to further check natural order sorting.

    For example:
        config device
            option name 'br-lan'
            list ports 'lan1'
            list ports 'sfp'
            list ports 'lan2'

    Should return interfaces data in order 'lan1', 'lan2', 'sfp'.
    """
    # TODO: refactor testtools hw mocks and use prepare_turrishw_root() instead
    prepare_turrishw("mox+ALL")

    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        # set lan ports
        backend.replace_list("network", "@device[0]", "ports", ["lan1", "sfp", "lan2"])

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert "networks" in res["data"]

    # check lan net ports sorting
    assert "lan" in res["data"]["networks"]
    lan_ports = res["data"]["networks"]["lan"]
    lan_ports_ids = [e["id"] for e in lan_ports]
    assert ["lan1", "lan2", "sfp"] == lan_ports_ids


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0"), ("turris", "6.0")], indirect=True
)
def test_update_settings(
    uci_configs_init, fix_mox_wan, infrastructure, network_restart_command, device, turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    filters = [("networks", "update_settings")]
    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()

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
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0"), ("turris", "6.0")], indirect=True
)
def test_update_settings_empty_wan(
    uci_configs_init, fix_mox_wan, infrastructure, network_restart_command, device, turris_os_version,
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


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "4.0"), ("turris", "6.0")], indirect=True)
def test_update_settings_more_wans(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
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
    uci_configs_init, fix_mox_wan, infrastructure, network_restart_command, device, turris_os_version,
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


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0"), ("turris", "6.0")], indirect=True)
def test_update_settings_unknown_assign(
    uci_configs_init, fix_mox_wan, infrastructure, network_restart_command, device, turris_os_version,
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
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
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
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0"), ("turris", "6.0")], indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    uci_configs_init,
    fix_mox_wan,
    init_script_result,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

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

    assert wan_port == uci.get_option_named(data, "network", "wan", "device")

    assert "bridge" == uci.get_option_named(data, "network", "br_lan", "type")
    assert lan_ports == uci.get_option_named(data, "network", "br_lan", "ports", [])

    assert "bridge" == uci.get_option_named(data, "network", "br_guest_turris", "type")
    assert uci.parse_bool(uci.get_option_named(data, "network", "br_guest_turris", "bridge_empty"))
    assert guest_ports == uci.get_option_named(data, "network", "br_guest_turris", "ports", [])

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


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_wifi_devices(
    uci_configs_init,
    init_script_result,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
):
    prepare_turrishw("mox+ALL")
    uci = get_uci_module(infrastructure.name)
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
	option disabled '0'""",  # noqa
            "wireless",  # noqa
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


def test_network_change_notification(uci_configs_init, infrastructure, notify_api):
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


@pytest.mark.parametrize(
    "device,turris_os_version", [("omnia", "4.0"), ("mox", "4.0"), ("turris", "6.0")], indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_one_lan_does_not_break(
    uci_configs_init,
    fix_mox_wan,
    init_script_result,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    networks = res["data"]["networks"]

    # filter non-configurable ports
    lan = res["data"]["networks"].pop("lan")
    guest = [i["id"] for i in lan[1:]]
    lan = [lan[0]["id"]]

    networks["lan"] = lan
    networks["guest"] = guest
    if networks["wan"]:  # mox does not have wan by default
        networks["wan"] = [networks["wan"][0]["id"]]
    networks["none"] = [i["id"] for i in networks["none"] if i["configurable"]]

    res = infrastructure.process_message(
        {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": True, "http_on_wan": True, "https_on_wan": False},
                "networks": networks
            },
        }
    )
    assert res["data"] == {"result": True}
    assert network_restart_was_called([])

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "network", "lan", "device") == "br-lan"
    # assert lan has only one interface
    assert len(uci.get_option_named(data, "network", "br_lan", "ports")) == 1
