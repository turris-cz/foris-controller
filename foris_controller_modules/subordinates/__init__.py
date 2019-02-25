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


class SubordinatesModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_list(self, data):
        return {"subordinates": self.handler.list_subordinates()}

    def action_add(self, data):
        res = self.handler.add_subordinate(**data)
        if res["result"]:
            self.notify(
                "add",
                {"controller_id": res["controller_id"]}
            )
            self.handler.restart_mqtt()
        return res

    def action_del(self, data):
        res = self.handler.del_subordinate(**data)
        if res:
            self.notify("del", data)
            self.handler.restart_mqtt()
        return {"result": res}

    def action_set(self, data):
        res = self.handler.set_subordinate(**data)
        if res:
            self.notify("set", data)
            self.handler.restart_mqtt()
        return {"result": res}

    def action_add_subsubordinate(self, data):
        res = self.handler.add_subsubordinate(**data)
        if res:
            self.notify("add_subsubordinate", data)
            self.handler.restart_mqtt()
        return {"result": res}

    def action_set_subsubordinate(self, data):
        res = self.handler.set_subsubordinate(**data)
        if res:
            self.notify("set_subsubordinate", data)
            self.handler.restart_mqtt()
        return {"result": res}

    def action_del_subsubordinate(self, data):
        res = self.handler.del_subsubordinate(**data)
        if res:
            self.notify("del_subsubordinate", data)
            self.handler.restart_mqtt()
        return {"result": res}


@wrap_required_functions([
    'list_subordinates',
    'add_subordinate',
    'del_subordinate',
    'set_subordinate',
    'add_subsubordinate',
    'del_subsubordinate',
    'set_subsubordinate',
    'restart_mqtt',
])
class Handler(object):
    pass
