# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2022, CZ.NIC z.s.p.o. (https://www.nic.cz/)

import json
import logging
import typing

from foris_controller_backends.cmdline import BaseCmdLine

logger = logging.getLogger(__name__)


class UbusBackend(BaseCmdLine):
    UBUS_CMD = "/bin/ubus"

    @staticmethod
    def call_ubus(ubus_object: str, method: str, data: typing.Optional[dict] = None) -> typing.Optional[dict]:
        """Method to call ubus executable and get data/trigger action provided by ubus objects.

        Try to return:
        * data from ubus object
        * fallback to empty dictionary in case ubus object doesn't return any
        * None in case of runtime failure during querying the ubus

        For example:
        `ubus call umdns reload` does not provide any output, neither it is really expected for method 'reload'.
        """
        cmd = [UbusBackend.UBUS_CMD, "call", ubus_object, method]
        if data:
            cmd.append(json.dumps(data))

        retval, stdout, stderr = BaseCmdLine._run_command(*cmd)
        if retval != 0:
            logger.warning("Failure during ubus call: %s", stderr)
            return None

        try:
            decoded = stdout.decode("utf-8")
            if decoded:
                return json.loads(decoded)
            else:
                return {}
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode response from ubus: %r", exc)
            return None
