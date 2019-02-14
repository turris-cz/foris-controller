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

import os
import re
import logging
import tarfile
import base64
import json
import typing
import pathlib
import shutil

from io import BytesIO
from collections import OrderedDict

from foris_controller.app import app_info

from foris_controller_backends.cmdline import AsyncCommand, BaseCmdLine
from foris_controller_backends.files import BaseFile, makedirs, inject_file_root
from foris_controller_backends.uci import (
    UciBackend, get_option_named, parse_bool, UciException, store_bool,
    get_option_anonymous, get_sections_by_type, get_section, UciRecordNotFound
)
from foris_controller.utils import RWLock
from foris_controller_backends.services import OpenwrtServices

logger = logging.getLogger(__name__)


subordinate_dir_lock = RWLock(app_info["lock_backend"])


class CaGenAsync(AsyncCommand):

    def generate_ca(self, notify_function, exit_notify_function, reset_notify_function):

        def handler_exit(process_data):
            exit_notify_function({
                "task_id": process_data.id,
                "status": "succeeded" if process_data.get_retval() == 0 else "failed"
            })

        def gen_handler(status):
            def handler(matched, process_data):
                notify_function({"task_id": process_data.id, "status": status})
            return handler

        task_id = self.start_process(
            ["/usr/bin/turris-cagen", "new_ca", "remote", "gen_ca", "gen_server", "turris"],
            [
                (r"^gen_ca: started", gen_handler("ca_generating")),
                (r"^gen_ca: finished", gen_handler("ca_done")),
                (r"^gen_server: started", gen_handler("server_generating")),
                (r"^gen_server: finished", gen_handler("server_done")),
            ],
            handler_exit,
            reset_notify_function,
        )

        return task_id

    def generate_token(self, name, notify_function, exit_notify_function, reset_notify_function):

        def handler_exit(process_data):
            exit_notify_function({
                "task_id": process_data.id,
                "name": name,
                "status": "succeeded" if process_data.get_retval() == 0 else "failed"
            })

        def gen_handler(status):
            def handler(matched, process_data):
                notify_function({"task_id": process_data.id, "status": status, "name": name})
            return handler

        task_id = self.start_process(
            ["/usr/bin/turris-cagen", "switch", "remote", "gen_client", name],
            [
                (r"^gen_client: started", gen_handler("token_generating")),
                (r"^gen_client: finished", gen_handler("token_done")),
            ],
            handler_exit,
            reset_notify_function,
        )

        return task_id


class CaGenCmds(BaseCmdLine):

    def get_status(self):
        output, _ = self._run_command_and_check_retval(
            ["/usr/bin/turris-cagen-status", "remote"], 0)
        output = output.decode("utf-8")
        ca_status = re.search(r"^status: (\w+)$", output, re.MULTILINE).group(1)
        clients = []
        in_cert_section = False
        server_cert_found = False
        for line in output.split("\n"):
            if in_cert_section:
                try:
                    cert_id, cert_type, name, status = line.split(" ")
                    if cert_type == "client":
                        clients.append({
                            "id": cert_id,
                            "name": name,
                            "status": status,
                        })
                    elif cert_type == "server" and status == "valid":
                        server_cert_found = True  # at least one valid server certificate required
                except ValueError:
                    continue
            if line == "## Certs:":
                in_cert_section = True

        # if server cert is missing this means that remote CA hasn't been generated yet
        ca_status = "generating" if ca_status == "ready" and not server_cert_found else ca_status

        return {
            "status": ca_status,
            "tokens": clients,
        }

    def revoke(self, cert_id):
        retval, _, _ = self._run_command(
            "/usr/bin/turris-cagen", "switch", "remote", "revoke", cert_id
        )
        return retval == 0

    def delete_ca(self):
        if RemoteUci().get_settings()["enabled"]:
            return False
        retval, _, _ = self._run_command("/usr/bin/turris-cagen", "drop_ca", "remote")
        return retval == 0


