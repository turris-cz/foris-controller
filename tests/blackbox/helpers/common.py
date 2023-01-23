# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2023, CZ.NIC z.s.p.o. (https://www.nic.cz/)

from types import ModuleType

from foris_controller_testtools.fixtures import UCI_CONFIG_DIR_PATH


def get_uci_backend_data(uci: ModuleType) -> dict:
    """Fetch raw config data from UCI backend."""
    with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
        data = backend.read()

    return data


def query_infrastructure(infrastructure, message: dict, expect_success: bool = True) -> dict:
    """Send message through infrastructure and check for errors based on expected result (success, failure).

    Succesful query should not contain errors, while failure should contain errors.
    Return whole response (dict), if assertions passes.
    """
    res = infrastructure.process_message(message)
    if not expect_success:
        assert "errors" in res.keys()
    else:
        assert "errors" not in res.keys()

    return res
