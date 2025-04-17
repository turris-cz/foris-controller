#
# foris-controller
# Copyright (C) 2021-2022 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import base64
import os
from pathlib import Path

import pytest
from foris_controller_testtools.fixtures import UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import (
    get_uci_module,
    network_restart_was_called,
    prepare_turrishw,
    prepare_turrishw_root,
)

from foris_controller import profiles

from .test_guest import WIFI_DEFAULT_ENCRYPTION

WIFI_DEFAULT_ENCRYPTION = "WPA2/3"
WIFI_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")
FINISH_WORKFLOWS = [e for e in profiles.WORKFLOWS if e not in (profiles.Workflow.UNSET)]
NEW_WORKFLOWS = [
    e for e in profiles.get_workflows() if e not in (profiles.Workflow.OLD, profiles.Workflow.SHIELD)
]

_DEFAULT_OLD_CONFIG = """config interface 'loopback'
    option ifname 'lo'
    option proto 'static'
    option ipaddr '127.0.0.1'
    option netmask '255.0.0.0'

config globals 'globals'
    option ula_prefix 'fd5b:2880:7df4::/48'

config interface 'lan'
    option type 'bridge'
    option ifname 'lan0 lan1 lan2 lan3 lan4'
    option proto 'static'
    option ipaddr '192.168.1.1'
    option netmask '255.255.255.0'
    option ip6assign '60'

config interface 'wan'
    option ifname '{}'
    option proto 'dhcp'
    option ipv6 '1'

config interface 'wan6'
    option proto 'dhcpv6'
    option ifname '@wan'
"""

_MIGRATED_CONFIG = """config interface 'loopback'
    option device 'lo'
    option proto 'static'
    option ipaddr '127.0.0.1'
    option netmask '255.0.0.0'

config globals 'globals'
    option ula_prefix 'fdb1:2f5f:6874::/48'

config interface 'wan'
    option proto 'dhcp'
    option ipv6 '1'
    option device '{}'

config interface 'lan'
    option proto 'static'
    option _turris_mode 'managed'
    option ip6assign '60'
    option bridge_empty '1'
    list ipaddr '172.16.1.1/24'
    option device 'br-lan'

config interface 'guest_turris'
    option enabled '1'
    option type 'bridge'
    option proto 'static'
    option ipaddr '10.111.222.1'
    option netmask '255.255.255.0'
    option bridge_empty '1'
    option ip6assign '64'

config interface 'wan6'
    option proto 'dhcpv6'
    option device '@wan'

config device
    list ports 'lan1'
    list ports 'lan2'
    list ports 'lan3'
    list ports 'lan4'
    option type 'bridge'
    option name 'br-lan'
    option macaddr '00:11:ff:cc:ee:bb'
"""


