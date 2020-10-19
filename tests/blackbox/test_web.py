#
# foris-controller
# Copyright (C) 2020-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import base64
import os
import sys

import pytest
from foris_controller import profiles
from foris_controller.exceptions import UciRecordNotFound
from foris_controller_testtools.fixtures import (
    FILE_ROOT_PATH,
    UCI_CONFIG_DIR_PATH,
    device,
    file_root_init,
    infrastructure,
    init_script_result,
    network_restart_command,
    only_backends,
    turris_os_version,
    uci_configs_init,
)
from foris_controller_testtools.utils import (
    FileFaker,
    get_uci_module,
    prepare_turrishw,
    prepare_turrishw_root,
    network_restart_was_called,
)

NEW_WORKFLOWS = [
    e for e in profiles.WORKFLOWS if e not in (profiles.WORKFLOW_OLD, profiles.WORKFLOW_SHIELD)
]

START_WORKFLOWS = [profiles.WORKFLOW_OLD, profiles.WORKFLOW_UNSET]
FINISH_WORKFLOWS = [e for e in profiles.WORKFLOWS if e not in (profiles.WORKFLOW_UNSET)]

EXPECTED_WORKFLOWS = {
    ("mox", "4.0"): list(set(NEW_WORKFLOWS).intersection(set(FINISH_WORKFLOWS))),
    ("mox", "3.10.7"): [],
    ("omnia", "4.0"): [profiles.WORKFLOW_MIN, profiles.WORKFLOW_ROUTER, profiles.WORKFLOW_BRIDGE],
    ("omnia", "3.10.7"): [profiles.WORKFLOW_OLD],
    ("turris", "4.0"): [profiles.WORKFLOW_OLD],
    ("turris", "3.10.7"): [profiles.WORKFLOW_OLD],
}

RECOMMENDED_WORKFLOWS = {
    ("mox", "3.10.7"): profiles.WORKFLOW_OLD,
    ("omnia", "4.0"): profiles.WORKFLOW_ROUTER,
    ("omnia", "3.10.7"): profiles.WORKFLOW_OLD,
    ("turris", "4.0"): profiles.WORKFLOW_OLD,
    ("turris", "3.10.7"): profiles.WORKFLOW_OLD,
}


@pytest.fixture(scope="function")
def installed_languages(request):
    trans_dir = "/usr/lib/python%s.%s/site-packages/foris/langs/" % (
        sys.version_info.major,
        sys.version_info.minor,
    )
    with FileFaker(FILE_ROOT_PATH, os.path.join(trans_dir, "cs.py"), False, "") as f1, FileFaker(
        FILE_ROOT_PATH, os.path.join(trans_dir, "de.py"), False, ""
    ) as f2, FileFaker(FILE_ROOT_PATH, os.path.join(trans_dir, "nb_NO.py"), False, "") as f3:
        yield f1, f2, f3


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
        ("mox", "3.10.7"),
        ("omnia", "4.0"),
        ("omnia", "3.10.7"),
        ("turris", "4.0"),
        ("turris", "3.10.7"),
    ],
    indirect=True,
)
def test_get_data(file_root_init, uci_configs_init, infrastructure, device, turris_os_version):
    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {
        "language",
        "reboot_required",
        "notification_count",
        "updater_running",
        "guide",
        "password_ready",
        "turris_os_version",
        "device",
    }
    assert len(res["data"]["language"]) in [2, 5]  # en, en_US
    assert res["data"]["notification_count"] >= 0
    assert "enabled" in res["data"]["guide"]
    assert "passed" in res["data"]["guide"]
    assert "workflow" in res["data"]["guide"]
    assert "workflow_steps" in res["data"]["guide"]


@pytest.mark.parametrize("code", ["cs", "nb_NO"])
def test_set_language(installed_languages, code, file_root_init, uci_configs_init, infrastructure):
    filters = [("web", "set_language")]
    old_notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {"module": "web", "action": "set_language", "kind": "request", "data": {"language": code}}
    )
    assert res == {
        "action": "set_language",
        "data": {"result": True},
        "kind": "reply",
        "module": "web",
    }
    assert infrastructure.get_notifications(old_notifications, filters=filters)[-1] == {
        "module": "web",
        "action": "set_language",
        "kind": "notification",
        "data": {"language": code},
    }


