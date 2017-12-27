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

from .fixtures import backend, infrastructure, ubusd_test


def test_get_registered(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "data_collect",
        "action": "get_registered",
        "kind": "request"
    })

    assert "errors" in res["data"].keys()
    assert "Incorrect input." in res["data"]["errors"][0]["description"]

    res = infrastructure.process_message({
        "module": "data_collect",
        "action": "get_registered",
        "kind": "request",
        "data": {
        }
    })
    assert "errors" in res["data"].keys()
    assert "Incorrect input." in res["data"]["errors"][0]["description"]

    res = infrastructure.process_message({
        "module": "data_collect",
        "action": "get_registered",
        "kind": "request",
        "data": {
            "email": "test@test.test",
            "language": "en"
        }
    })
    assert "status" in res["data"].keys()


def test_get(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "data_collect",
        "action": "get",
        "kind": "request"
    })
    assert "agreed" in res["data"].keys()


def test_set(infrastructure, ubusd_test):

    def set_agreed(agreed):
        notifications = infrastructure.get_notifications()
        res = infrastructure.process_message({
            "module": "data_collect",
            "action": "set",
            "kind": "request",
            "data": {
                "agreed": agreed
            }
        })
        assert res == {
            u'action': u'set',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'data_collect'
        }
        notifications = infrastructure.get_notifications(notifications)
        assert notifications[-1] == {
            u"module": u"data_collect",
            u"action": u"set",
            u"kind": u"notification",
            u"data": {
                u"agreed": agreed,
            }
        }
        res = infrastructure.process_message({
            "module": "data_collect",
            "action": "get",
            "kind": "request"
        })
        assert res == {
            u"module": u"data_collect",
            u"action": u"get",
            u"kind": u"reply",
            u"data": {
                u"agreed": agreed,
            }
        }

    set_agreed(True)
    set_agreed(False)
    set_agreed(True)
    set_agreed(False)
