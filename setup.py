#!/usr/bin/env python
#
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

from setuptools import setup
from foris_controller import __version__

DESCRIPTION = """
An program which is placed in top of a message bus and translates requests to commands for backends.
"""

setup(
    name='foris-controller',
    version=__version__,
    author='CZ.NIC, z.s.p.o. (http://www.nic.cz/)',
    author_email='stepan.henek@nic.cz',
    packages=[
        'foris_controller',
        'foris_controller.buses',
        'foris_controller_backends',
        'foris_controller_backends.about',
        'foris_controller_backends.cmdline',
        'foris_controller_backends.dns',
        'foris_controller_backends.data_collect',
        'foris_controller_backends.files',
        'foris_controller_backends.maintain',
        'foris_controller_backends.services',
        'foris_controller_backends.uci',
        'foris_controller_backends.web',
        'foris_controller_modules',
        'foris_controller_modules.about',
        'foris_controller_modules.about.handlers',
        'foris_controller_modules.data_collect',
        'foris_controller_modules.data_collect.handlers',
        'foris_controller_modules.dns',
        'foris_controller_modules.dns.handlers',
        'foris_controller_modules.maintain',
        'foris_controller_modules.maintain.handlers',
        'foris_controller_modules.web',
        'foris_controller_modules.web.handlers',
    ],
    package_data={
        'foris_controller': [
            'schemas', 'schemas/*.json', 'schemas/definitions', "schemas/definitions/*.json"
        ],
        'foris_controller_modules.about': ['schema', 'schema/*.json'],
        'foris_controller_modules.data_collect': ['schema', 'schema/*.json'],
        'foris_controller_modules.dns': ['schema', 'schema/*.json'],
        'foris_controller_modules.maintain': ['schema', 'schema/*.json'],
        'foris_controller_modules.web': ['schema', 'schema/*.json'],
    },
    scripts=['bin/foris-controller', "bin/foris-notify"],
    url='https://gitlab.labs.nic.cz/turris/foris-controller',
    license='COPYING',
    description=DESCRIPTION,
    long_description=open('README.rst').read(),
    requires=[
        'foris_schema',
        'prctl',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
    ],
    include_package_data=True,
    zip_safe=False,
)
