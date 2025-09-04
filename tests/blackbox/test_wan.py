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
from foris_controller_testtools.fixtures import UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import (
    get_uci_module,
    match_subdict,
    network_restart_was_called,
    prepare_turrishw_root,
    FileFaker,
)

from .helpers.common import get_uci_backend_data, query_infrastructure

CONNTEST_MAPPING = {
    'success' : '{"dns":"OK"}',
    'failed' : '{"ipv4":"FAILED"}',
    'unknown' : '{"ipv6":"UNKNOWN"}'
}

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_wan_files')
TMP_CONN_RESULTS = '/tmp/foris_conn_test'


@pytest.fixture(scope="function")
def check_connection_mock(request):
    with FileFaker(
        TMP_CONN_RESULTS, "results.json", True, CONNTEST_MAPPING.get(request.param)
    ) as check_connection:
        yield check_connection


@pytest.mark.parametrize("device,turris_os_version", [("mox", "6.0"),("omnia", "6.0")], indirect=True)
def test_get_settings(uci_configs_init, infrastructure, fix_mox_wan, device, turris_os_version):

    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {
        "wan_settings",
        "wan6_settings",
        "mac_settings",
        "interface_count",
        "interface_up_count",
        "qos",
        "vlan_settings",
    }
    assert "mac_address" in res["data"]["mac_settings"].keys()


