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
import shutil
import stat
import struct
import subprocess
import sys
import time

if sys.version_info < (3, 0):
    import SocketServer
else:
    import socketserver
    SocketServer = socketserver

from multiprocessing import Process, Value, Lock

from foris_controller.utils import RWLock

SOCK_PATH = "/tmp/foris-controller-test.soc"
NOTIFICATION_SOCK_PATH = "/tmp/foris-controller-notifications-test.soc"
NOTIFICATIONS_OUTPUT_PATH = "/tmp/foris-controller-notifications-test.json"
UBUS_PATH = "/tmp/ubus-foris-controller-test.soc"
UCI_CONFIG_DIR_PATH = "/tmp/uci_configs"
SERVICE_SCRIPT_DIR_PATH = "/tmp/test_init/"


notifications_lock = Lock()


class Locker(object):
    PLACE_BEGIN = 'B'
    PLACE_END = 'E'
    KIND_READ = 'R'
    KIND_WRITE = 'W'

    def __init__(self, locking_module, entity_object, output):
        self.lock = RWLock(locking_module)
        self.output = output
        self._output_lock = locking_module.Lock()
        self.entity = entity_object

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


def ubus_notification_listener(exiting):
    import prctl
    import signal
    prctl.set_pdeathsig(signal.SIGKILL)
    import ubus
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
            with notifications_lock:
                f.write(json.dumps({
                    "module": module_name,
                    "kind": "notification",
                    "action": data["action"],
                    "data": data["data"],
                }) + "\n")
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

        args = [
            "bin/foris-controller",
            "-m", "about", "-m", "data_collect", "-m", "web", "-m", "dns",
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
            res = ubus.call(module, function, {"data": inner_data})
            ubus.disconnect()
            return res[0]

        raise NotImplementedError()

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
    return backend_param


@pytest.fixture(params=["unix-socket", "ubus"], scope="module")
def infrastructure(request, backend):
    instance = Infrastructure(
        request.param, backend, request.config.getoption("--debug-output"))
    yield instance
    instance.exit()


@pytest.fixture(scope="module")
def infrastructure_unix_socket(request, backend):
    instance = Infrastructure(
        "unix-socket", backend, request.config.getoption("--debug-output"))
    yield instance
    instance.exit()


@pytest.fixture(params=["threading", "multiprocessing"], scope="function")
def locker_instance(request):
    if request.param == "threading":
        import threading
        output = []
        locker = Locker(threading, threading.Thread, output)
    elif request.param == "multiprocessing":
        import multiprocessing
        manager = multiprocessing.Manager()
        output = manager.list()
        locker = Locker(multiprocessing, multiprocessing.Process, output)
    yield locker


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

@pytest.fixture(scope="module")
def service_scripts():
    shutil.rmtree(SERVICE_SCRIPT_DIR_PATH, ignore_errors=True)
    try:
        os.makedirs(SERVICE_SCRIPT_DIR_PATH)
    except IOError:
        pass

    fail_file = os.path.join(SERVICE_SCRIPT_DIR_PATH, 'fail')
    with open(fail_file, 'w+') as f:
        f.write("""#!/bin/sh
echo failed $1 > %s
echo FAILED 1>&2
exit 1
""" % os.path.join(SERVICE_SCRIPT_DIR_PATH, "result")
        )
    os.chmod(fail_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    pass_file = os.path.join(SERVICE_SCRIPT_DIR_PATH, 'pass')
    with open(pass_file, 'w+') as f:
        f.write("""#!/bin/sh
echo passed $1 > %s
echo PASS
exit 0
""" % os.path.join(SERVICE_SCRIPT_DIR_PATH, "result")
        )
    os.chmod(pass_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    yield SERVICE_SCRIPT_DIR_PATH

    shutil.rmtree(SERVICE_SCRIPT_DIR_PATH, ignore_errors=True)
