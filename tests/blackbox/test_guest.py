#
# foris-controller
# Copyright (C) 2020-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
from foris_controller_testtools.fixtures import FILE_ROOT_PATH, UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import (
    FileFaker,
    check_service_result,
    get_uci_module,
    match_subdict,
    network_restart_was_called,
    prepare_turrishw,
)

from foris_controller.exceptions import UciRecordNotFound

WIFI_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")
WIFI_DEFAULT_ENCRYPTION = "WPA2/3"


@pytest.fixture(scope="function")
def guest_dnsmasq_files():
    leases = "\n".join(
        [
            "1539350286 16:25:34:43:52:61 10.10.2.1 first *",
            "1539350388 94:85:76:67:58:49 10.10.1.1 * *",
        ]
    )
    conntrack = "\n".join(
        [
            "ipv4     2 udp      17 30 src=10.10.2.1 dst=217.31.202.100 sport=36378 dport=123 "
            "packets=1 bytes=76 src=217.31.202.100 dst=172.20.6.87 sport=123 dport=36378 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 unknown  2 491 src=0.0.0.0 dst=224.0.0.1 packets=509 bytes=16288 [UNREPLIED] "
            "src=224.0.0.1 dst=0.0.0.0 packets=0 bytes=0 mark=0 zone=0 use=2",
            "ipv4     2 tcp      6 7383 ESTABLISHED src=172.20.6.100 dst=172.20.6.87 sport=48328 "
            "dport=80 packets=282 bytes=18364 src=172.20.6.87 dst=172.20.6.100 sport=80 dport=48328 "
            "packets=551 bytes=31002 [ASSURED] mark=0 zone=0 use=2",
            "ipv4     2 udp      17 30 src=10.111.222.213 dst=37.157.198.150 sport=60162 dport=123 "
            "packets=1 bytes=76 src=37.157.198.150 dst=172.20.6.87 sport=123 dport=60162 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 udp      17 34 src=10.111.222.213 dst=80.211.195.36 sport=57085 dport=123 "
            "packets=1 bytes=76 src=80.211.195.36 dst=172.20.6.87 sport=123 dport=57085 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 tcp      6 7440 ESTABLISHED src=172.20.6.100 dst=172.20.6.87 sport=35774 "
            "dport=22 packets=244 bytes=17652 src=172.20.6.87 dst=172.20.6.100 sport=22 dport=35774 "
            "packets=190 bytes=16637 [ASSURED] mark=0 zone=0 use=2",
            "ipv4     2 udp      17 173 src=127.0.0.1 dst=127.0.0.1 sport=42365 dport=53 packets=2 "
            "bytes=120 src=127.0.0.1 dst=127.0.0.1 sport=53 dport=42365 packets=2 bytes=164 [ASSURED] "
            "mark=0 zone=0 use=2",
        ]
    )
    with FileFaker(FILE_ROOT_PATH, "/tmp/dhcp.leases", False, leases) as lease_file, FileFaker(
        FILE_ROOT_PATH, "/proc/net/nf_conntrack", False, conntrack
    ) as conntrack_file:
        yield lease_file, conntrack_file


