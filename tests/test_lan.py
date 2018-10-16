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
    only_backends, uci_configs_init, infrastructure, ubusd_test, lock_backend, init_script_result,
    network_restart_command, device, turris_os_version, FILE_ROOT_PATH, file_root_init
)
from foris_controller_testtools.utils import (
    match_subdict, get_uci_module, check_service_result, FileFaker, prepare_turrishw
)

WIFI_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_wifi_files")


@pytest.fixture(scope="function")
def lan_dnsmasq_files():
    leases = "\n".join([
        "1539350186 11:22:33:44:55:66 192.168.1.1 prvni *",
        "1539350188 99:88:77:66:55:44 192.168.2.1 * *",
    ])
    conntrack = "\n".join([
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
    ])
    with \
            FileFaker(FILE_ROOT_PATH, "/tmp/dhcp.leases", False, leases) as lease_file, \
            FileFaker(FILE_ROOT_PATH, "/proc/net/nf_conntrack", False, conntrack) as conntrack_file:
        yield lease_file, conntrack_file


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "lan",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {"mode", "mode_managed", "mode_unmanaged", "interface_count"}
    assert res["data"]["mode"] in ["managed", "unmanaged"]

    assert set(res["data"]["mode_managed"].keys()) == {"router_ip", "netmask", "dhcp"}
    assert set(res["data"]["mode_managed"]["dhcp"].keys()) == {
        "enabled", "start", "limit", "lease_time", "clients"
    }

    assert set(res["data"]["mode_unmanaged"].keys()) == {"lan_type", "lan_static", "lan_dhcp"}
    assert res["data"]["mode_unmanaged"]["lan_type"] in ["static", "dhcp", "none"]
    assert set(res["data"]["mode_unmanaged"]["lan_dhcp"].keys()) in [{"hostname"}, set()]
    assert set(res["data"]["mode_unmanaged"]["lan_static"].keys()).issubset({
        "ip",  "netmask", "gateway", "dns1", "dns2"
    })


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
def test_update_settings(
    uci_configs_init, infrastructure, ubusd_test, network_restart_command,
    device, turris_os_version,
):
    filters = [("lan", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'lan'
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "lan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message({
            "module": "lan",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["module"] == "lan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(data, res["data"])

    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.5.8",
            u"netmask": u"255.255.255.0",
            u"dhcp": {u"enabled": False},
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.0.0.3",
            u"netmask": u"255.255.0.0",
            u"dhcp": {u"enabled": False},
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.3",
            u"netmask": u"255.252.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 1,
            },
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.2.0.3",
            u"netmask": u"255.255.0.0",
            u"dhcp": {u"enabled": False},
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {u"hostname": "bogatyr"},
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {},
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
            },
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
                u"dns1": "1.1.1.1",
            },
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
                u"dns1": "1.1.1.2",
                u"dns2": "8.8.8.8",
            },
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"none",
        }
    })


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
def test_wrong_update(
    uci_configs_init, infrastructure, ubusd_test, network_restart_command,
    device, turris_os_version,
):

    def update(data):
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert "errors" in res

    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.3",
            u"netmask": u"255.255.0.0",
            u"dhcp": {
                u"enabled": False,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 2,
            },
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.3",
            u"netmask": u"255.250.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 3,
            },
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.256",
            u"netmask": u"255.255.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 4,
            },
        }
    })
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.1",
            u"netmask": u"255.255.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time": 119,  # too small
            },
        }
    })

    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.256",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
            },
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.250.0.0",
                u"gateway": u"10.4.0.1",
            },
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.256.1",
            },
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
                u"dns1": "192.168.256.1",
            },
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
                u"dns2": "192.168.256.1",
            },
        }
    })
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"none",
            u"lan_none": {},
        }
    })


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    "orig_backend_val,api_val,new_backend_val", [
        ["", 12 * 60 * 60, "43200"],
        ["infinite", 0, "infinite"],
        ["120", 120, "120"],
        ["3m", 180, "180"],
        ["1h", 3600, "3600"],
    ],
    ids=["none", "infinite", "120", "3m", "1h"],
)
@pytest.mark.only_backends(['openwrt'])
def test_dhcp_lease(
    uci_configs_init, infrastructure, ubusd_test, lock_backend, network_restart_command,
    orig_backend_val, api_val, new_backend_val, device, turris_os_version,
):
    uci = get_uci_module(lock_backend)

    with uci.UciBackend() as backend:
        backend.set_option("dhcp", "lan", "leasetime", orig_backend_val)

    res = infrastructure.process_message({
        "module": "lan",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["mode_managed"]["dhcp"]["lease_time"] == api_val

    res = infrastructure.process_message({
        "module": "lan",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "mode": "managed",
            "mode_managed": {
                "router_ip": "10.1.0.3",
                "netmask": "255.252.0.0",
                "dhcp": {
                    "enabled": True,
                    "start": 10,
                    "limit": 50,
                    "lease_time": api_val,
                },
            }
        }
    })
    assert res["data"]["result"]

    with uci.UciBackend() as backend:
        data = backend.read()

    assert uci.get_option_named(data, "dhcp", "lan", "leasetime") == new_backend_val


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.only_backends(['openwrt'])
def test_update_settings_openwrt(
    uci_configs_init, infrastructure, ubusd_test, lock_backend, network_restart_command,
    device, turris_os_version,
):
    uci = get_uci_module(lock_backend)

    def update(data):
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res["data"]["result"]

        with uci.UciBackend() as backend:
            return backend.read()

    data = update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.5.8",
            u"netmask": u"255.255.255.0",
            u"dhcp": {u"enabled": False},
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "managed"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == "192.168.5.8"
    assert uci.get_option_named(data, "network", "lan", "netmask") == "255.255.255.0"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.3",
            u"netmask": u"255.252.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time": 0,
            },
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "managed"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == "10.1.0.3"
    assert uci.get_option_named(data, "network", "lan", "netmask") == "255.252.0.0"
    assert not uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))
    assert uci.get_option_named(data, "dhcp", "lan", "start") == "10"
    assert uci.get_option_named(data, "dhcp", "lan", "limit") == "50"
    assert uci.get_option_named(data, "dhcp", "lan", "dhcp_option") == ["6,10.1.0.3"]

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {u"hostname": "bogatyr"},
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname") == "bogatyr"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {},
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname") == "bogatyr"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {u"hostname": ""},
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "lan", "hostname", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
            },
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == "10.4.0.2"
    assert uci.get_option_named(data, "network", "lan", "netmask") == "255.254.0.0"
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.1"
    assert uci.get_option_named(data, "network", "lan", "dns", []) == []
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.5.0.2",
                u"netmask": u"255.255.254.0",
                u"gateway": u"10.4.0.8",
                u"dns1": "1.1.1.1",
            },
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == "10.5.0.2"
    assert uci.get_option_named(data, "network", "lan", "netmask") == "255.255.254.0"
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.8"
    assert uci.get_option_named(data, "network", "lan", "dns") == ["1.1.1.1"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"static",
            u"lan_static": {
                u"ip": u"10.4.0.2",
                u"netmask": u"255.254.0.0",
                u"gateway": u"10.4.0.1",
                u"dns1": "1.1.1.2",
                u"dns2": "8.8.8.8",
            },
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "static"
    assert uci.get_option_named(data, "network", "lan", "ipaddr") == "10.4.0.2"
    assert uci.get_option_named(data, "network", "lan", "netmask") == "255.254.0.0"
    assert uci.get_option_named(data, "network", "lan", "gateway") == "10.4.0.1"
    assert uci.get_option_named(data, "network", "lan", "dns") == ["8.8.8.8", "1.1.1.2"]
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))

    data = update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"none",
        }
    })
    assert uci.get_option_named(data, "network", "lan", "_turris_mode") == "unmanaged"
    assert uci.get_option_named(data, "network", "lan", "proto") == "none"
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "lan", "ignore"))



