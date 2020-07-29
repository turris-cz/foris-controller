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

import os

import pytest
from foris_controller_testtools.fixtures import (
    file_root_init,
    infrastructure,
    lock_backend,
    uci_configs_init,
)
from foris_controller_testtools.utils import FileFaker

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_about_files")


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get(uci_configs_init, infrastructure):
    res = infrastructure.process_message({"module": "about", "action": "get", "kind": "request"})
    assert res.keys() == {"action", "kind", "data", "module"}
    assert res["data"].keys() == {"model", "serial", "os_version", "os_branch", "kernel"}
    assert res["data"]["os_branch"].keys() == {"mode", "value"}


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_registration_number(infrastructure):
    res = infrastructure.process_message(
        {"module": "about", "action": "get_registration_number", "kind": "request"}
    )
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {u"registration_number"}


@pytest.mark.parametrize(
    "content,output",
    (
        (
            "earlyprintk console=ttyS0,115200 rootfstype=btrfs rootdelay=2 "
            "root=b301 rootflags=subvol=@,commit=5 rw cfg80211.freg=**",
            None,
        ),
        (
            "earlyprintk console=ttyS0,115200 rootfstype=btrfs rootdelay=2 "
            " turris_lists=contracts/shield "
            "root=b301 rootflags=subvol=@,commit=5 rw cfg80211.freg=**",
            "shield",
        ),
    ),
    ids=["none", "shield"],
)
def test_get_contract(content, output, lock_backend, file_root_init):
    os.environ["FORIS_FILE_ROOT"] = FILE_ROOT_PATH
    from foris_controller.app import app_info

    app_info["lock_backend"] = lock_backend
    from foris_controller_backends.about import SystemInfoFiles

    with FileFaker(FILE_ROOT_PATH, "/proc/cmdline", False, content):
        assert SystemInfoFiles().get_contract() == output

    del os.environ["FORIS_FILE_ROOT"]
