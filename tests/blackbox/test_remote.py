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

import os
import base64
import pytest
import shutil
import tarfile
import json
import uuid
import pathlib

from io import BytesIO

from foris_controller_testtools.fixtures import (
    backend, infrastructure, ubusd_test, only_backends, only_message_buses, uci_configs_init,
    init_script_result, lock_backend, file_root_init, network_restart_command,
    UCI_CONFIG_DIR_PATH, mosquitto_test, start_buses, FILE_ROOT_PATH
)
from foris_controller_testtools.utils import (
    match_subdict, get_uci_module, check_service_result
)

CERT_PATH = "/tmp/test-cagen/"


def prepare_subordinate_token(controller_id):
    def add_to_tar(tar, name, content):
        data = content.encode()
        fake_file = BytesIO(data)
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        info.mode = 0o0600
        fake_file.seek(0)
        tar.addfile(info, fake_file)
        fake_file.close()

    new_file = BytesIO()
    with tarfile.open(fileobj=new_file, mode="w:gz") as tar:
        add_to_tar(tar, f"some_name/token.crt", "token cert content")
        add_to_tar(tar, f"some_name/token.key", "token key content")
        add_to_tar(tar, f"some_name/ca.crt", "ca cert content")
        add_to_tar(tar, f"some_name/conf.json", json.dumps({
            "name": "some_name",
            "hostname": "localhost",
            "ipv4_ips": ["123.123.123.123"],
            "dhcp_names": [],
            "port": 11884,
            "device_id": controller_id,
        }))

    new_file.seek(0)
    final_content = new_file.read()
    new_file.close()

    return base64.b64encode(final_content).decode()


@pytest.fixture(scope="function")
def empty_certs():
    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass

    yield CERT_PATH

    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(scope="function")
def generating_certs():
    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass

    dir_path = os.path.join(CERT_PATH, "remote")
    os.makedirs(dir_path)

    with open(os.path.join(dir_path, "ca"), "w") as f:
        f.write("1\n")
        f.flush()

    yield CERT_PATH

    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(scope="function")
def ready_certs():
    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass

    dir_path = os.path.join(CERT_PATH, "remote")
    os.makedirs(dir_path)

    with open(os.path.join(dir_path, "ca"), "w") as f:
        f.write("4\n")
        f.flush()

    with open(os.path.join(dir_path, "01-turris-server"), "w") as f:
        f.write("valid\n")
        f.flush()

    with open(os.path.join(dir_path, "02-client1-client"), "w") as f:
        f.write("revoked\n")
        f.flush()

    with open(os.path.join(dir_path, "03-client2-client"), "w") as f:
        f.write("valid\n")
        f.flush()

    with open(os.path.join(dir_path, "04-client3-client"), "w") as f:
        f.write("generating\n")
        f.flush()

    yield CERT_PATH

    try:
        shutil.rmtree(CERT_PATH, ignore_errors=True)
    except Exception:
        pass



@pytest.mark.only_backends(['mock'])
def test_generate_ca_mock(infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_ca",
        "kind": "request",
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]