def test_get_settings(uci_configs_init, infrastructure):
    res = infrastructure.process_message(
        {"module": "guest", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {
        "enabled",
        "ip",
        "netmask",
        "dhcp",
        "interface_count",
        "interface_up_count",
        "qos",
    }
    assert set(res["data"]["qos"].keys()) == {"enabled", "upload", "download"}
    assert set(res["data"]["dhcp"].keys()) == {"enabled", "start", "limit", "lease_time", "clients"}


def test_update_settings(uci_configs_init, infrastructure, network_restart_command):
    filters = [("guest", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "guest", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "guest",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "guest"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message(
            {"module": "guest", "action": "get_settings", "kind": "request"}
        )
        assert res["module"] == "guest"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(data, res["data"])

    update({"enabled": False})
    update(
        {
            "enabled": True,
            "ip": "192.168.5.8",
            "netmask": "255.255.255.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.0.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": 24 * 60 * 60 + 1,
            },
            "qos": {"enabled": False},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.3.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": True, "download": 1200, "upload": 1000},
        }
    )


@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    uci_configs_init, init_script_result, infrastructure, network_restart_command
):
    filters = [("guest", "update_settings")]
    uci = get_uci_module(infrastructure.name)

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "guest", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "guest",
        }
        infrastructure.get_notifications(notifications, filters=filters)  # needed just for waiting
        assert network_restart_was_called([])
        if data["enabled"] and data["qos"]["enabled"]:
            check_service_result("sqm", "enable", True)
        else:
            check_service_result("sqm", "disable", True)

    # test guest network
    update(
        {
            "enabled": True,
            "ip": "192.168.8.1",
            "netmask": "255.255.255.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        }
    )
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    # this depends on default uci wireless config if it changes this line needs to be updated
    assert uci.get_option_named(data, "network", "guest_turris", "proto") == "static"
    assert uci.get_option_named(data, "network", "guest_turris", "ipaddr") == "192.168.8.1"
    assert uci.get_option_named(data, "network", "guest_turris", "netmask") == "255.255.255.0"
    assert uci.parse_bool(uci.get_option_named(data, "network", "br_guest_turris", "bridge_empty"))
    assert uci.get_option_named(data, "network", "guest_turris","ip6assign") == "64"

    assert uci.get_option_named(data, "network", "br_guest_turris", "name") == "br-guest-turris"
    assert uci.get_option_named(data, "network", "br_guest_turris", "type") == "bridge"

    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert uci.get_option_named(data, "dhcp", "guest_turris", "interface") == "guest_turris"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcp_option") == ["6,192.168.8.1"]

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert uci.get_option_named(data, "firewall", "guest_turris", "name") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris", "input") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "forward") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "output") == "ACCEPT"
    assert uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_forward_wan", "enabled")
    )
    assert (
        uci.get_option_named(data, "firewall", "guest_turris_forward_wan", "src") == "tr_guest"
    )
    assert uci.get_option_named(data, "firewall", "guest_turris_forward_wan", "dest") == "wan"
    assert uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "enabled")
    )
    assert uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "src") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "proto") == "tcpudp"
    assert uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "dest_port") == "53"
    assert uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "target") == "ACCEPT"
    assert uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "enabled")
    )
    assert uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "src") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "proto") == "udp"
    assert uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "src_port") == "67-68"
    assert uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "dest_port") == "67-68"
    assert uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "target") == "ACCEPT"

    # ipv6 dhcp
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "src") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "proto") == "udp"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "src_ip") == "fe80::/10"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "src_port") == "546-547"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "dest_ip") == "fe80::/10"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "dest_port") == "546-547"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "family") == "ipv6"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_DHCPv6", "target") == "ACCEPT"

    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "src") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "proto") == "icmp"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "src_ip") == "fe80::/10"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "family") == "ipv6"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_MLD", "icmp_type") == [
        '130/0', '131/0', '132/0', '143/0'
    ]

    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "src") == "tr_guest"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "proto") == "icmp"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "limit") == "1000/sec"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "family") == "ipv6"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "guest_turris_Allow_ICMPv6_Input", "icmp_type") == [
        'echo-request', 'echo-reply', 'destination-unreachable', 'packet-too-big', 'time-exceeded',
        'bad-header', 'unknown-header-type', 'router-solicitation', 'neighbour-solicitation',
        'router-advertisement', 'neighbour-advertisement'
    ]

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")

    # test + qos
    update(
        {
            "enabled": True,
            "ip": "192.168.9.1",
            "netmask": "255.255.255.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": True, "download": 1200, "upload": 1000},
        }
    )
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert uci.parse_bool(uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled"))
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "interface") == "br-guest-turris"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "qdisc") == "fq_codel"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "script") == "simple.qos"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "link_layer") == "none"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "verbosity") == "5"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "debug_logging") == "1"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "download") == "1000"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "upload") == "1200"

    # test + dhcp
    update(
        {
            "enabled": True,
            "ip": "192.168.11.1",
            "netmask": "255.255.255.0",
            "dhcp": {"enabled": True, "start": 25, "limit": 100, "lease_time": 201},
            "qos": {"enabled": False},
        }
    )
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert not uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert uci.get_option_named(data, "dhcp", "guest_turris", "interface") == "guest_turris"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "start") == "25"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "limit") == "100"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "leasetime") == "201"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcp_option") == ["6,192.168.11.1"]
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcpv6") == "server"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "ra") == "server"

    # test guest disabled
    update({"enabled": False})
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert not uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert not uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_forward_wan", "enabled")
    )
    assert not uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_dns_rule", "enabled")
    )
    assert not uci.parse_bool(
        uci.get_option_named(data, "firewall", "guest_turris_dhcp_rule", "enabled")
    )
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_0", "disabled"))
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_1", "disabled"))

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")


