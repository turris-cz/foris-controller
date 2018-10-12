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

from foris_controller.exceptions import UciRecordNotFound

from foris_controller_testtools.fixtures import (
    only_backends, uci_configs_init, infrastructure, ubusd_test, lock_backend, init_script_result,
    network_restart_command
)
from foris_controller_testtools.utils import (
    match_subdict, network_restart_was_called, get_uci_module, check_service_result
)


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "guest",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {"enabled", "ip", "netmask", "dhcp", "interface_count", "qos"}
    assert set(res["data"]["qos"].keys()) == {"enabled", "upload", "download"}
    assert set(res["data"]["dhcp"].keys()) == {"enabled", "start", "limit", "lease_time"}


def test_update_settings(
    uci_configs_init, infrastructure, ubusd_test, network_restart_command
):
    filters = [("guest", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message({
            "module": "guest",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'guest'
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "guest"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message({
            "module": "guest",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["module"] == "guest"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(data, res["data"])

    update({
        u"enabled": False,
    })
    update({
        u"enabled": True,
        u"ip": u"192.168.5.8",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": False},
        u"qos": {u"enabled": False},
    })
    update({
        u"enabled": True,
        u"ip": u"10.0.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"qos": {u"enabled": False},
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
            u"lease_time": 24 * 60 * 60 + 1,
        },
        u"qos": {u"enabled": False},
    })
    update({
        u"enabled": True,
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"qos": {
            u"enabled": True,
            u"download": 1200,
            u"upload": 1000,
        },
    })


@pytest.mark.only_backends(['openwrt'])
def test_update_settings_openwrt(
    uci_configs_init, lock_backend, init_script_result, infrastructure, ubusd_test,
    network_restart_command,
):
    filters = [("guest", "update_settings")]
    uci = get_uci_module(lock_backend)

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message({
            "module": "guest",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'guest'
        }
        infrastructure.get_notifications(notifications, filters=filters)  # needed just for waiting
        assert network_restart_was_called([])
        if data["enabled"] and data["qos"]["enabled"]:
            check_service_result("sqm", True, "enable")
        else:
            check_service_result("sqm", True, "disable")

    # test guest network
    update({
        u"enabled": True,
        u"ip": u"192.168.8.1",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": False},
        u"qos": {u"enabled": False},
    })
    with uci.UciBackend() as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    assert uci.get_option_named(data, "network", "guest_turris", "type") == "bridge"
    # this depends on default uci wireless config if it changes this line needs to be updated
    assert uci.get_option_named(data, "network", "guest_turris", "proto") == "static"
    assert uci.get_option_named(data, "network", "guest_turris", "ipaddr") == "192.168.8.1"
    assert uci.get_option_named(data, "network", "guest_turris", "netmask") == "255.255.255.0"
    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "bridge_empty"))

    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert uci.get_option_named(data, "dhcp", "guest_turris", "interface") == "guest_turris"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcp_option") == ["6,192.168.8.1"]

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert uci.get_option_named(data, "firewall", "guest_turris", "name") == "guest_turris"
    assert uci.get_option_named(data, "firewall", "guest_turris", "input") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "forward") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "output") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "enabled"))
    assert uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "src") == "guest_turris"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "dest") == "wan"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "enabled"))
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "src") == "guest_turris"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "proto") == "tcpudp"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "dest_port") == "53"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "target") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "enabled"))
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "src") == "guest_turris"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "proto") == "udp"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "src_port") == "67-68"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "dest_port") == "67-68"
    assert uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "target") == "ACCEPT"

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")

    # test + qos
    update({
        u"enabled": True,
        u"ip": u"192.168.9.1",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": False},
        u"qos": {
            u"enabled": True,
            u"download": 1200,
            u"upload": 1000,
        },
    })
    with uci.UciBackend() as backend:
        data = backend.read()
    assert uci.parse_bool(uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled"))
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "interface") \
        == "br-guest_turris"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "qdisc") == "fq_codel"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "script") == "simple.qos"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "link_layer") == "none"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "verbosity") == "5"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "debug_logging") == "1"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "download") == "1000"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "upload") == "1200"

    # test + dhcp
    update({
        u"enabled": True,
        u"ip": u"192.168.11.1",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": True, "start": 25, "limit": 100, "lease_time": 201},
        u"qos": {u"enabled": False},
    })
    with uci.UciBackend() as backend:
        data = backend.read()

    assert not uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert uci.get_option_named(data, "dhcp", "guest_turris", "interface") == "guest_turris"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "start") == "25"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "limit") == "100"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "leasetime") == "201"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcp_option") == ["6,192.168.11.1"]

    # test guest disabled
    update({
        u"enabled": False,
    })
    with uci.UciBackend() as backend:
        data = backend.read()
    assert not uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "enabled"))
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_0", "disabled"))
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_1", "disabled"))

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")


def test_wrong_update(uci_configs_init, infrastructure, ubusd_test, network_restart_command):

    def update(data):
        res = infrastructure.process_message({
            "module": "guest",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert "errors" in res

    update({
        u"enabled": False,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": False,
            u"start": 10,
            u"limit": 50,
        },
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
            u"lease_time": 119,
        },
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"qos": {
            u"enabled": False,
            u"download": 1200,
            u"upload": 1000,
        },
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.3",
        u"netmask": u"255.250.0.0",
        u"dhcp": {u"enabled": False},
        u"qos": {u"enabled": False},
    })
    update({
        u"enabled": True,
        u"ip": u"10.1.0.256",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"qos": {u"enabled": False},
    })


@pytest.mark.parametrize(
    "orig_backend_val,api_val,new_backend_val", [
        ["", 60 * 60, "3600"],
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
    orig_backend_val, api_val, new_backend_val,
):
    uci = get_uci_module(lock_backend)

    with uci.UciBackend() as backend:
        backend.add_section("dhcp", "dhcp", "guest_turris")
        backend.set_option("dhcp", "guest_turris", "leasetime", orig_backend_val)

    res = infrastructure.process_message({
        "module": "guest",
        "action": "get_settings",
        "kind": "request",
    })
    assert res["data"]["dhcp"]["lease_time"] == api_val

    res = infrastructure.process_message({
        "module": "guest",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "enabled": True,
            "ip": "10.1.0.3",
            "netmask": "255.252.0.0",
            "dhcp": {
                "enabled": True,
                "start": 10,
                "limit": 50,
                "lease_time": api_val,
            },
            "qos": {"enabled": False},
        }
    })
    assert res["data"]["result"]

    with uci.UciBackend() as backend:
        data = backend.read()

    assert uci.get_option_named(data, "dhcp", "guest_turris", "leasetime") == new_backend_val
