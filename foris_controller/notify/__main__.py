#!/usr/bin/env python

#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import argparse
import logging
import json
import typing

from foris_controller import __version__
from foris_controller.utils import get_validator_dirs


available_buses: typing.List[str] = ['unix-socket']


try:
    __import__("ubus")
    available_buses.append("ubus")
except ModuleNotFoundError:
    pass


try:
    __import__("paho.mqtt.client")
    available_buses.append("mqtt")
except ModuleNotFoundError:
    pass


logger = logging.getLogger("foris_notify")


def main():
    # Parse the command line options
    parser = argparse.ArgumentParser(prog="foris-notify")
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument(
        "-m", "--module", dest="module", help="module which will be used",
        required=True, type=str,
    )
    parser.add_argument(
        "-a", "--action", dest="action", help="action which will be performed",
        required=True, type=str
    )

    subparsers = parser.add_subparsers(help="buses", dest="bus")
    subparsers.required = True

    unix_parser = subparsers.add_parser("unix-socket", help="use unix socket to send notification")
    unix_parser.add_argument("--path", default='/tmp/foris-controller.soc')
    if "ubus" in available_buses:
        ubus_parser = subparsers.add_parser("ubus", help="use ubus to send notifications")
        ubus_parser.add_argument("--path", default='/var/run/ubus.sock')

    if "mqtt" in available_buses:
        mqtt_parser = subparsers.add_parser("mqtt", help="use mqtt to send notification")
        mqtt_parser.add_argument("--host", default='localhost')
        mqtt_parser.add_argument("--port", type=int, default=1883)

    parser.add_argument("-d", "--debug", action="store_true", default=False)
    parser.add_argument(
        "-n", "--no-validation", action="store_true", default=False,
        help="disables schema validation (based on foris-controller modules)"
    )
    parser.add_argument(
        '--extra-module-path', nargs=1, action='append', default=[],
        help="set extra path to module", required=False
    )
    parser.add_argument(
        "notification", metavar='NOTIFICATION', nargs="+", type=str,
        help="notification to be sent (in json format)"
    )

    options = parser.parse_args()
    notifications = [json.loads(e) for e in options.notification]

    if options.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()

    logger.debug("Version %s" % __version__)
    if options.bus == "ubus":
        from foris_controller.buses.ubus import UbusNotificationSender
        logger.info("Using ubus to send notifications.")
        sender = UbusNotificationSender(options.path)

    elif options.bus == "unix-socket":
        from foris_controller.buses.unix_socket import UnixSocketNotificationSender
        logger.info("Using unix-socket to send notifications.")
        sender = UnixSocketNotificationSender(options.path)

    elif options.bus == "mqtt":
        from foris_controller.buses.mqtt import MqttNotificationSender
        logger.info("Using mqtt to send notifications.")
        sender = MqttNotificationSender(options.host, options.port)

    # load validator
    if not options.no_validation:
        logger.debug("Validation will be performed.")
        from foris_schema import ForisValidator
        validator = ForisValidator(
            *get_validator_dirs([options.module], [e[0] for e in options.extra_module_path])
        )
    else:
        logger.debug("No validation")
        validator = None

    for notification in notifications:
        sender.notify(
            options.module, options.action, notification if notification else None, validator
        )


if __name__ == "__main__":
    main()
