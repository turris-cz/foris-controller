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

import json
import pytest
import subprocess

from foris_schema import ForisValidator

from foris_controller.utils import get_validator_dirs

from .fixtures import backend, infrastructure, ubusd_test


def notify_cmd(infras, module, action, data, validate=True):
    args = [
        "bin/foris-notify", "-m", module, "-a", action,
        infras.name, "--path", infras.notification_sock_path, json.dumps(data)
    ]
    if not validate:
        args.insert(1, "-n")
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


@pytest.fixture(scope="module")
def notify_api(infrastructure):
    if infrastructure.name == "ubus":
        from foris_controller.buses.ubus import UbusNotificationSender
        sender = UbusNotificationSender(infrastructure.notification_sock_path)

    elif infrastructure.name == "unix-socket":
        from foris_controller.buses.unix_socket import UnixSocketNotificationSender
        sender = UnixSocketNotificationSender(infrastructure.notification_sock_path)


    def notify(module, action, notification, validate=True):
        if validate:
            validator = ForisValidator(*get_validator_dirs([module]))
        else:
            validator = None
        sender.notify(module, action, notification, validator)

    yield notify
    sender.disconnect()


def test_notify_cmd(infrastructure, ubusd_test):
    retval, stdout, stderr = notify_cmd(
        infrastructure, "web", "set_language", {"language": "en"}, True)
    assert retval == 0

    assert infrastructure.last_notification() == {
        u"module": u"web",
        u"action": u"set_language",
        u"kind": u"notification",
        u"data": {u"language": u"en"},
    }

    retval, stdout, stderr = notify_cmd(
        infrastructure, "web", "set_language", {"language": "en", "invalid": True}, True)
    assert retval == 1
    assert u"ValidationError" in stderr
    assert infrastructure.notification_empty()

    retval, stdout, stderr = notify_cmd(
        infrastructure, "web", "set_language", {"language": "en", "invalid": True}, False)
    assert retval == 0

    assert infrastructure.last_notification() == {
        u"module": u"web",
        u"action": u"set_language",
        u"kind": u"notification",
        u"data": {u"language": u"en", u"invalid": True},
    }


def test_notify_api(infrastructure, ubusd_test, notify_api):
    import time
    notify = notify_api
    notify("web", "set_language", {"language": "en"}, True)
    time.sleep(0.2)
    assert infrastructure.last_notification() == {
        u"module": u"web",
        u"action": u"set_language",
        u"kind": u"notification",
        u"data": {u"language": u"en"},
    }

    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        notify("web", "set_language", {"language": "en", "invalid": True}, True)

    notify("web", "set_language", {"language": "en", "invalid": True}, False)
    time.sleep(0.2)
    assert infrastructure.last_notification() == {
        u"module": u"web",
        u"action": u"set_language",
        u"kind": u"notification",
        u"data": {u"language": u"en", u"invalid": True},
    }
