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

import os
import pytest

from .fixtures import lock_backend, service_scripts

from foris_controller.exceptions import ServiceCmdFailed

def get_service_module(lock_backend):
    from foris_controller.app import app_info
    app_info["lock_backend"] = lock_backend
    from foris_controller_backends import services
    return services


def get_results(script_dir):
    with open(os.join(script_dir, "result")) as f:
        res = f.read().strip().split(" ")
    return res.split(" ")


def test_start(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.start("pass")
        assert "passed", "start" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.start("fail")
        assert "failed", "start" == get_results(service_scripts)
        services.start("fail", False)
        assert "failed", "start" == get_results(service_scripts)


def test_stop(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.stop("pass")
        assert "passed", "stop" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.stop("fail")
        assert "failed", "stop" == get_results(service_scripts)
        services.stop("fail", False)
        assert "failed", "stop" == get_results(service_scripts)


def test_restart(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.restart("pass")
        assert "passed", "restart" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.restart("fail")
        assert "failed", "restart" == get_results(service_scripts)
        services.restart("fail", False)
        assert "failed", "restart" == get_results(service_scripts)


def test_reload(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.reload("pass")
        assert "passed", "reload" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.reload("fail")
        assert "failed", "reload" == get_results(service_scripts)
        services.reload("fail", False)
        assert "failed", "reload" == get_results(service_scripts)


def test_enable(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.enable("pass")
        assert "passed", "enable" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.enable("fail")
        assert "failed", "enable" == get_results(service_scripts)
        services.enable("fail", False)
        assert "failed", "enable" == get_results(service_scripts)


def test_disable(lock_backend, service_scripts):
    services_class = get_service_module(lock_backend).OpenwrtServices

    with services_class(service_scripts) as services:
        services.disable("pass")
        assert "passed", "disable" == get_results(service_scripts)
        with pytest.raises(ServiceCmdFailed):
            services.disable("fail")
        assert "failed", "disable" == get_results(service_scripts)
        services.disable("fail", False)
        assert "failed", "disable" == get_results(service_scripts)
