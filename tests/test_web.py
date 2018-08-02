#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import base64

from foris_controller_testtools.fixtures import (
    uci_configs_init, infrastructure, ubusd_test, file_root_init,
    init_script_result
)

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_web_files")


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get(file_root_init, uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "web",
        "action": "get_data",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {
        u"language", u"reboot_required", u"notification_count", u"updater_running",
        u"guide", u"password_ready",
    }
    assert len(res["data"]["language"]) in [2, 5]  # en, en_US
    assert res["data"]["notification_count"] >= 0
    assert "enabled" in res["data"]["guide"]
    assert "passed" in res["data"]["guide"]


@pytest.mark.file_root_path(FILE_ROOT_PATH)
@pytest.mark.parametrize("code", ["cs", "nb_NO"])
def test_set(code, file_root_init, uci_configs_init, infrastructure, ubusd_test):
    filters = [("web", "set_language")]
    old_notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message({
        "module": "web",
        "action": "set_language",
        "kind": "request",
        "data": {"language": code},
    })
    assert res == {
        u'action': u'set_language',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'web'
    }
    assert infrastructure.get_notifications(old_notifications, filters=filters)[-1] == {
        u"module": u"web",
        u"action": u"set_language",
        u"kind": u"notification",
        u"data": {
            u"language": code,
        }
    }


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_set_missing(file_root_init, uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "web",
        "action": "set_language",
        "kind": "request",
        "data": {"language": "zz"},
    })
    assert res == {
        u'action': u'set_language',
        u'data': {u'result': False},
        u'kind': u'reply',
        u'module': u'web'
    }


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_list_languages(file_root_init, uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "web",
        "action": "list_languages",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert u"languages" in res["data"].keys()
    assert set(res["data"]["languages"]) == {'en', 'cs', 'de', 'nb_NO'}


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_missing_data(file_root_init, uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "web",
        "action": "set_language",
        "kind": "request",
    })
    assert "errors" in res

@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_update_guide(file_root_init, init_script_result, uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "web",
        "action": "update_guide",
        "kind": "request",
        "data": {"enabled": False, "workflow": "standard"},
    })
    assert res["data"]["result"] is True

    res = infrastructure.process_message({
        "module": "web",
        "action": "get_data",
        "kind": "request",
    })
    assert res["data"]["guide"]["enabled"] is False
    assert res["data"]["guide"]["workflow"] == "standard"

    res = infrastructure.process_message({
        "module": "web",
        "action": "update_guide",
        "kind": "request",
        "data": {"enabled": True, "workflow": "standard"},
    })
    assert res["data"]["result"] is True

    def get_passed(passed):
        res = infrastructure.process_message({
            "module": "web",
            "action": "get_data",
            "kind": "request",
        })
        assert res["data"]["guide"]["enabled"] is True
        assert res["data"]["guide"]["workflow"] == "standard"
        assert res["data"]["guide"]["passed"] == passed
    get_passed([])

    def pass_step(msg, result):
        res = infrastructure.process_message(msg)
        assert res["data"]["result"] is True
        get_passed(result)
        # repeat it twice to be sure that it doesn't return duplicates
        res = infrastructure.process_message(msg)
        assert res["data"]["result"] is True
        get_passed(result)

    # Update password
    msg = {
        "module": "password",
        "action": "set",
        "kind": "request",
        "data": {"password": base64.b64encode(b"heslo").decode("utf-8"), "type": "foris"},
    }
    pass_step(msg, ["password"])

    # Update wan
    msg = {
        "module": "wan",
        "action": "update_settings",
        "kind": "request",
        "data": {
            'wan_settings': {'wan_type': 'dhcp', 'wan_dhcp': {}},
            'wan6_settings': {'wan6_type': 'none'},
            'mac_settings': {'custom_mac_enabled': False},
        }
    }
    pass_step(msg, ["password", "wan"])

    # Update timezone
    msg = {
        "module": "time",
        "action": "update_settings",
        "kind": "request",
        "data": {
            u"region": u"Europe",
            u"city": u"Prague",
            u"timezone": u"CET-1CEST,M3.5.0,M10.5.0/3",
            u"time_settings": {
                u"how_to_set_time": u"manual",
                u"time": u"2018-01-30T15:51:30.482515",
            }
        }
    }
    pass_step(msg, ["password", "wan", "time"])

    # Update dns
    msg = {
        "module": "dns",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "forwarding_enabled": False,
            "dnssec_enabled": False,
            "dns_from_dhcp_enabled": False,
        }
    }
    pass_step(msg, ["password", "wan", "time", "dns"])

    msg = {
        "module": "updater",
        "action": "update_settings",
        "kind": "request",
        "data": {
            "enabled": False,
        },
    }
    pass_step(msg, ["password", "wan", "time", "dns", "updater"])
