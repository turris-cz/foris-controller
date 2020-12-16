#
# foris-controller
# Copyright (C) 2018-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
    init_script_result,
    network_restart_command,
    device,
    turris_os_version,
    FILE_ROOT_PATH,
    file_root_init,
    UCI_CONFIG_DIR_PATH,
)
from foris_controller_testtools.utils import (
    match_subdict,
    get_uci_module,
    FileFaker,
    prepare_turrishw,
    check_service_result,
)

WIFI_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")


def all_equal(first, *items):
    return all(first == item for item in items)


@pytest.fixture(scope="function")
def lan_dnsmasq_files():
    leases = "\n".join(
        [
            "1539350186 11:22:33:44:55:66 192.168.1.1 prvni *",
            "1539350188 99:88:77:66:55:44 192.168.2.1 * *",
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
            "ipv4     2 udp      17 34 src=10.111.222.213 dst=192.168.1.1 sport=57085 dport=123 "
            "packets=1 bytes=76 src=80.211.195.36 dst=172.20.6.87 sport=123 dport=57085 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 tcp      6 7440 ESTABLISHED src=172.20.6.100 dst=172.20.6.87 sport=35774 "
            "dport=22 packets=244 bytes=17652 src=172.20.6.87 dst=172.20.6.100 sport=22 dport=35774 "
            "packets=190 bytes=16637 [ASSURED] mark=0 zone=0 use=2",
            "ipv4     2 udp      17 173 src=127.0.0.1 dst=127.0.0.1 sport=42365 dport=53 packets=2 "
            "bytes=120 src=127.0.0.1 dst=127.0.0.1 sport=53 dport=42365 packets=2 bytes=164 [ASSURED] "
            "mark=0 zone=0 use=2",
            "ipv6     10 udp      17 41 src=fd52:ad42:910e:0000:0000:0000:0000:64fa "
            "dst=fd21:36f9:644e:0000:0000:0000:0000:0001 sport=59532 dport=53 packets=1 bytes=102 "
            "src=fd21:36f9:644e:0000:0000:0000:0000:0001 dst=fd52:ad42:910e:0000:0000:0000:0000:64fa "
            "sport=53 dport=59532 packets=1 bytes=263 mark=0 zone=0 use=2"
        ]
    )
    odhcpd = "\n".join(
        [
            "fd52:ad42:a6c9::64fe\tprvni",
            "# lan 00010003d8e63397f73ed8cd7cda d208984 prvni 1608144105 1b5 128 fd52:ad42:a6c9::64fe/128",
            "fd52:ad42:a6c9::64fa\tdruhy",
            "# lan 00020000df167896750a08ce0782 e2343f3e druhy 1608148949 c34 128 fd52:ad42:a6c9::64fa/128 fd52:ad42:910e::64fa/128"
        ]
    )
    with FileFaker(
        FILE_ROOT_PATH, "/tmp/dhcp.leases", False, leases
    ) as lease_file,\
        FileFaker(
        FILE_ROOT_PATH, "/proc/net/nf_conntrack", False, conntrack
    ) as conntrack_file,\
        FileFaker(
        FILE_ROOT_PATH, "/tmp/hosts/odhcpd", False, odhcpd
    ) as odhcpd_file:
        yield lease_file, conntrack_file, odhcpd_file


