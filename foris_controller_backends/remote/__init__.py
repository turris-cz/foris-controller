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

from io import BytesIO
from collections import OrderedDict

from foris_controller.app import app_info

from foris_controller_backends.cmdline import AsyncCommand, BaseCmdLine
from foris_controller_backends.files import BaseFile, path_exists, makedirs
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    parse_bool,
    UciException,
    store_bool,
    get_option_anonymous,
)
from foris_controller_backends.networks import NetworksCmd
from foris_controller_backends.services import OpenwrtServices

logger = logging.getLogger(__name__)

NETBOOT_CONFIGURED_PATH = "/tmp/netboot-configured"


class RemoteAsync(AsyncCommand):
    def generate_ca(self, notify_function, exit_notify_function, reset_notify_function):
        def handler_exit(process_data):
            exit_notify_function(
                {
                    "task_id": process_data.id,
                    "status": "succeeded" if process_data.get_retval() == 0 else "failed",
                }
            )

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
            exit_notify_function(
                {
                    "task_id": process_data.id,
                    "name": name,
                    "status": "succeeded" if process_data.get_retval() == 0 else "failed",
                }
            )

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


class RemoteCmds(BaseCmdLine):
    def get_status(self):
        output, _ = self._run_command_and_check_retval(
            ["/usr/bin/turris-cagen-status", "remote"], 0
        )
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
                        clients.append({"id": cert_id, "name": name, "status": status})
                    elif cert_type == "server" and status == "valid":
                        server_cert_found = True  # at least one valid server certificate required
                except ValueError:
                    continue
            if line == "## Certs:":
                in_cert_section = True

        # if server cert is missing this means that remote CA hasn't been generated yet
        ca_status = "generating" if ca_status == "ready" and not server_cert_found else ca_status

        return {"status": ca_status, "tokens": clients}

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

    def get_netboot_status(self):
        output, _ = self._run_command_and_check_retval(["/bin/mount"], 0)
        for line in output.decode().split("\n"):
            match = re.match(r"^.* on / type (\w+) .*$", line)
            if match:
                if match.group(1) != "tmpfs":
                    return "no"
                break

        # we are in netboot
        return "ready" if path_exists(NETBOOT_CONFIGURED_PATH) else "booted"


class RemoteUci(object):
    DEFAULTS = {"enabled": False, "wan_access": False, "port": 11883}

    def get_settings(self):
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")
            firewall_data = backend.read("firewall")

        try:
            enabled = parse_bool(
                get_option_named(fosquitto_data, "fosquitto", "remote", "enabled", "0")
            )
            enabled = enabled and app_info["bus"] == "mqtt"
            port = int(get_option_named(fosquitto_data, "fosquitto", "remote", "port", "11884"))
            wan_access = parse_bool(
                get_option_named(
                    firewall_data, "firewall", "wan_fosquitto_turris_rule", "enabled", "0"
                )
            )

        except UciException:
            return RemoteUci.DEFAULTS

        return {"enabled": enabled, "port": port, "wan_access": wan_access}

    def update_settings(self, enabled, wan_access=None, port=None):
        result = True

        # set enabled to False when there is non compatible bus
        if app_info["bus"] != "mqtt":
            enabled = False
            result = False  # fail to set enabled = True due to incompatible bus

        # can't set when CA is missing
        if RemoteCmds().get_status()["status"] != "ready" and enabled:
            enabled = False
            result = False

        with UciBackend() as backend:
            if enabled:

                backend.add_section("firewall", "rule", "wan_fosquitto_turris_rule")
                backend.set_option("firewall", "wan_fosquitto_turris_rule", "name", "fosquitto_wan")
                backend.set_option(
                    "firewall", "wan_fosquitto_turris_rule", "enabled", store_bool(wan_access)
                )
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
                    "firewall", "wan_fosquitto_turris_rule", "enabled", store_bool(False)
                )

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


class RemoteFiles(BaseFile):
    BASE_CERT_PATH = "/etc/ssl/ca/remote"

    def set_netboot_configured(self):
        makedirs(os.path.dirname(NETBOOT_CONFIGURED_PATH), exist_ok=True)
        self._store_to_file(NETBOOT_CONFIGURED_PATH, "")
        return True

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

        def get_ipv4_addresses_from_uci(network_data, network_name):
            proto = get_option_named(network_data, "network", network_name, "proto", "none")
            if proto == "static":
                ip = get_option_named(network_data, "network", network_name, "ipaddr", "")
                # according to openwrt doc ipaddr can be list as well or space separated option
                if isinstance(ip, str):
                    return [e for e in ip.split(" ") if e]
                else:  # list
                    return ip
            return []

        def get_ipv4_addresess_from_cmd(network_name):
            network_info = NetworksCmd().get_network_info(network_name)
            if not network_info:
                # not found
                return []
            else:
                return network_info["ipv4"]

        # from uci
        with UciBackend() as backend:
            network_data = backend.read("network")
            system_data = backend.read("system")
            fosquitto_data = backend.read("fosquitto")

        ips["wan"].extend(get_ipv4_addresses_from_uci(network_data, "wan"))
        ips["lan"].extend(get_ipv4_addresses_from_uci(network_data, "lan"))
        ips["wan"].extend(get_ipv4_addresess_from_cmd("wan"))
        ips["lan"].extend(get_ipv4_addresess_from_cmd("lan"))

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
            add_to_tar(
                tar,
                "%s/conf.json" % name,
                json.dumps(
                    {
                        "name": name,
                        "hostname": hostname,
                        "ipv4_ips": ips,
                        "dhcp_names": dhcp_names,
                        "port": port,
                        "device_id": app_info["controller_id"],
                    }
                ),
            )

        fake_file.seek(0)
        final_content = fake_file.read()
        fake_file.close()

        return base64.b64encode(final_content).decode()
