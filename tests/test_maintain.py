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

import base64
import os
import pytest

from foris_controller_testtools.fixtures import (
    infrastructure, uci_configs_init, ubusd_test, file_root_init
)

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_maintain_files")


def test_reboot(uci_configs_init, infrastructure, ubusd_test):
    notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "reboot",
        "kind": "request",
    })
    assert "new_ips" in res["data"].keys()
    notifications = infrastructure.get_notifications(notifications)
    assert "new_ips" in notifications[-1]["data"].keys()


def test_generate_backup(uci_configs_init, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "generate_backup",
        "kind": "request",
    })
    assert "backup" in res["data"].keys()
    base64.b64decode(res["data"]["backup"])


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_restore_backup(file_root_init, uci_configs_init, infrastructure, ubusd_test):
    # read backup
    with open(os.path.join("/tmp/foris_files/tmp", "backup.tar.bz2.base64")) as f:
        backup = f.read()

    notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "restore_backup",
        "kind": "request",
        "data": {
            "backup": backup,
        },
    })
    assert res["data"] == {u"result": True}
    notifications = infrastructure.get_notifications()
    assert notifications[-1] == {
        u"module": u"maintain",
        u"action": u"reboot_required",
        u"kind": u"notification",
    }


def test_generate_and_restore(uci_configs_init, infrastructure, ubusd_test):
    notifications = infrastructure.get_notifications()

    res = infrastructure.process_message({
        "module": "maintain",
        "action": "generate_backup",
        "kind": "request",
    })
    assert "backup" in res["data"].keys()

    res = infrastructure.process_message({
        "module": "maintain",
        "action": "restore_backup",
        "kind": "request",
        "data": {
            "backup": res["data"]["backup"],
        },
    })
    assert res["data"] == {u"result": True}
    notifications = infrastructure.get_notifications()
    assert notifications[-1] == {
        u"module": u"maintain",
        u"action": u"reboot_required",
        u"kind": u"notification",
    }
