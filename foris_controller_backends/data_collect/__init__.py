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

import re

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.uci import (
    UciBackend, UciRecordNotFound, parse_bool, get_option_named, store_bool
)


class RegisteredCmds(BaseCmdLine):

    def get_registered(self, email, language):
        """ Returns registration status
        :param email: email which will be used in the server query
        :type email: str
        :param language: language which will be used in the server query (en/cs)
        :type language: str

        :returns: registration status and sometimes registration url
        :rtype: dict
        """

        # get registration code
        from foris_controller_backends.about import ServerUplinkFiles
        registration_code = ServerUplinkFiles().get_registration_number()
        if not registration_code:
            # failed to obtain registration code
            return {"status": "unknown"}
        retcode, stdout, _ = self._run_command(
            "/usr/share/server-uplink/registered.sh",
            email, language
        )
        if not retcode == 0:
            # cmd failed (e.g. connection failed)
            return {"status": "unknown"}

        # code field should be present
        code_re = re.search(r"code: ([0-9]+)", stdout)
        http_code = int(code_re.group(1))
        if http_code != 200:
            return {"status": "not_found"}

        # status should be present
        status_re = re.search(r"status: (\w+)", stdout)
        status = status_re.group(1)

        if status == "owned":
            return {"status": status}
        elif status in ["free", "foreign"]:
            url_re = re.search(r"url: ([^\s]+)", stdout)
            url = url_re.group(1)
            return {
                "status": status, "url": url,
                "registration_number": registration_code,
            }

        return {"status": "unknown"}


class DataCollectUci(object):
    def get_agreed(self):
        with UciBackend() as backend:
            foris_data = backend.read("foris")

        try:
            return parse_bool(get_option_named(foris_data, "foris", "eula", "agreed_collect"))
        except UciRecordNotFound:
            return False

    def set_agreed(self, agreed):
        with UciBackend() as backend:
            backend.add_section("foris", "config", "eula")
            backend.set_option("foris", "eula", "agreed_collect", store_bool(agreed))

        return True
