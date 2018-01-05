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


import itertools
import json
import os
import pytest
import socket
import shutil
import struct
import subprocess
import sys
import time
import uuid

if sys.version_info < (3, 0):
    import SocketServer
else:
    import socketserver
    SocketServer = socketserver

from multiprocessing import Process, Value, Lock


SOCK_PATH = "/tmp/foris-controller-test.soc"
NOTIFICATION_SOCK_PATH = "/tmp/foris-controller-notifications-test.soc"
NOTIFICATIONS_OUTPUT_PATH = "/tmp/foris-controller-notifications-test.json"
UBUS_PATH = "/tmp/ubus-foris-controller-test.soc"
UCI_CONFIG_DIR_PATH = "/tmp/uci_configs"


EXTRA_MODULE_PATHS = [
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_modules", "echo")
]
USED_MODULES = [
    "about", "data_collect", "web", "dns", "maintain", "password", "updater", "lan"
]

notifications_lock = Lock()


def _chunks(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]


@pytest.fixture(scope="session")
def ubusd_test():
    ubusd_instance = subprocess.Popen(["ubusd", "-A", "tests/ubus-acl", "-s", UBUS_PATH])
    yield ubusd_instance
    ubusd_instance.kill()
    try:
        os.unlink(SOCK_PATH)
    except:
        pass


def ubus_notification_listener(exiting):
    import prctl
    import signal
    prctl.set_pdeathsig(signal.SIGKILL)
    import ubus
    if ubus.get_connected():
        ubus.disconnect(False)
    ubus.connect(UBUS_PATH)
    global notifications_lock

    try:
        os.unlink(NOTIFICATIONS_OUTPUT_PATH)
    except OSError:
        if os.path.exists(NOTIFICATIONS_OUTPUT_PATH):
            raise

    with open(NOTIFICATIONS_OUTPUT_PATH, "w") as f:
        f.flush()

        def handler(module, data):
            module_name = module[len("foris-controller-"):]
            msg = {
                "module": module_name,
                "kind": "notification",
                "action": data["action"],
            }
            if "data" in data:
                msg["data"] = data["data"]

            with notifications_lock:
                f.write(json.dumps(msg) + "\n")
                f.flush()

        ubus.listen(("foris-controller-*", handler))
        while True:
            ubus.loop(200)
            if exiting.value:
                break


def unix_notification_listener():
    import prctl
    import signal
    from threading import Lock
    lock = Lock()
    prctl.set_pdeathsig(signal.SIGKILL)
    global notifications_lock

    try:
        os.unlink(NOTIFICATION_SOCK_PATH)
    except OSError:
        if os.path.exists(NOTIFICATION_SOCK_PATH):
            raise
    try:
        os.unlink(NOTIFICATIONS_OUTPUT_PATH)
    except OSError:
        if os.path.exists(NOTIFICATIONS_OUTPUT_PATH):
            raise

    class Server(SocketServer.ThreadingMixIn, SocketServer.UnixStreamServer):
        pass

    with open(NOTIFICATIONS_OUTPUT_PATH, "w") as f:
        f.flush()

        class Handler(SocketServer.StreamRequestHandler):
            def handle(self):
                while True:
                    length_raw = self.rfile.read(4)
                    if len(length_raw) != 4:
                        break
                    length = struct.unpack("I", length_raw)[0]
                    data = self.rfile.read(length)
                    with lock:
                        with notifications_lock:
                            f.write(data + "\n")
                            f.flush()

        server = Server(NOTIFICATION_SOCK_PATH, Handler)
        server.serve_forever()


