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


from foris_controller_backends.uci import (
    UciBackend,
    get_option_anonymous
)


class SystemUciCommands:

    @staticmethod
    def get_hostname() -> str:
        """ Get hostname uci setting. """

        with UciBackend() as backend:
            system_data = backend.read("system")

        hostname = get_option_anonymous(system_data, "system", "system", 0, "hostname", "turris")

        return hostname

    @staticmethod
    def set_hostname(hostname: str) -> bool:
        """ Set hostname uci setting. """

        with UciBackend() as backend:
            backend.set_option("system", "@system[0]", "hostname", hostname)
        return True
