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

from foris_controller.exceptions import UciException, UciRecordNotFound
from foris_controller_backends.uci import (
    get_sections_by_type, store_bool
)

logger = logging.getLogger(__name__)


class WifiUci(object):
    @staticmethod
    def get_wifi_devices(backend):
        try:
            wifi_data = backend.read("wifi")
            return get_sections_by_type(wifi_data, "wireless", "wifi-device")
        except (UciException, UciRecordNotFound):
            return []  # no wifi sections -> no gest wifi is running -> we're done

    @staticmethod
    def set_guest_wifi_disabled(backend):
        """ Should disable all guest wifi networks
        :param backend: backend controller instance
        :type backend: foris_controller_backends.uci.UciBackend
        """
        for i, _ in enumerate(WifiUci.get_wifi_devices(backend), 0):
            section_name = "guest_iface_%d" % i
            backend.add_section("wireless", "wifi-iface", section_name)
            backend.add_option("wireless", section_name, "disabled", store_bool(True))