@pytest.mark.only_backends(['openwrt'])
def test_generate_ca_openwrt(empty_certs, infrastructure, start_buses):

    filters = [("remote", "generate_ca")]

    # successful generation
    notifications = infrastructure.get_notifications(filters=filters)

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_ca",
        "kind": "request",
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]
    task_id = res["data"]["task_id"]

    new_notifications = infrastructure.get_notifications(notifications, filters=filters)
    while len(new_notifications) - len(notifications) < 5:
        new_notifications = infrastructure.get_notifications(new_notifications, filters=filters)

    assert new_notifications[-5]["action"] == "generate_ca"
    assert new_notifications[-5]["data"]["status"] == "ca_generating"
    assert new_notifications[-5]["data"]["task_id"] == task_id
    assert new_notifications[-4]["action"] == "generate_ca"
    assert new_notifications[-4]["data"]["status"] == "ca_done"
    assert new_notifications[-4]["data"]["task_id"] == task_id
    assert new_notifications[-3]["action"] == "generate_ca"
    assert new_notifications[-3]["data"]["status"] == "server_generating"
    assert new_notifications[-3]["data"]["task_id"] == task_id
    assert new_notifications[-2]["action"] == "generate_ca"
    assert new_notifications[-2]["data"]["status"] == "server_done"
    assert new_notifications[-2]["data"]["task_id"] == task_id
    assert new_notifications[-1]["action"] == "generate_ca"
    assert new_notifications[-1]["data"]["status"] == "succeeded"
    assert new_notifications[-1]["data"]["task_id"] == task_id

    # failed to generate
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_ca",
        "kind": "request",
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]
    task_id = res["data"]["task_id"]

    new_notifications = infrastructure.get_notifications(notifications, filters=filters)

    assert new_notifications[-1]["action"] == "generate_ca"
    assert new_notifications[-1]["data"]["status"] == "failed"
    assert new_notifications[-1]["data"]["task_id"] == task_id


@pytest.mark.only_backends(['mock'])
def test_ca_get_status_mock(infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "status" in res["data"]


@pytest.mark.only_backends(['openwrt'])
def test_get_status_openwrt_ready(ready_certs, infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert res == {
        u"module": u"remote",
        u"action": u"get_status",
        u"kind": u"reply",
        u"data": {
            u"status": u"ready",
            u"tokens": [
                {u"id": u"02", u"name": u"client1", u"status": u"revoked"},
                {u"id": u"03", u"name": u"client2", u"status": u"valid"},
                {u"id": u"04", u"name": u"client3", u"status": u"generating"},
            ],
        }
    }


@pytest.mark.only_backends(['openwrt'])
def test_get_status_openwrt_missing(empty_certs, infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert res == {
        u"module": u"remote",
        u"action": u"get_status",
        u"kind": u"reply",
        u"data": {u"status": "missing", u"tokens": []}
    }


@pytest.mark.only_backends(['openwrt'])
def test_get_status_openwrt_generating(generating_certs, infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert res == {
        u"module": u"remote",
        u"action": u"get_status",
        u"kind": u"reply",
        u"data": {u"status": u"generating", u"tokens": []}
    }


@pytest.mark.only_backends(['mock'])
def test_generate_token_mock(infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    orig_count = len(res["data"]["tokens"])

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_token",
        "kind": "request",
        "data": {"name": "new.token_1"},
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    assert len(res["data"]["tokens"]) == orig_count + 1
    assert res["data"]["tokens"][-1]["name"] == "new.token_1"


@pytest.mark.only_backends(['openwrt'])
def test_generate_token_openwrt_success(ready_certs, infrastructure, start_buses):

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    orig_count = len(res["data"]["tokens"])

    filters = [("remote", "generate_token")]

    notifications = infrastructure.get_notifications(filters=filters)

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_token",
        "kind": "request",
        "data": {"name": "new.token_1"},
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]
    task_id = res["data"]["task_id"]

    new_notifications = infrastructure.get_notifications(notifications, filters=filters)
    while len(new_notifications) - len(notifications) < 3:
        new_notifications = infrastructure.get_notifications(new_notifications, filters=filters)

    assert new_notifications[-3]["action"] == "generate_token"
    assert new_notifications[-3]["data"]["name"] == "new.token_1"
    assert new_notifications[-3]["data"]["status"] == "token_generating"
    assert new_notifications[-3]["data"]["task_id"] == task_id
    assert new_notifications[-2]["action"] == "generate_token"
    assert new_notifications[-2]["data"]["name"] == "new.token_1"
    assert new_notifications[-2]["data"]["status"] == "token_done"
    assert new_notifications[-2]["data"]["task_id"] == task_id
    assert new_notifications[-1]["action"] == "generate_token"
    assert new_notifications[-1]["data"]["name"] == "new.token_1"
    assert new_notifications[-1]["data"]["status"] == "succeeded"
    assert new_notifications[-1]["data"]["task_id"] == task_id

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    assert len(res["data"]["tokens"]) == orig_count + 1
    assert res["data"]["tokens"][-1]["name"] == "new.token_1"


@pytest.mark.only_backends(['openwrt'])
def test_generate_token_openwrt_failed(empty_certs, infrastructure, start_buses):

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    assert len(res["data"]["tokens"]) == 0

    filters = [("remote", "generate_token")]

    notifications = infrastructure.get_notifications(filters=filters)

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_token",
        "kind": "request",
        "data": {"name": "new.token_2"},
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]
    task_id = res["data"]["task_id"]

    new_notifications = infrastructure.get_notifications(notifications, filters=filters)
    while len(new_notifications) - len(notifications) < 1:
        new_notifications = infrastructure.get_notifications(new_notifications, filters=filters)

    assert new_notifications[-1]["action"] == "generate_token"
    assert new_notifications[-1]["data"]["name"] == "new.token_2"
    assert new_notifications[-1]["data"]["status"] == "failed"
    assert new_notifications[-1]["data"]["task_id"] == task_id

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    assert len(res["data"]["tokens"]) == 0


def test_generate_token_name_failed(empty_certs, infrastructure, start_buses):
    def wrong_name(name):
        res = infrastructure.process_message({
            "module": "remote",
            "action": "generate_token",
            "kind": "request",
            "data": {"name": name},
        })
        assert "errors" in res

    wrong_name("aaa%")
    wrong_name("bbb$")
    wrong_name("ccc!")


@pytest.mark.only_backends(['mock'])
def test_revoke_mock(infrastructure, start_buses):

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_token",
        "kind": "request",
        "data": {"name": "new.token_to_revoke"},
    })
    assert set(res.keys()) == {u"module", u"action", u"kind", u"data"}
    assert "task_id" in res["data"]

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    assert res["data"]["tokens"][-1]["name"] == "new.token_to_revoke"
    id_to_revoke = res["data"]["tokens"][-1]["id"]

    filters = [("remote", "revoke")]

    # successful generation
    notifications = infrastructure.get_notifications(filters=filters)

    # existing
    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": id_to_revoke},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is True

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"remote",
        u"action": u"revoke",
        u"kind": u"notification",
        u"data": {u"id": id_to_revoke},
    }

    # non-existing
    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": "FF"},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is False


