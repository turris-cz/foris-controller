#
# foris-controller
# Copyright (C) 2017-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import os

# load common fixtures
from foris_controller_testtools.fixtures import (
    uci_config_default_path,
    env_overrides,
    file_root,
    controller_modules,
    extra_module_paths,
    message_bus,
    backend,
    device,
    infrastructure,
    UCI_CONFIG_DIR_PATH
)

from foris_controller_testtools.utils import get_uci_module

DEFAULT_UCI_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "uci_configs", "defaults"
)


@pytest.fixture(scope="function")
def fix_mox_wan(infrastructure, device):
    """ Uci networks.wan.ifname should be eth0 on mox and eth2 on turris1x"""
    if device.startswith("mox"):
        uci = get_uci_module(infrastructure.name)
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            backend.set_option("network", "wan", "ifname", "eth0")


@pytest.fixture(scope="session")
def uci_config_default_path():
    return DEFAULT_UCI_CONFIG_DIR


@pytest.fixture(scope="session")
def cmdline_script_root():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_root")


@pytest.fixture(scope="session")
def file_root():
    # default src dirctory will be the same as for the scripts  (could be override later)
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_root")


@pytest.fixture(scope="module")
def controller_modules():
    return [
        "about",
        "web",
        "dns",
        "maintain",
        "password",
        "updater",
        "lan",
        "system",
        "time",
        "wan",
        "router_notifications",
        "wifi",
        "networks",
        "guest",
        "remote",
        "introspect",
    ]
