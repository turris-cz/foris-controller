#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import typing

import pytest
from foris_controller_testtools.fixtures import (
    infrastructure,
    uci_configs_init,
    file_root_init,
    ubusd_test,
    init_script_result,
    mosquitto_test,
    only_backends,
    device,
    turris_os_version,
    FILE_ROOT_PATH,
    UCI_CONFIG_DIR_PATH,
)
from foris_controller_testtools.utils import check_service_result, FileFaker, get_uci_module


def list_forwarders(infrastructure) -> typing.List[dict]:
    return infrastructure.process_message(
        {"module": "dns", "action": "list_forwarders", "kind": "request"}
    )["data"]["forwarders"]


def add_forwarder(infrastructure, data: dict, result: bool):
    action = "add_forwarder"
    filters = [("dns", action)]
    notifications = infrastructure.get_notifications(filters=filters)
    _edit_forwarder_wrapper(action)(infrastructure, data, result)
    if result:
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["data"]["name"]
        del notifications[-1]["data"]["name"]
        assert notifications[-1] == {
            "module": "dns",
            "action": action,
            "kind": "notification",
            "data": data,
        }


def set_forwarder(infrastructure, data: dict, result: bool):
    action = "set_forwarder"
    filters = [("dns", action)]
    notifications = infrastructure.get_notifications(filters=filters)
    _edit_forwarder_wrapper(action)(infrastructure, data, result)
    if result:
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1] == {
            "module": "dns",
            "action": action,
            "kind": "notification",
            "data": data,
        }


def _edit_forwarder_wrapper(action: str):
    def _edit_forwarder_action(infrastructure, data: dict, result: bool):
        res = infrastructure.process_message(
            {"module": "dns", "action": action, "kind": "request", "data": data}
        )
        assert res["data"]["result"] is result
    return _edit_forwarder_action


@pytest.fixture(scope="function")
def custom_forwarders():
    res1 = """\
name="99_google.conf"
description="Google"
ipv4="8.8.8.8"
ipv6="2001:4860:4860::8888"
"""

    res2 = """\
name="99_quad9.conf"
description="Quad9 (TLS)"
enable_tls="1"
port="853"
ipv4="9.9.9.10"
ipv6="2620:fe::10"
hostname="dns.quad9.net"
#pin_sha256="yioEpqeR4WtDwE9YxNVnCEkTxIjx6EEIwFSQW+lJsbc="
ca_file="/etc/ssl/certs/ca-certificates.crt"
"""

    res3 = """\
name="99_cloudflare.conf"
description="Cloudflare (TLS)"
enable_tls="1"
port="853"
#tls_port="453"
ipv4="1.1.1.1"
ipv6="2606:4700:4700::1111"
#hostname="dns.quad9.net"
pin_sha256="yioEpqeR4WtDwE9YxNVnCEkTxIjx6EEIwFSQW+lJsbc="
"""

    with FileFaker(
        FILE_ROOT_PATH, "/etc/resolver/dns_servers/99_google.conf", False, res1
    ) as res1, FileFaker(
        FILE_ROOT_PATH, "/etc/resolver/dns_servers/99_quad9.conf", False, res2
    ) as res2, FileFaker(
        FILE_ROOT_PATH, "/etc/resolver/dns_servers/99_cloudflare.conf", False, res3
    ) as res3:
        yield res1, res2, res3


