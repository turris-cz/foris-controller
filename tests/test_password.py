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
import random
import string

from .fixtures import infrastructure, ubusd_test


def test_set_and_check_system(infrastructure, ubusd_test):
    new_pass = "".join(random.choice(string.ascii_letters) for _ in range(20))
    old_notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "password",
        "action": "set",
        "kind": "request",
        "data": {"password": base64.b64encode(new_pass), "type": "system"},
    })
    assert res == {
        u'action': u'set',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'password'
    }
    assert infrastructure.get_notifications(old_notifications)[-1] == {
        u"module": u"password",
        u"action": u"set",
        u"kind": u"notification",
        u"data": {
            u"type": u"system"
        }
    }
    res = infrastructure.process_message({
        "module": "password",
        "action": "check",
        "kind": "request",
        "data": {"password": base64.b64encode(new_pass)},
    })
    assert res["data"]["status"] != u"good"


def test_set_and_check_foris(infrastructure, ubusd_test):
    new_pass = "".join(random.choice(string.ascii_letters) for _ in range(20))
    old_notifications = infrastructure.get_notifications()
    res = infrastructure.process_message({
        "module": "password",
        "action": "set",
        "kind": "request",
        "data": {"password": base64.b64encode(new_pass), "type": "foris"},
    })
    assert res == {
        u'action': u'set',
        u'data': {u'result': True},
        u'kind': u'reply',
        u'module': u'password'
    }
    assert infrastructure.get_notifications(old_notifications)[-1] == {
        u"module": u"password",
        u"action": u"set",
        u"kind": u"notification",
        u"data": {
            u"type": u"foris"
        }
    }
    res = infrastructure.process_message({
        "module": "password",
        "action": "check",
        "kind": "request",
        "data": {"password": base64.b64encode(new_pass)},
    })
    assert res == {
        u'action': u'check',
        u'data': {u'status': u"good"},
        u'kind': u'reply',
        u'module': u'password'
    }
