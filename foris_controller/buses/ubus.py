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

from __future__ import absolute_import

import logging
import ubus

logger = logging.getLogger("buses.ubus")

from foris_controller.message_router import Router


class UbusListener(object):
    def __init__(self, socket_path, backend):
        self.backend = backend
        ubus.connect(socket_path)

        def send(handler, data):
            logger.debug("Handling request")
            logger.debug("Data received '%s'." % str(data))
            router = Router(self.backend)
            response = router.process_message(data["message"])
            logger.debug("Sending response %s" % str(response))
            logger.debug("Handling finished.")
            handler.reply(response)

        logger.debug("Trying to register 'foris-controller' object.")
        ubus.add(
            "foris-controller",
            {
                "send": {"method": send, "signature": {
                    "message": ubus.BLOBMSG_TYPE_TABLE
                }},
            }
        )
        logger.debug("Object 'foris-controller' was registered.")

    def serve_forever(self):
        try:
            while True:
                ubus.loop(500)
        finally:
            ubus.disconnect()
