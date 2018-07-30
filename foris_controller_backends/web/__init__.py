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

import logging
import os

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
    def get_guide(foris_data):

        finished = parse_bool(get_option_named(foris_data, "foris", "wizard", "finished", '0'))
        # remedy for migration from older wizard
        step = int(get_option_named(foris_data, "foris", "wizard", "allowed_step_max", '0'))
        enabled = not finished and step < 7
        workflow = get_option_named(foris_data, "foris", "wizard", "workflow", 'standard')
        passed = get_option_named(foris_data, "foris", "wizard", "passed", [])

        return {
            "enabled": enabled,
            "workflow": workflow,
            "passed": passed,
        }

    def update_guide(self, enabled, workflow):

        with UciBackend() as backend:
            backend.add_section("foris", "config", "wizard")
            backend.set_option("foris", "wizard", "finished", store_bool(not enabled))
            backend.set_option("foris", "wizard", "workflow", workflow)

        return True

    def get_data(self):
        with UciBackend() as backend:
            data = backend.read("foris")

        return {
            "password_ready": ForisPasswordUci.is_password_set(data),
            "language": WebUciCommands.get_language(data),
            "guide": WebUciCommands.get_guide(data),
        }

    @staticmethod
    def update_passed(step):
        with UciBackend() as backend:
            data = backend.read("foris")
            passed = get_option_named(data, "foris", "wizard", "passed", [])
            if step not in passed:
                backend.add_section("foris", "config", "wizard")
                backend.add_to_list("foris", "wizard", "passed", [step])


class Languages(object):
    INSTALLED_LANG_MATCHES = [
        "/usr/lib/python2.7/site-packages/foris/langs/??.py",
        "/usr/lib/python2.7/site-packages/foris/langs/??_??.py",
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
