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

from foris_controller.exceptions import UciRecordNotFound

from foris_controller_testtools.fixtures import (
    only_backends, uci_configs_init, infrastructure, ubusd_test, lock_backend, init_script_result
)
from foris_controller_testtools.utils import (
    match_subdict, sh_was_called, get_uci_module, check_service_result
)


def test_get_settings(uci_configs_init, infrastructure, ubusd_test):
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
    assert "start" in res["data"]["dhcp"].keys()
    assert "limit" in res["data"]["dhcp"].keys()
    assert set(res["data"].keys()) == {"ip", "netmask", "dhcp"}


def test_update_settings(uci_configs_init, infrastructure, ubusd_test):
    filters = [("lan", "update_settings")]

    def update(data):
        notifications = infrastructure.get_notifications(filters=filters)
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
        notifications = infrastructure.get_notifications(notifications, filters=filters)
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
    })
    update({
        u"ip": u"10.0.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
    })
    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.252.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
        },
    })
    update({
        u"ip": u"10.2.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
    })


def test_wrong_update(uci_configs_init, infrastructure, ubusd_test):

    def update(data):
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert "errors" in res

    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": False,
            u"start": 10,
            u"limit": 50,
        },
    })
    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.250.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
        },
    })
    update({
        u"ip": u"10.1.0.256",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
        },
    })