@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.only_backends(['openwrt'])
def test_dhcp_clients(
    uci_configs_init, infrastructure, ubusd_test, lock_backend, network_restart_command,
    device, turris_os_version, lan_dnsmasq_files
):
    def update(data, clients):
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'lan'
        }
        res = infrastructure.process_message({
            "module": "lan",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["data"]["mode_managed"]["dhcp"]["clients"] == clients

    # Return both
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.1.1",
            u"netmask": u"255.252.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 1,
            },
        }
    }, [
        {
            "ip": "192.168.1.1", "mac": "11:22:33:44:55:66",
            "expires": 1539350186, "active": True, "hostname": "prvni"
        },
        {
            "ip": "192.168.2.1", "mac": "99:88:77:66:55:44",
            "expires": 1539350188, "active": False, "hostname": "*"
        }
    ])

    # Return other mode
    update({
        "mode": "unmanaged",
        "mode_unmanaged": {
            u"lan_type": u"dhcp",
            u"lan_dhcp": {u"hostname": "bogatyr"},
        }
    }, [])

    # Return empty when disabled
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.1.1",
            u"netmask": u"255.252.0.0",
            u"dhcp": {
                u"enabled": False,
            },
        }
    }, [])

    # Return first
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.1.1",
            u"netmask": u"255.255.255.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 1,
            },
        }
    }, [
        {
            "ip": "192.168.1.1", "mac": "11:22:33:44:55:66",
            "expires": 1539350186, "active": True, "hostname": "prvni"
        },
    ])

    # Return second
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"192.168.2.1",
            u"netmask": u"255.255.255.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 1,
            },
        }
    }, [
        {
            "ip": "192.168.2.1", "mac": "99:88:77:66:55:44",
            "expires": 1539350188, "active": False, "hostname": "*"
        }
    ])

    # Missed range
    update({
        "mode": "managed",
        "mode_managed": {
            u"router_ip": u"10.1.0.3",
            u"netmask": u"255.252.0.0",
            u"dhcp": {
                u"enabled": True,
                u"start": 10,
                u"limit": 50,
                u"lease_time":  24 * 60 * 60 + 1,
            },
        }
    }, [])