def test_get_settings(file_root_init, uci_configs_init, infrastructure, ubusd_test, mosquitto_test):
    res = infrastructure.process_message(
        {"module": "dns", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "forwarding_enabled" in res["data"].keys()
    assert "available_forwarders" in res["data"].keys()
    assert "forwarder" in res["data"].keys()
    assert "dnssec_enabled" in res["data"].keys()
    assert "dns_from_dhcp_enabled" in res["data"].keys()


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings(
    file_root_init,
    uci_configs_init,
    infrastructure,
    ubusd_test,
    device,
    turris_os_version,
    init_script_result,
):
    filters = [("dns", "update_settings")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"dns",
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
        },
    }
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
                "dns_from_dhcp_domain": "test",
            },
        }
    )
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
        },
    }
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"dns",
    }


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_and_get_settings(
    file_root_init,
    uci_configs_init,
    infrastructure,
    ubusd_test,
    device,
    turris_os_version,
    init_script_result,
):
    filters = [("dns", "update_settings")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"dns",
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
        },
    }
    res = infrastructure.process_message(
        {"module": "dns", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["forwarding_enabled"] is False
    assert res["data"]["dnssec_enabled"] is False
    assert res["data"]["dns_from_dhcp_enabled"] is False
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": True,
                "forwarder": "",
                "dnssec_enabled": True,
                "dns_from_dhcp_enabled": True,
                "dns_from_dhcp_domain": "test",
            },
        }
    )
    assert res == {
        u"action": u"update_settings",
        u"data": {u"result": True},
        u"kind": u"reply",
        u"module": u"dns",
    }
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
        },
    }
    res = infrastructure.process_message(
        {"module": "dns", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["forwarding_enabled"] is True
    assert res["data"]["forwarder"] == ""
    assert res["data"]["dnssec_enabled"] is True
    assert res["data"]["dns_from_dhcp_enabled"] is True
    assert res["data"]["dns_from_dhcp_domain"] == "test"


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_service_restart(
    file_root_init,
    uci_configs_init,
    init_script_result,
    infrastructure,
    ubusd_test,
    device,
    turris_os_version,
):
    infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    check_service_result("resolver", "restart", True)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_forwarder(
    file_root_init,
    custom_forwarders,
    uci_configs_init,
    init_script_result,
    infrastructure,
    ubusd_test,
    device,
    turris_os_version,
):
    uci = get_uci_module(infrastructure.name)

    # Get forwarder list
    res = infrastructure.process_message(
        {"module": "dns", "action": "get_settings", "kind": "request"}
    )
    assert sorted(res["data"]["available_forwarders"], key=lambda x: x["name"]) == sorted(
        [
            {"name": "", "description": "", "editable": False},
            {"name": "99_google", "description": "Google", "editable": False},
            {"name": "99_cloudflare", "description": "Cloudflare (TLS)", "editable": False},
            {"name": "99_quad9", "description": "Quad9 (TLS)", "editable": False},
        ],
        key=lambda x: x["name"],
    )

    # Update non-existing
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": True,
                "forwarder": "non-existing",
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    assert res["data"]["result"] is False

    # Update to providers dns
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": True,
                "forwarder": "",
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    assert res["data"]["result"] is True

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert uci.get_option_named(data, "resolver", "common", "forward_custom", "") is ""

    # Update to some
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": True,
                "forwarder": "99_google",
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
    )
    assert res["data"]["result"] is True

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert uci.get_option_named(data, "resolver", "common", "forward_custom") == "99_google"


def test_list_forwarders(
    file_root_init, custom_forwarders, uci_configs_init, infrastructure, ubusd_test, mosquitto_test
):
    res = infrastructure.process_message(
        {"module": "dns", "action": "list_forwarders", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "forwarders" in res["data"].keys()
    assert len(res["data"]["forwarders"]) == 3


@pytest.mark.only_backends(["openwrt"])
def test_set_forwarder(
    custom_forwarders, uci_configs_init, infrastructure, ubusd_test, mosquitto_test
):
    # new
    data = {
        "ipaddresses": {"ipv4": "2.2.2.2", "ipv6": "2001:4860:4860::2222"},
        "description": "Myforward",
        "tls_type": "no",
    }
    add_forwarder(infrastructure, data, True)
    data["name"] = "myforward_6842e9378ffb5c6be0b97309a48f6bc4"
    data["editable"] = True
    data["tls_pin"] = ""
    data["tls_hostname"] = ""
    assert data in list_forwarders(infrastructure)

    # update
    data = {
        "name": "myforward_6842e9378ffb5c6be0b97309a48f6bc4",
        "ipaddresses": {"ipv4": "2.2.2.2", "ipv6": "2001:4860:4860::2222"},
        "description": "Myforward (TLS)",
        "tls_type": "pin",
        "tls_pin": "12345566777",
    }
    set_forwarder(infrastructure, data, True)
    data["editable"] = True
    data["tls_hostname"] = ""
    assert data in list_forwarders(infrastructure)

    # non-editable
    data = {
        "name": "99_google",
        "ipaddresses": {"ipv4": "3.3.3.3", "ipv6": "2001:4860:4860::2222"},
        "description": "MyGoogle",
        "tls_type": "no",
    }
    set_forwarder(infrastructure, data, False)
    data["editable"] = False
    data["editable"] = ""
    data["tls_hostname"] = ""
    assert data not in list_forwarders(infrastructure)


@pytest.mark.only_backends(["openwrt"])
def test_del_forwarder(
    file_root_init, custom_forwarders, uci_configs_init, infrastructure, ubusd_test, mosquitto_test
):
    filters = [("dns", "del_forwarder")]
    notifications = infrastructure.get_notifications(filters=filters)

    # editable
    data = {
        "ipaddresses": {"ipv4": "2.2.2.2", "ipv6": "2001:4860:4860::2222"},
        "description": "Myforward",
        "tls_type": "no",
    }
    add_forwarder(infrastructure, data, True)
    data["name"] = "myforward_6842e9378ffb5c6be0b97309a48f6bc4"
    data["editable"] = True
    data["tls_pin"] = ""
    data["tls_hostname"] = ""
    assert data in list_forwarders(infrastructure)

    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "del_forwarder",
            "kind": "request",
            "data": {"name": "myforward_6842e9378ffb5c6be0b97309a48f6bc4"},
        }
    )
    assert res["data"]["result"] is True

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "dns",
        "action": "del_forwarder",
        "kind": "notification",
        "data": {"name": "myforward_6842e9378ffb5c6be0b97309a48f6bc4"},
    }
    assert "myforward_6842e9378ffb5c6be0b97309a48f6bc4" not in [e["name"] for e in list_forwarders(infrastructure)]

    # non-existing
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "del_forwarder",
            "kind": "request",
            "data": {"name": "83_nonexisting"},
        }
    )
    assert res["data"]["result"] is False

    # non-editable
    res = infrastructure.process_message(
        {
            "module": "dns",
            "action": "del_forwarder",
            "kind": "request",
            "data": {"name": "99_google"},
        }
    )
    assert res["data"]["result"] is False
    assert "99_google" in [e["name"] for e in list_forwarders(infrastructure)]
