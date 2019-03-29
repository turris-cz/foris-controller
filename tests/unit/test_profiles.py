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

import pytest

from foris_controller import profiles


@pytest.fixture(
    params=[
        (
            profiles.WORKFLOW_OLD,
            [
                profiles.STEP_PASSWORD,
                profiles.STEP_WAN,
                profiles.STEP_TIME,
                profiles.STEP_DNS,
                profiles.STEP_UPDATER,
                profiles.STEP_FINISHED,
            ],
        ),
        (profiles.WORKFLOW_UNSET, [profiles.STEP_PASSWORD, profiles.STEP_PROFILE]),
        (
            profiles.WORKFLOW_MIN,
            [profiles.STEP_PASSWORD, profiles.STEP_PROFILE, profiles.STEP_FINISHED],
        ),
        (
            profiles.WORKFLOW_ROUTER,
            [
                profiles.STEP_PASSWORD,
                profiles.STEP_PROFILE,
                profiles.STEP_NETWORKS,
                profiles.STEP_WAN,
                profiles.STEP_TIME,
                profiles.STEP_DNS,
                profiles.STEP_UPDATER,
                profiles.STEP_FINISHED,
            ],
        ),
    ],
    ids=[
        profiles.WORKFLOW_OLD,
        profiles.WORKFLOW_UNSET,
        profiles.WORKFLOW_MIN,
        profiles.WORKFLOW_ROUTER,
    ],
)
def all_profiles(request):
    yield request.param[0], request.param[1][:]


def test_strait_workflow(all_profiles):
    workflow, steps = all_profiles
    passed = []

    while len(steps):
        expected = steps.pop(0)
        assert profiles.next_step(passed, workflow) == expected
        passed.append(expected)
    assert profiles.next_step(passed, workflow) is None


@pytest.fixture(
    params=[
        (profiles.WORKFLOW_UNSET, [profiles.STEP_PASSWORD, profiles.STEP_PROFILE]),
        (
            profiles.WORKFLOW_MIN,
            [profiles.STEP_PASSWORD, profiles.STEP_PROFILE, profiles.STEP_FINISHED],
        ),
        (
            profiles.WORKFLOW_ROUTER,
            [
                profiles.STEP_PASSWORD,
                profiles.STEP_PROFILE,
                profiles.STEP_NETWORKS,
                profiles.STEP_WAN,
                profiles.STEP_TIME,
                profiles.STEP_DNS,
                profiles.STEP_UPDATER,
                profiles.STEP_FINISHED,
            ],
        ),
    ],
    ids=[profiles.WORKFLOW_UNSET, profiles.WORKFLOW_MIN, profiles.WORKFLOW_ROUTER],
)
def profile_changable(request):
    yield request.param[0], request.param[1][:]


def test_mixed_workflow(profile_changable, all_profiles):
    workflow1, steps1 = profile_changable
    workflow2, steps2 = all_profiles
    passed = []

    while len(steps1):
        expected = steps1.pop(0)
        assert profiles.next_step(passed, workflow1) == expected
        passed.append(expected)
        if expected == profiles.STEP_PROFILE:
            break

    steps2 = [e for e in steps2 if e not in passed]
    while len(steps2):
        expected = steps2.pop(0)
        assert profiles.next_step(passed, workflow2) == expected
        passed.append(expected)
        if expected == profiles.STEP_PROFILE:
            break
    assert profiles.next_step(passed, workflow2) is None
