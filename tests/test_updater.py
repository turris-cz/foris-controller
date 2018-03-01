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

import pytest

from foris_controller.exceptions import UciRecordNotFound

from foris_controller_testtools.fixtures import (
    only_backends, uci_configs_init, infrastructure, ubusd_test, lock_backend
)

from .test_uci import get_uci_module


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "updater",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "enabled" in res["data"].keys()
    assert "required_languages" in res["data"].keys()
    assert "user_lists" in res["data"].keys()
    assert "approvals" in res["data"].keys()
    assert "status" in res["data"]["approvals"].keys()
    assert "branch" in res["data"].keys()


def test_update_settings(uci_configs_init, infrastructure, ubusd_test):
    def update_settings(new_settings):
        res = infrastructure.process_message({
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": new_settings,
        })
        assert "result" in res["data"] and res["data"]["result"] is True
        res = infrastructure.process_message({
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["data"] == new_settings

    update_settings({
        "enabled": True,
        "branch": "",
        "approvals": {"status": "off"},
        "user_lists": [],
        "required_languages": [],
    })

    update_settings({
        "enabled": False,
        "branch": "nightly",
        "approvals": {"status": "on"},
        "user_lists": ['list1'],
        "required_languages": ['cs'],
    })

    update_settings({
        "enabled": False,
        "branch": "",
        "approvals": {"status": "delayed", "delay": 24},
        "user_lists": ['list2'],
        "required_languages": ['cs', 'de'],
    })

    update_settings({
        "enabled": True,
        "branch": "",
        "approvals": {"status": "off"},
        "user_lists": [],
        "required_languages": [],
    })


@pytest.mark.only_backends(['openwrt'])
def test_uci(uci_configs_init, lock_backend, infrastructure, ubusd_test):

    uci = get_uci_module(lock_backend)

    def update_settings(new_settings):
        res = infrastructure.process_message({
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": new_settings,
        })
        assert "result" in res["data"] and res["data"]["result"] is True

    update_settings({
        "enabled": True,
        "branch": "",
        "approvals": {"status": "off"},
        "user_lists": [],
        "required_languages": [],
    })
    with uci.UciBackend() as backend:
        data = backend.read("updater")
    assert not uci.parse_bool(uci.get_option_named(data, "updater", "override", "disable"))
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "override", "branch")
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "approvals", "auto_grant_seconds")
    assert not uci.parse_bool(uci.get_option_named(data, "updater", "approvals", "need"))
    assert uci.get_option_named(data, "updater", "pkglists", "lists", []) == []
    assert uci.get_option_named(data, "updater", "l10n", "langs", []) == []

    update_settings({
        "enabled": False,
        "branch": "nightly",
        "approvals": {"status": "on"},
        "user_lists": ['list1'],
        "required_languages": ['cs'],
    })
    with uci.UciBackend() as backend:
        data = backend.read("updater")
    assert uci.parse_bool(uci.get_option_named(data, "updater", "override", "disable"))
    assert uci.get_option_named(data, "updater", "override", "branch") == "nightly"
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "approvals", "auto_grant_seconds")
    assert uci.parse_bool(uci.get_option_named(data, "updater", "approvals", "need"))
    assert uci.get_option_named(data, "updater", "pkglists", "lists", []) == ['list1']
    assert uci.get_option_named(data, "updater", "l10n", "langs", []) == ["cs"]

    update_settings({
        "enabled": False,
        "branch": "",
        "approvals": {"status": "delayed", "delay": 24},
        "user_lists": ['list2'],
        "required_languages": ['cs', 'de'],
    })
    with uci.UciBackend() as backend:
        data = backend.read("updater")
    assert uci.parse_bool(uci.get_option_named(data, "updater", "override", "disable"))
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "override", "branch")
    assert int(uci.get_option_named(data, "updater", "approvals", "auto_grant_seconds")) \
        == 24 * 60 * 60
    assert uci.parse_bool(uci.get_option_named(data, "updater", "approvals", "need"))
    assert uci.get_option_named(data, "updater", "pkglists", "lists", []) == ['list2']
    assert uci.get_option_named(data, "updater", "l10n", "langs", []) == ["cs", "de"]

    update_settings({
        "enabled": True,
        "branch": "",
        "approvals": {"status": "off"},
        "user_lists": [],
        "required_languages": [],
    })
    with uci.UciBackend() as backend:
        data = backend.read("updater")
    assert not uci.parse_bool(uci.get_option_named(data, "updater", "override", "disable"))
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "override", "branch")
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(data, "updater", "approvals", "auto_grant_seconds")
    assert not uci.parse_bool(uci.get_option_named(data, "updater", "approvals", "need"))
    assert uci.get_option_named(data, "updater", "pkglists", "lists", []) == []
    assert uci.get_option_named(data, "updater", "l10n", "langs", []) == []
