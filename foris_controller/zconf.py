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

import ipaddress
import json
import logging
import threading
import typing
from enum import Enum, auto

import ifaddr
import zeroconf

from foris_controller.app import app_info

logger = logging.getLogger(__name__)


class ZconfService:
    TYPE = "_mqtt._tcp.local."
    POLL_TIMEOUT = 5.0  # in seconds

    class State(Enum):
        CONNECTED = auto()
        DISCONNECTED = auto()
        CLOSED = auto()

    def __init__(self):
        self.zconf = zeroconf.Zeroconf()
        self.addresses = ZconfService.get_addresses()
        self.state = ZconfService.State.DISCONNECTED
        self.terminate_event = threading.Event()
        self.address_watcher = None

        if not app_info["zeroconf_enabled"]:
            logger.debug("Zeroconf is not enabled. Skipping configuration")
            self.state = ZconfService.State.CLOSED
            return  # ZconfService will never connect

        # register service
        self.register_service()

        # run address updater thread
        self.address_watcher = threading.Thread(target=self.update_service_loop)
        self.address_watcher.start()

    def make_info(self) -> zeroconf.ServiceInfo:
        return zeroconf.ServiceInfo(
            ZconfService.TYPE,
            f"{app_info['controller_id']}.foris-controller.{ZconfService.TYPE}",
            parsed_addresses=self.addresses,
            port=app_info["zeroconf_port"],
            properties={"addresses": json.dumps(self.addresses)},
        )

    def register_service(self):
        if self.addresses:
            logger.debug("Registering zeroconf with addresses %s", self.addresses)
            self.zconf.register_service(self.make_info())
            self.state = ZconfService.State.CONNECTED

    def update_service_loop(self):
        while True:
            # Waiting for possible termination
            if self.terminate_event.wait(ZconfService.POLL_TIMEOUT):
                return

            # Update ip addresses if needed
            new_addresses = ZconfService.get_addresses()
            if self.addresses != new_addresses:
                self.addresses = new_addresses

                if self.addresses and self.state == ZconfService.State.CONNECTED:
                    # Updating connected state
                    logger.debug(
                        "Updating zeroconf with new addresses %s", self.addresses
                    )
                    self.zconf.update_service(self.make_info())

                elif self.addresses and self.state == ZconfService.State.DISCONNECTED:
                    # Service was disconnected it needs to be registered again
                    self.register_service()

                elif not self.addresses and self.state == ZconfService.State.CONNECTED:
                    # Unregister service when there are no addresses
                    self.zconf.unregister_service(self.make_info())
                    self.state = ZconfService.State.DISCONNECTED

    def close(self):
        if self.state != ZconfService.State.CLOSED:

            logger.debug("Closing zconf service")
            self.zconf.close()

            if self.address_watcher:
                self.terminate_event.set()
                self.address_watcher.join()

        self.state = ZconfService.State.CLOSED

    @staticmethod
    def get_addresses() -> typing.List[str]:
        """ Get IPs which shall be propagated unsing zconf """
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

        if not private_ips:
            logger.debug("No addresses available for zeroconf")

        return sorted(private_ips)
