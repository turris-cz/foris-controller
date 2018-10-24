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
import os
import sys
import turrishw

from foris_controller import profiles
from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.files import BaseMatch
from foris_controller_backends.password import ForisPasswordUci
from foris_controller_backends.uci import UciBackend, get_option_named, store_bool, parse_bool
from foris_controller.exceptions import UciException, UciRecordNotFound

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"


class WebUciCommands(object):

    @staticmethod
    def get_language(foris_data):
        try:
            return get_option_named(foris_data, "foris", "settings", "lang")
        except UciRecordNotFound:
            return DEFAULT_LANGUAGE

    def set_language(self, language):
        if language not in Languages.list_languages():
            return False

        with UciBackend() as backend:
            backend.add_section("foris", "config", "settings")
            backend.set_option("foris", "settings", "lang", language)
            # try to update LUCI as well (best effort)
            try:
                backend.add_section("luci", "core", "main")
                backend.set_option("luci", "main", "lang", language)
            except UciException:
                pass

        return True

    @staticmethod
    def _detect_basic_workflow():
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) < 4:
            return profiles.WORKFLOW_OLD
        else:
            if SystemInfoFiles().get_model() == "turris":
                return profiles.WORKFLOW_OLD
        return profiles.WORKFLOW_UNSET

    @staticmethod
    def _detect_recommended_workflow():
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) > 3:
            if SystemInfoFiles().get_model() == "turris":
                return profiles.WORKFLOW_OLD
            else:
                if len(turrishw.get_ifaces()) > 1:
                    return profiles.WORKFLOW_ROUTER
                else:
                    return profiles.WORKFLOW_BRIDGE

        return profiles.WORKFLOW_OLD

    @staticmethod
    def _detect_available_workflows():
        model = SystemInfoFiles().get_model()
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) >= 4:
            if model == "turris":
                return [profiles.WORKFLOW_OLD]
            else:
                if len(turrishw.get_ifaces()) > 1:
                    return [
                        e for e in profiles.WORKFLOWS if e not in (
                            profiles.WORKFLOW_OLD,
                            profiles.WORKFLOW_UNSET,
                        )
                    ]
                else:
                    return [
                        profiles.WORKFLOW_MIN, profiles.WORKFLOW_BRIDGE,
                    ]
        if model in ["turris", "omnia"]:
            return [profiles.WORKFLOW_OLD]
        return []

    @staticmethod
    def get_guide_data(foris_data):

        finished = parse_bool(get_option_named(foris_data, "foris", "wizard", "finished", '0'))
        # remedy for migration from older wizard
        step = int(get_option_named(foris_data, "foris", "wizard", "allowed_step_max", '0'))
        enabled = not finished and step < 7
        workflow = get_option_named(
            foris_data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow()
        )
        passed = get_option_named(foris_data, "foris", "wizard", "passed", [])

        res = {
            "enabled": enabled,
            "workflow": workflow,
            "passed": passed,
        }
        next_step = profiles.next_step(passed, workflow)
        if enabled and next_step:
            res["next_step"] = next_step
        return res

    def update_guide(self, enabled, workflow=None):
        if enabled:
            if workflow not in WebUciCommands._detect_available_workflows():
                return False
            with UciBackend() as backend:
                backend.add_section("foris", "config", "wizard")
                backend.set_option("foris", "wizard", "finished", store_bool(False))
                backend.set_option("foris", "wizard", "workflow", workflow)

            WebUciCommands.update_passed("profile")
        else:
            with UciBackend() as backend:
                backend.add_section("foris", "config", "wizard")
                backend.set_option("foris", "wizard", "finished", store_bool(True))
            WebUciCommands.update_passed("finished")

        return True

    def get_data(self):
        with UciBackend() as backend:
            data = backend.read("foris")

        return {
            "password_ready": ForisPasswordUci.is_password_set(data),
            "language": WebUciCommands.get_language(data),
            "guide": WebUciCommands.get_guide_data(data),
        }

    @staticmethod
    def update_passed(step):
        with UciBackend() as backend:
            data = backend.read("foris")
            passed = get_option_named(data, "foris", "wizard", "passed", [])
            if step not in passed:
                passed += [step]
                backend.add_section("foris", "config", "wizard")
                backend.replace_list("foris", "wizard", "passed", passed)
            workflow = get_option_named(
                data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow())
            if set(profiles.WORKFLOWS[workflow]).issubset(set(passed)):
                backend.add_section("foris", "config", "wizard")
                backend.set_option("foris", "wizard", "finished", store_bool(True))

    def get_guide(self):
        with UciBackend() as backend:
            data = backend.read("foris")
        current_workflow = get_option_named(
            data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow())
        recommended_workflow = WebUciCommands._detect_recommended_workflow()
        available_workflows = WebUciCommands._detect_available_workflows()
        return {
            "current_workflow": current_workflow,
            "recommended_workflow": recommended_workflow,
            "available_workflows": available_workflows,
        }

    def reset_guide(self, new_workflow=None):
        try:
            with UciBackend() as backend:
                try:
                    backend.del_option("foris", "wizard", "passed")
                except (UciRecordNotFound, UciException):
                    pass
                try:
                    backend.del_option("foris", "wizard", "finished")
                except (UciRecordNotFound, UciException):
                    pass
                backend.add_section("foris", "config", "wizard")
                workflow = new_workflow if new_workflow else WebUciCommands._detect_basic_workflow()
                backend.set_option("foris", "wizard", "workflow", workflow)
        except (UciException, UciRecordNotFound):
            return False
        return True


class Languages(object):
    LANG_DIR = "/usr/lib/python%s.%s/site-packages/foris/langs/" % (
        sys.version_info.major, sys.version_info.minor)
    INSTALLED_LANG_MATCHES = [
        os.path.join(LANG_DIR, "??.py"),
        os.path.join(LANG_DIR, "??_??.py"),
    ]

    @staticmethod
    def list_languages():
        """ List installed languages
        :returns: list of installed languages
        :rtype: list of str
        """

        return [DEFAULT_LANGUAGE] + [
            os.path.basename(e)[:-3]
            for e in BaseMatch.list_files(Languages.INSTALLED_LANG_MATCHES)
        ]