@pytest.mark.file_root_path(WIFI_ROOT_PATH)
@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.only_backends(['openwrt'])
def test_interface_count(
    file_root_init, uci_configs_init, infrastructure, ubusd_test, network_restart_command,
    device, turris_os_version,
):
    prepare_turrishw("mox")  # plain mox without any boards

    def set_and_test(networks, wifi_devices, count):
        res = infrastructure.process_message({
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {
                    "ssh_on_wan": False,
                    "http_on_wan": False,
                    "https_on_wan": False,
                },
                "networks": networks
            }
        })
        assert res["data"] == {"result": True}
        res = infrastructure.process_message({
            "module": "wifi",
            "action": "update_settings",
            "kind": "request",
            "data": {"devices": wifi_devices}
        })
        assert res["data"] == {"result": True}
        res = infrastructure.process_message({
            "module": "lan",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["data"]["interface_count"] == count

    # No wifi no interfaces
    set_and_test(
        {
            "wan": [],
            "lan": [],
            "guest": [],
            "none": ["eth0"],
        },
        [
            {
                "id": 0,
                "enabled": False,
            },
            {
                "id": 1,
                "enabled": False,
            },
        ],
        0
    )

    # Single interface no wifi
    set_and_test(
        {
            "wan": [],
            "lan": ["eth0"],
            "guest": [],
            "none": [],
        },
        [
            {
                "id": 0,
                "enabled": False,
            },
            {
                "id": 1,
                "enabled": False,
            },
        ],
        1
    )

    # One wifi no interface
    set_and_test(
        {
            "wan": ["eth0"],
            "lan": [],
            "guest": [],
            "none": [],
        },
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
                "guest_wifi": {
                    "enabled": False,
                },
            },
            {
                "id": 1,
                "enabled": False,
            },
        ],
        1
    )
    set_and_test(
        {
            "wan": [],
            "lan": [],
            "guest": ["eth0"],
            "none": [],
        },
        [
            {
                "id": 0,
                "enabled": False,
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
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                },
            },
        ],
        1
    )

    # two wifis no iterface
    set_and_test(
        {
            "wan": [],
            "lan": [],
            "guest": ["eth0"],
            "none": [],
        },
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
                "guest_wifi": {
                    "enabled": False,
                },
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
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                },
            },
        ],
        2
    )

    # interface and wifis enabled
    set_and_test(
        {
            "wan": [],
            "lan": ["eth0"],
            "guest": [],
            "none": [],
        },
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
                "guest_wifi": {
                    "enabled": False,
                },
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
                "guest_wifi": {
                    "enabled": True,
                    "SSID": "Turris-testik",
                    "password": "ssapssap",
                },
            },
        ],
        3
    )
