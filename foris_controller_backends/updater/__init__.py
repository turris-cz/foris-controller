#
# foris-controller
# Copyright (C) 2019-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import typing
from datetime import datetime
from functools import wraps

from foris_controller.exceptions import UciException
from foris_controller.updater import (
    svupdater,
    svupdater_approvals,
    svupdater_autorun,
    svupdater_exceptions,
    svupdater_l10n,
    svupdater_lists,
    svupdater_packages,
)

logger = logging.getLogger(__name__)


def run_updater_after(func):
    """ Decorator to run pkgupdate after function finishes"""
    @wraps(func)
    def inner(*args, **kwargs):
        res = func(*args, **kwargs)

        if svupdater_autorun.enabled():
            try:
                svupdater.run()
            except svupdater_exceptions.ExceptionUpdaterDisabled:
                pass  # failed to run updater, but settings were updated

        return res

    return inner


class UpdaterUci(object):
    def get_settings(self, lang="en"):

        res = {
            "enabled": svupdater_autorun.enabled(),
            "user_lists": [],  # don't return package lists, return empty list for compatibility instead
            "languages": svupdater_l10n.languages(),
            "approval_settings": {"status": "on" if svupdater_autorun.approvals() else "off"},
        }

        delay_time = svupdater_autorun.auto_approve_time()
        if delay_time:
            res["approval_settings"]["delay"] = delay_time
            if res["approval_settings"]["status"] == "on":
                res["approval_settings"]["status"] = "delayed"

        return res

    def get_enabled(self) -> typing.Optional[bool]:
        return svupdater_autorun.enabled()

    @run_updater_after
    def update_settings(self, languages, approvals_status, approvals_delay, enabled):
        svupdater_autorun.set_enabled(enabled)

        if approvals_status is not None:
            if approvals_status == "off":
                svupdater_autorun.set_approvals(False)
            elif approvals_status == "on":
                svupdater_autorun.set_approvals(True)
                svupdater_autorun.set_auto_approve_time(0)
            elif approvals_status == "delayed":
                svupdater_autorun.set_approvals(True)
                svupdater_autorun.set_auto_approve_time(approvals_delay)
            else:
                raise NotImplementedError()

        Updater.update_languages(languages)

        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands

            WebUciCommands.update_passed("updater")
        except UciException:
            pass

        return True

    @run_updater_after
    def update_package_lists(self, package_lists):
        svupdater_lists.update_pkglists(self._jsonschema_to_svupdater(package_lists))
        return True

    def _jsonschema_to_svupdater(self, user_lists):
        """Restructure data from jsonschema format into structure that svupdater expects"""
        res = {}
        for lst in user_lists:
            res[lst["name"]] = {opt["name"]: opt["enabled"] for opt in lst.get("options", {})}

        return res


class Updater:
    def updater_running(self):
        """ Returns indicator whether the updater is running
        :returns: True if updater is running False otherwise
        :rtype: bool
        """
        logger.debug("Calling opkg_lock() check whether the updater is running")
        res = svupdater.opkg_lock()
        logger.debug("opkg_lock() -> %s", res)
        return res

    def get_approval(self):
        """ Returns current approval
        :returns: approval
        :rtype: dict
        """
        logger.debug("Try to get current approval.")
        approval = svupdater_approvals.current()
        logger.debug("Approval obtained: %s", approval)
        if approval:
            approval["present"] = True
            approval["time"] = datetime.fromtimestamp(approval["time"]).isoformat()
            approval["reboot"] = bool(approval["reboot"])

            # remove cur_ver: None and new_ver: None
            for record in approval["plan"]:
                if record["new_ver"] is None:
                    del record["new_ver"]
                if record["cur_ver"] is None:
                    del record["cur_ver"]

            return approval
        else:
            return {"present": False}

    @staticmethod
    def _get_options(lst):
        """Reformat key-value dictionary into flat structure"""
        options = []

        for name, data in lst.get("options", {}).items():
            item = {
                "name": name,
                "title": data["title"],
                "description": data["description"],
                "enabled": data.get("enabled", data.get("default", False)),
                "labels": Updater._get_labels(data["labels"]),
            }
            if data["url"] is not None:
                item["url"] = data["url"]

            options.append(item)

        return options

    @staticmethod
    def _get_labels(labels):
        """Reformat nested dictionary into flat structure"""

        return [
            {
                "name": name,
                "title": data["title"],
                "description": data["description"],
                "severity": data["severity"],
            }
            for name, data in labels.items()
        ]

    @staticmethod
    def get_package_lists(lang):
        logger.debug("Getting package lists for '%s'", lang)
        package_lists = svupdater_lists.pkglists(lang)
        logger.debug("Package lists obtained: %s", package_lists)

        exported = []
        for lst_name, lst in package_lists.items():
            item = {
                "name": lst_name,
                "enabled": lst["enabled"],
                "title": lst["title"],
                "description": lst["description"],
                "options": Updater._get_options(lst),
                "labels": Updater._get_labels(lst["labels"]),
            }
            if lst["url"] is not None:
                item["url"] = lst["url"]

            exported.append(item)

        return exported

    @staticmethod
    def query_installed_packages(packages: typing.List[str]) -> typing.List[str]:
        """ Query whether packages are installed or provided by another packages """
        ret = []

        status = svupdater_packages.Status()
        for package in packages:
            if status.installed(package):
                # we don't care about particular package names
                # it just need to be installed or provided by another package
                ret.append(package)

        return sorted(ret)

    @staticmethod
    def get_languages():
        logger.debug("Getting languages")
        languages = svupdater_l10n.languages()
        logger.debug("Languages obtained: %s", languages)
        return [{"code": k, "enabled": v} for k, v in languages.items()]

    @staticmethod
    @run_updater_after
    def update_languages(languages):
        if languages is not None:
            svupdater_l10n.update_languages(languages)

        return True

    def resolve_approval(self, approval_id, solution):
        """ Resolves approval
        """
        try:
            logger.debug("Resolving approval %s (->%s)", approval_id, solution)
            svupdater_approvals.approve(
                approval_id
            ) if solution == "grant" else svupdater_approvals.deny(approval_id)
            logger.debug("Approval resolved %s (->%s)", approval_id, solution)

            # Run updater after approval was granted
            if solution == "grant":
                try:
                    self.run(False)
                except svupdater_exceptions.ExceptionUpdaterDisabled:
                    pass  # updater failed to run, but approval was resolved

        except svupdater_exceptions.ExceptionUpdaterApproveInvalid:
            logger.warning("Failed to resolve approval %s (->%s)", approval_id, solution)

            return False

        return True

    def run(self, set_reboot_indicator):
        """ Starts updater run
        """

        try:
            logger.debug(
                "Staring to trigger updater (set_reboot_indicator=%s)", set_reboot_indicator
            )
            hooks = ["/usr/bin/maintain-reboot-needed"] if set_reboot_indicator else []
            svupdater.run(hooklist=hooks)
            logger.debug("Updater triggered")
        except svupdater_exceptions.ExceptionUpdaterDisabled:
            return False

        return True
