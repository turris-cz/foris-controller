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
import time

import pytest
from foris_controller_testtools.fixtures import FILE_ROOT_PATH as TMP_FILE_ROOT_PATH
from foris_controller_testtools.utils import FileFaker

FILE_ROOT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_about_files")


@pytest.fixture(scope="function")
def uptime_file(file_root_init):
    """fake /proc/uptime inside the copied file root (read by the openwrt backend)"""
    with FileFaker(TMP_FILE_ROOT_PATH, "/proc/uptime", False, "12345.67 98765.43\n"):
        yield


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get(uci_configs_init, uptime_file, infrastructure):
    res = infrastructure.process_message({"module": "about", "action": "get", "kind": "request"})
    assert res.keys() == {"action", "kind", "data", "module"}
    assert res["data"].keys() == {"model", "serial", "os_version", "os_branch", "kernel", "uptime"}
    assert res["data"]["os_branch"].keys() == {"mode", "value"}
    assert isinstance(res["data"]["uptime"], int)
    assert res["data"]["uptime"] >= 0


@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_registration_number(infrastructure):
    res = infrastructure.process_message({"module": "about", "action": "get_registration_number", "kind": "request"})
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert set(res["data"].keys()) == {"registration_number"}


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


@pytest.mark.parametrize(
    "device,expected_result",
    [
        ("shield", "shield"),
        ("mox", None),
    ],
)
@pytest.mark.only_backends(["openwrt"])
@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_router_customization(
    uci_configs_init, uptime_file, infrastructure, prepare_turrishw, device, expected_result
):
    prepare_turrishw(device)
    res = infrastructure.process_message(
        {
            "module": "about",
            "action": "get",
            "kind": "request",
        }
    )

    assert "errors" not in res.keys()
    if expected_result:
        assert "customization" in res["data"]
        assert res["data"]["customization"] == expected_result


@pytest.mark.parametrize(
    "content,expected",
    (
        ("12345.67 98765.43\n", 12346),
        ("0.00 0.00\n", 0),
        ("100 200\n", 100),
    ),
    ids=["rounds-up", "zero", "no-fraction"],
)
@pytest.mark.only_backends(["openwrt"])
@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_uptime(uci_configs_init, file_root_init, infrastructure, content, expected):
    with FileFaker(TMP_FILE_ROOT_PATH, "/proc/uptime", False, content):
        res = infrastructure.process_message({"module": "about", "action": "get", "kind": "request"})

    assert "errors" not in res.keys()
    assert res["data"]["uptime"] == expected


@pytest.mark.only_backends(["mock"])
@pytest.mark.file_root_path(FILE_ROOT_PATH)
def test_get_uptime_grows(uci_configs_init, infrastructure):
    first = infrastructure.process_message({"module": "about", "action": "get", "kind": "request"})
    time.sleep(1.1)
    second = infrastructure.process_message({"module": "about", "action": "get", "kind": "request"})

    assert second["data"]["uptime"] > first["data"]["uptime"]
