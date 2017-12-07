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

from .fixtures import backend, infrastructure, ubusd_test


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
