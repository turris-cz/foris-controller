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
import socket
import struct
import sys

if sys.version_info >= (3, 0):
    from socketserver import BaseRequestHandler, UnixStreamServer, ThreadingMixIn
else:
    from SocketServer import (
        BaseRequestHandler, UnixStreamServer, ThreadingMixIn as NonObjectThreadingMixIn
    )

    class ThreadingMixIn(object, NonObjectThreadingMixIn):
        pass

from foris_controller.message_router import Router

logger = logging.getLogger(__name__)


class UnixSocketHandler(BaseRequestHandler):

    def setup(self):
        """ Connection initialization
        """
        logger.debug("Client connected.")
        self.router = Router()

    def handle(self):
        """ Main handler
        """
        logger.debug("Handling request")
        while True:
            try:
                # read data from the socket
                length_data = self.request.recv(4)
                if not length_data:
                    logger.debug("Connection closed.")
                    break
                length = struct.unpack("I", length_data)[0]
                logger.debug("Length received '%s'." % str(length))
                received_data = self.request.recv(length)
                logger.debug("Data received '%s'." % str(received_data))
                try:
                    parsed = json.loads(received_data.decode("utf8"))
                except ValueError:
                    logger.warning("Wrong data received.")
                    continue

                response = self.router.process_message(parsed)
                response = json.dumps(response).encode("utf8")
                response_length = struct.pack("I", len(response))
                logger.debug("Sending response (len=%d) %s" % (len(response), str(response)))
                self.request.send(response_length + response)

            except:
                logger.debug("Connection closed.")
                break

        logger.debug("Handling finished.")

    def finish(self):
        """ Connection closing
        """
        logger.debug("Client diconnected.")


class UnixSocketListener(ThreadingMixIn, UnixStreamServer):

    def __init__(self, socket_path):
        """ Init listener project

        :param socket_path: path to ubus socket
        :type socket_path: str
        """

        try:
            os.unlink(socket_path)
        except OSError:
            pass

        UnixStreamServer.__init__(self, socket_path, UnixSocketHandler)


class UnixSocketNotificationSender(object):

    def __init__(self, socket_path):
        """ Inits object which handles sending notification via unix-socket

        :param socket_path: path to ubus socket
        :type socket_path: str
        """
        self.socket_path = socket_path
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(socket_path)

    def _validate(self, msg, validator):
        logger.debug("Starting to validate notification.")
        from jsonschema import ValidationError
        try:
            validator.validate(msg)
        except ValidationError:
            validator.validate_verbose(msg)
        logger.debug("Notification validation passed.")

    def notify(self, module, action, data, validator=None):
        msg = {
            "module": module,
            "kind": "notification",
            "action": action,
            "data": data,
        }
        if validator:
            self._validate(msg, validator)
        notification = json.dumps(msg).encode("utf8")
        notification_length = struct.pack("I", len(notification))
        logger.debug("Sending notification (len=%d) %s" % (len(notification), str(notification)))
        self.socket.send(notification_length + notification)


    def disconnect(self):
        logger.debug("Disconnecting from unix socket")
        self.socket.close()