class RemoteUci(object):
    DEFAULTS = {
        "enabled": False,
        "wan_access": False,
        "port": 11883,
    }

    def get_settings(self):
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")
            firewall_data = backend.read("firewall")

        try:
            enabled = parse_bool(get_option_named(
                fosquitto_data, "fosquitto", "remote", "enabled", "0"))
            enabled = enabled and app_info["bus"] == "mqtt"
            port = int(get_option_named(fosquitto_data, "fosquitto", "remote", "port", "11884"))
            wan_access = parse_bool(get_option_named(
                firewall_data, "firewall", "wan_fosquitto_turris_rule", "enabled", "0"))

        except UciException:
            return RemoteUci.DEFAULTS

        return {
            "enabled": enabled,
            "port": port,
            "wan_access": wan_access,
        }

    def update_settings(self, enabled, wan_access=None, port=None):
        result = True

        # set enabled to False when there is non compatible bus
        if app_info["bus"] != "mqtt":
            enabled = False
            result = False  # fail to set enabled = True due to incompatible bus

        # can't set when CA is missing
        if CaGenCmds().get_status()["status"] != "ready" and enabled:
            enabled = False
            result = False

        with UciBackend() as backend:
            if enabled:

                backend.add_section("firewall", "rule", "wan_fosquitto_turris_rule")
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "name", "fosquitto_wan")
                backend.set_option(
                    "firewall", "wan_fosquitto_turris_rule", "enabled", store_bool(wan_access))
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "target", "ACCEPT")
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "dest_port", port)
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "proto", "tcp")
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "src", "wan")

                backend.add_section("fosquitto", "remote", "remote")
                backend.set_option("fosquitto", "remote", "enabled", store_bool(True))
                backend.set_option("fosquitto", "remote", "port", port)

            else:
                backend.add_section("firewall", "rule", "wan_fosquitto_turris_rule")
                backend.set_option(
                    "firewall", "wan_fosquitto_turris_rule", "enabled", store_bool(False))

                backend.add_section("fosquitto", "remote", "remote")
                backend.set_option("fosquitto", "remote", "enabled", store_bool(False))

        with OpenwrtServices() as services:
            services.reload("firewall")
            if app_info["bus"] == "mqtt":
                services.enable("fosquitto", fail_on_error=False)  # might be already enabled
                services.restart("fosquitto")
            else:
                # Stop fosquitto when running incomaptible bus (best effort)
                services.disable("fosquitto", fail_on_error=False)
                services.stop("fosquitto", fail_on_error=False)

        return result

    def list_subordinates(self):
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")

        res = []

        for item in get_sections_by_type(fosquitto_data, "fosquitto", "subordinate"):
            controller_id = item["name"]
            enabled = parse_bool(item["data"].get("enabled", "0"))
            res.append(
                {
                    "controller_id": controller_id, "enabled": enabled,
                    "custom_name": item["data"].get("custom_name", ""),
                }
            )

        return res

    @staticmethod
    def add_subordinate(controller_id: str, address: str, port: int):
        with UciBackend() as backend:
            backend.add_section("fosquitto", "subordinate", controller_id)
            backend.set_option("fosquitto", controller_id, "enabled", store_bool(True))
            backend.set_option("fosquitto", controller_id, "address", address)
            backend.set_option("fosquitto", controller_id, "port", port)

    def set_subordinate(self, controller_id: str, enabled: bool, custom_name: str) -> bool:
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")
            try:
                get_section(fosquitto_data, "fosquitto", controller_id)
            except UciRecordNotFound:
                return False

            backend.set_option("fosquitto", controller_id, "enabled", store_bool(enabled))
            backend.set_option("fosquitto", controller_id, "custom_name", custom_name)

        with OpenwrtServices() as services:
            services.reload("fosquitto")

        return True

    @staticmethod
    def del_subordinate(controller_id: str) -> bool:
        with UciBackend() as backend:
            try:
                backend.del_section("fosquitto", controller_id)
            except UciException:
                return False

        with OpenwrtServices() as services:
            services.reload("fosquitto")

        return True


