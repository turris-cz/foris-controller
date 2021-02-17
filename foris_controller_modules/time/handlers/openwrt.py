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

import logging
import typing

from datetime import datetime

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper
from foris_controller_backends.time import TimeUciCommands, TimeAsyncCmds

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtTimeHandler(Handler, BaseOpenwrtHandler):
    uci = TimeUciCommands()
    async_cmd = TimeAsyncCmds()

    @logger_wrapper(logger)
    def get_settings(self):
        """ Get time settings

        :returns: current time settiongs
        :rtype: dict
        """
        return self.uci.get_settings()

    @logger_wrapper(logger)
    def update_settings(
        self,
        region: str,
        country: str,
        city: str,
        how_to_set_time: str,
        ntp_extras: typing.Optional[typing.List[str]] = None,
        time: typing.Optional[datetime] = None,
    ) -> bool:
        """ Updates current time settings

        :param region: set the region (Europe, America, Asia, ...)
        :param city: set the city (Prague, London, ...)
        :param how_to_set_time: "ntp" or "manual"
        :param time: time to be set
        :returns: True if update passes
        """

        return self.uci.update_settings(region, country, city, how_to_set_time, ntp_extras, time)

    @logger_wrapper(logger)
    def ntpdate_trigger(self, exit_notify_function, reset_notify_function):
        """ Triggers the ntpdate command in async mode
        :param exit_notify_function: function for sending notification when the cmds finishes
        :type exit_notify_function: callable
        :param reset_notify_function: function to reconnect to the notification bus
        :type reset_notify_function: callable
        :returns: generated_ntpdate_id
        :rtype: str
        """
        return self.async_cmd.ntpd_trigger(exit_notify_function, reset_notify_function)