@pytest.fixture(scope='function')
def inject_network(uci_configs_init, device, request):
    """ You no longer need fix_mox_wan using this fixture. """
    if request.param:
        config = globals().get(request.param)
        network_path = Path(UCI_CONFIG_DIR_PATH, 'network')
        with open(network_path, 'w') as f:
            f.write(config.format("eth0" if device == "mox" else "eth2"))


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize(
    "inject_network,device,turris_os_version",
    [
        ("_DEFAULT_OLD_CONFIG", "omnia", "4.0"),
        ("_DEFAULT_OLD_CONFIG", "mox", "4.0")
    ], indirect=True
)
def test_get_settings(
    infrastructure, device, turris_os_version,
    inject_network
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "networks", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    nets = res['data']['networks']
    assert len(nets['lan']) > 0
    assert len(nets['wan']) > 0

# guest module


@pytest.mark.file_root_path(WIFI_ROOT_PATH)
@pytest.mark.parametrize(
    "inject_network,device,turris_os_version",
    [
        ("_DEFAULT_OLD_CONFIG", "mox", "4.0"),
        ("_MIGRATED_CONFIG", "mox", "4.0")
    ],
    indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_guest_interface_count(
    file_root_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
    inject_network
):
    prepare_turrishw("mox")  # plain mox without any boards

    def set_and_test(networks, wifi_devices, count):
        res = infrastructure.process_message(
            {
                "module": "networks",
                "action": "update_settings",
                "kind": "request",
                "data": {
                    "firewall": {"ssh_on_wan": False, "http_on_wan": False, "https_on_wan": False},
                    "networks": networks,
                },
            }
        )
        assert res["data"] == {"result": True}
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": wifi_devices},
            }
        )
        assert res["data"] == {"result": True}
        res = infrastructure.process_message(
            {"module": "guest", "action": "get_settings", "kind": "request"}
        )
        assert res["data"]["interface_count"] == count

    # No wifi no interfaces
    set_and_test(
        {"wan": [], "lan": [], "guest": [], "none": ["eth0"]},
        [{"id": 0, "enabled": False}, {"id": 1, "enabled": False}],
        0,
    )

    # Single interface no wifi
    set_and_test(
        {"wan": [], "lan": [], "guest": ["eth0"], "none": []},
        [{"id": 0, "enabled": False}, {"id": 1, "enabled": False}],
        1,
    )

    # One wifi no interface
    set_and_test(
        {"wan": [], "lan": ["eth0"], "guest": [], "none": []},
        [
            {
                "id": 0,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 8,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
        ],
        2,
    )

    # interface and wifis enabled
    set_and_test(
        {"wan": [], "lan": [], "guest": ["eth0"], "none": []},
        [
            {
                "id": 0,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 8,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
        ],
        3,
    )

# lan module


@pytest.mark.parametrize(
    "inject_network, device,turris_os_version",
    [
        ("_DEFAULT_OLD_CONFIG","mox", "4.0")
    ],
    indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_lan_update_settings_openwrt(
    infrastructure, network_restart_command, device, turris_os_version, inject_network
):
    uci = get_uci_module(infrastructure.name)

    def read_backend():
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            return backend.read()

    def update(data):
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" not in res
        assert res["data"]["result"]

        return read_backend()
    init_data = read_backend()

    assert uci.get_option_named(init_data, "network", "lan", "ifname") == "lan0 lan1 lan2 lan3 lan4"

    data = update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.5.8",
                "netmask": "255.255.255.0",
                "dhcp": {"enabled": False},
            },
            "lan_redirect": False,
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "managed"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["192.168.5.8/24"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))


@pytest.mark.parametrize(
    "inject_network, device,turris_os_version",
    [
        ("_MIGRATED_CONFIG","mox", "4.0")
    ],
    indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_lan_update_settings_openwrt_migrated_config(
    infrastructure, network_restart_command, device, turris_os_version, inject_network
):
    uci = get_uci_module(infrastructure.name)

    def read_backend():
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            return backend.read()

    def update(data):
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" not in res
        assert res["data"]["result"]

        return read_backend()

    init_data = read_backend()

    assert uci.get_option_anonymous(init_data, "network", "device", 0, "ports") == ["lan1", "lan2", "lan3", "lan4"]

    data = update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.5.8",
                "netmask": "255.255.255.0",
                "dhcp": {"enabled": False},
            },
            "lan_redirect": False,
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "managed"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["192.168.5.8/24"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))