@pytest.mark.only_backends(['openwrt'])
def test_revoke_openwrt_ready(ready_certs, infrastructure, start_buses):
    filters = [("remote", "revoke")]

    # successful generation
    notifications = infrastructure.get_notifications(filters=filters)

    # existing
    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": "03"},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is True

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"remote",
        u"action": u"revoke",
        u"kind": u"notification",
        u"data": {u"id": "03"},
    }

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "data" in res
    assert "tokens" in res["data"]
    matched = [e for e in res["data"]["tokens"] if e["id"] == "03"][0]
    assert matched["status"] == "revoked"

    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": "FF"},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is False


@pytest.mark.only_backends(['openwrt'])
def test_revoke_openwrt_missing(empty_certs, infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": "03"},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is False


def test_delete_ca(ready_certs, infrastructure, start_buses):
    filters = [("remote", "delete_ca")]

    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "remote",
        "action": "delete_ca",
        "kind": "request",
    })
    assert "data" in res
    assert "result" in res["data"]
    assert res["data"]["result"] is True

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"remote",
        u"action": u"delete_ca",
        u"kind": u"notification",
    }

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "status" in res["data"]
    assert res["data"]["status"] == "missing"


def test_get_settings(uci_configs_init, infrastructure, start_buses):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res["data"].keys()) == {
        u"enabled", u"wan_access", u"port",
    }


