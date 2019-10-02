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
import json

from foris_controller_testtools.fixtures import (
    only_backends,
    uci_configs_init,
    infrastructure,
    notify_cmd,
    start_buses,
    ubusd_test,
    mosquitto_test,
)

from foris_controller_testtools.utils import match_subdict

STORED_NOTIFICATIONS = [
    {
        "displayed": False,
        "id": "1518776436-2593",
        "severity": "restart",
        "messages": {"cs": "REBOOT1 CS", "en": "REBOOT1 EN", "nb_NO": "REBOOT1 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2598",
        "severity": "restart",
        "messages": {"cs": "REBOOT2 CS", "en": "REBOOT2 EN", "nb_NO": "REBOOT2 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2603",
        "severity": "news",
        "messages": {"cs": "NEWS1 CS", "en": "NEWS1 EN", "nb_NO": "NEWS1 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2608",
        "severity": "news",
        "messages": {"cs": "NEWS2 CS", "en": "NEWS2 EN", "nb_NO": "NEWS2 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2613",
        "severity": "error",
        "messages": {"cs": "ERROR1 CS", "en": "ERROR1 EN", "nb_NO": "ERROR1 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2618",
        "severity": "error",
        "messages": {"cs": "ERROR2 CS", "en": "ERROR2 EN", "nb_NO": "ERROR2 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2623",
        "severity": "update",
        "messages": {"cs": "UPDATE1 CS", "en": "UPDATE1 EN", "nb_NO": "UPDATE1 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2628",
        "severity": "update",
        "messages": {"cs": "UPDATE2 CS", "en": "UPDATE2 EN", "nb_NO": "UPDATE2 nb_NO"},
    },
    {
        "displayed": False,
        "id": "1518776436-2629",
        "severity": "update",
        "messages": {"cs": "", "en": "", "nb_NO": ""},
    },
]


@pytest.fixture(scope="function")
def stored_notifications():
    path = "/tmp/foris-controller-stored-notifications.json"
    try:
        os.unlink(path)
    except Exception:
        pass

    with open(path, "w") as f:
        json.dump({"notifications": STORED_NOTIFICATIONS}, f)
        f.flush()

    yield path

    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.mark.parametrize("language", ["en", "cs", "nb_NO", ""])
def test_list(language, stored_notifications, uci_configs_init, infrastructure, start_buses):
    msg = {"module": "router_notifications", "action": "list", "kind": "request"}
    if language:
        msg["data"] = {"lang": language}
    res = infrastructure.process_message(msg)
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "notifications" in res["data"].keys()


def test_mark_as_displayed(stored_notifications, uci_configs_init, infrastructure, start_buses):
    ids = ["1518776436-2598", "1518776436-2628"]
    res = infrastructure.process_message(
        {
            "module": "router_notifications",
            "action": "mark_as_displayed",
            "kind": "request",
            "data": {"ids": ids},
        }
    )
    assert res == {
        u"module": u"router_notifications",
        u"action": u"mark_as_displayed",
        u"kind": u"reply",
        u"data": {u"result": True},
    }
    res = infrastructure.process_message(
        {
            "module": "router_notifications",
            "action": "list",
            "kind": "request",
            "data": {"lang": "en"},
        }
    )
    assert "notifications" in res["data"].keys()
    for notification in res["data"]["notifications"]:
        assert notification["displayed"] == (notification["id"] in ids)


def test_mark_as_displayed_notification(notify_cmd, uci_configs_init, infrastructure, start_buses):
    # these notifications are meant to be send by external program
    # to imitate such behavior just call cmd foris-notify
    filters = [("router_notifications", "mark_as_displayed")]

    def mark_as_displayed_notification(data):
        notifications = infrastructure.get_notifications(filters=filters)
        retval, _, _ = notify_cmd("router_notifications", "mark_as_displayed", data)
        assert retval == 0
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "router_notifications"
        assert notifications[-1]["action"] == "mark_as_displayed"
        assert notifications[-1]["kind"] == "notification"
        assert notifications[-1]["data"] == data

    def mark_as_displayed_notification_failed(data):
        new_notifications = infrastructure.get_notifications(filters=filters)
        retval, _, _ = notify_cmd("router_notifications", "mark_as_displayed", data)
        assert not retval == 0
        old_notifications = infrastructure.get_notifications(filters=filters)
        assert new_notifications == old_notifications

    mark_as_displayed_notification({"ids": ["1518776436-2595"], "new_count": 3})
    mark_as_displayed_notification(
        {"ids": ["1518776436-2595", "1518776436-2595", "1518776436-2595"], "new_count": 0}
    )
    mark_as_displayed_notification_failed({"ids": ["1518776436x-2595"], "new_count": 3})
    mark_as_displayed_notification_failed(
        {"ids": ["1518776436-2595", "1518776436-2595", "1518776436x-2595"], "new_count": 0}
    )
    mark_as_displayed_notification_failed({"ids": ["1518776436-2595"], "new_count": -1})


def test_get_settings(uci_configs_init, infrastructure, start_buses):
    res = infrastructure.process_message(
        {"module": "router_notifications", "action": "get_settings", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "emails" in res["data"].keys()
    assert "reboots" in res["data"].keys()


def test_update_settings(uci_configs_init, infrastructure, start_buses):
    filters = [("router_notifications", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "update_settings",
                "kind": "request",
                "data": data,
            }
        )
        assert res == {
            u"action": u"update_settings",
            u"data": {u"result": True},
            u"kind": u"reply",
            u"module": u"router_notifications",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "router_notifications"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(notifications[-1]["data"], data)

        res = infrastructure.process_message(
            {"module": "router_notifications", "action": "get_settings", "kind": "request"}
        )
        assert match_subdict(data, res["data"])

    update({"emails": {"enabled": False}, "reboots": {"delay": 1, "time": "03:30"}})

    update(
        {
            "emails": {
                "enabled": True,
                "common": {
                    "to": ["user1@example.com", "user2@example.com"],
                    "severity_filter": 1,
                    "send_news": False,
                },
                "smtp_type": "turris",
                "smtp_turris": {"sender_name": "name1"},
            },
            "reboots": {"delay": 0, "time": "04:20"},
        }
    )
    update(
        {
            "emails": {
                "enabled": True,
                "common": {
                    "to": ["user1@example.com", "user2@example.com"],
                    "severity_filter": 1,
                    "send_news": False,
                },
                "smtp_type": "turris",
                "smtp_turris": {"sender_name": "name2"},
            },
            "reboots": {"delay": 0, "time": "04:20"},
        }
    )

    update(
        {
            "emails": {
                "enabled": True,
                "common": {
                    "to": ["user3@example.com", "user2@example.com"],
                    "severity_filter": 2,
                    "send_news": True,
                },
                "smtp_type": "custom",
                "smtp_custom": {
                    "from": "turris1@example.com",
                    "host": "example1.com",
                    "port": 25,
                    "security": "none",
                    "username": "user1",
                    "password": "pass1",
                },
            },
            "reboots": {"delay": 2, "time": "05:10"},
        }
    )
    update(
        {
            "emails": {
                "enabled": True,
                "common": {
                    "to": ["user3@example.com", "user2@example.com"],
                    "severity_filter": 2,
                    "send_news": True,
                },
                "smtp_type": "custom",
                "smtp_custom": {
                    "from": "turris2@example.com",
                    "host": "example2.com",
                    "port": 26,
                    "security": "ssl",
                    "username": "user2",
                    "password": "pass2",
                },
            },
            "reboots": {"delay": 2, "time": "05:10"},
        }
    )


def test_create(stored_notifications, uci_configs_init, infrastructure, start_buses):
    def create(message, severity, immediate):
        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "list",
                "kind": "request",
                "data": {"lang": "en"},
            }
        )
        assert "notifications" in res["data"].keys()
        old_ids = [e["id"] for e in res["data"]["notifications"]]

        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "create",
                "kind": "request",
                "data": {"severity": severity, "msg": message, "immediate": immediate},
            }
        )
        assert res == {
            u"module": u"router_notifications",
            u"action": u"create",
            u"kind": u"reply",
            u"data": {u"result": True},
        }

        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "list",
                "kind": "request",
                "data": {"lang": "en"},
            }
        )

        assert "notifications" in res["data"].keys()
        new_ids = [e["id"] for e in res["data"]["notifications"]]
        assert len(new_ids) == len(old_ids) + 1
        new_msg = [
            e for e in res["data"]["notifications"] if e["id"] in set(new_ids) - set(old_ids)
        ][0]
        assert new_msg["severity"] == severity
        assert new_msg["msg"] == message

    create("msg1", "news", True)
    create("msg2", "restart", False)
    create("msg3", "update", False)
    create("msg4", "error", False)


def test_create_notification(notify_cmd, uci_configs_init, infrastructure, start_buses):
    # these notifications are meant to be send by external program
    # to imitate such behavior just call cmd foris-notify
    filters = [("router_notifications", "create")]

    def create_notification(data):
        notifications = infrastructure.get_notifications(filters=filters)
        retval, _, _ = notify_cmd("router_notifications", "create", data)
        assert retval == 0
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "router_notifications"
        assert notifications[-1]["action"] == "create"
        assert notifications[-1]["kind"] == "notification"
        assert notifications[-1]["data"] == data

    create_notification({"severity": "restart", "id": "1518776436-2595", "new_count": 1})
    create_notification({"severity": "news", "id": "1518776436-2596", "new_count": 2})
    create_notification({"severity": "update", "id": "1518776436-2597", "new_count": 3})
    create_notification({"severity": "error", "id": "1518776436-2598", "new_count": 4})


def test_update_email_settings(uci_configs_init, infrastructure, start_buses):
    filters = [("router_notifications", "update_email_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "update_email_settings",
                "kind": "request",
                "data": data,
            }
        )
        assert res == {
            u"action": u"update_email_settings",
            u"data": {u"result": True},
            u"kind": u"reply",
            u"module": u"router_notifications",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "router_notifications"
        assert notifications[-1]["action"] == "update_email_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(notifications[-1]["data"], data)

        res = infrastructure.process_message(
            {"module": "router_notifications", "action": "get_settings", "kind": "request"}
        )
        assert match_subdict(data, res["data"]["emails"])

    update({"enabled": False})
    update(
        {
            "enabled": True,
            "common": {
                "to": ["user1@example.com", "user2@example.com"],
                "severity_filter": 1,
                "send_news": False,
            },
            "smtp_type": "turris",
            "smtp_turris": {"sender_name": "name1"},
        }
    )
    update(
        {
            "enabled": True,
            "common": {
                "to": ["user1@example.com", "user2@example.com"],
                "severity_filter": 1,
                "send_news": False,
            },
            "smtp_type": "turris",
            "smtp_turris": {"sender_name": "name2"},
        }
    )

    update(
        {
            "enabled": True,
            "common": {
                "to": ["user3@example.com", "user2@example.com"],
                "severity_filter": 2,
                "send_news": True,
            },
            "smtp_type": "custom",
            "smtp_custom": {
                "from": "turris1@example.com",
                "host": "example1.com",
                "port": 25,
                "security": "none",
                "username": "user1",
                "password": "pass1",
            },
        }
    )
    update(
        {
            "enabled": True,
            "common": {
                "to": ["user3@example.com", "user2@example.com"],
                "severity_filter": 2,
                "send_news": True,
            },
            "smtp_type": "custom",
            "smtp_custom": {
                "from": "turris2@example.com",
                "host": "example2.com",
                "port": 26,
                "security": "ssl",
                "username": "user2",
                "password": "pass2",
            },
        }
    )


def test_update_reboot_settings(uci_configs_init, infrastructure, start_buses):
    filters = [("router_notifications", "update_reboot_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
        res = infrastructure.process_message(
            {
                "module": "router_notifications",
                "action": "update_reboot_settings",
                "kind": "request",
                "data": data,
            }
        )
        assert res == {
            u"action": u"update_reboot_settings",
            u"data": {u"result": True},
            u"kind": u"reply",
            u"module": u"router_notifications",
        }
        notifications = infrastructure.get_notifications(notifications, filters=filters)
        assert notifications[-1]["module"] == "router_notifications"
        assert notifications[-1]["action"] == "update_reboot_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(notifications[-1]["data"], data)

        res = infrastructure.process_message(
            {"module": "router_notifications", "action": "get_settings", "kind": "request"}
        )
        assert match_subdict(data, res["data"]["reboots"])

    update({"delay": 1, "time": "03:30"})
    update({"delay": 0, "time": "04:20"})
    update({"delay": 2, "time": "05:10"})