def test_wrong_update(uci_configs_init, infrastructure, network_restart_command):
    def update(data):
        res = infrastructure.process_message(
            {"module": "guest", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" in res

    update(
        {
            "enabled": False,
            "ip": "10.1.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False, "start": 10, "limit": 50},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": True, "start": 10, "limit": 50, "lease_time": 119},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False, "download": 1200, "upload": 1000},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.250.0.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        }
    )
    update(
        {
            "enabled": True,
            "ip": "10.1.0.256",
            "netmask": "255.255.0.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        }
    )


@pytest.mark.parametrize(
    "orig_backend_val,api_val,new_backend_val",
    [
        ["", 60 * 60, "3600"],
        ["infinite", 0, "infinite"],
        ["120", 120, "120"],
        ["3m", 180, "180"],
        ["1h", 3600, "3600"],
    ],
    ids=["none", "infinite", "120", "3m", "1h"],
)
@pytest.mark.only_backends(["openwrt"])
def test_dhcp_lease(
    uci_configs_init,
    infrastructure,
    network_restart_command,
    orig_backend_val,
    api_val,
    new_backend_val,
):
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.add_section("dhcp", "dhcp", "guest_turris")
        backend.set_option("dhcp", "guest_turris", "leasetime", orig_backend_val)

    res = infrastructure.process_message(
        {"module": "guest", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["dhcp"]["lease_time"] == api_val

    res = infrastructure.process_message(
        {
            "module": "guest",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "enabled": True,
                "ip": "10.1.0.3",
                "netmask": "255.252.0.0",
                "dhcp": {"enabled": True, "start": 10, "limit": 50, "lease_time": api_val},
                "qos": {"enabled": False},
            },
        }
    )
    assert res["data"]["result"]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "dhcp", "guest_turris", "leasetime") == new_backend_val


@pytest.mark.only_backends(["openwrt"])
def test_dhcp_clients(
    uci_configs_init,
    init_script_result,
    infrastructure,
    network_restart_command,
    guest_dnsmasq_files,
):
    def update(data, clients):
        res = infrastructure.process_message(
            {"module": "guest", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "guest",
        }
        res = infrastructure.process_message(
            {"module": "guest", "action": "get_settings", "kind": "request"}
        )
        assert res["data"]["dhcp"]["clients"] == clients

    # Return both
    update(
        {
            "enabled": True,
            "ip": "10.10.0.1",
            "netmask": "255.255.252.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": 24 * 60 * 60 + 1,
            },
            "qos": {"enabled": False},
        },
        [
            {
                "ip": "10.10.2.1",
                "mac": "16:25:34:43:52:61",
                "expires": 1539350286,
                "active": True,
                "hostname": "first",
                "static": False,
            },
            {
                "ip": "10.10.1.1",
                "mac": "94:85:76:67:58:49",
                "expires": 1539350388,
                "active": False,
                "hostname": "*",
                "static": False,
            },
        ],
    )

    # Return empty when disabled
    update(
        {
            "enabled": True,
            "ip": "10.10.0.1",
            "netmask": "255.255.252.0",
            "dhcp": {"enabled": False},
            "qos": {"enabled": False},
        },
        [],
    )

    # Return first
    update(
        {
            "enabled": True,
            "ip": "10.10.2.1",
            "netmask": "255.255.255.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": 24 * 60 * 60 + 1,
            },
            "qos": {"enabled": False},
        },
        [
            {
                "ip": "10.10.2.1",
                "mac": "16:25:34:43:52:61",
                "expires": 1539350286,
                "active": True,
                "hostname": "first",
                "static": False,
            }
        ],
    )

    # Return second
    update(
        {
            "enabled": True,
            "ip": "10.10.1.1",
            "netmask": "255.255.255.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": 24 * 60 * 60 + 1,
            },
            "qos": {"enabled": False},
        },
        [
            {
                "ip": "10.10.1.1",
                "mac": "94:85:76:67:58:49",
                "expires": 1539350388,
                "active": False,
                "hostname": "*",
                "static": False,
            }
        ],
    )

    # Missed range
    update(
        {
            "enabled": True,
            "ip": "192.168.1.1",
            "netmask": "255.255.0.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": 24 * 60 * 60 + 1,
            },
            "qos": {"enabled": False},
        },
        [],
    )


@pytest.mark.file_root_path(WIFI_ROOT_PATH)
@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_interface_count(
    file_root_init,
    uci_configs_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
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
                "channel": 11,
                "htmode": "HT20",
                "band": "2g",
                "encryption": WIFI_DEFAULT_ENCRYPTION,
                "ieee80211w_disabled": False,
                "password": "passpass",
                "guest_wifi": {"enabled": False},
            },
        ],
        1,
    )
    set_and_test(
        {"wan": [], "lan": ["eth0"], "guest": [], "none": []},
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


def test_update_settings_dhcp_range(uci_configs_init, infrastructure, network_restart_command):
    def update(ip, netmask, start, limit, result):
        res = infrastructure.process_message(
            {
                "module": "guest",
                "action": "update_settings",
                "kind": "request",
                "data": {
                    "enabled": True,
                    "ip": ip,
                    "netmask": netmask,
                    "dhcp": {
                        "enabled": True,
                        "start": start,
                        "limit": limit,
                        "lease_time": 24 * 60 * 60 + 1,
                    },
                    "qos": {"enabled": False},
                },
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": result},
            "kind": "reply",
            "module": "guest",
        }

    # default
    update("192.168.1.1", "255.255.255.0", 150, 100, True)
    # last
    update("192.168.1.1", "255.255.255.0", 150, 105, True)
    # first wrong
    update("192.168.1.1", "255.255.255.0", 150, 106, False)
    # other range
    update("10.10.0.1", "255.255.192.0", (2 ** 13), (2 ** 13) - 1, True)
    update("10.10.0.1", "255.255.192.0", (2 ** 13), (2 ** 13) - 1, True)
    # too high number
    update("10.10.0.1", "255.255.192.0", (2 ** 32), 1, False)
    # last valid router ip
    update("192.168.1.99", "255.255.255.0", 100, 150, True)
    # router ip in range
    update("192.168.1.100", "255.255.255.0", 100, 150, False)


@pytest.mark.only_backends(["openwrt"])
def test_get_settings_missing_wireless(uci_configs_init, infrastructure):
    os.unlink(os.path.join(uci_configs_init[0], "wireless"))
    res = infrastructure.process_message(
        {"module": "guest", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
