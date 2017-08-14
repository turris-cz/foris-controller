#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from ..exceptions import UnknownAction


class BaseModule(object):

    def perform_action(self, action, data):
        action_function = getattr(self, "action_%s" % action)
        if not action_function:
            self.logger.error("Unkown action '%s'!" % action)
            raise UnknownAction(action)

        self.logger.debug("Starting to perform '%s' action" % action)
        res = action_function(data)
        self.logger.debug("Action '%s' finished" % action)
        return res