def test_update_settings(
    uci_configs_init, init_script_result, infrastructure, start_buses, network_restart_command,
    ready_certs,
):
    filters = [("remote", "update_settings")]

    def update(new_settings):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message({
            "module": "remote",
            "action": "update_settings",
            "kind": "request",
            "data": new_settings,
        })
        assert "result" in res["data"]
        if infrastructure.name != "mqtt":  # only possible for mqtt bus
            assert res["data"]["result"] is False
            return

        assert res["data"]["result"] is True

        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["data"] == new_settings

        res = infrastructure.process_message({
            "module": "remote",
            "action": "get_settings",
            "kind": "request",
        })
        assert match_subdict(new_settings, res["data"])

    update({u"enabled": False})
    update({
        "enabled": True,
        "wan_access": True,
        "port": 11885,
    })
    update({
        "enabled": True,
        "wan_access": False,
        "port": 11886,
    })

@pytest.mark.only_message_buses(['unix-socket', 'ubus'])
def test_update_settings_ubus_unix(
    uci_configs_init, init_script_result, lock_backend, infrastructure, start_buses,
):
    def update(new_settings):
        res = infrastructure.process_message({
            "module": "remote",
            "action": "update_settings",
            "kind": "request",
            "data": new_settings,
        })
        assert "result" in res["data"]
        assert res["data"]["result"] is False

        res = infrastructure.process_message({
            "module": "remote",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["data"]["enabled"] is False

        if infrastructure.backend_name == "openwrt":
            check_service_result("firewall", "reload", passed=True)
            check_service_result("fosquitto", "disable", passed=True, clean=False)
            check_service_result("fosquitto", "stop", passed=True)

    update({u"enabled": False})
    update({
        "enabled": True,
        "wan_access": True,
        "port": 11885,
    })
    update({
        "enabled": True,
        "wan_access": False,
        "port": 11886,
    })


@pytest.mark.only_message_buses(['mqtt'])
@pytest.mark.only_backends(['openwrt'])
def test_update_settings_openwrt_mqtt(
    uci_configs_init, init_script_result, lock_backend, infrastructure, start_buses, ready_certs,
):

    uci = get_uci_module(lock_backend)

    def update(data):
        res = infrastructure.process_message({
            "module": "remote",
            "action": "update_settings",
            "kind": "request",
            "data": data,
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'remote'
        }
        check_service_result("firewall", "reload", passed=True)
        check_service_result("fosquitto", "enable", passed=True, clean=False)
        check_service_result("fosquitto", "restart", passed=True)

    update({
        "enabled": False,
    })
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    assert uci.parse_bool(uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "enabled")) is False

    update({
        "enabled": True,
        "port": 123,
        "wan_access": False,
    })

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "enabled")) is False
    assert uci.parse_bool(uci.get_option_named(data, "fosquitto", "remote", "enabled")) is True
    assert int(uci.get_option_named(data, "fosquitto", "remote", "port")) == 123

    update({
        "enabled": True,
        "port": 1234,
        "wan_access": True,
    })

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "enabled")) is True
    assert uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "name") == "fosquitto_wan"
    assert uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "target") == "ACCEPT"
    assert uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "proto") == "tcp"
    assert uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "src") == "wan"
    assert uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "dest_port") == "1234"

    assert uci.parse_bool(uci.get_option_named(data, "fosquitto", "remote", "enabled")) is True
    assert int(uci.get_option_named(data, "fosquitto", "remote", "port")) == 1234

    update({
        "enabled": False,
    })
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "wan_fosquitto_turris_rule", "enabled")) is False
    assert uci.parse_bool(uci.get_option_named(data, "fosquitto", "remote", "enabled")) is False


@pytest.mark.only_backends(['mock'])
def test_get_token_mock(infrastructure, start_buses):

    query_data = {}
    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_ca",
        "kind": "request",
    })
    assert "errors" not in res

    query_data["id"] = "FF"
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status"} == set(res["data"].keys())
    assert res["data"]["status"] == "not_found"

    res = infrastructure.process_message({
        "module": "remote",
        "action": "generate_token",
        "kind": "request",
        "data": {"name": "get_token"},
    })
    assert "errors" not in res
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_status",
        "kind": "request",
    })
    assert "errors" not in res
    assert res["data"]["tokens"][-1]["name"] == "get_token"
    token = res["data"]["tokens"][-1]

    query_data["id"] = token["id"]
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status", "token"} == set(res["data"].keys())
    assert res["data"]["status"] == "valid"

    res = infrastructure.process_message({
        "module": "remote",
        "action": "revoke",
        "kind": "request",
        "data": {"id": token["id"]},
    })
    assert "result" in res["data"]
    assert res["data"]["result"] is True

    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status"} == set(res["data"].keys())
    assert res["data"]["status"] == "revoked"


