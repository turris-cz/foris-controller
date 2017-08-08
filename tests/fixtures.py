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


import os
import json
import pytest
import socket
import subprocess
import time

UNIX_SOCK_PATH = "/tmp/foris-controller-test.soc"


class Infrastructure(object):
    def __init__(self, name, backend_name):
        try:
            os.unlink(UNIX_SOCK_PATH)
        except:
            pass

        self.name = name
        self.backend_name = backend_name
        if name == "unix-socket":
            pass
        else:
            raise NotImplementedError()
        if backend_name not in ["--openwrt-backend", "--mock-backend"]:
            raise NotImplementedError()

        self.server = subprocess.Popen([
            "bin/foris-controller", "-d", backend_name, name, "--path", UNIX_SOCK_PATH
        ])

    def exit(self):
        self.server.kill()

    def process_message(self, data):
        if self.name == "unix-socket":
            while not os.path.exists(UNIX_SOCK_PATH):
                time.sleep(1)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(UNIX_SOCK_PATH)
            sock.sendall(json.dumps(data).encode("utf8"))

            received = b''
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                received += data

            return json.loads(received.decode("utf8"))

        raise NotImplementedError()


@pytest.fixture(params=['--openwrt-backend', '--mock-backend'], scope="session")
def backend(request):
    return request.param


@pytest.fixture(params=["unix-socket"], scope="session")
def infrastructure(request, backend):
    instance = Infrastructure(request.param, backend)
    yield instance
    instance.exit()
