#
# foris-controller
# Copyright (C) 2018-20 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import uuid
import time

from datetime import datetime

from foris_controller.exceptions import UciRecordNotFound

from foris_controller_testtools.fixtures import (
    only_backends,
    uci_configs_init,
    infrastructure,
    clean_reboot_indicator,
    updater_languages,
    updater_userlists,
    device,
    turris_os_version,
    start_buses,
    ubusd_test,
    mosquitto_test,
    UCI_CONFIG_DIR_PATH,
)
from foris_controller_testtools.utils import set_approval, get_uci_module, match_subdict


def wait_for_updater_run_finished(notifications, infrastructure):
    filters = [("updater", "run")]
    # filter notifications
    notifications = [e for e in notifications if e["module"] == "updater" and e["action"] == "run"]

    def notification_status_count(notifications, name):
        return len(
            [
                e
                for e in notifications
                if e["module"] == "updater" and e["action"] == "run" and e["data"]["status"] == name
            ]
        )

    # the count of updater run has to be increased
    before_count = notification_status_count(notifications, "initialize")

    # and instances should finish
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    initialize_count = notification_status_count(notifications, "initialize")
    exit_count = notification_status_count(notifications, "exit")
    while before_count == initialize_count or initialize_count > exit_count:
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        initialize_count = notification_status_count(notifications, "initialize")
        exit_count = notification_status_count(notifications, "exit")


def updated_match_expected(result, new_settings):
    """Check if returned data match expected settings"""
    del result["data"]["approval"]

    list_data = result["data"].pop("user_lists")
    assert {e["name"] for e in new_settings["user_lists"]} == {e["name"] for e in list_data if e["enabled"]}

    lang_data = result["data"].pop("languages")
    assert set(new_settings["languages"]) == {e["code"] for e in lang_data if e["enabled"]}

    del new_settings["user_lists"]
    del new_settings["languages"]
    assert match_subdict(new_settings, result["data"])


def match_userlist_options(result, new_settings, defaults):
    """Check if returned user lists options match expected settings"""
    list_data = result["data"].pop("user_lists")

    new_settings_options = {
        ulist["name"]: {
            opt["name"] for opt in ulist.get("options", []) if opt["enabled"]
        }
        for ulist in new_settings["user_lists"]
    }
    list_options = {
        ulist["name"]: {
            opt["name"] for opt in ulist.get("options", []) if opt["enabled"]
        }
        for ulist in list_data if ulist["enabled"]
    }

    # compare user list options minus the expected defaults
    # to confirm that everything was written succesfully
    for lst, opts in list_options.items():
        if lst in defaults:
            list_options[lst] = opts.difference(defaults[lst])

    assert new_settings_options == list_options