@pytest.mark.only_backends(['openwrt'])
def test_get_token_openwrt(
    ready_certs, uci_configs_init, init_script_result, lock_backend, infrastructure, start_buses, file_root_init
):

    query_data = {}
    uci = get_uci_module(lock_backend)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("system", "@system[0]", "hostname", "testhostname")
        backend.set_option("network", "wan", "ipaddr", "10.1.1.111")
        backend.set_option("network", "wan", "proto", "dhcp")
        backend.set_option("network", "wan", "hostname", "name_on_wan")
        backend.set_option("network", "lan", "ipaddr", "192.168.31.1")
        backend.set_option("network", "lan", "proto", "static")
        backend.set_option("network", "lan", "hostname", "name_on_lan")
        backend.set_option("fosquitto", "remote", "port", "12345")

    query_data["id"] = "FF"
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status"} == set(res["data"].keys())
    assert res["data"]["status"] == "not_found"

    query_data["id"] = "02"
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status"} == set(res["data"].keys())
    assert res["data"]["status"] == "revoked"

    query_data["id"] = "03"
    res = infrastructure.process_message({
        "module": "remote",
        "action": "get_token",
        "kind": "request",
        "data": query_data,
    })
    assert {"status", "token"} == set(res["data"].keys())
    assert res["data"]["status"] == "valid"

    # token is supposed to be a base64 encoded tarball
    token_data = BytesIO(base64.b64decode(res["data"]["token"]))
    with tarfile.open(fileobj=token_data, mode="r:gz") as tar:
        # check names
        assert {e.name for e in tar.getmembers()} == {
            "client2/token.crt",
            "client2/token.key",
            "client2/ca.crt",
            "client2/conf.json",
        }

        # check files
        for tarinfo in tar:
            assert tarinfo.isreg()
            assert tarinfo.mode == 0o0600
            assert tarinfo.size > 0

        # check conf
        with tar.extractfile("client2/conf.json") as f:
            conf = json.load(f)

        assert set(conf.keys()) == {"hostname", "name", "ipv4_ips", "dhcp_names", "port", "device_id"}

        assert conf["hostname"] == "testhostname"
        assert conf["name"] == "client2"
        assert conf["port"] == 12345
        assert conf["device_id"] == "%016X" % uuid.getnode()

        assert "172.20.6.87" in conf["ipv4_ips"]["lan"]
        assert "192.168.31.1" in conf["ipv4_ips"]["lan"]
        assert "172.20.6.87" in conf["ipv4_ips"]["wan"]
        assert "10.1.1.111" not in conf["ipv4_ips"]["wan"]  # wan is set via dhcp

        assert "name_on_wan" == conf["dhcp_names"]["wan"]
        assert "" == conf["dhcp_names"]["lan"]


@pytest.mark.only_message_buses(['mqtt'])
@pytest.mark.only_backends(['openwrt'])
def test_delete_ca_when_enabled(
    uci_configs_init, init_script_result, infrastructure, start_buses, network_restart_command, file_root_init,
    ready_certs,
):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "enabled": True,
            "wan_access": False,
            "port": 11886,
        }
    })
    assert res["data"]["result"]
    res = infrastructure.process_message({
        "module": "remote",
        "action": "delete_ca",
        "kind": "request",
    })
    assert res["data"]["result"] is False


@pytest.mark.only_backends(['openwrt'])
def test_enable_generating(
    uci_configs_init, init_script_result, infrastructure, start_buses, network_restart_command, file_root_init,
    generating_certs,
):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "enabled": True,
            "wan_access": False,
            "port": 11886,
        }
    })
    assert not res["data"]["result"]


