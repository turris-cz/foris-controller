#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
from .utils import match_subdict


def test_get_settings(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "lan",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "ip" in res["data"].keys()
    assert "netmask" in res["data"].keys()
    assert "dhcp" in res["data"].keys()
    assert "enabled" in res["data"]["dhcp"].keys()
    assert "guest_network" in res["data"].keys()
    assert "enabled" in res["data"]["guest_network"].keys()


def test_update_settings(infrastructure, ubusd_test):

    def update(data):
        notifications = infrastructure.get_notifications()
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'lan'
        }
        notifications = infrastructure.get_notifications(notifications)
        assert notifications[-1]["module"] == "lan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message({
            "module": "lan",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["module"] == "lan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(data, res["data"])

    update({
        u"ip": u"192.168.5.8",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.0.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
        },
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.2.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.8.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": False,
            },
        },
    })
    update({
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.9.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": True,
                u"download": 1200,
                u"upload": 1000,
            },
        },
    })
