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

from .fixtures import backend, message_bus, infrastructure, ubusd_test

BACKUP = """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
ciVFA8lMq61280Ik4kAn/i7kinChIeoKRFY=
"""


def test_reboot(infrastructure, ubusd_test):
    notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "reboot",
        "kind": "request",
    })
    assert "new_ips" in res["data"].keys()
    notifications = infrastructure.get_notifications(notifications)
    assert "new_ips" in notifications[-1]["data"].keys()


def test_generate_backup(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "generate_backup",
        "kind": "request",
    })
    assert "backup" in res["data"].keys()
    base64.b64decode(res["data"]["backup"])


def test_restore_backup(infrastructure, ubusd_test):
    notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "maintain",
        "action": "restore_backup",
        "kind": "request",
        "data": {
            "backup": BACKUP,
        },
    })
    assert res["data"] == {u"result": True}
    notifications = infrastructure.get_notifications()
    assert notifications[-1] == {
        u"module": u"maintain",
        u"action": u"reboot_required",
        u"kind": u"notification",
    }


def test_generate_and_restore(infrastructure, ubusd_test):
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
