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

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class RemoteModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_generate_ca(self, data):
        def notify(msg):
            self.notify("generate_ca", msg)

        # notify and exit notify are the same
        async_id = self.handler.generate_ca(notify, notify, self.reset_notify)

        return {"task_id": async_id}

    def action_get_status(self, data):
        return self.handler.get_status()

    def action_generate_token(self, data):
        def notify(msg):
            self.notify("generate_token", msg)

        # notify and exit notify are the same
        async_id = self.handler.generate_token(data["name"], notify, notify, self.reset_notify)

        return {"task_id": async_id}

    def action_revoke(self, data):
        res = self.handler.revoke(data["id"])
        if res:
            self.notify("revoke", {"id": data["id"]})
        return {"result": res}

    def action_delete_ca(self, data):
        res = self.handler.delete_ca()
        if res:
            self.notify("delete_ca")
        return {"result": res}

    def action_get_settings(self, data):
        return self.handler.get_settings()

    def action_update_settings(self, data):
        """
        param data: {"enabled": False} / {"enabled": True, "network": ...}
        """
        res = self.handler.update_settings(**data)
        if res:
            self.notify("update_settings", data)

        return {"result": res}

    def action_get_token(self, data):
        return self.handler.get_token(**data)

    def action_set_netboot_configured(self, data):
        res = self.handler.set_netboot_configured(**data)
        if res:
            self.notify("set_netboot_configured")
        return {"result": res}


@wrap_required_functions(
    [
        "generate_ca",
        "get_status",
        "generate_token",
        "revoke",
        "delete_ca",
        "get_settings",
        "update_settings",
        "get_token",
        "get_netboot_status",
        "set_netboot_configured",
    ]
)
class Handler(object):
    pass