@pytest.mark.parametrize("lang", ["en", "cs", "de", "nb_NO", "xx"])
def test_get_settings(
    updater_languages, updater_userlists, uci_configs_init, infrastructure, start_buses, lang
):
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
            "data": {"lang": lang},
        }
    )

    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "enabled" in res["data"].keys()
    assert "languages" in res["data"].keys()
    assert {"enabled", "code"} == set(res["data"]["languages"][0].keys())
    assert "user_lists" in res["data"].keys()
    assert {"enabled", "name", "title", "description", "hidden", "options"} == set(
        res["data"]["user_lists"][0].keys()
    )
    assert "approval_settings" in res["data"].keys()
    assert "status" in res["data"]["approval_settings"].keys()
    assert "approval" in res["data"].keys()


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_clear(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    settings = {
        "enabled": True,
        "approval_settings": {"status": "off"},
        "user_lists": [],
        "languages": []
    }

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": settings,
        }
    )
    assert "result" in res["data"] and res["data"]["result"] is True
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
            "data": {"lang": "en"},
        }
    )

    updated_match_expected(res, settings)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_clear_and_write(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    """Test that clearing of settings won't leave some setting enabled"""

    def update_settings(new_settings):
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "update_settings",
                "kind": "request",
                "data": new_settings,
            }
        )
        assert "result" in res["data"] and res["data"]["result"] is True
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "get_settings",
                "kind": "request",
                "data": {"lang": "en"},
            }
        )
        updated_match_expected(res, new_settings)

    update_settings(
        {"enabled": True, "approval_settings": {"status": "off"}, "user_lists": [], "languages": []}
    )
    update_settings(
        {
            "enabled": True,
            "approval_settings": {"status": "on"},
            "user_lists": [
                {"name": "dvb"}
            ],
            "languages": ["cs", "de", "nb_NO"],
        }
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_languages(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    settings = {
        "enabled": True,
        "approval_settings": {"status": "on"},
        "user_lists": [],
        "languages": ["cs", "de", "nb_NO"],
    }

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": settings,
        }
    )
    assert "result" in res["data"] and res["data"]["result"] is True
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
            "data": {"lang": "en"},
        }
    )

    lang_data = res["data"].pop("languages")
    assert set(settings["languages"]) == {e["code"] for e in lang_data if e["enabled"]}


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_with_defaults(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    settings = {
        "enabled": True,
        "approval_settings": {"status": "on"},
        "user_lists": [
            {"name": "i_agree_honeypot", "options": [{"name": "haas", "enabled": True}]}
        ],
        "languages": ["cs"],
    }
    defaults = {"i_agree_honeypot": {"minipot"}}

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": settings,
        }
    )
    assert "result" in res["data"] and res["data"]["result"] is True
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
            "data": {"lang": "en"},
        }
    )

    match_userlist_options(res, settings, defaults)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_overrride_defaults(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    settings = {
        "enabled": True,
        "approval_settings": {"status": "on"},
        "user_lists": [
            {"name": "i_agree_honeypot", "options": [{"name": "minipot", "enabled": False}]},
            {"name": "i_agree_datacollect", "options": [{"name": "survey", "enabled": True}]},
        ],
        "languages": ["cs"],
    }
    defaults = {"i_agree_datacollect": {"dynfw"}}

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": settings,
        }
    )
    assert "result" in res["data"] and res["data"]["result"] is True
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "get_settings",
            "kind": "request",
            "data": {"lang": "en"},
        }
    )

    match_userlist_options(res, settings, defaults)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_settings_disable_updater_keep_settings(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    def update_settings(new_settings, expected=None):
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "update_settings",
                "kind": "request",
                "data": new_settings,
            }
        )
        assert "result" in res["data"] and res["data"]["result"] is True
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "get_settings",
                "kind": "request",
                "data": {"lang": "en"},
            }
        )
        new_settings = expected if expected else new_settings
        updated_match_expected(res, new_settings)

    update_settings(
        {"enabled": True, "approval_settings": {"status": "off"}, "user_lists": [], "languages": []},
    )
    update_settings(
        {"enabled": False},
        {
            "enabled": False,
            "approval_settings": {"status": "off"},
            "user_lists": [],
            "languages": [],
        },
    )


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_update_settings_openwrt(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):
    filters = [("updater", "run")]
    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "enabled": True,
                "approval_settings": {"status": "off"},
                "user_lists": [],
                "languages": [],
            },
        }
    )
    assert res["data"]["result"]
    wait_for_updater_run_finished(notifications, infrastructure)


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("language", ["cs", "nb_NO"])
def test_approval(
    language, updater_languages, updater_userlists, uci_configs_init, infrastructure, start_buses
):
    def approval(data):
        set_approval(data)
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "get_settings",
                "kind": "request",
                "data": {"lang": language},
            }
        )
        approval = res["data"]["approval"]
        if data:
            data["present"] = True
            data["time"] = datetime.fromtimestamp(data["time"]).isoformat()
            for record in data["plan"]:
                if record["new_ver"] is None:
                    del record["new_ver"]
                if record["cur_ver"] is None:
                    del record["cur_ver"]
            assert data == approval
        else:
            assert approval == {"present": False}

    approval(None)
    approval(
        {
            "hash": str(uuid.uuid4()),
            "status": "asked",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        }
    )
    approval(
        {
            "hash": str(uuid.uuid4()),
            "status": "granted",
            "time": int(time.time()),
            "plan": [
                {"name": "package1", "op": "install", "cur_ver": None, "new_ver": "1.0"},
                {"name": "package2", "op": "remove", "cur_ver": "2.0", "new_ver": None},
            ],
            "reboot": True,
        }
    )
    approval(
        {
            "hash": str(uuid.uuid4()),
            "status": "denied",
            "time": int(time.time()),
            "plan": [
                {"name": "package3", "op": "upgrade", "cur_ver": "1.0", "new_ver": "1.1"},
                {"name": "package4", "op": "downgrade", "cur_ver": "2.1", "new_ver": "2.0"},
                {"name": "package5", "op": "remove", "cur_ver": None, "new_ver": None},
                {"name": "package6", "op": "upgrade", "cur_ver": None, "new_ver": "1.1"},
                {"name": "package7", "op": "downgrade", "cur_ver": None, "new_ver": "2.0"},
            ],
            "reboot": True,
        }
    )


