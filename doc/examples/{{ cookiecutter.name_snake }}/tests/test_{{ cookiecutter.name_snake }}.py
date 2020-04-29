{{ cookiecutter.license_short }}

import pytest

from foris_controller_testtools.fixtures import (
    only_message_buses,
    backend,
    infrastructure,
    notify_api,
)


def test_get_slices(infrastructure):
    res = infrastructure.process_message(
        {"module": "{{ cookiecutter.name_snake }}", "action": "get_slices", "kind": "request"}
    )
    assert "error" not in res
    assert "data" in res
    assert "slices" in res["data"]


@pytest.mark.parametrize("slices", [10, 15])
def test_set_slices(infrastructure, slices):
    filters = [("{{ cookiecutter.name_snake }}", "set_slices")]

    notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {"module": "{{ cookiecutter.name_snake }}", "action": "set_slices", "kind": "request", "data": {"slices": slices}}
    )
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        u"module": "{{ cookiecutter.name_snake }}",
        u"action": "set_slices",
        u"kind": "notification",
        u"data": {"slices": slices},
    }
    res = infrastructure.process_message(
        {"module": "{{ cookiecutter.name_snake }}", "action": "get_slices", "kind": "request"}
    )
    assert res["data"]["slices"] == slices


@pytest.mark.parametrize("slices", [10, 15])
def test_reload_chart_notification(notify_api, infrastructure, slices):
    filters = [("{{ cookiecutter.name_snake }}", "reload_chart")]
    notify = notify_api
    notifications = infrastructure.get_notifications(filters=filters)
    notify("{{ cookiecutter.name_snake }}", "reload_chart", {})
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "{{ cookiecutter.name_snake }}",
        "action": "reload_chart",
        "kind": "notification",
        "data": {},
    }


def test_list(infrastructure):
    res = infrastructure.process_message({"module": "{{ cookiecutter.name_snake }}", "action": "list", "kind": "request"})
    assert "records" in res["data"]


@pytest.mark.only_message_buses(["mqtt"])
def test_timestamp_announcements(infrastructure):
    filters = [("{{ cookiecutter.name_snake }}", "announce_time")]

    notifications = infrastructure.get_notifications([], filters=filters)
    assert "timestamp" in notifications[-1]["data"]
    timestamp1 = notifications[-1]["data"]["timestamp"]

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert "timestamp" in notifications[-1]["data"]
    timestamp2 = notifications[-1]["data"]["timestamp"]

    assert timestamp1 < timestamp2
    assert round(timestamp2 - timestamp1, 0) == 2.0  # there is 2s delay in announcer