@pytest.mark.only_backends(['openwrt'])
def test_enable_empty(
    uci_configs_init, init_script_result, infrastructure, start_buses, network_restart_command, file_root_init,
    empty_certs,
):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "enabled": True,
            "wan_access": False,
            "port": 11886,
        }
    })
    assert not res["data"]["result"]


@pytest.mark.only_message_buses(['unix-socket', 'ubus'])
def test_complex_subordinates_unsupported(uci_configs_init, infrastructure, start_buses, file_root_init):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "list_subordinates",
        "kind": "request",
    })
    assert res == {
        "module": "remote",
        "action": "list_subordinates",
        "kind": "reply",
        "data": {"subordinates": []}
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subordinate",
        "kind": "request",
        "data": {
            "token": prepare_subordinate_token("1122334455667788"),
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788", "custom_name": "set_xx", "enabled": False,
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }


@pytest.mark.only_message_buses(['mqtt'])
def test_complex_subordinates(
    uci_configs_init, infrastructure, start_buses, file_root_init, init_script_result
):
    def in_list(controller_id):
        res = infrastructure.process_message({
            "module": "remote",
            "action": "list_subordinates",
            "kind": "request",
        })
        assert "subordinates" in res["data"]
        output = None
        for record in res["data"]["subordinates"]:
            assert set(record.keys()) == {"custom_name", "controller_id", "enabled", "subsubordinates"}
            if record["controller_id"] == controller_id:
                output = record
        return output

    assert None is in_list("1122334455667788")
    token = prepare_subordinate_token("1122334455667788")

    filters = [("remote", "add_subordinate")]
    notifications = infrastructure.get_notifications(filters=filters)

    # add
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subordinate",
        "kind": "request",
        "data": {
            "token": token,
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "reply",
        "data": {"result": True, "controller_id": "1122334455667788"}
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True)
    assert notifications[-1] == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "notification",
        "data": {"controller_id": "1122334455667788"}
    }
    assert in_list("1122334455667788") == {
        "controller_id": "1122334455667788", "enabled": True, "custom_name": "",
        "subsubordinates": [],
    }

    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subordinate",
        "kind": "request",
        "data": {
            "token": token,
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True, expected_found=False)

    assert in_list("1122334455667788") == {
        "controller_id": "1122334455667788", "enabled": True, "custom_name": "",
        "subsubordinates": [],
    }

    # add2
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subordinate",
        "kind": "request",
        "data": {
            "token": prepare_subordinate_token("8877665544332211"),
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "reply",
        "data": {"result": True, "controller_id": "8877665544332211"}
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True)
    assert notifications[-1] == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "notification",
        "data": {"controller_id": "8877665544332211"}
    }
    assert in_list("8877665544332211") == {
        "controller_id": "8877665544332211", "enabled": True, "custom_name": "",
        "subsubordinates": [],
    }

    # set
    filters = [("remote", "set_subordinate")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788", "custom_name": "test_set1", "enabled": False,
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "remote",
        "action": "set_subordinate",
        "kind": "notification",
        "data": {"controller_id": "1122334455667788", "custom_name": "test_set1", "enabled": False}
    }
    assert in_list("1122334455667788") == {
        "controller_id": "1122334455667788", "custom_name": "test_set1", "enabled": False,
        "subsubordinates": [],
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "2222334455667788", "custom_name": "test_set2", "enabled": True,
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True, expected_found=False)

    # del
    filters = [("remote", "del_subordinate")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "remote",
        "action": "del_subordinate",
        "kind": "notification",
        "data": {"controller_id": "1122334455667788"}
    }
    assert None is in_list("1122334455667788")

    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    if infrastructure.backend_name == "openwrt":
        check_service_result("fosquitto", "reload", passed=True, expected_found=False)
    assert None is in_list("1122334455667788")


