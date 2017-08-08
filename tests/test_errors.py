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

def test_wrong_input_format(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "non-existing",
        "action": "get",
        "kind": "request",
    })
    assert res == {
        u'action': u'get',
        u'data': {u'errors': [u'Incorrect input.']},
        u'kind': u'request',
        u'module': u'non-existing'
    }

def test_wrong_input_kind(infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "about",
        "action": "get",
        "kind": "reply",
        "data": {
            "model": "Turris Omnia",
            "board_name": "rtrom01",
            "kernel": "4.4.77-967673b9d511e4292e3bcb76c9e064bc-0",
            "os_version": "3.7",
            "serial": "0000000B00009CD6",
            "temperature": {"CPU": 73},
            "firewall_status": {"working": False, "last_check": 1501857960},
            "ucollect_status": {"working": True, "last_check": 1501857970},
        },
    })
    assert res == {
            u'action': u'get',
            u'data': {
                u'errors': [
                    u'Wrong message kind (only request are allowed).'
                ]
            },
            u'kind': u'reply',
            u'module': u'about'
    }