class Infrastructure(object):
    def __init__(self, name, backend_name, debug_output=False):
        try:
            os.unlink(SOCK_PATH)
        except:
            pass

        self.name = name
        self.backend_name = backend_name
        if name not in ["unix-socket", "ubus"]:
            raise NotImplementedError()
        if backend_name not in ["openwrt", "mock"]:
            raise NotImplementedError()

        self.sock_path = SOCK_PATH
        if name == "ubus":
            self.sock_path = UBUS_PATH
            while not os.path.exists(self.sock_path):
                time.sleep(0.3)

        kwargs = {}
        if not debug_output:
            devnull = open(os.devnull, 'wb')
            kwargs['stderr'] = devnull
            kwargs['stdout'] = devnull

        self._exiting = Value('i', 0)
        self._exiting.value = False

        if name == "unix-socket":
            self.listener = Process(target=unix_notification_listener, args=tuple())
            self.listener.start()
        elif name == "ubus":
            self.listener = Process(target=ubus_notification_listener, args=(self._exiting, ))
            self.listener.start()

        modules = list(itertools.chain.from_iterable([("-m", e) for e in USED_MODULES]))
        extra_paths = list(itertools.chain.from_iterable(
            [("--extra-module-path", e) for e in EXTRA_MODULE_PATHS]))

        args = [
            "bin/foris-controller",
        ] + modules + extra_paths + [
            "-d", "-b", backend_name, name, "--path", self.sock_path
        ]

        if name == "unix-socket":
            args.append("--notifications-path")
            args.append(NOTIFICATION_SOCK_PATH)
            self.notification_sock_path = NOTIFICATION_SOCK_PATH
        else:
            self.notification_sock_path = self.sock_path

        self.server = subprocess.Popen(args, **kwargs)

    def exit(self):
        self._exiting.value = True
        self.server.kill()
        self.listener.terminate()
        try:
            os.unlink(NOTIFICATIONS_OUTPUT_PATH)
        except OSError:
            pass
        try:
            import ubus  # disconnect from ubus if connected
            ubus.disconnect()
        except:
            pass

    def process_message(self, data):
        if self.name == "unix-socket":
            while not os.path.exists(self.sock_path):
                time.sleep(1)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.sock_path)
            data = json.dumps(data).encode("utf8")
            length_bytes = struct.pack("I", len(data))
            sock.sendall(length_bytes + data)

            length = struct.unpack("I", sock.recv(4))[0]
            received = sock.recv(length)
            recv_len = len(received)
            while recv_len < length:
                received += sock.recv(length)
                recv_len = len(received)

            return json.loads(received.decode("utf8"))

        elif self.name == "ubus":
            import ubus
            module = "foris-controller-%s" % data.get("module", "?")
            wait_process = subprocess.Popen(
                ["ubus", "wait_for", module, "-s", self.sock_path])
            wait_process.wait()
            if not ubus.get_connected():
                ubus.connect(self.sock_path)
            function = data.get("action", "?")
            inner_data = data.get("data", {})
            dumped_data = json.dumps(inner_data)
            request_id = str(uuid.uuid4())
            if len(dumped_data) > 512 * 1024:
                for data_part in _chunks(dumped_data, 512 * 1024):
                    ubus.call(module, function, {
                        "data": {}, "final": False, "multipart": True,
                        "request_id": request_id, "multipart_data": data_part,
                    })

                res = ubus.call(module, function, {
                    "data": {}, "final": True, "multipart": True,
                    "request_id": request_id, "multipart_data": "",
                })

            else:
                res = ubus.call(module, function, {
                    "data": inner_data, "final": True, "multipart": False,
                    "request_id": request_id, "multipart_data": "",
                })

            ubus.disconnect()
            return {
                u"module": data["module"],
                u"action": data["action"],
                u"kind": u"reply",
                u"data": json.loads("".join([e["data"] for e in res])),
            }

        raise NotImplementedError()

    def process_message_ubus_raw(self, data, request_id, final, multipart, multipart_data):
        import ubus
        module = "foris-controller-%s" % data.get("module", "?")
        wait_process = subprocess.Popen(
            ["ubus", "wait_for", module, "-s", self.sock_path])
        wait_process.wait()
        if not ubus.get_connected():
            ubus.connect(self.sock_path)
        function = data.get("action", "?")
        res = ubus.call(module, function, {
            "data": data, "final": final, "multipart": multipart,
            "request_id": request_id, "multipart_data": multipart_data,
        })
        return {
            u"module": data["module"],
            u"action": data["action"],
            u"kind": u"reply",
            u"data": json.loads("".join([e["data"] for e in res])),
        } if res else None

    def get_notifications(self, old_data=None):
        while not os.path.exists(NOTIFICATIONS_OUTPUT_PATH):
            time.sleep(0.2)

        global notifications_lock

        while True:
            with notifications_lock:
                with open(NOTIFICATIONS_OUTPUT_PATH) as f:
                    data = f.readlines()
                    last_data = [json.loads(e.strip()) for e in data]
                    if not old_data == last_data:
                        break
        return last_data


@pytest.fixture(scope="module")
def backend(backend_param):
    """ The backend name obtained via cmd line args"""
    return backend_param


@pytest.fixture(autouse=True)
def only_backends(request, backend):
    """ Set which backends should be used (others will be skipped)
    """
    if request.node.get_marker('only_backends'):
        if backend not in request.node.get_marker('only_backends').args[0]:
            pytest.skip("unsupported backend for this test '%s'" % backend)


@pytest.fixture(params=["unix-socket", "ubus"], scope="module")
def message_bus(request, backend):
    """ Message bus name (parametrized fixture) """
    return request.param


@pytest.fixture(autouse=True)
def only_message_buses(request, message_bus):
    """ Set which message buses should be used (others will be skipped)
    """
    if request.node.get_marker('only_message_buses'):
        if message_bus not in request.node.get_marker('only_message_buses').args[0]:
            pytest.skip("unsupported message bus for this test '%s'" % message_bus)


@pytest.fixture(scope="module")
def infrastructure(request, backend, message_bus):
    instance = Infrastructure(
        message_bus, backend, request.config.getoption("--debug-output"))
    yield instance
    instance.exit()


@pytest.fixture(params=["threading", "multiprocessing"], scope="function")
def lock_backend(request):
    if request.param == "threading":
        import threading
        yield threading
    elif request.param == "multiprocessing":
        import multiprocessing
        yield multiprocessing


@pytest.fixture(scope="function")
def uci_config_dir():
    shutil.rmtree(UCI_CONFIG_DIR_PATH, ignore_errors=True)
    try:
        os.makedirs(UCI_CONFIG_DIR_PATH)
    except IOError:
        pass

    with open(os.path.join(UCI_CONFIG_DIR_PATH, 'test1'), 'w+'):
        pass

    with open(os.path.join(UCI_CONFIG_DIR_PATH, 'test2'), 'w+') as f:
        f.write("""
config anonymous

config anonymous
	option option1 'aeb bb'
	option option2 'xxx'
	list list1 'single item'
	list list2 'item 1'
	list list2 'item 2'
	list list2 'item 3'
	list list2 'item 4'
    list list3 'itema'
    list list3 'itemb'

config named 'named1'

config named 'named2'
	option option1 'aeb bb'
	option option2 'xxx'
	list list1 'single item'
	list list2 'item 1'
	list list2 'item 2'
	list list2 'item 3'
	list list2 'item 4'
    list list3 'itema'
    list list3 'itemb'
"""
        )

    yield UCI_CONFIG_DIR_PATH

    shutil.rmtree(UCI_CONFIG_DIR_PATH, ignore_errors=True)