@pytest.mark.only_backends(['openwrt'])
@pytest.mark.only_message_buses(['mqtt'])
def test_complex_subordinates_openwrt(
    uci_configs_init, infrastructure, start_buses, file_root_init, init_script_result, lock_backend
):
    uci = get_uci_module(lock_backend)
    token = prepare_subordinate_token("1122334455667788")
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subordinate",
        "kind": "request",
        "data": {
            "token": token,
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subordinate",
        "kind": "reply",
        "data": {"result": True, "controller_id": "1122334455667788"}
    }

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(
        data, "fosquitto", "1122334455667788", "address", "") == "123.123.123.123"
    assert uci.get_option_named(
        data, "fosquitto", "1122334455667788", "port", "") == "11884"
    assert uci.parse_bool(uci.get_option_named(
        data, "fosquitto", "1122334455667788", "enabled", ""))

    subordinate_root = \
        pathlib.Path(FILE_ROOT_PATH) / "etc" / "fosquitto" / "bridges" / "1122334455667788"
    assert subordinate_root.exists()
    assert (subordinate_root / "conf.json").exists()
    assert (subordinate_root / "token.crt").exists()
    assert (subordinate_root / "token.key").exists()
    assert (subordinate_root / "ca.crt").exists()

    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788",
            "enabled": False,
            "custom_name": "openwrt1",
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subordinate",
        "kind": "reply",
        "data": {"result": True}
    }

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert not uci.parse_bool(uci.get_option_named(
        data, "fosquitto", "1122334455667788", "enabled", ""))
    assert uci.get_option_named(data, "fosquitto", "1122334455667788", "custom_name") == "openwrt1"

    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "1122334455667788",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subordinate",
        "kind": "reply",
        "data": {"result": True}
    }

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "fosquitto", "1122334455667788", "custom_name", "") == ""

    with pytest.raises(uci.UciRecordNotFound):
        uci.get_section(data, "fosquitto", "1122334455667788")
    assert not subordinate_root.exists()


@pytest.mark.only_message_buses(['unix-socket', 'ubus'])
def test_complex_subsubordinates_unsupported(uci_configs_init, infrastructure, start_buses, file_root_init):
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "8877665544332211",
            "via": "1122334455667788",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "8877665544332211",
            "custom_name": "sub1",
            "enabled": False
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "8877665544332211",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }


@pytest.mark.only_message_buses(['mqtt'])
def test_complex_subsubordinates(
    uci_configs_init, infrastructure, start_buses, file_root_init, init_script_result, lock_backend
):
    # prepare subordinates
    def add_subordinate(controller_id, result):
        token = prepare_subordinate_token(controller_id)
        res = infrastructure.process_message({
            "module": "remote",
            "action": "add_subordinate",
            "kind": "request",
            "data": {
                "token": token,
            }
        })
        if result:
            assert res == {
                "module": "remote",
                "action": "add_subordinate",
                "kind": "reply",
                "data": {"result": True, "controller_id": controller_id}
            }
        else:
            assert res == {
                    "module": "remote",
                    "action": "add_subordinate",
                    "kind": "reply",
                    "data": {"result": False}
                }
    add_subordinate("8888888888888888", True)
    add_subordinate("7777777777777777", True)

    def check_under(parent, child):
        res = infrastructure.process_message({
            "module": "remote",
            "action": "list_subordinates",
            "kind": "request",
        })
        assert 1 == len([
            e for record in res["data"]["subordinates"] if record["controller_id"] == parent
            for e in record["subsubordinates"] if e["controller_id"] == child
        ])

    filters = [("remote", "add_subsubordinate")]
    notifications = infrastructure.get_notifications(filters=filters)
    # add subsub success
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "6666666666666666",
            "via": "8888888888888888",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "notification",
        "data": {"controller_id": "6666666666666666", "via": "8888888888888888"}
    }
    check_under("8888888888888888", "6666666666666666")

    # already added
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "6666666666666666",
            "via": "7777777777777777",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }

    # add subsub with same controller_id as sub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "7777777777777777",
            "via": "8888888888888888",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }

    # add subsub when via subsub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "5555555555555555",
            "via": "6666666666666666",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }

    # add subsub when via non existing
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "5555555555555555",
            "via": "1111111111111111",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }

    # add sub but subsub already exists
    add_subordinate("6666666666666666", False)

    filters = [("remote", "set_subsubordinate")]
    notifications = infrastructure.get_notifications(filters=filters)
    # set subsub success
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "6666666666666666",
            "custom_name": "setsubsub1",
            "enabled": False,
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "notification",
        "data": {
            "controller_id": "6666666666666666",
            "custom_name": "setsubsub1",
            "enabled": False,
        }
    }
    res = infrastructure.process_message({
        "module": "remote",
        "action": "list_subordinates",
        "kind": "request",
    })
    assert "subordinates" in res["data"]
    for record in res["data"]["subordinates"]:
        if record["controller_id"] == "8888888888888888":
            assert record["subsubordinates"][0] == {
                "controller_id": "6666666666666666",
                "enabled": False,
                "custom_name": "setsubsub1"
            }

    # set sub via subsub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "7777777777777777",
            "custom_name": "setsubsub2",
            "enabled": False,
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }

    filters = [("remote", "del_subsubordinate")]
    notifications = infrastructure.get_notifications(filters=filters)
    # del subsub success
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "6666666666666666",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "notification",
        "data": {"controller_id": "6666666666666666"}
    }

    # del subsub when id is for sub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "7777777777777777",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "reply",
        "data": {"result": False}
    }


