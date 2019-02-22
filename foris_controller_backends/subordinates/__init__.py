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
import logging
import tarfile
import base64
import json
import typing
import pathlib
import shutil

from io import BytesIO

from foris_controller.app import app_info

from foris_controller_backends.files import BaseFile, makedirs, inject_file_root
from foris_controller_backends.uci import (
    UciBackend, parse_bool, UciException, store_bool,
    get_sections_by_type, get_section, UciRecordNotFound
)
from foris_controller.utils import RWLock
from foris_controller_backends.services import OpenwrtServices

logger = logging.getLogger(__name__)


subordinate_dir_lock = RWLock(app_info["lock_backend"])


class SubordinatesUci(object):

    def list_subordinates(self):
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")

        res = []
        subordinates_map = {}

        for item in get_sections_by_type(fosquitto_data, "fosquitto", "subsubordinate"):
            if "via" in item["data"]:
                subsubs = subordinates_map.get(item["data"]["via"], [])
                subsubs.append({
                    "controller_id": item["name"],
                    "custom_name": item["data"].get("custom_name", ""),
                    "enabled": parse_bool(item["data"].get("enabled", "1")),
                })
                subordinates_map[item["data"]["via"]] = subsubs

        for item in get_sections_by_type(fosquitto_data, "fosquitto", "subordinate"):
            controller_id = item["name"]
            enabled = parse_bool(item["data"].get("enabled", "0"))
            res.append(
                {
                    "controller_id": controller_id, "enabled": enabled,
                    "custom_name": item["data"].get("custom_name", ""),
                    "subsubordinates": subordinates_map.get(controller_id, []),
                }
            )

        return res

    def add_subsubordinate(self, controller_id, via):
        if not app_info["bus"] == "mqtt":
            return False

        with subordinate_dir_lock.writelock:
            if controller_id in self.existing_controller_ids():
                return False
            if via not in [e["controller_id"] for e in self.list_subordinates()]:
                return False

            with UciBackend() as backend:
                backend.add_section("fosquitto", "subsubordinate", controller_id)
                backend.set_option("fosquitto", controller_id, "via", via)
                backend.set_option("fosquitto", controller_id, "enabled", store_bool(True))

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return True

    def set_subsubordinate(self, controller_id, enabled, custom_name):
        if not app_info["bus"] == "mqtt":
            return False

        with subordinate_dir_lock.writelock:
            sub_list = self.list_subordinates()
            records = [
                e
                for record in sub_list
                for e in record["subsubordinates"]
                if e["controller_id"] == controller_id
            ]

            if not records:
                return False  # missing

            with UciBackend() as backend:
                backend.add_section("fosquitto", "subsubordinate", controller_id)
                backend.set_option("fosquitto", controller_id, "custom_name", custom_name)
                backend.set_option("fosquitto", controller_id, "enabled", store_bool(enabled))

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return True

    def del_subsubordinate(self, controller_id):
        if not app_info["bus"] == "mqtt":
            return False

        with subordinate_dir_lock.writelock:
            sub_list = self.list_subordinates()
            records = [
                e
                for record in sub_list
                for e in record["subsubordinates"]
                if e["controller_id"] == controller_id
            ]

            if not records:
                return False  # missing

            with UciBackend() as backend:
                backend.del_section("fosquitto", controller_id)

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return True

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
            services.restart("fosquitto")

        return True

    @staticmethod
    def del_subordinate(controller_id: str) -> bool:
        with UciBackend() as backend:
            fosquitto_data = backend.read("fosquitto")
            to_delete = [
                e["name"] for e in
                get_sections_by_type(fosquitto_data, "fosquitto", "subsubordinate")
                if e["data"].get("via") == controller_id
            ]
            try:
                backend.del_section("fosquitto", controller_id)
                for id_to_delete in to_delete:
                    backend.del_section("fosquitto", id_to_delete)
            except UciException:
                return False

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return True

    def existing_controller_ids(self):
        sub_list = self.list_subordinates()
        return [app_info["controller_id"]] + [
            e["controller_id"] for e in sub_list
        ] + [
            e["controller_id"]
            for record in sub_list
            for e in record["subsubordinates"]
        ]


class SubordinatesFiles(BaseFile):
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

            try:  # try chown (best effort)
                shutil.chown(new_file, "mosquitto", "mosquitto")
            except (LookupError, PermissionError):
                pass

    @staticmethod
    def remove_subordinate(controller_id: str):
        path = pathlib.Path("/etc/fosquitto/bridges") / controller_id
        shutil.rmtree(inject_file_root(str(path)), True)


class SubordinatesComplex:
    def add_subordinate(self, token):
        if not app_info["bus"] == "mqtt":
            return {"result": False}

        conf, file_data = SubordinatesFiles.extract_token_subordinate(token)

        with subordinate_dir_lock.writelock:

            if conf["device_id"] in SubordinatesUci().existing_controller_ids():
                return {"result": False}

            SubordinatesFiles.store_subordinate_files(conf["device_id"], file_data)

            guessed_ip = ""
            # it would be more common to use wan ip first
            if conf["ipv4_ips"].get("wan", None):
                guessed_ip = conf["ipv4_ips"]["wan"][0]
            elif conf["ipv4_ips"].get("lan", None):
                guessed_ip = conf["ipv4_ips"]["lan"][0]

            SubordinatesUci.add_subordinate(conf["device_id"], guessed_ip, conf["port"])

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return {"result": True, "controller_id": conf["device_id"]}

    def del_subordinate(self, controller_id):

        with subordinate_dir_lock.writelock:
            if not SubordinatesUci.del_subordinate(controller_id):
                return False
            SubordinatesFiles.remove_subordinate(controller_id)

        with OpenwrtServices() as services:
            services.restart("fosquitto")

        return True