def test_set_language_missing(
    installed_languages, file_root_init, uci_configs_init, infrastructure
):
    res = infrastructure.process_message(
        {"module": "web", "action": "set_language", "kind": "request", "data": {"language": "zz"}}
    )
    assert res == {
        "action": "set_language",
        "data": {"result": False},
        "kind": "reply",
        "module": "web",
    }


def test_list_languages(installed_languages, file_root_init, uci_configs_init, infrastructure):
    res = infrastructure.process_message(
        {"module": "web", "action": "list_languages", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "languages" in res["data"].keys()
    assert set(res["data"]["languages"]) == {"en", "cs", "de", "nb_NO"}


def test_set_language_missing_data(
    installed_languages, file_root_init, uci_configs_init, infrastructure
):
    res = infrastructure.process_message(
        {"module": "web", "action": "set_language", "kind": "request"}
    )
    assert "errors" in res


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
        ("mox", "3.10.7"),
        ("omnia", "4.0"),
        ("omnia", "3.10.7"),
        ("turris", "4.0"),
        ("turris", "3.10.7"),
    ],
    indirect=True,
)
def test_get_guide(file_root_init, uci_configs_init, infrastructure, device, turris_os_version):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "web", "action": "get_guide", "kind": "request"}
    )

    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {
        "current_workflow",
        "available_workflows",
        "recommended_workflow",
    }


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "3.10.7"),
        ("omnia", "4.0"),
        ("omnia", "3.10.7"),
        ("turris", "4.0"),
        ("turris", "3.10.7"),
    ],
    indirect=True,
)
@pytest.mark.only_backends(["openwrt"])
def test_get_guide_openwrt(
    file_root_init, uci_configs_init, infrastructure, device, turris_os_version
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "web", "action": "get_guide", "kind": "request"}
    )
    assert set(res["data"]["available_workflows"]) == set(
        EXPECTED_WORKFLOWS[device, turris_os_version]
    )
    assert res["data"]["recommended_workflow"] == RECOMMENDED_WORKFLOWS[device, turris_os_version]


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.only_backends(["openwrt"])
def test_get_guide_mox_variants(
    file_root_init, uci_configs_init, infrastructure, device, turris_os_version
):

    prepare_turrishw("mox")
    res = infrastructure.process_message(
        {"module": "web", "action": "get_guide", "kind": "request"}
    )
    assert set(res["data"]["available_workflows"]) == {
        profiles.WORKFLOW_MIN,
        profiles.WORKFLOW_BRIDGE,
    }
    assert res["data"]["recommended_workflow"] == profiles.WORKFLOW_BRIDGE

    prepare_turrishw("mox+C")
    res = infrastructure.process_message(
        {"module": "web", "action": "get_guide", "kind": "request"}
    )
    assert set(res["data"]["available_workflows"]) == {
        profiles.WORKFLOW_MIN,
        profiles.WORKFLOW_ROUTER,
        profiles.WORKFLOW_BRIDGE,
    }
    assert res["data"]["recommended_workflow"] == profiles.WORKFLOW_ROUTER

    prepare_turrishw("mox+EEC")
    res = infrastructure.process_message(
        {"module": "web", "action": "get_guide", "kind": "request"}
    )
    assert set(res["data"]["available_workflows"]) == {
        profiles.WORKFLOW_MIN,
        profiles.WORKFLOW_ROUTER,
        profiles.WORKFLOW_BRIDGE,
    }
    assert res["data"]["recommended_workflow"] == profiles.WORKFLOW_ROUTER


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_update_guide(file_root_init, uci_configs_init, infrastructure, device, turris_os_version):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"enabled": True, "workflow": profiles.WORKFLOW_OLD},  # doesn't matter which
        }
    )

    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {"result"}


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
        ("mox", "3.10.7"),
        ("omnia", "4.0"),
        ("omnia", "3.10.7"),
        ("turris", "4.0"),
        ("turris", "3.10.7"),
    ],
    indirect=True,
)
@pytest.mark.only_backends(["openwrt"])
@pytest.mark.parametrize("workflow", list(profiles.WORKFLOWS))
def test_update_guide_openwrt(
    file_root_init,
    init_script_result,
    uci_configs_init,
    infrastructure,
    network_restart_command,
    workflow,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    try:
        orig = uci.get_option_named(data, "foris", "wizard", "workflow")
    except UciRecordNotFound:
        orig = None

    res = infrastructure.process_message(
        {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"enabled": True, "workflow": workflow},
        }
    )
    assert res["data"]["result"] is (workflow in EXPECTED_WORKFLOWS[device, turris_os_version])

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    if res["data"]["result"]:
        assert uci.get_option_named(data, "foris", "wizard", "workflow") == workflow
        passed = uci.get_option_named(data, "foris", "wizard", "passed")
        assert "profile" in passed
        if set(profiles.WORKFLOWS[workflow]).issubset(set(passed)):
            assert uci.parse_bool(uci.get_option_named(data, "foris", "wizard", "finished"))
    else:
        try:
            new = uci.get_option_named(data, "foris", "wizard", "workflow", None)
        except UciRecordNotFound:
            new = None
        assert orig == new


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_reset_guide(file_root_init, uci_configs_init, infrastructure, device, turris_os_version):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {"module": "web", "action": "reset_guide", "kind": "request"}
    )
    assert res["data"] == {"result": True}
    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert res["data"]["guide"]["enabled"] is True
    assert res["data"]["guide"]["workflow"] in [profiles.WORKFLOW_UNSET, profiles.WORKFLOW_OLD]
    assert res["data"]["guide"]["passed"] == []

    res = infrastructure.process_message(
        {"module": "web", "action": "update_guide", "kind": "request", "data": {"enabled": False}}
    )
    assert res["data"]["result"] is True

    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert res["data"]["guide"]["enabled"] is False
    assert res["data"]["guide"]["passed"] == ["finished"]

    res = infrastructure.process_message(
        {"module": "web", "action": "reset_guide", "kind": "request"}
    )
    assert res["data"] == {"result": True}

    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert res["data"]["guide"]["enabled"] is True
    assert res["data"]["guide"]["workflow"] in [profiles.WORKFLOW_UNSET, profiles.WORKFLOW_OLD]
    assert res["data"]["guide"]["passed"] == []


