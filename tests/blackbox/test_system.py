#
# foris-controller
# Copyright (C) 2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller_testtools.fixtures import UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import get_uci_module


def _set_hostname(infrastructure, hostname: str) -> dict:
    res = infrastructure.process_message(
        {
            "module": "system",
            "action": "set_hostname",
            "kind": "request",
            "data": {
                "hostname": hostname
            }
        }
    )
    return res


def _get_hostname(infrastructure) -> str:
    res = infrastructure.process_message(
        {"module": "system", "action": "get_hostname", "kind": "request"}
    )
    assert "errors" not in res.keys()
    return res["data"]["hostname"]


@pytest.mark.parametrize('hostname', ['','My custom hostname%'])
def test_set_short_or_invalid_hostname(infrastructure, hostname) -> None:
    """ Assert that hostname string is not valid. """
    res = _set_hostname(infrastructure, hostname)
    assert "errors" in res.keys()
    err = res['errors'][0]['stacktrace']
    assert f"ValidationError: '{hostname}' does not match '^[A-Za-z-_0-9]{{1,63}}$'" in err


def test_get_hostname(infrastructure):
    """ Test getting hostname. """
    hostname = _get_hostname(infrastructure)
    assert hostname == 'turris'


def test_set_and_check_hostname(infrastructure):
    """ Test setting and getting `hostname` via message-bus. """
    new_hostname = 'furry'
    success = _set_hostname(infrastructure, new_hostname)
    assert "errors" not in success.keys()
    assert success['data']["result"] is True

    ret_hostname = _get_hostname(infrastructure)
    assert new_hostname == ret_hostname


@pytest.mark.only_backends(["openwrt"])
def test_set_and_check_with_uci(infrastructure, uci_configs_init):
    """ Test setting and getting `hostname` via uci interface. """
    uci = get_uci_module(infrastructure.name)

    new_hostname = 'blurry'
    _set_hostname(infrastructure, new_hostname)

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()
    hostname_uci = uci.get_option_anonymous(data, "system", "system", 0, "hostname")
    assert new_hostname == hostname_uci


@pytest.mark.only_backends(["openwrt"])
def test_get_hostname_irregular(infrastructure, uci_configs_init):
    """ Irregular hostname set in UCI should not fail on validation. """

    uci = get_uci_module(infrastructure.name)

    irregular_hostname = r"Hostname/with%irregularities"

    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        backend.del_option("system", "@system[0]", "hostname")
        backend.set_option("system", "@system[0]", "hostname", irregular_hostname)

    res = _get_hostname(infrastructure)
    assert res == irregular_hostname
