#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.remote import (
    CaGenAsync, CaGenCmds, RemoteUci, RemoteFiles, RemoteComplex
)

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtRemoteHandler(Handler, BaseOpenwrtHandler):

    asynchronuous = CaGenAsync()
    cmds = CaGenCmds()
    uci = RemoteUci()
    files = RemoteFiles()
    complex = RemoteComplex()

    @logger_wrapper(logger)
    def generate_ca(self, notify, exit_notify, reset_notify):
        return self.asynchronuous.generate_ca(notify, exit_notify, reset_notify)

    @logger_wrapper(logger)
    def get_status(self):
        return self.cmds.get_status()

    @logger_wrapper(logger)
    def generate_token(self, name, notify, exit_notify, reset_notify):
        return self.asynchronuous.generate_token(name, notify, exit_notify, reset_notify)

    @logger_wrapper(logger)
    def revoke(self, cert_id):
        return self.cmds.revoke(cert_id)

    @logger_wrapper(logger)
    def delete_ca(self):
        return self.cmds.delete_ca()

    @logger_wrapper(logger)
    def get_settings(self):
        return self.uci.get_settings()

    @logger_wrapper(logger)
    def update_settings(self, enabled, wan_access=None, port=None):
        return self.uci.update_settings(enabled, wan_access, port)

    @logger_wrapper(logger)
    def get_token(self, id):
        filtered = [e for e in self.cmds.get_status()["tokens"] if e["id"] == id]
        if not filtered:
            return {"status": "not_found"}
        if filtered[0]["status"] == "revoked":
            return {"status": "revoked"}

        return {
            "status": "valid",
            "token": self.files.get_token(id=id, name=filtered[0]["name"])
        }

    @logger_wrapper(logger)
    def list_subordinates(self):
        return OpenwrtRemoteHandler.uci.list_subordinates()

    @logger_wrapper(logger)
    def add_subordinate(self, token):
        return OpenwrtRemoteHandler.complex.add_subordinate(token)

    @logger_wrapper(logger)
    def del_subordinate(self, controller_id):
        return OpenwrtRemoteHandler.complex.del_subordinate(controller_id)

    @logger_wrapper(logger)
    def set_subordinate(self, controller_id, enabled, custom_name):
        return OpenwrtRemoteHandler.uci.set_subordinate(controller_id, enabled, custom_name)

    @logger_wrapper(logger)
    def add_subsubordinate(self, controller_id: str, via: str) -> bool:
        return OpenwrtRemoteHandler.uci.add_subsubordinate(controller_id, via)

    @logger_wrapper(logger)
    def set_subsubordinate(self, controller_id, enabled, custom_name) -> bool:
        return OpenwrtRemoteHandler.uci.set_subsubordinate(controller_id, enabled, custom_name)

    @logger_wrapper(logger)
    def del_subsubordinate(self, controller_id) -> bool:
        return OpenwrtRemoteHandler.uci.del_subsubordinate(controller_id)