@pytest.mark.file_root_path(WIFI_ROOT_PATH)
@pytest.mark.parametrize(
    "inject_network,device,turris_os_version",
    [
        ("_DEFAULT_OLD_CONFIG", "mox", "4.0"),
        ("_MIGRATED_CONFIG", "mox", "4.0")
    ],
    indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_lan_interface_count(
    file_root_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
    lan_dnsmasq_files,
    inject_network
):
    prepare_turrishw("mox")  # plain mox without any boards

    def set_and_test(networks, wifi_devices, count):
        res = infrastructure.process_message(
            {
                "module": "networks",
                "action": "update_settings",
                "kind": "request",
                "data": {
                    "firewall": {"ssh_on_wan": False, "http_on_wan": False, "https_on_wan": False},
                    "networks": networks,
                },
            }
        )
        assert res["data"] == {"result": True}
        res = infrastructure.process_message(
            {
                "module": "wifi",
                "action": "update_settings",
                "kind": "request",
                "data": {"devices": wifi_devices},
            }
        )
        assert res["data"] == {"result": True}
        res = infrastructure.process_message(
            {"module": "lan", "action": "get_settings", "kind": "request"}
        )
        assert res["data"]["interface_count"] == count

    # No wifi no interfaces
    set_and_test(
        {"wan": [], "lan": [], "guest": [], "none": ["eth0"]},
        [{"id": 0, "enabled": False}, {"id": 1, "enabled": False}],
        0,
    )

    # Single interface
    set_and_test(
        {"wan": [], "lan": ["eth0"], "guest": [], "none": []},
        [{"id": 0, "enabled": False}, {"id": 1, "enabled": False}],
        1,
    )

    set_and_test(
        {"wan": ["eth0"], "lan": [], "guest": [], "none": []},
        [
            {
                "id": 0,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            },
            {"id": 1, "enabled": False},
        ],
        1,
    )
    set_and_test(
        {"wan": [], "lan": [], "guest": ["eth0"], "none": []},
        [
            {"id": 0, "enabled": False},
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
        ],
        1,
    )

    # two wifis no interface
    set_and_test(
        {"wan": [], "lan": [], "guest": ["eth0"], "none": []},
        [
            {
                "id": 0,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            },
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 8,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
        ],
        2,
    )

    # interface and wifis enabled
    set_and_test(
        {"wan": [], "lan": ["eth0"], "guest": [], "none": []},
        [
            {
                "id": 0,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            },
            {
                "id": 1,
                "enabled": True,
                "SSID": "Turris",
                "hidden": False,
                "channel": 8,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                    "encryption": WIFI_DEFAULT_ENCRYPTION,
                },
            },
        ],
        3,
    )

