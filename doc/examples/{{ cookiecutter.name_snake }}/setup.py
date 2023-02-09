{{ cookiecutter.license_short }}

from foris_controller_{{cookiecutter.name_snake}}_module import __version__
from setuptools import setup

DESCRIPTION = """
{{ cookiecutter.name }} module for Foris Controller
"""

setup(
    name="foris-controller-{{ cookiecutter.name_snake }}-module",
    version=__version__,
    author="CZ.NIC, z.s.p.o. (https://www.nic.cz/)",
    author_email="packaging@turris.cz",
    packages=[
        "foris_controller_{{ cookiecutter.name_snake }}_module",
        "foris_controller_backends",
        "foris_controller_backends.{{ cookiecutter.name_snake }}",
        "foris_controller_modules",
        "foris_controller_modules.{{ cookiecutter.name_snake }}",
        "foris_controller_modules.{{ cookiecutter.name_snake }}.handlers",
    ],
    package_data={"foris_controller_modules.{{ cookiecutter.name_snake }}": ["schema", "schema/*.json"]},
    namespace_packages=["foris_controller_modules", "foris_controller_backends"],
    license='GPL-3.0-only',
    description=DESCRIPTION,
    long_description=open("README.rst").read(),
    install_requires=[
        "foris-controller @ git+https://gitlab.nic.cz/turris/foris-controller/foris-controller.git"
    ],
    entry_points={
        "foris_controller_announcer": [
            "{{ cookiecutter.name_snake }} = foris_controller_{{ cookiecutter.name_snake }}_module.announcer:make_time_message"
        ]
    },
    extras_require={
        'tests': [
            'pytest',
            'foris-controller-testtools @ git+https://gitlab.nic.cz/turris/foris-controller/foris-controller-testtools.git@v0.13.0#egg=foris-controller-testtools',
            'foris-client @ git+https://gitlab.nic.cz/turris/foris-controller/foris-client.git#egg=foris-client',
            'ubus',
            'paho-mqtt',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