def test_get_settings(uci_configs_init, infrastructure, lan_dnsmasq_files):
    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert res.keys() == {"action", "kind", "data", "module"}
    assert res["data"].keys() == {
        "mode",
        "mode_managed",
        "mode_unmanaged",
        "interface_count",
        "interface_up_count",
        "lan_redirect"
    }
    assert res["data"]["mode"] in ["managed", "unmanaged"]

    assert set(res["data"]["mode_managed"].keys()) == {"router_ip", "netmask", "dhcp"}
    assert set(res["data"]["mode_managed"]["dhcp"].keys()) == {
        "enabled",
        "start",
        "limit",
        "lease_time",
        "clients",
        "ipv6clients"
    }

    assert set(res["data"]["mode_unmanaged"].keys()) == {"lan_type", "lan_static", "lan_dhcp"}
    assert res["data"]["mode_unmanaged"]["lan_type"] in ["static", "dhcp", "none"]
    assert set(res["data"]["mode_unmanaged"]["lan_dhcp"].keys()) in [{"hostname"}, set()]
    assert set(res["data"]["mode_unmanaged"]["lan_static"].keys()).issubset(
        {"ip", "netmask", "gateway", "dns1", "dns2"}
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version, lan_dnsmasq_files
):
    filters = [("lan", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "lan",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "lan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message(
            {"module": "lan", "action": "get_settings", "kind": "request"}
        )
        assert res["module"] == "lan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"

        data_lan_redirect = data.pop("lan_redirect", None)
        res_lan_redirect = res["data"].pop("lan_redirect")
        if data_lan_redirect:
            # we can get lan_redirect in reply data regardless of whether we updated it or not
            # so compare it only in case of updated lan_redirect
            assert data_lan_redirect == res_lan_redirect

        assert match_subdict(data, res["data"])

    update(
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
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.0.0.3",
                "netmask": "255.255.0.0",
                "dhcp": {"enabled": False},
            },
            "lan_redirect": True,
        }
    )
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.252.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 1,
                },
            },
        }
    )
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.2.0.3",
                "netmask": "255.255.0.0",
                "dhcp": {"enabled": False},
            },
        }
    )

    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {"hostname": "bogatyr"}},
        }
    )

    update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {}}})

    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                },
            },
        }
    )

    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                    "dns1": "1.1.1.1",
                },
            },
        }
    )

    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                    "dns1": "1.1.1.2",
                    "dns2": "8.8.8.8",
                },
            },
        }
    )

    update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "none"}})


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_wrong_update(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):
    def update(data):
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" in res

    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.255.0.0",
                "dhcp": {
                    "enabled": False,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 2,
                },
            },
        }
    )
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.250.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 3,
                },
            },
        }
    )
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.256",
                "netmask": "255.255.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 4,
                },
            },
        }
    )
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.1",
                "netmask": "255.255.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 119,  # too small
                },
            },
        }
    )

    update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "dhcp"}})
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.256",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                },
            },
        }
    )
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.250.0.0",
                    "gateway": "10.4.0.1",
                },
            },
        }
    )
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.256.1",
                },
            },
        }
    )
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                    "dns1": "192.168.256.1",
                },
            },
        }
    )
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                    "dns2": "192.168.256.1",
                },
            },
        }
    )
    update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "none", "lan_none": {}}})


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.parametrize(
    "orig_backend_val,api_val,new_backend_val",
    [
        ["", 12 * 60 * 60, "43200"],
        ["infinite", 0, "infinite"],
        ["120", 120, "120"],
        ["3m", 180, "180"],
        ["2h", 7200, "7200"],
        ["1d", 86400, "86400"],
    ],
    ids=["none", "infinite", "120", "3m", "2h", "1d"],
)
@pytest.mark.only_backends(["openwrt"])
def test_dhcp_lease(
    uci_configs_init,
    infrastructure,
    network_restart_command,
    orig_backend_val,
    api_val,
    new_backend_val,
    device,
    turris_os_version,
    lan_dnsmasq_files
):
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("dhcp", "lan", "leasetime", orig_backend_val)

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["mode_managed"]["dhcp"]["lease_time"] == api_val

    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "10.1.0.3",
                    "netmask": "255.252.0.0",
                    "dhcp": {"enabled": True, "start": 10, "limit": 50, "lease_time": api_val},
                },
            },
        }
    )
    assert res["data"]["result"]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "dhcp", "lan", "leasetime") == new_backend_val


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):
    uci = get_uci_module(infrastructure.name)

    def update(data):
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" not in res
        assert res["data"]["result"]

        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            return backend.read()

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
    assert not uci.parse_bool(uci.get_option_named(data, "firewall", "redirect_192_168_1_1", "enabled"))

    data = update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.252.0.0",
                "dhcp": {"enabled": True, "start": 10, "limit": 50, "lease_time": 0},
            },
            "lan_redirect": True,
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "managed"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["10.1.0.3/14"]
    assert not uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))
    assert uci.get_option_named(data, "dhcp", "lan", "start") == "10"
    assert uci.get_option_named(data, "dhcp", "lan", "limit") == "50"
    assert uci.get_option_named(data, "dhcp", "lan", "dhcp_option") == ["6,10.1.0.3"]
    assert uci.parse_bool(uci.get_option_named(data, "firewall", "redirect_192_168_1_1", "enabled"))

    data = update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {"hostname": "bogatyr"}},
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname") == "bogatyr"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {}}})
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname") == "bogatyr"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {"hostname": ""}},
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                },
            },
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["10.4.0.2/15"]
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.1"
    assert uci.get_option_named(data, "network", "lan", "dns", []) == []
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.5.0.2",
                    "netmask": "255.255.254.0",
                    "gateway": "10.4.0.8",
                    "dns1": "1.1.1.1",
                },
            },
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["10.5.0.2/23"]
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.8"
    assert uci.get_option_named(data, "network", "lan", "dns") == ["1.1.1.1"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {
                "lan_type": "static",
                "lan_static": {
                    "ip": "10.4.0.2",
                    "netmask": "255.254.0.0",
                    "gateway": "10.4.0.1",
                    "dns1": "1.1.1.2",
                    "dns2": "8.8.8.8",
                },
            },
        }
    )
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == ["10.4.0.2/15"]
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.1"
    assert uci.get_option_named(data, "network", "lan", "dns") == ["8.8.8.8", "1.1.1.2"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({"mode": "unmanaged", "mode_unmanaged": {"lan_type": "none"}})
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "none"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_dhcp_clients_openwrt(
    uci_configs_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
    lan_dnsmasq_files,
):
    def update(data, clients):
        res = infrastructure.process_message(
            {"module": "lan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "lan",
        }
        res = infrastructure.process_message(
            {"module": "lan", "action": "get_settings", "kind": "request"}
        )
        assert res["data"]["mode_managed"]["dhcp"]["clients"] == clients

    # Return both
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.1.1",
                "netmask": "255.252.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 1,
                },
            },
        },
        [
            {
                "ip": "192.168.1.1",
                "mac": "11:22:33:44:55:66",
                "expires": 1539350186,
                "active": True,
                "hostname": "prvni",
            },
            {
                "ip": "192.168.2.1",
                "mac": "99:88:77:66:55:44",
                "expires": 1539350188,
                "active": False,
                "hostname": "*",
            },
        ],
    )

    # Return other mode
    update(
        {
            "mode": "unmanaged",
            "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {"hostname": "bogatyr"}},
        },
        [],
    )

    # Return empty when disabled
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.1.1",
                "netmask": "255.252.0.0",
                "dhcp": {"enabled": False},
            },
        },
        [],
    )

    # Return first
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.1.1",
                "netmask": "255.255.255.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 1,
                },
            },
        },
        [
            {
                "ip": "192.168.1.1",
                "mac": "11:22:33:44:55:66",
                "expires": 1539350186,
                "active": True,
                "hostname": "prvni",
            }
        ],
    )

    # Return second
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "192.168.2.1",
                "netmask": "255.255.255.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 1,
                },
            },
        },
        [
            {
                "ip": "192.168.2.1",
                "mac": "99:88:77:66:55:44",
                "expires": 1539350188,
                "active": False,
                "hostname": "*",
            }
        ],
    )

    # Missed range
    update(
        {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.252.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": 24 * 60 * 60 + 1,
                },
            },
        },
        [],
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_dhcp_clients_openwrt_ipv6leases(
    uci_configs_init,
    infrastructure,
    device,
    turris_os_version,
    lan_dnsmasq_files,
):
    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"]["mode_managed"]["dhcp"]["ipv6clients"][2]["active"]
    assert res["data"]["mode_managed"]["dhcp"]["ipv6clients"][2]["ipv6"] == "fd52:ad42:910e::64fa"


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
    lan_dnsmasq_files
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

    # Single interface no wifi
    set_and_test(
        {"wan": [], "lan": ["eth0"], "guest": [], "none": []},
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
                "hwmode": "11g",
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
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
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
                "hwmode": "11g",
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
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
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
                "hwmode": "11g",
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
                "hwmode": "11g",
                "password": "passpass",
                "guest_wifi": {"enabled": True, "SSID": "Turris-testik", "password": "ssapssap"},
            },
        ],
        3,
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_dhcp_range(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):
    def update(ip, netmask, start, limit, result):
        res = infrastructure.process_message(
            {
                "module": "lan",
                "action": "update_settings",
                "kind": "request",
                "data": {
                    "mode": "managed",
                    "mode_managed": {
                        "router_ip": ip,
                        "netmask": netmask,
                        "dhcp": {
                            "enabled": True,
                            "start": start,
                            "limit": limit,
                            "lease_time": 24 * 60 * 60 + 1,
                        },
                    },
                },
            }
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": result},
            "kind": "reply",
            "module": "lan",
        }

    # default
    update("192.168.1.1", "255.255.255.0", 150, 100, True)
    # last
    update("192.168.1.1", "255.255.255.0", 150, 104, True)
    # first wrong
    update("192.168.1.1", "255.255.255.0", 150, 106, False)
    # other range
    update("10.10.0.1", "255.255.192.0", (2 ** 13), (2 ** 13) - 2, True)
    # too high number
    update("10.10.0.1", "255.255.192.0", (2 ** 32), 1, False)
    # last valid router ip
    update("192.168.1.99", "255.255.255.0", 100, 150, True)
    # router ip in range
    update("192.168.1.100", "255.255.255.0", 100, 150, False)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_dns_option(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):
    uci = get_uci_module(infrastructure.name)

    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "unmanaged",
                "mode_unmanaged": {
                    "lan_type": "static",
                    "lan_static": {
                        "ip": "10.4.0.2",
                        "netmask": "255.254.0.0",
                        "gateway": "10.4.0.1",
                        "dns1": "2.2.2.2",
                        "dns2": "8.8.8.8",
                    },
                },
            },
        }
    )
    assert res["data"]["result"]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "lan", "dns")
        backend.set_option("network", "lan", "dns", "1.1.1.1 8.8.8.8")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["mode_unmanaged"]["lan_static"]["dns1"] == "8.8.8.8"
    assert res["data"]["mode_unmanaged"]["lan_static"]["dns2"] == "1.1.1.1"