@pytest.mark.parametrize(
    "device,turris_os_version",
    [
        ("mox", "4.0"),
        ("mox", "3.10.7"),
        ("omnia", "4.0"),
        ("omnia", "3.10.7"),
        ("turris", "4.0"),
        ("turris", "3.10.7"),
    ],
    indirect=True,
)
@pytest.mark.only_backends(["openwrt"])
def test_reset_guide_openwrt(
    file_root_init, uci_configs_init, infrastructure, device, turris_os_version
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)

    res = infrastructure.process_message(
        {"module": "web", "action": "reset_guide", "kind": "request"}
    )
    assert res["data"] == {"result": True}

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "foris", "wizard", "workflow") in [
        profiles.WORKFLOW_UNSET,
        profiles.WORKFLOW_OLD,
    ]
    assert not uci.parse_bool(
        uci.get_option_named(data, "foris", "wizard", "finished", uci.store_bool(False))
    )

    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert res["data"]["guide"]["enabled"] is True
    allowed_workflows = EXPECTED_WORKFLOWS[device, turris_os_version]
    possible_workflows = allowed_workflows + [profiles.WORKFLOW_UNSET]
    assert (res["data"]["guide"]["workflow"] in possible_workflows) or not allowed_workflows
    assert res["data"]["guide"]["passed"] == []

    res = infrastructure.process_message(
        {"module": "web", "action": "update_guide", "kind": "request", "data": {"enabled": False}}
    )
    assert res["data"]["result"]

    if allowed_workflows:
        res = infrastructure.process_message(
            {"module": "web", "action": "get_data", "kind": "request"}
        )
        assert res["data"]["guide"]["enabled"] is False
        assert res["data"]["guide"]["passed"] == ["finished"]
        assert res["data"]["device"] == device
        assert res["data"]["turris_os_version"] == turris_os_version

    res = infrastructure.process_message(
        {"module": "web", "action": "reset_guide", "kind": "request"}
    )
    assert res["data"] == {"result": True}

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    assert uci.get_option_named(data, "foris", "wizard", "workflow") in [
        profiles.WORKFLOW_UNSET,
        profiles.WORKFLOW_OLD,
    ]
    assert not uci.parse_bool(
        uci.get_option_named(data, "foris", "wizard", "finished", uci.store_bool(False))
    )

    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert res["data"]["guide"]["enabled"] is True
    assert (res["data"]["guide"]["workflow"] in possible_workflows) or not allowed_workflows
    assert res["data"]["guide"]["passed"] == []