@pytest.mark.only_backends(['openwrt'])
@pytest.mark.only_message_buses(['mqtt'])
def test_complex_subsubordinates_openwrt(
    uci_configs_init, infrastructure, start_buses, file_root_init, init_script_result, lock_backend
):
    uci = get_uci_module(lock_backend)

    def add_subordinate(controller_id):
        token = prepare_subordinate_token(controller_id)
        res = infrastructure.process_message({
            "module": "remote",
            "action": "add_subordinate",
            "kind": "request",
            "data": {
                "token": token,
            }
        })
        assert res == {
            "module": "remote",
            "action": "add_subordinate",
            "kind": "reply",
            "data": {"result": True, "controller_id": controller_id}
        }
        check_service_result("fosquitto", "reload", passed=True)

    add_subordinate("4444444444444444")
    add_subordinate("5555555555555555")

    # add subsub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "2222222222222222",
            "via": "4444444444444444",
        }
    })
    assert res == {
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    check_service_result("fosquitto", "reload", passed=True)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "fosquitto", "2222222222222222", "via") == "4444444444444444"

    # set subsub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "2222222222222222",
            "custom_name": "subsubnamex",
            "enabled": False
        }
    })
    assert res == {
        "module": "remote",
        "action": "set_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    check_service_result("fosquitto", "reload", passed=True)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "fosquitto", "2222222222222222", "via") == "4444444444444444"
    assert uci.get_option_named(data, "fosquitto", "2222222222222222", "custom_name") \
        == "subsubnamex"
    assert not uci.parse_bool(
        uci.get_option_named(data, "fosquitto", "2222222222222222", "enabled"))

    # del subsub
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "2222222222222222",
        }
    })
    assert res == {
        "module": "remote",
        "action": "del_subsubordinate",
        "kind": "reply",
        "data": {"result": True}
    }
    check_service_result("fosquitto", "reload", passed=True)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    with pytest.raises(uci.UciRecordNotFound):
        uci.get_section(data, "fosquitto", "2222222222222222")

    # del section and all its subsections
    res = infrastructure.process_message({
        "module": "remote",
        "action": "add_subsubordinate",
        "kind": "request",
        "data": {
            "controller_id": "1111111111111111",
            "via": "4444444444444444",
        }
    })
    assert res["data"]["result"]
    res = infrastructure.process_message({
        "module": "remote",
        "action": "del_subordinate",
        "kind": "request",
        "data": {
            "controller_id": "4444444444444444",
        }
    })
    assert res["data"]["result"]

    with pytest.raises(uci.UciRecordNotFound):
        uci.get_section(data, "fosquitto", "1111111111111111")