def test_approval_resolve(
    updater_languages, updater_userlists, uci_configs_init, infrastructure, start_buses
):
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "resolve_approval",
            "kind": "request",
            "data": {"hash": str(uuid.uuid4()), "solution": "grant"},
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "result" in res["data"].keys()

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "resolve_approval",
            "kind": "request",
            "data": {"hash": str(uuid.uuid4()), "solution": "deny"},
        }
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "result" in res["data"].keys()


@pytest.mark.only_backends(["openwrt"])
def test_approval_resolve_openwrt(
    updater_languages, updater_userlists, uci_configs_init, infrastructure, start_buses
):
    filters = [("updater", "run")]

    def resolve(approval_data, query_data, result):
        set_approval(approval_data)
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {
                "module": "updater",
                "action": "resolve_approval",
                "kind": "request",
                "data": query_data,
            }
        )
        assert res["data"]["result"] == result
        if res["data"]["result"]:
            res = infrastructure.process_message(
                {
                    "module": "updater",
                    "action": "get_settings",
                    "kind": "request",
                    "data": {"lang": "en"},
                }
            )
            approval = res["data"]["approval"]
            if query_data["solution"] == "deny":
                assert approval["status"] == "denied"
            elif query_data["solution"] == "grant":
                assert approval["status"] == "granted"
                wait_for_updater_run_finished(notifications, infrastructure)

    # No approval
    set_approval(None)
    resolve(None, {"hash": str(uuid.uuid4()), "solution": "grant"}, False)
    resolve(None, {"hash": str(uuid.uuid4()), "solution": "deny"}, False)

    # Other approval
    resolve(
        {
            "hash": str(uuid.uuid4()),
            "status": "asked",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": str(uuid.uuid4()), "solution": "grant"},
        False,
    )
    resolve(
        {
            "hash": str(uuid.uuid4()),
            "status": "asked",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": str(uuid.uuid4()), "solution": "deny"},
        False,
    )

    # Incorrect status
    approval_id = str(uuid.uuid4())
    resolve(
        {
            "hash": approval_id,
            "status": "granted",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": approval_id, "solution": "grant"},
        False,
    )
    resolve(
        {
            "hash": approval_id,
            "status": "denied",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": approval_id, "solution": "deny"},
        False,
    )

    # Passed
    approval_id = str(uuid.uuid4())
    resolve(
        {
            "hash": approval_id,
            "status": "asked",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": approval_id, "solution": "grant"},
        True,
    )
    resolve(
        {
            "hash": approval_id,
            "status": "asked",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": approval_id, "solution": "deny"},
        True,
    )
    resolve(
        {
            "hash": approval_id,
            "status": "denied",
            "time": int(time.time()),
            "plan": [],
            "reboot": False,
        },
        {"hash": approval_id, "solution": "grant"},
        True,
    )


def test_run(uci_configs_init, infrastructure, start_buses):
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "run",
            "kind": "request",
            "data": {"set_reboot_indicator": True},
        }
    )
    assert res == {"module": "updater", "action": "run", "kind": "reply", "data": {"result": True}}
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "run",
            "kind": "request",
            "data": {"set_reboot_indicator": False},
        }
    )
    assert res == {"module": "updater", "action": "run", "kind": "reply", "data": {"result": True}}


@pytest.mark.only_backends(["openwrt"])
def test_run_notifications(uci_configs_init, infrastructure, start_buses):
    filters = [("updater", "run")]
    try:
        os.unlink(clean_reboot_indicator)
    except Exception:
        pass

    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "run",
            "kind": "request",
            "data": {"set_reboot_indicator": False},
        }
    )
    assert res["data"]["result"]
    wait_for_updater_run_finished(notifications, infrastructure)

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "run",
            "kind": "request",
            "data": {"set_reboot_indicator": True},
        }
    )
    assert res["data"]["result"]
    wait_for_updater_run_finished(notifications, infrastructure)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_get_enabled(
    updater_languages,
    updater_userlists,
    uci_configs_init,
    infrastructure,
    start_buses,
    device,
    turris_os_version,
):

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "enabled": True,
                "approval_settings": {"status": "off"},
                "user_lists": [],
                "languages": [],
            },
        }
    )
    assert res["data"]["result"]

    res = infrastructure.process_message(
        {"module": "updater", "action": "get_enabled", "kind": "request"}
    )
    assert res["data"]["enabled"] is True

    res = infrastructure.process_message(
        {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": {"enabled": False},
        }
    )
    assert res["data"]["result"]

    res = infrastructure.process_message(
        {"module": "updater", "action": "get_enabled", "kind": "request"}
    )
    assert res["data"]["enabled"] is False