@pytest.mark.only_backends(["openwrt"])
def test_get_settings_missing_wireless(uci_configs_init, infrastructure, lan_dnsmasq_files):
    os.unlink(os.path.join(uci_configs_init[0], "wireless"))
    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_dhcp_client_settings(
    uci_configs_init,
    init_script_result,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
    lan_dnsmasq_files,
):
    filters = [("lan", "set_dhcp_client")]

    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.1.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 10,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }

    def set_client(data, reason=None):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "lan", "action": "set_dhcp_client", "kind": "request", "data": data}
        )
        assert res["data"]["result"] is True or res["data"]["reason"] == reason
        if not reason:
            notifications = infrastructure.get_notifications(notifications, filters=filters)
            assert notifications[-1] == {
                "module": "lan",
                "action": "set_dhcp_client",
                "kind": "notification",
                "data": data,
            }

        return infrastructure.process_message(
            {"module": "lan", "action": "get_settings", "kind": "request"}
        )["data"]["mode_managed"]["dhcp"]["clients"]

    # set all
    client_list = set_client(
        {"mac": "81:22:33:44:55:66", "hostname": "static-client1", "ip": "192.168.1.5"}
    )
    assert (
        len(
            [
                e
                for e in client_list
                if e["ip"] == "192.168.1.5"
                and e["mac"] == "81:22:33:44:55:66"
                and e["hostname"] == "static-client1"
            ]
        )
        == 1
    )

    # unset hostname
    client_list = set_client({"mac": "81:22:33:44:55:66", "hostname": "", "ip": "192.168.1.5"})
    assert (
        len(
            [
                e
                for e in client_list
                if e["ip"] == "192.168.1.5"
                and e["mac"] == "81:22:33:44:55:66"
                and e["hostname"] == ""
            ]
        )
        == 1
    )

    # ignore -> don't assign ip
    client_list = set_client({"mac": "84:22:33:44:55:66", "hostname": "", "ip": "ignore"})
    assert (
        len(
            [
                e
                for e in client_list
                if e["ip"] == "ignore" and e["mac"] == "84:22:33:44:55:66" and e["hostname"] == ""
            ]
        )
        == 1
    )

    # test uppercase conversion
    client_list = set_client({"mac": "aa:bb:cc:dd:55:66", "hostname": "", "ip": "192.168.1.7"})
    assert (
        len(
            [
                e
                for e in client_list
                if e["ip"] == "192.168.1.7"
                and e["mac"] == "AA:BB:CC:DD:55:66"
                and e["hostname"] == ""
            ]
        )
        == 1
    )

    # it is possible to set same ip for two macs
    set_client({"mac": "81:22:33:44:55:66", "hostname": "", "ip": "192.168.1.3"})
    set_client({"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.1.3"})

    client_list = set_client({"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.1.9"})

    orig_client_list = client_list

    # out of lan
    client_list = set_client(
        {"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.2.3"}, "out-of-network"
    )
    assert orig_client_list == client_list

    # set in dynamic range
    client_list = set_client(
        {"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.1.11"}, "in-dynamic"
    )
    assert orig_client_list == client_list

    # clear if in dynamic
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.1.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 5,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    client_list = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )["data"]["mode_managed"]["dhcp"]["clients"]
    assert "192.168.1.9" not in [e["ip"] for e in client_list]

    # clear when out of network range
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.5.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 5,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    client_list = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )["data"]["mode_managed"]["dhcp"]["clients"]
    assert "192.168.1.3" not in [e["ip"] for e in client_list]

    orig_client_list = client_list

    # dhcp disabled
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.5.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {"enabled": False},
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    set_client({"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.5.3"}, "disabled")

    # unmanaged mode
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "unmanaged",
                "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {"hostname": "gromoboj"}},
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    set_client({"mac": "82:22:33:44:55:66", "hostname": "", "ip": "192.168.5.3"}, "disabled")


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_dhcp_client_settings_openwrt(
    uci_configs_init,
    init_script_result,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
    lan_dnsmasq_files,
):

    uci = get_uci_module(infrastructure.name)

    def get_uci_data():
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            data = backend.read()

        return [dict(e["data"]) for e in uci.get_sections_by_type(data, "dhcp", "host")]

    def set_client(data):
        res = infrastructure.process_message(
            {"module": "lan", "action": "set_dhcp_client", "kind": "request", "data": data}
        )
        assert res == {
            "action": "set_dhcp_client",
            "kind": "reply",
            "module": "lan",
            "data": {"result": True},
        }

        infrastructure.process_message(
            {"module": "lan", "action": "get_settings", "kind": "request"}
        )
        check_service_result("dnsmasq", "restart", True)

        return get_uci_data()

    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.8.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 10,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }

    # full
    data = set_client(
        {"mac": "AA:22:33:44:55:66", "hostname": "my-second-hostname", "ip": "192.168.8.4"}
    )
    assert {"ip": "192.168.8.4", "name": "my-second-hostname", "mac": "AA:22:33:44:55:66"} in data

    # without hostname
    data = set_client({"mac": "BB:22:33:44:55:66", "hostname": "", "ip": "192.168.8.8"})
    assert {"ip": "192.168.8.8", "mac": "BB:22:33:44:55:66"} in data

    # ignored
    data = set_client({"mac": "CC:22:33:44:55:66", "hostname": "", "ip": "ignore"})
    assert {"ip": "ignore", "mac": "CC:22:33:44:55:66"} in data

    # multiple macs
    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )["data"]["mode_managed"]["dhcp"]["clients"]

    assert len(res) == 3  # full, without hostname, ignore

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("dhcp", "@host[0]", "mac", "DD:22:33:44:55:66 EE:22:33:44:55:66")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )["data"]["mode_managed"]["dhcp"]["clients"]

    assert len(res) == 2  # full, without hostname, ignore
    assert "DD:22:33:44:55:66" not in [e["mac"] for e in res]
    assert "EE:22:33:44:55:66" not in [e["mac"] for e in res]

    # split records on save
    uci_data = get_uci_data()
    assert len(uci_data) == 3
    assert "DD:22:33:44:55:66 EE:22:33:44:55:66" in [e["mac"] for e in uci_data]

    uci_data = set_client({"mac": "EE:22:33:44:55:66", "hostname": "splitted", "ip": "192.168.8.2"})
    assert len(uci_data) == 4
    assert "DD:22:33:44:55:66" in [e["mac"] for e in uci_data]
    assert "EE:22:33:44:55:66" in [e["mac"] for e in uci_data]

    # delete record if dynamic overlaps
    assert "192.168.8.8" in [e["ip"] for e in uci_data]
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.8.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 5,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )
    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    uci_data = get_uci_data()
    assert len(uci_data) == 3
    assert "192.168.8.8" not in [e["ip"] for e in uci_data]

    # delete record if it doesn't fit in network range
    assert "192.168.8.2" in [e["ip"] for e in uci_data]
    assert "192.168.8.4" in [e["ip"] for e in uci_data]
    res = infrastructure.process_message(
        {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "mode": "managed",
                "mode_managed": {
                    "router_ip": "192.168.9.1",
                    "netmask": "255.255.255.0",
                    "dhcp": {
                        "enabled": True,
                        "start": 5,
                        "limit": 50,
                        "lease_time": 24 * 60 * 60,
                    },
                },
            },
        }
    )

    assert res == {
        "action": "update_settings",
        "data": {"result": True},
        "kind": "reply",
        "module": "lan",
    }
    uci_data = get_uci_data()
    assert len(uci_data) == 1
    assert "192.168.8.2" not in [e["ip"] for e in uci_data]
    assert "192.168.8.4" not in [e["ip"] for e in uci_data]

    # test missing mac in dhcp client
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        section_name = backend.add_section("dhcp", "host")
        backend.set_option("dhcp", section_name, "ip", "192.168.9.25")  # only ip is mandatory
    client_list = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )["data"]["mode_managed"]["dhcp"]["clients"]
    assert "192.168.9.25" not in [e["ip"] for e in client_list]

    # test tab in macaddress field
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("dhcp", "@host[0]", "mac", "\tEE:22:33:44:55:66")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_ipv6_address_in_dns(uci_configs_init, infrastructure, device, turris_os_version, lan_dnsmasq_files):
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "lan", "dns", "ff::")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res