class RemoteFiles(BaseFile):
    BASE_CERT_PATH = "/etc/ssl/ca/remote"

    def detect_location(self):
        """
        :returns: (hostname, ips, dhcp_names)
        """
        ips = {"wan": [], "lan": []}
        dhcp_names = {"wan": "", "lan": ""}

        def get_dhcp_name_from_network(network_data, network_name):
            proto = get_option_named(network_data, "network", network_name, "proto", "none")
            if proto == "dhcp":
                return get_option_named(network_data, "network", network_name, "hostname", "")
            return ""

        def get_ips_from_network(network_data, network_name):
            proto = get_option_named(network_data, "network", network_name, "proto", "none")
            if proto == "static":
                ip = get_option_named(network_data, "network", network_name, "ipaddr", "")
                # according to openwrt doc ipaddr can be list as well or space separated option
                if isinstance(ip, str):
                    return [e for e in ip.split(" ") if e]
                else:  # list
                    return ip
            return []

        def get_ips_from_cmd(network_name):
            retval, stdout, stderr = BaseCmdLine._run_command("/sbin/ifstatus", network_name)
            if retval != 0:
                return []
            try:
                data = json.loads(stdout)
            except ValueError:
                return []
            try:
                return [e["address"] for e in data["ipv4-address"]]
            except KeyError:
                return []

        # from uci
        with UciBackend() as backend:
            network_data = backend.read("network")
            system_data = backend.read("system")
            fosquitto_data = backend.read("fosquitto")

        ips["wan"].extend(get_ips_from_network(network_data, "wan"))
        ips["lan"].extend(get_ips_from_network(network_data, "lan"))
        ips["wan"].extend(get_ips_from_cmd("wan"))
        ips["lan"].extend(get_ips_from_cmd("lan"))

        # remove ip duplicities, preserver order
        for network in ips:
            ips[network] = [e for e in OrderedDict((ip, None) for ip in ips[network])]

        dhcp_names = {
            "wan": get_dhcp_name_from_network(network_data, "wan"),
            "lan": get_dhcp_name_from_network(network_data, "lan"),
        }

        hostname = get_option_anonymous(system_data, "system", "system", 0, "hostname", "")
        port = int(get_option_named(fosquitto_data, "fosquitto", "remote", "port", "11884"))

        return hostname, port, ips, dhcp_names

    def get_token(self, id, name):
        cert_content = self._file_content(os.path.join(RemoteFiles.BASE_CERT_PATH, "%s.crt" % id))
        key_content = self._file_content(os.path.join(RemoteFiles.BASE_CERT_PATH, "%s.key" % id))
        ca_content = self._file_content(os.path.join(RemoteFiles.BASE_CERT_PATH, "ca.crt"))

        def add_to_tar(tar, name, content):
            data = content.encode()
            fake_file = BytesIO(data)
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o0600
            fake_file.seek(0)
            tar.addfile(info, fake_file)
            fake_file.close()

        fake_file = BytesIO()
        with tarfile.open(fileobj=fake_file, mode="w:gz") as tar:
            add_to_tar(tar, "%s/token.crt" % name, cert_content)
            add_to_tar(tar, "%s/token.key" % name, key_content)
            add_to_tar(tar, "%s/ca.crt" % name, ca_content)
            hostname, port, ips, dhcp_names = self.detect_location()
            add_to_tar(tar, "%s/conf.json" % name, json.dumps({
                "name": name,
                "hostname": hostname,
                "ipv4_ips": ips,
                "dhcp_names": dhcp_names,
                "port": port,
                "device_id": app_info["controller_id"],
            }))

        fake_file.seek(0)
        final_content = fake_file.read()
        fake_file.close()

        return base64.b64encode(final_content).decode()

    @staticmethod
    def extract_token_subordinate(token: str) -> typing.Tuple[dict, dict]:
        token_data = BytesIO(base64.b64decode(token))
        with tarfile.open(fileobj=token_data, mode="r:gz") as tar:
            config_file = [e.name for e in tar.getmembers() if e.name.endswith(".json")][0]
            with tar.extractfile(config_file) as f:
                conf = json.load(f)
            file_data = {}
            for member in tar.getmembers():
                with tar.extractfile(member.name) as f:
                    file_data[os.path.basename(member.name)] = f.read()
        return conf, file_data

    @staticmethod
    def store_subordinate_files(controller_id: str, file_data: dict):
        path_root = pathlib.Path("/etc/fosquitto/bridges") / controller_id
        makedirs(str(path_root), 0o0777)
        for name, content in file_data.items():
            new_file = pathlib.Path(inject_file_root(str(path_root / name)))
            new_file.touch(0o0600)
            with new_file.open("wb") as f:
                f.write(content)
                f.flush()

    @staticmethod
    def remove_subordinate(controller_id: str):
        path = pathlib.Path("/etc/fosquitto/bridges") / controller_id
        shutil.rmtree(inject_file_root(str(path)), True)


class RemoteComplex:
    def add_subordinate(self, token):
        if not app_info["bus"] == "mqtt":
            return {"result": False}

        conf, file_data = RemoteFiles.extract_token_subordinate(token)

        with subordinate_dir_lock.writelock:
            forbidden_controller_ids = [app_info["controller_id"]] + [
                e["controller_id"] for e in RemoteUci().list_subordinates()
            ]  # my controller_id + already stored controller ids

            if conf["device_id"] in forbidden_controller_ids:
                return {"result": False}

            RemoteFiles.store_subordinate_files(conf["device_id"], file_data)
            RemoteUci.add_subordinate(conf["device_id"], conf["ipv4_ips"][0], conf["port"])

        with OpenwrtServices() as services:
            services.reload("fosquitto")

        return {"result": True, "controller_id": conf["device_id"]}

    def del_subordinate(self, controller_id):

        with subordinate_dir_lock.writelock:
            if not RemoteUci.del_subordinate(controller_id):
                return False
            RemoteFiles.remove_subordinate(controller_id)

        with OpenwrtServices() as services:
            services.reload("fosquitto")

        return True
