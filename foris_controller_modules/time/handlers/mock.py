#
# foris-controller
# Copyright (C) 2018-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import logging
import random
import typing

from datetime import datetime

from turris_timezone import TZ_GNU

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockTimeHandler(Handler, BaseMockHandler):
    guide_set = BaseMockHandler._manager.Value(bool, False)
    region = "Europe"
    country = "00"
    city = "Prague"
    timezone = "UTC"
    how_to_set_time = "ntp"
    time = datetime.now()
    ntpdate_id_set = set()
    ntp_servers = [
        "217.31.202.100",
        "195.113.144.201",
        "195.113.144.238",
        "2001:1488:ffff::100",
        "ntp.nic.cz",
        "0.openwrt.pool.ntp.org",
        "1.openwrt.pool.ntp.org",
        "2.openwrt.pool.ntp.org",
        "3.openwrt.pool.ntp.org",
    ]
    ntp_extras = []

    @logger_wrapper(logger)
    def get_settings(self):
        """ Mocks get time settings

        :returns: current time settiongs
        :rtype: str
        """
        result = {
            "region": self.region,
            "country": self.country,
            "city": self.city,
            "time_settings": {
                "how_to_set_time": self.how_to_set_time,
                "ntp_servers": self.ntp_servers,
                "ntp_extras": self.ntp_extras
            },
            "timezone": self.timezone,
        }
        return result

    @logger_wrapper(logger)
    def update_settings(
        self,
        region: str,
        country: str,
        city: str,
        how_to_set_time: str,
        ntp_extras: typing.Optional[typing.List[str]],
        time: typing.Optional[datetime] = None,
    ) -> bool:
        """ Mocks updates current time settings

        :param region: set the region (Europe, America, Asia, ...)
        :param country: ISO/IEC 3166 alpha2 country code (US, CZ, DE, ...)
        :param city: set the city (Prague, London, ...)
        :param how_to_set_time: "ntp" or "manual"
        :param time: time to be set
        :returns: True if update passes
        """
        self.region = region
        self.country = country
        self.city = city
        self.timezone = TZ_GNU.get(f"{region}/{city.replace(' ', '_')}", "UTC")
        self.how_to_set_time = how_to_set_time
        self.ntp_extras = ntp_extras or []
        if time is not None:
            self.time = time
        MockTimeHandler.guide_set.set(True)
        return True

    @logger_wrapper(logger)
    def ntpdate_trigger(self, exit_notify_function, reset_notify_function):
        """ Mocks triggering of the ntpdate command
        :param exit_notify_function: function for sending notification when the cmds finishes
        :type exit_notify_function: callable
        :param reset_notify_function: function to reconnect to the notification bus
        :type reset_notify_function: callable
        :returns: generated_ntpdate_id
        :rtype: str
        """
        new_ntpdate_id = "%032X" % random.randrange(2 ** 32)
        self.ntpdate_id_set.add(new_ntpdate_id)
        return new_ntpdate_id
