#
# foris-controller
# Copyright (C) 2025 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from copy import deepcopy
from enum import Enum
from functools import lru_cache
from importlib import metadata


logger = logging.getLogger(__name__)


class Workflow(str, Enum):
    UNSET = "unset"
    OLD = "old"
    ROUTER = "router"
    MIN = "min"
    SHIELD = "shield"
    BRIDGE = "bridge"


class Step(str, Enum):
    PASSWORD = "password"
    PROFILE = "profile"
    NETWORKS = "networks"
    WAN = "wan"
    TIME = "time"
    DNS = "dns"
    UPDATER = "updater"
    LAN = "lan"
    FINISHED = "finished"


WORKFLOWS = {
    Workflow.OLD: [Step.PASSWORD, Step.WAN, Step.TIME, Step.DNS, Step.UPDATER, Step.FINISHED],
    Workflow.ROUTER: [
        Step.PASSWORD,
        Step.PROFILE,
        Step.NETWORKS,
        Step.WAN,
        Step.TIME,
        Step.DNS,
        Step.UPDATER,
        Step.FINISHED,
    ],
    Workflow.MIN: [Step.PASSWORD, Step.PROFILE, Step.FINISHED],
    Workflow.SHIELD: [Step.PASSWORD, Step.FINISHED],
    Workflow.BRIDGE: [
        Step.PASSWORD,
        Step.PROFILE,
        Step.NETWORKS,
        Step.LAN,
        Step.TIME,
        Step.DNS,
        Step.UPDATER,
        Step.FINISHED,
    ],
    Workflow.UNSET: [Step.PASSWORD, Step.PROFILE],
}


@lru_cache
def get_workflows():
    workflows = deepcopy(WORKFLOWS)

    extra_workflows = []
    for entry_point in metadata.entry_points(group="foris_controller_workflow_extras"):
        logger.debug("Loading workflow extras entry point %s", entry_point.name)
        for priority, name, workflow, *rest in entry_point.load():
            if not isinstance(priority, int) or not isinstance(name, str) or not isinstance(workflow, str) or rest:
                logger.warning("Wrong extras entry point format for %s", entry_point.name)
                continue
            logger.debug("Added extra step '%s' for workflow '%s'", name, workflow)
            extra_workflows.append((priority, name, workflow))

    extra_workflows.sort()  # sort order priority, name

    for workflow in workflows:
        extras = [e[1] for e in extra_workflows if e[2] == workflow]
        if extras:
            if workflow == Workflow.UNSET:
                logger.warning("Can't modify 'UNSET' workflow")
                continue

            workflows[workflow] = workflows[workflow][:-1] + extras + [workflows[workflow][-1]]

    return workflows


def next_step(passed, workflow: Workflow):
    """Returns next step in a given workflow or None (if finihsed)

    :param passed: list of passed steps
    :type passed: list
    :param workflow: workflow name
    :type workflow: str

    :returns: next step if needed or None
    :rtype: str or None
    """
    for step in get_workflows()[workflow]:
        if step not in passed:
            return step
    return None
