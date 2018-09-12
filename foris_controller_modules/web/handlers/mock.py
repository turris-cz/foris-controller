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

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockWebHandler(Handler, BaseMockHandler):
    guide_workflow = "standard"
    guide_enabled = True
    language_list = ['en', 'de', 'cs', 'nb_NO']
    current_language = 'en'

    def get_language(self):
        """ Mocks get language

        :returns: current language
        :rtype: str
        """
        return self.current_language

    @logger_wrapper(logger)
    def set_language(self, language):
        """ Sets language

        :returns: True
        :rtype: bool
        """
        if language in MockWebHandler.language_list:
            MockWebHandler.current_language = language
            return True
        return False

    @logger_wrapper(logger)
    def list_languages(self):
        """ Lists languages

        :returns: available languages
        :rtype: list
        """
        return MockWebHandler.language_list[:]

    def reboot_required(self):
        return False

    def updater_running(self):
        from foris_controller_modules.updater.handlers.mock import MockUpdaterHandler
        return MockUpdaterHandler.updater_running

    def get_notification_count(self):
        from foris_controller_modules.router_notifications.handlers.mock import \
                MockRouterNotificationsHandler
        return len([e for e in MockRouterNotificationsHandler.notifications if not e["displayed"]])

    def update_guide(self, enabled, workflow):
        MockWebHandler.guide_enabled = enabled
        MockWebHandler.guide_workflow = workflow
        if not enabled:
            from foris_controller_modules.password.handlers import MockPasswordHandler
            from foris_controller_modules.wan.handlers import MockWanHandler
            from foris_controller_modules.time.handlers import MockTimeHandler
            from foris_controller_modules.dns.handlers import MockDnsHandler
            from foris_controller_modules.updater.handlers import MockUpdaterHandler
            # Clean passed in mock backend
            for e in [
                MockPasswordHandler,
                MockWanHandler,
                MockTimeHandler,
                MockDnsHandler,
                MockUpdaterHandler,
            ]:
                e.guide_set.set(False)
        return True

    def get_guide(self):
        from foris_controller_modules.password.handlers import MockPasswordHandler
        from foris_controller_modules.wan.handlers import MockWanHandler
        from foris_controller_modules.time.handlers import MockTimeHandler
        from foris_controller_modules.dns.handlers import MockDnsHandler
        from foris_controller_modules.updater.handlers import MockUpdaterHandler
        from foris_controller_modules.networks.handlers import MockNetworksHandler
        passed = [
            e[0] for e in [
                ("password", MockPasswordHandler),
                ("networks", MockNetworksHandler),
                ("wan", MockWanHandler),
                ("time", MockTimeHandler),
                ("dns", MockDnsHandler),
                ("updater", MockUpdaterHandler),
            ] if e[1].guide_set.get()
        ]
        return {
            "enabled": MockWebHandler.guide_enabled,
            "workflow": MockWebHandler.guide_workflow,
            "passed": passed,
        }

    def is_password_set(self):
        from foris_controller_modules.password.handlers import MockPasswordHandler
        return MockPasswordHandler.guide_set.get()

    @logger_wrapper(logger)
    def get_data(self):
        return {
            'language': self.get_language(),
            'reboot_required': self.reboot_required(),
            'updater_running': self.updater_running(),
            'notification_count': self.get_notification_count(),
            'guide': self.get_guide(),
            'password_ready': self.is_password_set(),
        }
