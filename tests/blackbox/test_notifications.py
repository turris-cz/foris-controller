#
# foris-controller
# Copyright (C) 2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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


@pytest.fixture(scope="module")
def extra_module_paths():
    """ Override of extra module paths fixture
    """
    return [os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_modules", "echo")]


def test_notify_cmd(notify_cmd, uci_configs_init, infrastructure):
    filters = [("web", "set_language")]
    notifications = infrastructure.get_notifications(filters=filters)
    retval, stdout, stderr = notify_cmd("web", "set_language", {"language": "en"}, True)
    assert retval == 0

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "web",
        "action": "set_language",
        "kind": "notification",
        "data": {"language": "en"},
    }

    retval, stdout, stderr = notify_cmd(
        "web", "set_language", {"language": "en", "invalid": True}, True
    )
    assert retval == 1
    assert b"ValidationError" in stderr
    assert notifications == infrastructure.get_notifications(filters=filters)

    retval, stdout, stderr = notify_cmd(
        "web", "set_language", {"language": "en", "invalid": True}, False
    )
    assert retval == 0

    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "web",
        "action": "set_language",
        "kind": "notification",
        "data": {"language": "en", "invalid": True},
    }


def test_notify_api(uci_configs_init, infrastructure, notify_api):
    filters = [("web", "set_language"), ("echo", "echo")]
    notify = notify_api
    notifications = infrastructure.get_notifications(filters=filters)
    notify("web", "set_language", {"language": "en"}, True)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "web",
        "action": "set_language",
        "kind": "notification",
        "data": {"language": "en"},
    }

    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        notify("web", "set_language", {"language": "en", "invalid": True}, True)
    assert notifications == infrastructure.get_notifications(filters=filters)

    notify("web", "set_language", {"language": "en", "invalid": True}, False)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {
        "module": "web",
        "action": "set_language",
        "kind": "notification",
        "data": {"language": "en", "invalid": True},
    }

    notify("echo", "echo")
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1] == {"module": "echo", "action": "echo", "kind": "notification"}
