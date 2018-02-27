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
import sys
import prctl
import os
import signal
import json
import threading
import struct

from foris_controller.utils import LOGGER_MAX_LEN

logger = logging.getLogger(__name__)

if sys.version_info >= (3, 0):
    from socketserver import BaseRequestHandler, UnixStreamServer, ThreadingMixIn
else:
    from SocketServer import (
        BaseRequestHandler, UnixStreamServer, ThreadingMixIn as NonObjectThreadingMixIn
    )

    class ThreadingMixIn(object, NonObjectThreadingMixIn):
        pass


def worker(
    socket_path, timeout, validator,
    sender_class, sender_args,
    notification_sender_class, notification_sender_args
):
    os.umask(0o0077)
    # make sure that it exits if parent is killed
    prctl.set_pdeathsig(signal.SIGKILL)

    # TODO wait for other foris-controller fully started

    sender_instance = sender_class(*sender_args)
    notification_sender_instance = notification_sender_class(*notification_sender_args)

    server = ClientSocketListener(
        socket_path, validator, sender_instance, notification_sender_instance, timeout)

    server.serve_forever()


class ClientSocketHandler(BaseRequestHandler):
    def setup(self):
        logger.debug("Client connected.")

    def _check_msg(self, notification):
        if "module" not in notification or "action" not in notification:
            logger.warning('Wrong notification "%s"', notification)
            raise ValueError('Wrong notification "%s"' % notification)

    def _forward_notification(self, notification):
        logger.debug("Forwarding notification.")
        self._check_msg(notification)
        with self.server.notification_sender_lock:
            self.server.notification_sender.notify(
                notification["module"], notification["action"],
                notification.get("data", None), self.server.validator
            )
        logger.debug("Notification forwarded.")

    def _reply_to_request(self, request):
        self._check_msg(request)

        with self.server.sender_lock:
            msg = self.server.sender.send(
                request["module"], request["action"], request.get("data", None),
                timeout=self.server.timeout
            )
            logger.debug("Request forwarded")

        response = {
            "module": request["module"],
            "action": request["action"],
            "kind": "reply",
            "data": msg,
        }

        response = json.dumps(response).encode("utf8")
        response_length = struct.pack("I", len(response))
        logger.debug("Sending response (len=%d) %s" % (
            len(response), str(response)[:LOGGER_MAX_LEN]
        ))
        self.request.sendall(response_length + response)

    def handle(self):
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
                received_data_len = len(received_data)
                logger.debug("Data recieved len %d", received_data_len)
                while received_data_len < length:
                    received_data += self.request.recv(length - received_data_len)
                    received_data_len = len(received_data)
                    logger.debug("Data recieved len %d", received_data_len)

                logger.debug("Data received '%s'." % str(received_data)[:LOGGER_MAX_LEN])
                try:
                    parsed = json.loads(received_data.decode("utf8"))
                except ValueError:
                    logger.warning("Wrong data received.")
                    continue

                kind = parsed.get("kind", None)
                if kind == "notification":
                    self._forward_notification(parsed)
                elif kind == "request":
                    self._reply_to_request(parsed)
                elif kind is None:
                    logger.warning("Missing kind in recieved message.")
                else:
                    logger.warning("Unknown kind '%s'", kind)

            except Exception:
                logger.debug("Connection closed.")
                break

        logger.debug("Handling finished.")

    def finish(self):
        logger.debug("Client diconnected.")


class ClientSocketListener(ThreadingMixIn, UnixStreamServer):
    def __init__(
        self, socket_path, validator, sender_instance, notification_sender_instance, timeout=0
    ):

        self.sender = sender_instance
        self.notification_sender = notification_sender_instance
        self.timeout = timeout
        self.validator = validator

        self.sender_lock = threading.Lock()
        self.notification_sender_lock = threading.Lock()

        try:
            os.unlink(socket_path)
        except OSError:
            pass

        UnixStreamServer.__init__(self, socket_path, ClientSocketHandler)
