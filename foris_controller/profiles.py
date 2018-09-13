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


WORKFLOW_OLD = "old"
WORKFLOW_ROUTER = "router"
WORKFLOW_MIN = "min"

STEP_PASSWORD = "password"
STEP_PROFILE = "profile"
STEP_NETWORKS = "networks"
STEP_WAN = "wan"
STEP_TIME = "time"
STEP_DNS = "dns"
STEP_UPDATER = "updater"


WORKFLOWS = {
    WORKFLOW_OLD: [
        STEP_PASSWORD,
        STEP_WAN,
        STEP_TIME,
        STEP_DNS,
        STEP_UPDATER,
    ],
    WORKFLOW_ROUTER: [
        STEP_PASSWORD,
        STEP_PROFILE,
        STEP_NETWORKS,
        STEP_WAN,
        STEP_TIME,
        STEP_DNS,
        STEP_UPDATER,
    ],
    WORKFLOW_MIN: [
        STEP_PASSWORD,
        STEP_PROFILE,
    ],
}


def next_step(passed, workflow):
    """ Returns next step in a given workflow or None (if finihsed)

    :param passed: list of passed steps
    :type passed: list
    :param workflow: workflow name
    :type workflow: str

    :returns: next step if needed or None
    :rtype: str or None
    """
    for step in WORKFLOWS[workflow]:
        if step not in passed:
            return step
    return None