@pytest.mark.parametrize("device,turris_os_version", [("omnia", "4.0")], indirect=True)
@pytest.mark.parametrize(
    "old_workflow,new_workflow",
    [
        (profiles.WORKFLOW_OLD, profiles.WORKFLOW_OLD),
        (profiles.WORKFLOW_SHIELD, profiles.WORKFLOW_SHIELD),
    ]
    + [
        (profiles.WORKFLOW_UNSET, e) for e in set(FINISH_WORKFLOWS).intersection(set(NEW_WORKFLOWS))
    ],
)
def test_walk_through_guide(
    file_root_init,
    init_script_result,
    uci_configs_init,
    infrastructure,
    network_restart_command,
    old_workflow,
    new_workflow,
    device,
    turris_os_version,
):
    if infrastructure.backend_name in ["openwrt"]:
        prepare_turrishw_root(device, turris_os_version)

    res = infrastructure.process_message(
        {
            "module": "web",
            "action": "reset_guide",
            "kind": "request",
            "data": {"new_workflow": old_workflow},
        }
    )
    assert res["data"] == {"result": True}
    res = infrastructure.process_message({"module": "web", "action": "get_data", "kind": "request"})
    assert old_workflow == res["data"]["guide"]["workflow"]

    def check_passed(passed, workflow, enabled):
        res = infrastructure.process_message(
            {"module": "web", "action": "get_data", "kind": "request"}
        )
        assert res["data"]["guide"]["enabled"] is enabled
        assert res["data"]["guide"]["workflow"] == workflow
        assert res["data"]["guide"]["passed"] == passed
        assert res["data"]["guide"]["workflow_steps"] == [e for e in profiles.WORKFLOWS[workflow]]
        if enabled:
            assert res["data"]["guide"]["next_step"] == profiles.next_step(passed, workflow)
        else:
            assert "next_step" not in res["data"]["guide"]

    def pass_step(msg, passed, target_workflow, enabled):
        res = infrastructure.process_message(msg)
        assert res["data"]["result"] is True
        check_passed(passed, target_workflow, enabled)

    def password_step(passed, target_workflow, enabled):
        # Update password
        msg = {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {"password": base64.b64encode(b"heslo").decode("utf-8"), "type": "foris"},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def profile_step(passed, target_workflow, enabled):
        # Update guide
        msg = {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"workflow": new_workflow, "enabled": True},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def networks_step(passed, target_workflow, enabled):
        # Update networks
        res = infrastructure.process_message(
            {"module": "networks", "action": "get_settings", "kind": "request"}
        )
        ports = (
            res["data"]["networks"]["wan"]
            + res["data"]["networks"]["lan"]
            + res["data"]["networks"]["guest"]
            + res["data"]["networks"]["none"]
        )
        ports = [e for e in ports if e["configurable"]]
        wan_port = ports.pop()["id"]
        lan_ports, guest_ports, none_ports = [], [], []
        for i, port in enumerate(ports):
            if i % 3 == 0:
                lan_ports.append(port["id"])
            elif i % 3 == 1:
                guest_ports.append(port["id"])
            elif i % 3 == 2:
                none_ports.append(port["id"])

        msg = {
            "module": "networks",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "firewall": {"ssh_on_wan": True, "http_on_wan": False, "https_on_wan": True},
                "networks": {
                    "wan": [wan_port],
                    "lan": lan_ports,
                    "guest": guest_ports,
                    "none": none_ports,
                },
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def wan_step(passed, target_workflow, enabled):
        # Update wan
        msg = {
            "module": "wan",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "wan_settings": {"wan_type": "dhcp", "wan_dhcp": {}},
                "wan6_settings": {"wan6_type": "none"},
                "mac_settings": {"custom_mac_enabled": False},
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def time_step(passed, target_workflow, enabled):
        # Update timezone
        msg = {
            "module": "time",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "region": "Europe",
                "country": "CZ",
                "city": "Prague",
                "timezone": "CET-1CEST,M3.5.0,M10.5.0/3",
                "time_settings": {
                    "how_to_set_time": "manual",
                    "time": "2018-01-30T15:51:30.482515",
                },
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def dns_step(passed, target_workflow, enabled):
        # Update dns
        msg = {
            "module": "dns",
            "action": "update_settings",
            "kind": "request",
            "data": {
                "forwarding_enabled": False,
                "dnssec_enabled": False,
                "dns_from_dhcp_enabled": False,
            },
        }
        pass_step(msg, passed, target_workflow, enabled)

    def updater_step(passed, target_workflow, enabled):
        # update Updater
        msg = {
            "module": "updater",
            "action": "update_settings",
            "kind": "request",
            "data": {"enabled": False},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def lan_step(passed, target_workflow, enabled):
        msg = {
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": {"mode": "unmanaged", "mode_unmanaged": {"lan_type": "dhcp", "lan_dhcp": {}}},
        }
        pass_step(msg, passed, target_workflow, enabled)

    def finished_step(passed, target_workflow, enabled):
        # Update guide
        msg = {
            "module": "web",
            "action": "update_guide",
            "kind": "request",
            "data": {"enabled": False},
        }
        pass_step(msg, passed, target_workflow, enabled)

    MAP = {
        "password": password_step,
        "profile": profile_step,
        "networks": networks_step,
        "wan": wan_step,
        "time": time_step,
        "dns": dns_step,
        "updater": updater_step,
        "lan": lan_step,
        "finished": finished_step,
    }

    passed = []

    check_passed(passed, old_workflow, True)
    active_workflow = old_workflow
    for step in profiles.WORKFLOWS[old_workflow]:
        last = set(profiles.WORKFLOWS[active_workflow]) != set(passed + [step])
        if step == profiles.STEP_PROFILE:
            active_workflow = new_workflow
            break
        MAP[step](passed + [step], active_workflow, last)
        passed.append(step)
    for step in profiles.WORKFLOWS[active_workflow]:
        if step in passed:
            continue
        last = set(profiles.WORKFLOWS[active_workflow]) != set(passed + [step])
        MAP[step](passed + [step], active_workflow, last)
        passed.append(step)


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
@pytest.mark.parametrize("password_set,wan_configured", ((True, True), (False, False)))
@pytest.mark.only_backends(["openwrt"])
def test_auto_set_unconfigured_wan(
    password_set,
    wan_configured,
    file_root_init,
    uci_configs_init,
    infrastructure,
    fix_mox_wan,
    device,
    turris_os_version,
    network_restart_command,
):
    prepare_turrishw_root(device, turris_os_version)

    uci = get_uci_module(infrastructure.name)
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.set_option("network", "wan", "proto", "none")

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    assert res["data"]["wan_settings"]["wan_type"] == "none"

    res = infrastructure.process_message(
        {"module": "web", "action": "reset_guide", "kind": "request"}
    )
    assert res["data"] == {"result": True}

    if password_set:

        res = infrastructure.process_message(
            {
                "module": "password",
                "action": "set",
                "kind": "request",
                "data": {"password": base64.b64encode(b"heslo").decode("utf-8"), "type": "foris"},
            }
        )
        assert res["data"]["result"] is True

    res = infrastructure.process_message(
        {"module": "web", "action": "update_guide", "kind": "request", "data": {"enabled": False}}
    )
    assert res["data"]["result"] is True

    res = infrastructure.process_message(
        {"module": "wan", "action": "get_settings", "kind": "request"}
    )
    if wan_configured:
        assert res["data"]["wan_settings"]["wan_type"] == "dhcp"
        assert network_restart_was_called([])
    else:
        assert res["data"]["wan_settings"]["wan_type"] == "none"
