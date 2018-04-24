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

import logging
import pbkdf2

logger = logging.getLogger(__name__)

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.uci import (
    UciBackend, get_option_named, UciException, UciRecordNotFound
)


class ForisPasswordUci(object):
    def set_password(self, password):
        # use 48bit pseudo-random salt internally generated by pbkdf2
        new_password_hash = pbkdf2.crypt(password, iterations=1000)
        with UciBackend() as backend:
            backend.add_section("foris", "config", "auth")
            backend.set_option("foris", "auth", "password", new_password_hash)

        # update wizard passed in foris web (best effort)
        try:
            with UciBackend() as backend:
                backend.add_section("foris", "config", "wizard")
                backend.add_to_list("foris", "wizard", "passed", ["password"])
        except UciException:
            pass

        return True

    def check_password(self, password):
        with UciBackend() as backend:
            foris_data = backend.read("foris")

        # This could raise UciRecordNotFound which should be caught elsewhere
        password_hash = get_option_named(foris_data, "foris", "auth", "password")

        return password_hash == pbkdf2.crypt(password, salt=password_hash)

    def is_password_set(self):
        with UciBackend() as backend:
            data = backend.read("foris")
        try:
            get_option_named(data, "foris", "auth", "password")
            return True
        except (UciRecordNotFound, UciException):
            return False


class SystemPasswordCmd(BaseCmdLine):

    def set_password(self, password):
        busybox_passwd = "/bin/passwd"
        logger.debug("Setting system password.")
        passwords = "%(password)s\n%(password)s\n" % dict(password=password)
        retval, _, _ = self._run_command(busybox_passwd, input_data=passwords)
        if retval != 0:
            logger.error("Failed to set system password.")
            return False

        return True
