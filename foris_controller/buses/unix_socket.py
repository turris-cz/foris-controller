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

import json
import logging
import os
import sys

if sys.version_info >= (3, 0):
    from socketserver import BaseRequestHandler, UnixStreamServer, ThreadingMixIn
else:
    from SocketServer import BaseRequestHandler, UnixStreamServer, ThreadingMixIn

from foris_controller.message_router import Router

logger = logging.getLogger("buses.unix_socket")


class UnixSocketHandler(BaseRequestHandler):

    def setup(self):
        logger.debug("Client connected.")

    def handle(self):
        logger.debug("Handling request")
        # read data from the socket
        received_data = self.request.recv(4096)
        logger.debug("Data received '%s'." % str(received_data))
        try:
            parsed = json.loads(str(received_data))
        except ValueError:
            logger.warning("Wrong data received. Handling finished.")
            return

        router = Router(self.server.backend)
        response = router.process_message(parsed)
        logger.debug("Sending response %s" % str(response))
        self.request.send(json.dumps(response))
        logger.debug("Handling finished.")

    def finish(self):
        logger.debug("Client diconnected.")


class UnixSocketListener(object, ThreadingMixIn, UnixStreamServer):

    def __init__(self, socket_path, backend):

        try:
            os.unlink(socket_path)
        except OSError:
            pass

        self.backend = backend
        UnixStreamServer.__init__(self, socket_path, UnixSocketHandler)
