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

import json
import ipaddress
import logging
import typing

import ifaddr
import zeroconf

from foris_controller.app import app_info

logger = logging.getLogger(__file__)


TYPE = "_mqtt._tcp.local."


def get_addresses() -> typing.List[str]:
    ips: typing.Set[str] = set()
    for adapter in ifaddr.get_adapters():
        if (
            app_info["zeroconf_devices"]
            and adapter.name not in app_info["zeroconf_devices"]
        ):
            logger.debug(
                "skipping '%s' device for zeroconf configuration", adapter.name
            )
            continue
        ips |= set(e.ip for e in adapter.ips if e.is_IPv4)

    private_ips = [e for e in ips if ipaddress.ip_address(e).is_private]

    return private_ips


def register() -> typing.Optional[zeroconf.Zeroconf]:
    """ Tries to register as a service using zeroconf """

    if not app_info["zeroconf_enabled"]:
        logger.debug("Zeroconf is not enabled. Skipping configuration")
        return None

    addresses = get_addresses()

    if not addresses:
        logger.debug("No addresses available for zeroconf")
        return None

    logger.debug("Runing zeroconf on %s", addresses)

    info = zeroconf.ServiceInfo(
        TYPE,
        f"{app_info['controller_id']}.foris-controller.{TYPE}",
        parsed_addresses=addresses,
        port=app_info["zeroconf_port"],
        properties={"addresses": json.dumps(addresses)},
    )

    zconf = zeroconf.Zeroconf()
    zconf.register_service(info)

    return zconf
