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

import pytest
import random
import string

from .fixtures import backend, infrastructure, ubusd_test


@pytest.mark.parametrize("chars_len", (1024, 1024 * 1024, 10 * 1024 * 1024))
def test_long_messsages(infrastructure, ubusd_test, chars_len):
    data = {
        "random_characters": "".join(random.choice(string.ascii_letters) for _ in range(chars_len))
    }
    res = infrastructure.process_message({
        "module": "echo",
        "action": "echo",
        "kind": "request",
        "data": {"request_msg": data}
    })
    assert res["data"]["reply_msg"] == data