# networks module


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize(
    "inject_network,device,turris_os_version", [
        ("_DEFAULT_OLD_CONFIG","mox", "5.2"),
        ("_MIGRATED_CONFIG","mox", "5.2")
    ], indirect=True
)
def test_get_settings_more_wans(
    inject_network, fix_mox_wan, infrastructure, device, turris_os_version
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


@pytest.mark.parametrize(
    "inject_network,device,turris_os_version", [
        ("_DEFAULT_OLD_CONFIG","omnia", "4.0"),
        ("_DEFAULT_OLD_CONFIG","mox", "4.0"),
        ("_MIGRATED_CONFIG", "mox", "4.0")
    ],
    indirect=True
)
def test_update_settings(
    inject_network, infrastructure, network_restart_command, device, turris_os_version,
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


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize(
    "inject_network,device,turris_os_version", [
        ("_DEFAULT_OLD_CONFIG", "omnia", "4.0"),
        ("_DEFAULT_OLD_CONFIG", "mox", "4.0"),
        ("_MIGRATED_CONFIG", "mox", "4.0")
    ],
    indirect=True
)
def test_update_settings_empty_wan(
    inject_network, infrastructure, network_restart_command, device, turris_os_version,
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


@pytest.mark.parametrize(
    "inject_network,device,turris_os_version",
    [
        ("_DEFAULT_OLD_CONFIG", "omnia", "4.0"),
        ("_DEFAULT_OLD_CONFIG", "mox", "4.0"),
        ("_MIGRATED_CONFIG", "omnia", "4.0"),
        ("_MIGRATED_CONFIG", "mox", "4.0")
    ],
    indirect=True
)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    inject_network,
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

    # DEBUG BEGIN
    devices = uci.get_sections_by_type(data, "network", "device")
    anonymous = [ac for ac in filter(lambda x: x['name'].startswith("cfg"), devices)]
    assert anonymous == []
    # DEBUG END;

    assert "bridge" == uci.get_option_named(data, "network", "br_lan", "type")
    # assert uci.parse_bool(uci.get_option_named(data, "network", "lan", "bridge_empty"))
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


@pytest.mark.parametrize(
    "inject_network,device,turris_os_version",
    [("_DEFAULT_OLD_CONFIG","omnia", "4.0")],
    indirect=True,
)
@pytest.mark.parametrize(
    "old_workflow,new_workflow",
    [
        (profiles.Workflow.OLD, profiles.Workflow.OLD),
        (profiles.Workflow.SHIELD, profiles.Workflow.SHIELD),
    ]
    + [
        (profiles.Workflow.UNSET, e) for e in set(FINISH_WORKFLOWS).intersection(set(NEW_WORKFLOWS))
    ],
)
def test_walk_through_guide(
    inject_network,
    file_root_init,
    init_script_result,
    infrastructure,
    network_restart_command,
    old_workflow,
    new_workflow,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {
            "module": "web",
            "action": "reset_guide",
            "kind": "request",
            "data": {"new_workflow": old_workflow},
        }
    )
    assert res["data"] == {"result": True}
    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert old_workflow == res["data"]["guide"]["workflow"]

    def check_passed(passed, workflow, enabled):
        res = infrastructure.process_message(
            {"module": "web", "action": "get_data", "kind": "request"}
        )
        assert res["data"]["guide"]["enabled"] is enabled
        assert res["data"]["guide"]["workflow"] == workflow
        assert res["data"]["guide"]["passed"] == passed
        assert res["data"]["guide"]["workflow_steps"] == [e for e in profiles.get_workflows()[workflow]]
        if enabled:
            assert res["data"]["guide"]["next_step"] == profiles.next_step(passed, workflow)
        else:
            assert "next_step" not in res["data"]["guide"]

    def pass_step(msg, passed, target_workflow, enabled):
        res = infrastructure.process_message(msg)
        assert res["data"]["result"] is True
        check_passed(passed, target_workflow, enabled)

    def password_step(passed, target_workflow, enabled):
        # Update password
        msg = {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {"password": base64.b64encode(b"heslo").decode("utf-8"), "type": "foris"},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def profile_step(passed, target_workflow, enabled):
        # Update guide
        msg = {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"workflow": new_workflow, "enabled": True},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def networks_step(passed, target_workflow, enabled):
        # Update networks
        res = infrastructure.process_message(
            {"module": "networks", "action": "get_settings", "kind": "request"}
        )
        ports = (
            res["data"]["networks"]["wan"]
            + res["data"]["networks"]["lan"]
            + res["data"]["networks"]["guest"]
            + res["data"]["networks"]["none"]
        )
        ports = [e for e in ports if e["configurable"]]
        wan_port = ports.pop()["id"]
        lan_ports, guest_ports, none_ports = [], [], []
        for i, port in enumerate(ports):
            if i % 3 == 0:
                lan_ports.append(port["id"])
            elif i % 3 == 1:
                guest_ports.append(port["id"])
            elif i % 3 == 2:
                none_ports.append(port["id"])

        msg = {
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
        pass_step(msg, passed, target_workflow, enabled)

    def wan_step(passed, target_workflow, enabled):
        # Update wan
        msg = {
            "module": "wan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
                "wan6_settings": {"wan6_type": "none"},
                "mac_settings": {"custom_mac_enabled": False},
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def time_step(passed, target_workflow, enabled):
        # Update timezone
        msg = {
            "module": "time",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "region": "Europe",
                "country": "CZ",
                "city": "Prague",
                "timezone": "CET-1CEST,M3.5.0,M10.5.0/3",
                "time_settings": {
                    "how_to_set_time": "manual",
                    "time": "2018-01-30T15:51:30.482515",
                },
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def dns_step(passed, target_workflow, enabled):
        # Update dns
        msg = {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def updater_step(passed, target_workflow, enabled):
        # update Updater
        msg = {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": {"enabled": False},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def lan_step(passed, target_workflow, enabled):
        msg = {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {"mode": "unmanaged", "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {}}},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def finished_step(passed, target_workflow, enabled):
        # Update guide
        msg = {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"enabled": False},
        }
        pass_step(msg, passed, target_workflow, enabled)

    MAP = {
        "password": password_step,
        "profile": profile_step,
        "networks": networks_step,
        "wan": wan_step,
        "time": time_step,
        "dns": dns_step,
        "updater": updater_step,
        "lan": lan_step,
        "finished": finished_step,
    }

    passed = []

    check_passed(passed, old_workflow, True)
    active_workflow = old_workflow
    for step in profiles.get_workflows()[old_workflow]:
        last = set(profiles.get_workflows()[active_workflow]) != set(passed + [step])
        if step == profiles.Step.PROFILE:
            active_workflow = new_workflow
            break
        MAP[step](passed + [step], active_workflow, last)
        passed.append(step)
    for step in profiles.get_workflows()[active_workflow]:
        if step in passed:
            continue
        last = set(profiles.get_workflows()[active_workflow]) != set(passed + [step])
        MAP[step](passed + [step], active_workflow, last)
        passed.append(step)