@pytest.mark.parametrize("device,turris_os_version", [("omnia","6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_interface_openwrt(uci_configs_init, infrastructure, device, turris_os_version):
    """Test that we can get wan interface settings from just the interface.

    For example:

    config interface 'wan'
        option device 'eth2'
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)
    uci_data = get_uci_backend_data(uci)

    assert not uci.section_exists(uci_data, "network", "dev_wan")

    query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )


@pytest.mark.parametrize("device,turris_os_version", [("omnia","6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_device_openwrt(uci_configs_init, infrastructure, device, turris_os_version):
    """Test that we can get wan interface options from device section.

    For example:

    config interface 'wan'
        option device 'eth2'

    config device 'dev_wan'
        option name 'eth2'
        option macaddr 'AA:BB:CC:11:22:33'
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)
    uci_data = get_uci_backend_data(uci)

    assert uci.get_option_named(uci_data, "network", "wan", "macaddr", "") == ""

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.add_section("network", "device", "dev_wan")
        backend.set_option("network", "dev_wan", "name", "eth2")
        backend.set_option("network", "dev_wan", "macaddr", "AA:BB:CC:11:22:33")

    query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )


@pytest.mark.parametrize("device,turris_os_version", [("omnia","6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_macaddr_from_interface_openwrt(uci_configs_init, infrastructure, device, turris_os_version):
    """Test that we can still get MAC address even from legacy config.

    config interface 'wan'
        option macaddr 'AA:BB:CC:11:22:33'
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "wan", "macaddr", "AA:BB:CC:11:22:33")

    uci_data = get_uci_backend_data(uci)
    assert not uci.section_exists(uci_data, "network", "dev_wan")

    res = query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert res["data"]["mac_settings"]["custom_mac"] == "AA:BB:CC:11:22:33"


@pytest.mark.parametrize("device,turris_os_version", [("omnia","6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_macaddr_from_device_openwrt(uci_configs_init, infrastructure, device, turris_os_version):
    """Test that we will get MAC address from device instead of interface.

    Prefer the `device` section and ignore macaddr from `interface`.

    config interface 'wan'
        option macaddr 'AA:BB:CC:DD:EE:FF'

    config device 'dev_wan'
        option macaddr '11:22:33:44:55:66'
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "wan", "macaddr", "AA:BB:CC:11:22:33")

        backend.add_section("network", "device", "dev_wan")
        backend.set_option("network", "dev_wan", "macaddr", "11:22:33:44:55:66")

    res = query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert res["data"]["mac_settings"]["custom_mac"] == '11:22:33:44:55:66'


@pytest.mark.parametrize("device,turris_os_version", [("omnia","6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_wan_settings_pppoe_credentials_missing_openwrt(
    uci_configs_init, infrastructure, device, turris_os_version
):
    """Test that we can get at least some fallback values for PPPoE credentials, in case that uci options are missings.

    For example:

    config interface 'wan'
        option device 'eth2'
        option proto 'pppoe'
        option username 'myuser'
        # <-- mandatory `option password` is missing...

    will give fallback to "" on missing option `password`

    wan_pppoe: {username: "myuser", password: ""}
    """
    def check_get(expected_username: str, expected_password: str):
        res = query_infrastructure(
            infrastructure,
            {"module": "wan", "action": "get_settings", "kind": "request"}
        )

        assert res["data"]["wan_settings"]["wan_type"] == "pppoe"
        assert res["data"]["wan_settings"]["wan_pppoe"]["username"] == expected_username
        assert res["data"]["wan_settings"]["wan_pppoe"]["password"] == expected_password

    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    # password is missing
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "wan", "proto", "pppoe")
        backend.set_option("network", "wan", "username", "myuser")

    check_get("myuser", "")

    # username is missing
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "wan", "username")
        backend.set_option("network", "wan", "password", "mypassword")

    check_get("", "mypassword")

    # both username and password are missing
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "wan", "password", fail_on_error=False)

    check_get("", "")


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_set_custom_macaddr_openwrt(
    uci_configs_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
):
    """Test that new `device` section for 'dev_wan' is created if needed.

    Test scenario in which there is just `interface 'wan'` without any L2 options,
    like fresh network config from medkit.

    Before update:
    ```
    config interface 'wan'
        option device 'eth2'
    ```

    After update:
    ```
    config interface 'wan'
        option device 'eth2'

    config device 'dev_wan'
        option name 'eth2'
        option macaddr '11:22:33:44:55:66'
    ```
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)
    uci_data = get_uci_backend_data(uci)

    assert uci.get_option_named(uci_data, "network", "wan", "device", "") == "eth2"
    assert uci.get_option_named(uci_data, "network", "wan", "macaddr", "") == ""
    assert not uci.section_exists(uci_data, "network", "dev_wan")

    msg_data = {
        "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
        "wan6_settings": {"wan6_type": "none"},
        "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
    }

    query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "update_settings", "kind": "request", "data": msg_data}
    )

    uci_data = get_uci_backend_data(uci)

    assert uci.get_option_named(uci_data, "network", "wan", "device", "") == "eth2"
    assert uci.get_option_named(uci_data, "network", "wan", "macaddr", "") == ""

    assert uci.section_exists(uci_data, "network", "dev_wan")
    assert uci.get_option_named(uci_data, "network", "dev_wan", "name", "") == "eth2"
    assert uci.get_option_named(uci_data, "network", "dev_wan", "macaddr", "") == "11:22:33:44:55:66"


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_delete_l2_options_openwrt(
    uci_configs_init,
    infrastructure,
    network_restart_command,
    device,
    turris_os_version,
):
    """Check that removing last L2 option from `wan` device will clear that device.

    And we are still able to get overall wan settings from `interface`.

    Before update:
    ```
    config interface 'wan'
        option device 'eth2'

    config device 'dev_wan'
        option name 'eth2'
        option macaddr '11:22:33:AA:BB:CC'
    ```

    After update:
    ```
    config interface 'wan'
        option device 'eth2'

    config device 'dev_wan'
        option name 'eth2'
    """
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)
    uci_data = get_uci_backend_data(uci)

    assert uci.get_option_named(uci_data, "network", "wan", "macaddr", "") == ""

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.add_section("network", "device", "dev_wan")
        backend.set_option("network", "dev_wan", "name", "eth2")
        backend.set_option("network", "dev_wan", "macaddr", "11:22:33:AA:BB:CC")

    msg_data = {
        "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
        "wan6_settings": {"wan6_type": "none"},
        "mac_settings": {"custom_mac_enabled": False},
    }
    query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "update_settings", "kind": "request", "data": msg_data}
    )

    uci_data = get_uci_backend_data(uci)

    assert uci.get_option_named(uci_data, "network", "dev_wan", "name", "") == "eth2"
    assert uci.get_option_named(uci_data, "network", "dev_wan", "macaddr", "") == ""
    # check that setting doesn't by any chance moved to wan `interface`
    assert uci.get_option_named(uci_data, "network", "wan", "macaddr", "") == ""

    query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )


@pytest.mark.parametrize("device,turris_os_version", [("omnia","4.0"),("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_ipv6prefix_as_an_option(uci_configs_init, infrastructure, fix_mox_wan, device, turris_os_version):
    """ Fallback test since ipv6prefix option is newly set as list, but uci still may contain plain option. """

    prepare_turrishw_root(device, turris_os_version)

    data = {
        "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
        "wan6_settings": {
            "wan6_type": "6in4",
            "wan6_6in4": {
                "mtu": 1480,
                "server_ipv4": "111.22.33.44",
                "ipv6_prefix": "2001:470:6e:39::/64",
                "dynamic_ipv4": {"enabled": False},
            },
        },
        "mac_settings": {"custom_mac_enabled": False},
    }
    infrastructure.process_message(
        {"module": "wan", "action": "update_settings", "kind": "request", "data": data}
    )
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "wan6", "ip6prefix", fail_on_error=False)
        # save as an option
        backend.set_option("network", "wan6", "ip6prefix", "2001:470:6e:39::/64")
    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_wan_status(uci_configs_init, infrastructure):
    res = infrastructure.process_message(
        {"module": "wan", "action": "get_wan_status", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "up" in res["data"].keys()
    assert "last_seen_duid" in res["data"].keys()
    assert "proto" in res["data"].keys()


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings(
    infrastructure, network_restart_command, device, fix_mox_wan, turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    filters = [("wan", "update_settings")]

    def update(input_data, output_data, notification_data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "wan", "action": "update_settings", "kind": "request", "data": input_data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wan",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "wan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert notification_data == notifications[-1]["data"]

        res = infrastructure.process_message(
            {"module": "wan", "action": "get_settings", "kind": "request"}
        )
        assert res["module"] == "wan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(output_data, res["data"])
        mac_settings = res["data"]["mac_settings"]
        assert "mac_address" in mac_settings.keys()
        if mac_settings["custom_mac_enabled"]:
            assert "custom_mac" in mac_settings.keys()

    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {
            "wan_type": "dhcp", "wan6_type": "none", "custom_mac_enabled": False
        },
    )
    # WAN
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {"hostname": "my-nice-turris4"}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {"hostname": "my-nice-turris4"}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "dhcp", "wan6_type": "none", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {
                "wan_type": "pppoe",
                "wan_pppoe": {"username": "my_user", "password": "pass1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {
                "wan_type": "pppoe",
                "wan_pppoe": {"username": "my_user", "password": "pass1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "pppoe", "wan6_type": "none", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {"ip": "10.0.0.10", "netmask": "255.255.0.0", "gateway": "10.0.0.1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {"ip": "10.0.0.10", "netmask": "255.255.0.0", "gateway": "10.0.0.1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "static", "wan6_type": "none", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {
                    "ip": "10.0.0.10",
                    "netmask": "255.255.0.0",
                    "gateway": "10.0.0.1",
                    "dns1": "10.0.0.1",
                    "dns2": "8.8.8.8",
                },
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {
                    "ip": "10.0.0.10",
                    "netmask": "255.255.0.0",
                    "gateway": "10.0.0.1",
                    "dns1": "10.0.0.1",
                    "dns2": "8.8.8.8",
                },
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "static", "wan6_type": "none", "custom_mac_enabled": False},
    )
    # WAN6
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "dhcpv6", "wan6_dhcpv6": {"duid": ""}},
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "dhcpv6", "wan6_dhcpv6": {"duid": ""}},
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "dhcp", "wan6_type": "dhcpv6", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "dhcpv6",
                "wan6_dhcpv6": {"duid": "00030001d858d7004555"},
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "dhcpv6",
                "wan6_dhcpv6": {"duid": "00030001d858d7004555"},
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": 'de:ad:be:ef:99:99'},
        },
        {"wan_type": "dhcp", "wan6_type": "dhcpv6", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                },
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": 'de:ad:be:ef:99:99'},
        },
        {"wan_type": "dhcp", "wan6_type": "static", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {
            "wan_type": "dhcp", "wan6_type": "static", "custom_mac_enabled": False
        },
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "111.22.33.44",
                    "ipv6_prefix": "2001:470:6e:39::/64",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "111.22.33.44",
                    "ipv6_prefix": "2001:470:6e:39::/64",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "dhcp", "wan6_type": "6in4", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "222.33.44.55",
                    "ipv6_prefix": "2002:471:6e:3a::/64",
                    "ipv6_address": "2002:471:6e:3a::1/64",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "222.33.44.55",
                    "ipv6_prefix": "2002:471:6e:3a::/64",
                    "ipv6_address": "2002:471:6e:3a::1/64",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "dhcp", "wan6_type": "6in4", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1280,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "2001:470:6f:39::/64",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1280,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "2001:470:6f:39::/64",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False, "mac_address": "de:ad:be:ef:99:99"},
        },
        {"wan_type": "dhcp", "wan6_type": "6in4", "custom_mac_enabled": False},
    )


@pytest.mark.only_backends(['mock'])
@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_change_mac(
    infrastructure, network_restart_command, device, fix_mox_wan, turris_os_version,
):
    filters = [("wan", "update_settings")]

    def update(input_data, output_data, notification_data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {"module": "wan", "action": "update_settings", "kind": "request", "data": input_data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wan",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "wan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert notification_data == notifications[-1]["data"]

        res = infrastructure.process_message(
            {"module": "wan", "action": "get_settings", "kind": "request"}
        )
        assert res["module"] == "wan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(output_data, res["data"])
        mac_settings = res["data"]["mac_settings"]
        assert "mac_address" in mac_settings.keys()
        if mac_settings["custom_mac_enabled"]:
            assert "custom_mac" in mac_settings.keys()
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1280,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1280,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        },
        {"wan_type": "dhcp", "wan6_type": "6in4", "custom_mac_enabled": False},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {
                "custom_mac_enabled": True,
                "custom_mac": "11:22:33:44:55:66",
                "mac_address": "11:22:33:44:55:66",
            },
        },
        {"wan_type": "dhcp", "wan6_type": "none", "custom_mac_enabled": True},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": ""}},
            "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": ""}},
            "mac_settings": {
                "custom_mac_enabled": True,
                "custom_mac": "11:22:33:44:55:66",
                "mac_address": "11:22:33:44:55:66",
            },
        },
        {"wan_type": "dhcp", "wan6_type": "6to4", "custom_mac_enabled": True},
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": "1.2.3.4"}},
            "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
        },
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": "1.2.3.4"}},
            "mac_settings": {
                "custom_mac_enabled": True,
                "custom_mac": "11:22:33:44:55:66",
                "mac_address": "11:22:33:44:55:66",
            },
        },
        {"wan_type": "dhcp", "wan6_type": "6to4", "custom_mac_enabled": True},
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_wan_openwrt_backend(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):

    uci = get_uci_module(infrastructure.name)

    def _filter_possible_list(data, *args):
        option = uci.get_option_named(data, *args)

        if isinstance(option, list):
            option = option[0]

        return option

    def update(data):
        res = infrastructure.process_message(
            {"module": "wan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wan",
        }
        assert network_restart_was_called([])
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            data = backend.read()
        return data

    # WAN
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {"hostname": "my-nice-turris"}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == "my-nice-turris"
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    data = update(
        {
            "wan_settings": {
                "wan_type": "pppoe",
                "wan_pppoe": {"username": "my_user", "password": "pass1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "pppoe"
    assert uci.get_option_named(data, "network", "wan", "username") == "my_user"
    assert uci.get_option_named(data, "network", "wan", "password") == "pass1"
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    data = update(
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {"ip": "10.0.0.10", "netmask": "255.255.0.0", "gateway": "10.0.0.1"},
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "static"
    assert uci.get_option_named(data, "network", "wan", "ipaddr") == "10.0.0.10"
    assert uci.get_option_named(data, "network", "wan", "netmask") == "255.255.0.0"
    assert uci.get_option_named(data, "network", "wan", "gateway") == "10.0.0.1"
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    data = update(
        {
            "wan_settings": {
                "wan_type": "static",
                "wan_static": {
                    "ip": "10.0.0.10",
                    "netmask": "255.255.0.0",
                    "gateway": "10.0.0.1",
                    "dns1": "10.0.0.1",
                    "dns2": "8.8.8.8",
                },
            },
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "static"
    assert uci.get_option_named(data, "network", "wan", "ipaddr") == "10.0.0.10"
    assert uci.get_option_named(data, "network", "wan", "netmask") == "255.255.0.0"
    assert uci.get_option_named(data, "network", "wan", "gateway") == "10.0.0.1"
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.get_option_named(data, "network", "wan", "dns", []) == ["8.8.8.8", "10.0.0.1"]
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    # WAN6
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "dhcpv6",
                "wan6_dhcpv6": {"duid": "00030001d858d7004566"},
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "dhcpv6"
    assert uci.get_option_named(data, "network", "wan6", "clientid") == "00030001d858d7004566"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "static"
    assert (
        uci.get_option_named(data, "network", "wan6", "ip6addr")
        == "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64"
    )
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix") == "2001:1488:fffe:6::/60"
    assert uci.get_option_named(data, "network", "wan6", "ip6gw") == "2001:1488:fffe:6::1"
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "static"
    assert (
        uci.get_option_named(data, "network", "wan6", "ip6addr")
        == "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64"
    )
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix") == "2001:1488:fffe:6::/60"
    assert uci.get_option_named(data, "network", "wan6", "ip6gw") == "2001:1488:fffe:6::1"
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "dns", []) == [
        "2001:4860:4860::8888",
        "2001:1488:fffe:6::1",
    ]
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.section_exists(data, "network", "dev_wan")
    assert uci.get_option_named(data, "network", "dev_wan", "macaddr", "") == "11:22:33:44:55:66"
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "lan", "ip6assign")
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": ""}},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "6to4"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ipaddr", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.get_option_named(data, "network", "lan", "ip6assign", "") == "60"
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "enabled", "0")
        )
        is True
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "proto", "") == "ipv6"
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "src", "") == "wan"
    assert (
        uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "src_ip", "")
        == "192.88.99.1"
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "target", "") == "ACCEPT"

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "lan", "ip6assign")
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": "1.5.7.9"}},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "6to4"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ipaddr", "") == "1.5.7.9"
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert uci.get_option_named(data, "network", "lan", "ip6assign", "") == "60"
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "enabled", "0")
        )
        is True
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "proto", "") == "ipv6"
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "src", "") == "wan"
    assert (
        uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "src_ip", "")
        == "192.88.99.1"
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "target", "") == "ACCEPT"

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "lan", "ip6assign")
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1470,
                    "server_ipv4": "1.22.33.44",
                    "ipv6_prefix": "2001:470:6a:39::/64",
                    "ipv6_address": "2001:470:6e:39::1",
                    "dynamic_ipv4": {"enabled": False},
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "6in4"
    assert _filter_possible_list(data, "network", "wan6", "ip6addr", "") == "2001:470:6e:39::1"
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == "2001:470:6a:39::/64"
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "peeraddr", "") == "1.22.33.44"
    assert uci.get_option_named(data, "network", "wan6", "mtu", "") == "1470"
    assert uci.get_option_named(data, "network", "wan6", "tunnelid", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "username", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "password", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "enabled", "0")
        )
        is True
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "family", "") == "ipv4"
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "src", "") == "wan"
    assert (
        uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "src_ip", "") == "1.22.33.44"
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "proto", "") == "41"
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "target", "") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1290,
                    "server_ipv4": "1.222.33.44",
                    "ipv6_prefix": "2001:470:6c:39::/64",
                    "ipv6_address": "2001:470:6c:39::2",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "123456",
                        "username": "user11",
                        "password_or_key": "passphrase11",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )

    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "6in4"
    assert _filter_possible_list(data, "network", "wan6", "ip6addr", "") == "2001:470:6c:39::2"
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == "2001:470:6c:39::/64"
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "peeraddr", "") == "1.222.33.44"
    assert uci.get_option_named(data, "network", "wan6", "mtu", "") == "1290"
    assert uci.get_option_named(data, "network", "wan6", "tunnelid", "") == "123456"
    assert uci.get_option_named(data, "network", "wan6", "username", "") == "user11"
    assert uci.get_option_named(data, "network", "wan6", "password", "") == "passphrase11"
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "enabled", "")
        )
        is True
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "family", "") == "ipv4"
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "src", "") == "wan"
    assert (
        uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "src_ip", "")
        == "1.222.33.44"
    )
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "proto", "") == "41"
    assert uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "target", "") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is True
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "0")) is True

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    assert uci.get_option_named(data, "network", "wan", "proto") == "dhcp"
    assert uci.get_option_named(data, "network", "wan", "hostname", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "proto") == "none"
    assert uci.get_option_named(data, "network", "wan6", "ip6addr", "") == ""
    assert _filter_possible_list(data, "network", "wan6", "ip6prefix", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "ip6gw", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "peeraddr", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "mtu", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "tunnelid", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "username", "") == ""
    assert uci.get_option_named(data, "network", "wan6", "password", "") == ""
    assert uci.get_option_named(data, "network", "wan", "macaddr", "") == ""
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6in4_rule", "enabled", "0")
        )
        is False
    )
    assert (
        uci.parse_bool(
            uci.get_option_named(data, "firewall", "turris_wan_6to4_rule", "enabled", "0")
        )
        is False
    )
    assert uci.parse_bool(uci.get_option_named(data, "network", "wan", "ipv6", "0")) is False
    assert uci.parse_bool(uci.get_option_named(data, "resolver", "common", "net_ipv6", "1")) is False


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_wrong_update(
    uci_configs_init, infrastructure, network_restart_command, device, turris_os_version,
):
    def update(data):
        res = infrastructure.process_message(
            {"module": "wan", "action": "update_settings", "kind": "request", "data": data}
        )
        assert "errors" in res

    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::",
                    "gateway": "2001:1488:fffe:6::1/128",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1/128",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": None,
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": None,
                    "gateway": "2001:1488:fffe:6::1/128",
                    "dns1": "2001:1488:fffe:6::1",
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "static",
                "wan6_static": {
                    "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                    "network": "2001:1488:fffe:6::/60",
                    "gateway": "2001:1488:fffe:6::1",
                    "dns1": None,
                    "dns2": "2001:4860:4860::8888",
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": "256.0.0.0"}},
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "11.22.333.44",
                    "ipv6_prefix": "2001:470:6f:39::/64",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "2001:470::6f:39::/64",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "2001:470:6f:39::/129",
                    "dynamic_ipv4": {
                        "enabled": True,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {
                "wan6_type": "6in4",
                "wan6_6in4": {
                    "mtu": 1480,
                    "server_ipv4": "11.22.33.44",
                    "ipv6_prefix": "2001:470:6f:39::/64",
                    "dynamic_ipv4": {
                        "enabled": False,
                        "tunnel_id": "1122334455",
                        "username": "user1",
                        "password_or_key": "passphrase1",
                    },
                },
            },
            "mac_settings": {"custom_mac_enabled": False},
        }
    )


@pytest.mark.parametrize('check_connection_mock', ["success"], indirect=True)
def test_connection_test(check_connection_mock, uci_configs_init, infrastructure):
    """When triggering test on openwrt backend, `connection_test_status`
    is unfinished while the test is running."""
    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "connection_test_status",
            "kind": "request",
            "data": {"test_id": "non-existing"},
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert res["data"] == {"status": "not_found"}

    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "connection_test_trigger",
            "kind": "request",
            "data": {"test_kinds": ["ipv4", "ipv6", "dns"]},
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "test_id" in res["data"].keys()

    test_id = res["data"]["test_id"]
    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "connection_test_status",
            "kind": "request",
            "data": {"test_id": test_id},
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert res["data"]["status"] in ["running", "finished"]
    assert "data" in res["data"]


def _connection_test(infrastructure, test_kind, expected):
    """Helper function to test mocked output using openwrt backend only."""
    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "connection_test_trigger",
            "kind": "request",
            "data": {"test_kinds": [test_kind]}
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "test_id" in res["data"].keys()

    test_id = res["data"]["test_id"]
    status = None
    while status != "finished":
        res = infrastructure.process_message(
            {
                "module": "wan",
                "action": "connection_test_status",
                "kind": "request",
                "data": {"test_id": test_id},
            }
        )
        status = res["data"]["status"]

    assert status == "finished"
    assert test_kind in res["data"]["data"]
    assert res["data"]["data"][test_kind] == expected

    return True


@pytest.mark.parametrize("check_connection_mock", ["success"], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_connection_test_openwrt_ok(check_connection_mock, uci_configs_init, infrastructure):
    assert _connection_test(infrastructure, "dns", "OK")


@pytest.mark.parametrize("check_connection_mock", ["failed"], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_connection_test_openwrt_failed(check_connection_mock, uci_configs_init, infrastructure):
    assert _connection_test(infrastructure, "ipv4", "FAILED")


@pytest.mark.parametrize("check_connection_mock", ["unknown"], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_connection_test_openwrt_unknown(check_connection_mock, uci_configs_init, infrastructure):
    assert _connection_test(infrastructure, "ipv6", "UNKNOWN")


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_missing_wan6_openwrt(
    uci_configs_init, infrastructure, network_restart_command, fix_mox_wan, device, turris_os_version,
):
    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_section("network", "wan6")

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert "wan6_settings" in res["data"].keys()
    assert res["data"]["wan6_settings"]["wan6_type"] == "dhcpv6"

    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
                "wan6_settings": {"wan6_type": "dhcpv6", "wan6_dhcpv6": {"duid": ""}},
                "mac_settings": {"custom_mac_enabled": False},
            },
        }
    )
    assert "result" in res["data"]
    assert res["data"]["result"]

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert "wan6_settings" in res["data"].keys()
    assert res["data"]["wan6_settings"]["wan6_type"] == "dhcpv6"

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "network", "wan6", "proto") == "dhcpv6"
    assert uci.get_option_named(data, "network", "wan6", "device") == "@wan"


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_dns_option(
    uci_configs_init, infrastructure, network_restart_command, fix_mox_wan, device, turris_os_version,
):
    uci = get_uci_module(infrastructure.name)

    res = infrastructure.process_message(
        {
            "module": "wan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "wan_settings": {
                    "wan_type": "static",
                    "wan_static": {
                        "ip": "10.0.0.10",
                        "netmask": "255.255.0.0",
                        "gateway": "10.0.0.1",
                        "dns1": "10.0.0.1",
                        "dns2": "8.8.8.8",
                    },
                },
                "wan6_settings": {
                    "wan6_type": "static",
                    "wan6_static": {
                        "ip": "2001:1488:fffe:6:da9e:f3ff:fe73:59c/64",
                        "network": "2001:1488:fffe:6::/60",
                        "gateway": "2001:1488:fffe:6::1",
                        "dns1": "2001:1488:fffe:6::1",
                        "dns2": "2001:4860:4860::8888",
                    },
                },
                "mac_settings": {"custom_mac_enabled": False},
            },
        }
    )
    assert res["data"]["result"]

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("network", "wan", "dns")
        backend.set_option("network", "wan", "dns", "1.1.1.1 8.8.8.8")
        backend.del_option("network", "wan6", "dns")
        backend.set_option("network", "wan6", "dns", "2001:4860:4860::8888 2001:4860:4860::9999")

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert res["data"]["wan_settings"]["wan_static"]["dns1"] == "8.8.8.8"
    assert res["data"]["wan_settings"]["wan_static"]["dns2"] == "1.1.1.1"
    assert res["data"]["wan6_settings"]["wan6_static"]["dns1"] == "2001:4860:4860::9999"
    assert res["data"]["wan6_settings"]["wan6_static"]["dns2"] == "2001:4860:4860::8888"


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_missing_wireless(uci_configs_init, infrastructure, fix_mox_wan, device, turris_os_version):
    prepare_turrishw_root(device,turris_os_version)
    os.unlink(os.path.join(uci_configs_init[0], "wireless"))
    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}


@pytest.mark.parametrize("device, turris_os_version",[("mox", "4.0"),("omnia","4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_wan6_options_can_be_empty(uci_configs_init, infrastructure, device, turris_os_version):

    prepare_turrishw_root(device, turris_os_version)
    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_section("network", "wan6")
        backend.add_section("network", "interface", "wan6")
        backend.set_option("network", "wan6", "proto", "static")

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()


@pytest.mark.parametrize("device, turris_os_version",[("mox", "4.0"),("omnia","4.0")], indirect=True)
def test_update_mac_address_and_disable(
    uci_configs_init,
    network_restart_command,
    infrastructure,
    device,
    turris_os_version,
):

    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    data = {
        "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
        "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": ""}},
        "mac_settings": {"custom_mac_enabled": True, "custom_mac": "11:22:33:44:55:66"},
    }
    data_2 = {
        "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
        "wan6_settings": {"wan6_type": "6to4", "wan6_6to4": {"ipv4_address": ""}},
        "mac_settings": {"custom_mac_enabled": False},
    }
    res = infrastructure.process_message(
        {"module": "wan", "action": "update_settings", "kind": "request", "data": data}
    )

    assert "errors" not in res.keys()
    assert res['data']['result']

    res = infrastructure.process_message(
        {"module": "wan", "action": "update_settings", "kind": "request", "data": data_2}
    )

    assert "errors" not in res.keys()

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert "custom_mac" not in res.keys()


@pytest.mark.parametrize(
    "device, turris_os_version, wan_mac",
    [
        ("mox", "4.0", "de:ad:be:ef:99:99"),
        ("omnia", "4.0", "d8:58:d7:00:92:9e"),
        # TODO: ("turris", "4.0", "00:00:00:00:00:00") mising data in /sys/class of mock file
    ],
    indirect=["device", "turris_os_version"]
)
@pytest.mark.only_backends(["openwrt"])
def test_different_devices(uci_configs_init, infrastructure, device, fix_mox_wan, turris_os_version, wan_mac):

    prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res.keys()
    assert res["data"]["mac_settings"]["mac_address"] == wan_mac


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_qos_openwrt(
    infrastructure, network_restart_command, device, fix_mox_wan, turris_os_version
):
    prepare_turrishw_root(device, turris_os_version)
    uci = get_uci_module(infrastructure.name)

    res = infrastructure.process_message(
        {
            "module": "wan", "action": "update_settings", "kind": "request",
            "data": {
                "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
                "wan6_settings": {"wan6_type": "none"},
                "mac_settings": {"custom_mac_enabled": False},
                "qos": {"enabled": True, "upload": 2048, "download": 512}
            }
        }
    )
    assert "errors" not in res.keys()

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
        assert uci.get_option_named(data, "sqm", "wan_limit_turris", "enabled") == "1"
        assert int(uci.get_option_named(data, "sqm", "wan_limit_turris", "upload")) == 2048
        assert int(uci.get_option_named(data, "sqm", "wan_limit_turris", "download")) == 512
        assert uci.get_option_named(data, "sqm", "wan_limit_turris", "interface") == "eth0"
        assert uci.get_option_named(data, "sqm", "wan_limit_turris", "script") == "piece_of_cake.qos"


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_qos_settings_persistent(
    infrastructure, network_restart_command, device, fix_mox_wan, turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    def update(input_data):
        res = infrastructure.process_message(
            {"module": "wan", "action": "update_settings", "kind": "request", "data": input_data}
        )
        assert res == {
            "action": "update_settings",
            "data": {"result": True},
            "kind": "reply",
            "module": "wan",
        }
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "qos": {"enabled": True, "upload": 2048, "download": 512}
        },
    )
    update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "qos": {"enabled": False}
        }
    )
    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert "errors" not in res.keys()
    assert res["data"]["qos"] == {"enabled": False, "upload": 2048, "download": 512}


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_settings_vlan_openwrt(infrastructure, network_restart_command, device, turris_os_version):
    """Test fetching VLAN ID.

    VLAN settings should be 'enabled' only when VLAN ID is set.
    VLAN settings should be 'disabled' without VLAN ID set.
    """
    prepare_turrishw_root(device, turris_os_version)
    uci = get_uci_module(infrastructure.name)

    # (1) no vlan id set
    res = query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"},
    )
    assert "vlan_settings" in res["data"]
    assert res["data"]["vlan_settings"] == {"enabled": False}

    # (2) read vlan id
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "wan", "device", "eth2.200")

    res = query_infrastructure(
        infrastructure,
        {"module": "wan", "action": "get_settings", "kind": "request"},
    )
    assert "vlan_settings" in res["data"]
    assert res["data"]["vlan_settings"] == {"enabled": True, "vlan_id": 200}


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "6.0")], indirect=True)
def test_update_settings_vlan(
    infrastructure, network_restart_command, device, turris_os_version
):
    """Test update of VLAN ID for WAN interface.

    Test following scenarios:
    * (1) Set VLAN ID
    * (2) Unset/reset VLAN ID
    * (3) Setting VLAN ID outside of the defined range (1<, >4094) should fail
    """
    def update(data, expect_success=True):
        query_infrastructure(
            infrastructure,
            {"module": "wan", "action": "update_settings", "kind": "request", "data": data},
            expect_success
        )

        # `get_settings` should always succeed
        res = query_infrastructure(
            infrastructure,
            {"module": "wan", "action": "get_settings", "kind": "request"},
        )

        return res

    # (1)
    res = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 100}
        }
    )
    assert res["data"]["vlan_settings"]["enabled"] is True
    assert res["data"]["vlan_settings"]["vlan_id"] == 100

    # (2)
    res = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": False}
        }
    )
    assert res["data"]["vlan_settings"]["enabled"] is False
    assert "vlan_id" not in res["data"]["vlan_settings"]

    # (3) test VLAN ID range edge cases (2<, >4094)
    res = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 4095}
        },
        expect_success=False
    )
    assert res["data"]["vlan_settings"]["enabled"] is False
    assert "vlan_id" not in res["data"]["vlan_settings"]

    res = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 0}
        },
        expect_success=False
    )
    assert res["data"]["vlan_settings"]["enabled"] is False
    assert "vlan_id" not in res["data"]["vlan_settings"]


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "6.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_vlan_openwrt(
    infrastructure, network_restart_command, device, turris_os_version
):
    """Test update of VLAN ID for WAN interface.

    Test following scenarios:
    * (1) Set VLAN ID
    * (2) Unset/reset VLAN ID
    * (3) Setting VLAN ID outside of the defined range (1<, >4094) should fail
    """
    uci = get_uci_module(infrastructure.name)

    def update(data, expect_success=True):
        query_infrastructure(
            infrastructure,
            {"module": "wan", "action": "update_settings", "kind": "request", "data": data},
            expect_success
        )

        if expect_success:
            assert network_restart_was_called([])

        return get_uci_backend_data(uci)

    # (1)
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 100}
        }
    )
    assert uci.get_option_named(data, "network", "wan", "device", "") == "eth2.100"
    assert uci.get_option_named(data, "network", "dev_wan", "name", "") == "eth2.100"

    # (2)
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": False}
        }
    )
    assert uci.get_option_named(data, "network", "wan", "device", "") == "eth2"
    assert uci.get_option_named(data, "network", "dev_wan", "name", "") == "eth2"

    # (3) test VLAN ID range edge cases (1<, >4094)
    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 4095}
        },
        expect_success=False
    )
    assert uci.get_option_named(data, "network", "wan", "device", "") == "eth2"
    assert uci.get_option_named(data, "network", "dev_wan", "name", "") == "eth2"

    data = update(
        {
            "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
            "wan6_settings": {"wan6_type": "none"},
            "mac_settings": {"custom_mac_enabled": False},
            "vlan_settings": {"enabled": True, "vlan_id": 0}
        },
        expect_success=False
    )
    assert uci.get_option_named(data, "network", "wan", "device", "") == "eth2"
    assert uci.get_option_named(data, "network", "dev_wan", "name", "") == "eth2"
