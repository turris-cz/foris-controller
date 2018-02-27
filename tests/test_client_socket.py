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

import os
import pytest


from foris_controller_testtools.fixtures import infrastructure_with_client_socket, ubusd_test


@pytest.fixture(scope="module")
def extra_module_paths():
    """ Override of extra module paths fixture
    """
    return [
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_modules", "echo")
    ]


def test_request(infrastructure_with_client_socket, ubusd_test):
    def request(req, reply):
        res = infrastructure_with_client_socket.send_request_via_client_socket(req)
        assert res == reply

    request({
        "module": "echo",
        "action": "echo",
        "kind": "request",
        "data": {"request_msg": {"text": "testmsg1"}}
    }, {
        "module": "echo",
        "action": "echo",
        "kind": "reply",
        "data": {"reply_msg": {"text": "testmsg1"}}
    })

    request({
        "module": "echo",
        "action": "echo",
        "kind": "request",
        "data": {"request_msg": {"text": "testmsg2"}}
    }, {
        "module": "echo",
        "action": "echo",
        "kind": "reply",
        "data": {"reply_msg": {"text": "testmsg2"}}
    })


def test_notification(infrastructure_with_client_socket, ubusd_test):
    def notify(msg):
        notifications = infrastructure_with_client_socket.get_notifications()
        infrastructure_with_client_socket.send_notification_via_client_socket(msg)
        notifications = infrastructure_with_client_socket.get_notifications(notifications)
        assert notifications[-1] == msg

    notify({
        "module": "echo",
        "action": "echo",
        "kind": "notification",
    })

    notify({
        "module": "echo",
        "action": "echo2",
        "kind": "notification",
        "data": {"msg": "notification text"}
    })
