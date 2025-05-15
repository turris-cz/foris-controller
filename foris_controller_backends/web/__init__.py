#
# foris-controller
# Copyright (C) 2020-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import typing

import turrishw

from foris_controller import profiles
from foris_controller.exceptions import UciException, UciRecordNotFound
from foris_controller_backends.about import SystemInfoFiles
from foris_controller_backends.files import BaseMatch
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.password import ForisPasswordUci
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    parse_bool,
    store_bool,
)
from foris_controller_backends.wan import WanUci

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"


class WebUciCommands:
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
    def _get_configurable_ifaces():
        return [k for k, v in turrishw.get_ifaces().items() if v["type"] != "wifi"]

    @staticmethod
    def _detect_basic_workflow() -> str:
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) < 4:
            return profiles.Workflow.OLD.value
        else:
            if SystemInfoFiles().get_model() == "turris":
                return profiles.Workflow.OLD.value
            elif SystemInfoFiles().get_contract() == "shield":
                return profiles.Workflow.SHIELD.value
        return profiles.Workflow.UNSET.value

    @staticmethod
    def _detect_recommended_workflow() -> str:
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) > 3:
            if SystemInfoFiles().get_model() == "turris":
                return profiles.Workflow.OLD.value
            else:
                if len(WebUciCommands._get_configurable_ifaces()) > 1:
                    return profiles.Workflow.ROUTER.value
                else:
                    return profiles.Workflow.BRIDGE.value

        return profiles.Workflow.OLD.value

    @staticmethod
    def _detect_available_workflows():
        model = SystemInfoFiles().get_model()
        if int(SystemInfoFiles().get_os_version().split(".", 1)[0]) >= 4:
            if model == "turris":
                return [profiles.Workflow.OLD.value]
            else:
                if len(WebUciCommands._get_configurable_ifaces()) > 1:
                    return [
                        e.value
                        for e in profiles.get_workflows()
                        if e
                        not in (
                            profiles.Workflow.OLD,
                            profiles.Workflow.UNSET,
                            profiles.Workflow.SHIELD,
                        )
                    ]
                else:
                    return [profiles.Workflow.MIN.value, profiles.Workflow.BRIDGE.value]
        if model in ["turris", "omnia"]:
            return [profiles.Workflow.OLD.value]
        return []

    @staticmethod
    def get_guide_data(foris_data):

        finished = parse_bool(get_option_named(foris_data, "foris", "wizard", "finished", "0"))
        # remedy for migration from older wizard
        step = int(get_option_named(foris_data, "foris", "wizard", "allowed_step_max", "0"))
        enabled = not finished and step < 7
        workflow = get_option_named(
            foris_data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow()
        )
        passed = get_option_named(foris_data, "foris", "wizard", "passed", [])

        res = {"enabled": enabled, "workflow": workflow, "passed": passed}
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
                foris_data = backend.read("foris")
                backend.add_section("foris", "config", "wizard")
                backend.set_option("foris", "wizard", "finished", store_bool(True))
            if profiles.Step.PASSWORD in self.get_guide_data(foris_data)["passed"]:
                # if a password was try to update wan if it ws not configured
                if WanUci().update_unconfigured_wan_to_default():
                    MaintainCommands().restart_network()

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
    def update_passed(step: typing.Union[str, profiles.Step]):
        step = step.value if isinstance(step, profiles.Step) else step
        with UciBackend() as backend:
            data = backend.read("foris")
            passed = get_option_named(data, "foris", "wizard", "passed", [])
            if step not in passed:
                passed += [step]
                backend.add_section("foris", "config", "wizard")
                backend.replace_list("foris", "wizard", "passed", passed)
            workflow = get_option_named(
                data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow()
            )
            if set(profiles.get_workflows()[workflow]).issubset(set(passed)):
                backend.add_section("foris", "config", "wizard")
                backend.set_option("foris", "wizard", "finished", store_bool(True))

    def get_guide(self):
        with UciBackend() as backend:
            data = backend.read("foris")
        current_workflow = get_option_named(
            data, "foris", "wizard", "workflow", WebUciCommands._detect_basic_workflow()
        )
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
                backend.del_option("foris", "wizard", "passed", fail_on_error=False)
                backend.del_option("foris", "wizard", "finished", fail_on_error=False)
                backend.add_section("foris", "config", "wizard")
                workflow = new_workflow if new_workflow else WebUciCommands._detect_basic_workflow()
                backend.set_option("foris", "wizard", "workflow", workflow)
        except (UciException, UciRecordNotFound):
            return False
        return True


class Languages():
    # reForis is the only web UI of Turris OS at the moment, so only look for reForis translations
    LANG_DIR = "/usr/lib/python%s.%s/site-packages/reforis/translations" % (
        sys.version_info.major,
        sys.version_info.minor,
    )
    INSTALLED_LANG_MATCHES = [os.path.join(LANG_DIR, "??"), os.path.join(LANG_DIR, "??_??")]

    @staticmethod
    def list_languages() -> typing.List[str]:
        """ List installed languages
        :returns: list of installed languages
        :rtype: list of str
        """

        return list({DEFAULT_LANGUAGE} | {
            os.path.basename(e) for e in BaseMatch.list_files(Languages.INSTALLED_LANG_MATCHES)
        })