def test_get_settings_lan_redirect(uci_configs_init, infrastructure, lan_dnsmasq_files):
    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"]["lan_redirect"]


@pytest.mark.only_backends(["openwrt"])
def test_get_settings_lan_redirect_openwrt(uci_configs_init, infrastructure, lan_dnsmasq_files):
    uci = get_uci_module(infrastructure.name)

    # with redirect_192_168_1_1.enabled set it should return its value
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("firewall", "redirect_192_168_1_1", "enabled", 0)

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"]["lan_redirect"] is False

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("firewall", "redirect_192_168_1_1", "enabled", 1)

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"]["lan_redirect"]

    # with redirect_192_168_1_1.enabled unset it should return lan_redirect == True
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("firewall", "redirect_192_168_1_1", "enabled")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()
    assert res["data"]["lan_redirect"]

    # with missing section redirect_192_168_1_1 it shouldn't return lan_redirect
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_section("firewall", "redirect_192_168_1_1")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()
    assert "lan_redirect" not in res["data"].keys()


@pytest.mark.only_backends(["openwrt"])
def test_ip_slash_netmask(uci_configs_init, infrastructure):
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "lan", "netmask")
        backend.del_option("network", "lan", "ipaddr")
        backend.set_option("network", "lan", "ipaddr", "192.168.1.1/24")

    res = infrastructure.process_message(
        {"module": "lan", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()

    mode_managed = res["data"]["mode_managed"]
    mode_unmanaged = res["data"]["mode_unmanaged"]["lan_static"]

    assert all_equal(mode_managed["router_ip"], mode_unmanaged["ip"], "192.168.1.1")
    assert all_equal(mode_managed["netmask"], mode_unmanaged["netmask"], "255.255.255.0")
