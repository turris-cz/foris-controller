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


import base64
import os
import pytest
import random
import string


PASS_PATH = "/tmp/passwd_input"
FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_password_files")


@pytest.fixture
def pass_file():
    try:
        os.unlink(PASS_PATH)
    except Exception:
        pass

    yield PASS_PATH

    try:
        os.unlink(PASS_PATH)
    except Exception:
        pass


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_set_and_check_system(
    uci_configs_init, pass_file, infrastructure, device, turris_os_version
):
    filters = [("password", "set")]
    new_pass = "".join(random.choice(string.ascii_letters) for _ in range(20))
    old_notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode(new_pass.encode()).decode("utf-8"),
                "type": "system",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": True},
        "kind": "reply",
        "module": "password",
    }
    assert infrastructure.get_notifications(old_notifications, filters=filters)[-1] == {
        "module": "password",
        "action": "set",
        "kind": "notification",
        "data": {"type": "system"},
    }
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "check",
            "kind": "request",
            "data": {"password": base64.b64encode(new_pass.encode()).decode("utf-8")},
        }
    )
    assert res["data"]["status"] != "good"


@pytest.mark.parametrize("device,turris_os_version", [("mox", "4.0")], indirect=True)
def test_set_and_check_foris(
    uci_configs_init, pass_file, infrastructure, device, turris_os_version
):
    filters = [("password", "set")]
    new_pass = "".join(random.choice(string.ascii_letters) for _ in range(20))
    old_notifications = infrastructure.get_notifications(filters=filters)
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode(new_pass.encode()).decode("utf-8"),
                "type": "foris",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": True},
        "kind": "reply",
        "module": "password",
    }
    assert infrastructure.get_notifications(old_notifications, filters=filters)[-1] == {
        "module": "password",
        "action": "set",
        "kind": "notification",
        "data": {"type": "foris"},
    }
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "check",
            "kind": "request",
            "data": {"password": base64.b64encode(new_pass.encode()).decode("utf-8")},
        }
    )
    assert res == {
        "action": "check",
        "data": {"status": "good"},
        "kind": "reply",
        "module": "password",
    }


@pytest.mark.only_backends(["openwrt"])
def test_passowrd_openwrt(uci_configs_init, pass_file, infrastructure):
    new_pass = "".join(random.choice(string.ascii_letters) for _ in range(20))
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode(new_pass.encode()).decode("utf-8"),
                "type": "system",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": True},
        "kind": "reply",
        "module": "password",
    }
    with open(pass_file) as f:
        assert f.read() == ("%(password)s\n%(password)s\n" % dict(password=new_pass))


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_password_filter(uci_configs_init, pass_file, infrastructure):
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode("password_from_haas".encode()).decode("utf-8"),
                "type": "system",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": False, "list": "haas", "count": 101},
        "kind": "reply",
        "module": "password",
    }
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode("password_from_other".encode()).decode("utf-8"),
                "type": "foris",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": False, "list": "other", "count": 666},
        "kind": "reply",
        "module": "password",
    }
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode("valid".encode()).decode("utf-8"),
                "type": "system",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": True},
        "kind": "reply",
        "module": "password",
    }
    res = infrastructure.process_message(
        {
            "module": "password",
            "action": "set",
            "kind": "request",
            "data": {
                "password": base64.b64encode("valid".encode()).decode("utf-8"),
                "type": "foris",
            },
        }
    )
    assert res == {
        "action": "set",
        "data": {"result": True},
        "kind": "reply",
        "module": "password",
    }
