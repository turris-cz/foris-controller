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
    infrastructure, uci_configs_init, ubusd_test, init_script_result,
    only_backends, device, turris_os_version, FILE_ROOT_PATH, lock_backend
)
from foris_controller_testtools.utils import check_service_result, FileFaker, get_uci_module


@pytest.fixture(scope="function")
def custom_forwarders():
    res2 = """\
name="quad9-dns-normal"
description="Quad DNS resolver without filtering."
enable_tls="1"
port="853"
ipv4="9.9.9.10"
ipv6="2620:fe::10"
hostname="dns.quad9.net"
#pin_sha256="G+ullr8exb9aHemu3vmI9Jwquuqe0DwnBdFHss8UfVw="
ca_file="/etc/ssl/certs/ca-certificates.crt"
"""

    res1 = """\
name="ODVR NIC.CZ"
description="DNS resolver cznic"
ipv4="217.31.204.130"
ipv6="2001:1488:800:400::130"
"""
    with \
            FileFaker(FILE_ROOT_PATH, "/etc/resolver/dns_servers/odvr-nic-dns.conf", False, res1) as res1, \
            FileFaker(FILE_ROOT_PATH, "/etc/resolver/dns_servers/quad9-normal.conf", False, res2) as res2:
        yield res1, res2


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "dns",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "forwarding_enabled" in res["data"].keys()
    assert "available_forwarders" in res["data"].keys()
    assert "forwarder" in res["data"].keys()
    assert "dnssec_enabled" in res["data"].keys()
    assert "dns_from_dhcp_enabled" in res["data"].keys()


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
def test_update_settings(
    uci_configs_init, infrastructure, ubusd_test, device, turris_os_version,
    init_script_result
):
    filters = [("dns", "update_settings")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": False,
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    assert res == {
        u'action': u'update_settings',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'dns'
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"dns",
        u"action": u"update_settings",
        u"kind": u"notification",
        u"data": {
            u"forwarding_enabled": False,
            u"dnssec_enabled": False,
            u"dns_from_dhcp_enabled": False,
        }
    }
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": False,
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
            "dns_from_dhcp_domain": "test",
        }
    })
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"dns",
        u"action": u"update_settings",
        u"kind": u"notification",
        u"data": {
            u"forwarding_enabled": False,
            u"dnssec_enabled": False,
            u"dns_from_dhcp_enabled": False,
            u"dns_from_dhcp_domain": "test",
        }
    }
    assert res == {
        u'action': u'update_settings',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'dns'
    }


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
def test_update_and_get_settings(
    uci_configs_init, infrastructure, ubusd_test, device, turris_os_version,
    init_script_result,
):
    filters = [("dns", "update_settings")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": False,
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    assert res == {
        u'action': u'update_settings',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'dns'
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"dns",
        u"action": u"update_settings",
        u"kind": u"notification",
        u"data": {
            u"forwarding_enabled": False,
            u"dnssec_enabled": False,
            u"dns_from_dhcp_enabled": False,
        }
    }
    res = infrastructure.process_message({
        "module": "dns",
        "action": "get_settings",
        "kind": "request",
    })
    assert res['data']["forwarding_enabled"] is False
    assert res['data']["dnssec_enabled"] is False
    assert res['data']["dns_from_dhcp_enabled"] is False
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": True,
            "forwarder": "",
            "dnssec_enabled": True,
            "dns_from_dhcp_enabled": True,
            "dns_from_dhcp_domain": "test",
        }
    })
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"dns",
        u"action": u"update_settings",
        u"kind": u"notification",
        u"data": {
            u"forwarding_enabled": True,
            u"forwarder": "",
            u"dnssec_enabled": True,
            u"dns_from_dhcp_enabled": True,
            u"dns_from_dhcp_domain": u"test",
        }
    }
    assert res == {
        u'action': u'update_settings',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'dns'
    }
    res = infrastructure.process_message({
        "module": "dns",
        "action": "get_settings",
        "kind": "request",
    })
    assert res['data']["forwarding_enabled"] is True
    assert res['data']["forwarder"] == ""
    assert res['data']["dnssec_enabled"] is True
    assert res['data']["dns_from_dhcp_enabled"] is True
    assert res['data']["dns_from_dhcp_domain"] == "test"


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.only_backends(['openwrt'])
def test_update_settings_service_restart(
    uci_configs_init, init_script_result, infrastructure, ubusd_test, device, turris_os_version,
):

    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": False,
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    check_service_result("resolver", "restart", True)


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
    ],
    indirect=True
)
@pytest.mark.only_backends(['openwrt'])
def test_update_settings_forwarder(
    lock_backend, custom_forwarders, uci_configs_init, init_script_result, infrastructure,
    ubusd_test, device, turris_os_version,
):
    uci = get_uci_module(lock_backend)

    # Get forwarder list
    res = infrastructure.process_message({
        "module": "dns",
        "action": "get_settings",
        "kind": "request",
    })
    assert sorted(res["data"]["available_forwarders"], key=lambda x: x["name"]) == sorted([
        {"name": "", "description": ""},
        {"name": "odvr-nic-dns", "description": "DNS resolver cznic"},
        {"name": "quad9-normal", "description": "Quad DNS resolver without filtering."},
        ], key=lambda x: x["name"])

    # Update non-existing
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": True,
            "forwarder": "non-existing",
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    assert res["data"]["result"] is False

    # Update to providers dns
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": True,
            "forwarder": "",
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    assert res["data"]["result"] is True

    with uci.UciBackend() as backend:
        data = backend.read()
    assert uci.get_option_named(data, "resolver", "common", "forward_custom", "") is ""

    # Update to some
    res = infrastructure.process_message({
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": True,
            "forwarder": "odvr-nic-dns",
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    })
    assert res["data"]["result"] is True

    with uci.UciBackend() as backend:
        data = backend.read()
    assert uci.get_option_named(data, "resolver", "common", "forward_custom") == "odvr-nic-dns"
