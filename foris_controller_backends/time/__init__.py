#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.app import app_info
from foris_controller_backends.uci import (
    UciBackend, get_option_anonymous, get_option_named, parse_bool, store_bool
)
from foris_controller_backends.services import OpenwrtServices
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller.utils import writelock, RWLock


logger = logging.getLogger(__name__)


class SetTimeCommand(BaseCmdLine):
    time_lock = RWLock(app_info["lock_backend"])

    @writelock(time_lock, logger)
    def set_time(self, time):
        """ Sets current time using date command
        :param time: time to be set
        :type time: datetime.datetime
        """
        # don't care about retvals of next command (it should raise an exception on error)
        self._run_command("/bin/date", "-u", "-s", time.strftime("%Y-%m-%d %H:%M:%S"))

        # sometimes hwclock fails without an error so let's try to call it twice to be sure
        self._run_command("/sbin/hwclock", "-u", "-w")
        self._run_command("/sbin/hwclock", "-u", "-w")


class TimeUciCommands(object):

    def get_settings(self):

        with UciBackend() as backend:
            system_data = backend.read("system")

        timezone = get_option_anonymous(system_data, "system", "system", 0, "timezone")
        zonename = get_option_anonymous(system_data, "system", "system", 0, "zonename")
        try:
            region, city = zonename.split("/")
        except ValueError:
            region, city = "", ""
        ntp = parse_bool(get_option_named(system_data, "system", "ntp", "enabled"))

        return {
            "region": region,
            "city": city,
            "timezone": timezone,
            "time_settings":  {"how_to_set_time": "ntp" if ntp else "manual"},
        }

    def update_settings(self, region, city, timezone, how_to_set_time, time=None):
        """
        :param time: Time to be set
        """

        with UciBackend() as backend:
            backend.set_option("system", "@system[0]", "timezone", timezone)
            backend.set_option("system", "@system[0]", "zonename", "%s/%s" % (region, city))
            backend.set_option("system", "ntp", "enabled", store_bool(how_to_set_time == "ntp"))

        with OpenwrtServices() as services:
            if how_to_set_time == "ntp":
                # enable might fail, when sysntpd is already enabled
                services.enable("sysntpd", fail_on_error=False)
                services.restart("sysntpd", fail_on_error=False)
            else:
                # disable might fail, when sysntpd is already disabled
                services.disable("sysntpd", fail_on_error=False)
                services.stop("sysntpd", fail_on_error=False)

        if how_to_set_time == "manual":
            SetTimeCommand().set_time(time)  # time should be set (thanks to validation)

        return True
