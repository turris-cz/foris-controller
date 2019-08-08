import pytest

from foris_controller_testtools.fixtures import (
    only_message_buses,
    backend,
    infrastructure,
    start_buses,
    mosquitto_test,
    ubusd_test,
    notify_api,
)


def test_get_slices(infrastructure, start_buses):
    res = infrastructure.process_message(
        {"module": "sample", "action": "get_slices", "kind": "request"}
    )
    assert "error" not in res
    assert "data" in res
    assert "slices" in res["data"]


@pytest.mark.parametrize("slices", [10, 15])
def test_set_slices(infrastructure, start_buses, slices):
    notifications = infrastructure.get_notifications()
    res = infrastructure.process_message(
        {"module": "sample", "action": "set_slices", "kind": "request", "data": {"slices": slices}}
    )
    notifications = infrastructure.get_notifications(notifications)
    assert notifications[-1] == {
        u"module": u"sample",
        u"action": u"set_slices",
        u"kind": u"notification",
        u"data": {u"slices": slices},
    }
    res = infrastructure.process_message(
        {"module": "sample", "action": "get_slices", "kind": "request"}
    )
    assert res["data"]["slices"] == slices


@pytest.mark.parametrize("slices", [10, 15])
def test_reload_chart_notification(notify_api, infrastructure, start_buses, slices):
    filters = [("sample", "reload_chart")]
    notify = notify_api
    notifications = infrastructure.get_notifications(filters=filters)
    notify("sample", "reload_chart", {})
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": u"sample",
        u"action": u"reload_chart",
        u"kind": u"notification",
        u"data": {},
    }


def test_list(infrastructure, start_buses):
    res = infrastructure.process_message({"module": "sample", "action": "list", "kind": "request"})
    assert "records" in res["data"]


@pytest.mark.only_message_buses(["mqtt"])
def test_timestamp_announcements(mosquitto_test, start_buses, infrastructure):
    filters = [("sample", "announce_time")]

    notifications = infrastructure.get_notifications([], filters=filters)
    assert "timestamp" in notifications[-1]["data"]
    timestamp1 = notifications[-1]["data"]["timestamp"]

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert "timestamp" in notifications[-1]["data"]
    timestamp2 = notifications[-1]["data"]["timestamp"]

    assert timestamp1 < timestamp2
    assert round(timestamp2 - timestamp1, 0) == 2.0  # there is 2s delay in announcer
