# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2022, CZ.NIC z.s.p.o. (https://www.nic.cz/)

import os
from pathlib import Path

import pytest
from foris_controller_testtools.fixtures import lock_backend

CMDLINE_ROOT = Path(__file__).resolve().parent / "test_root"


@pytest.fixture(scope="function")
def custom_cmdline_root():
    os.environ["FORIS_CMDLINE_ROOT"] = str(CMDLINE_ROOT)
    yield CMDLINE_ROOT
    del os.environ["FORIS_CMDLINE_ROOT"]


@pytest.fixture
def ubus_backend(lock_backend):
    from foris_controller.app import app_info

    app_info["lock_backend"] = lock_backend
    from foris_controller_backends import ubus

    yield ubus.UbusBackend


def test_ubus_call_with_return_value(custom_cmdline_root, ubus_backend):
    """Check that ubus query which should return data, will return some data."""
    data = ubus_backend.call_ubus(ubus_object="iwinfo", method="info", data={"device": "radio0"})

    assert isinstance(data, dict)
    assert bool(data)  # we don't care about particular values, there just have to be something in dict


def test_ubus_call_without_return_value(custom_cmdline_root, ubus_backend):
    """Check that ubus query, which does not provide output data, will return no data (empty dict).

    Empty dict means that, apart from response data, ubus query was successful.
    """
    data = ubus_backend.call_ubus(ubus_object="dummy_noreturn", method="reload")

    assert data == {}


def test_ubus_call_nonexisting_object(custom_cmdline_root, ubus_backend):
    """Check that response from nonexisting ubus object is None.

    `None` should be returned only in case of ubus call failure:
    e.g. runtime failure, non-existing object or method, JSON response decoding fails, etc.
    """
    data = ubus_backend.call_ubus(ubus_object="nonsense", method="foomethod")

    assert data is None
