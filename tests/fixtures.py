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
import os
import pytest
import socket
import subprocess
import time
import threading

from foris_controller.utils import RWLock

SOCK_PATH = "/tmp/foris-controller-test.soc"
UBUS_PATH = "/tmp/ubus-foris-controller-test.soc"


class Locker(object):
    PLACE_BEGIN = 'B'
    PLACE_END = 'E'
    KIND_READ = 'R'
    KIND_WRITE = 'W'

    def __init__(self):
        self.lock = RWLock()
        self.output = []
        self._output_lock = threading.Lock()

    def store_log(self, kind, place):
        with self._output_lock:
            self.output.append((kind, place))


@pytest.fixture(scope="session")
def ubusd_test():
    ubusd_instance = subprocess.Popen(["ubusd", "-A", "tests/ubus-acl", "-s", UBUS_PATH])
    yield ubusd_instance
    ubusd_instance.kill()
    try:
        os.unlink(SOCK_PATH)
    except:
        pass


class Infrastructure(object):
    def __init__(self, name, backend_name, suppress_output=False):
        try:
            os.unlink(SOCK_PATH)
        except:
            pass

        self.name = name
        self.backend_name = backend_name
        if name not in ["unix-socket", "ubus"]:
            raise NotImplementedError()
        if backend_name not in ["openwrt-backend", "mock-backend"]:
            raise NotImplementedError()

        self.sock_path = SOCK_PATH
        if name == "ubus":
            self.sock_path = UBUS_PATH
            while not os.path.exists(self.sock_path):
                time.sleep(0.3)

        kwargs = {}
        if suppress_output:
            devnull = open(os.devnull, 'wb')
            kwargs['stderr'] = devnull
            kwargs['stdout'] = devnull

        self.server = subprocess.Popen([
            "bin/foris-controller", "-d", "--" + backend_name, name, "--path", self.sock_path
        ], **kwargs)

    def exit(self):
        self.server.kill()

    def process_message(self, data):
        if self.name == "unix-socket":
            while not os.path.exists(self.sock_path):
                time.sleep(1)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.sock_path)
            sock.sendall(json.dumps(data).encode("utf8"))

            received = b''
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                received += data

            return json.loads(received.decode("utf8"))

        elif self.name == "ubus":
            import ubus
            wait_process = subprocess.Popen(
                ["ubus", "wait_for", "foris-controller", "-s", self.sock_path])
            wait_process.wait()
            if not ubus.get_connected():
                ubus.connect(self.sock_path)
            res = ubus.call("foris-controller", "send", {"message": data})
            ubus.disconnect()
            return res[0]

        raise NotImplementedError()


@pytest.fixture(scope="module")
def backend(backend_param):
    return backend_param


@pytest.fixture(params=["unix-socket", "ubus"], scope="module")
def infrastructure(request, backend):
    instance = Infrastructure(
        request.param, backend, request.config.getoption("--suppress-output"))
    yield instance
    instance.exit()

@pytest.fixture(scope="function")
def locker_instance():
    yield Locker()
