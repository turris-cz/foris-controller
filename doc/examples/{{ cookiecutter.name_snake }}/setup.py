{{ cookiecutter.license_short }}

from setuptools import setup

from foris_controller_{{ cookiecutter.name_snake }}_module import __version__

DESCRIPTION = """
{{ cookiecutter.name }} module for Foris Controller
"""

setup(
    name="foris-controller-{{ cookiecutter.name_snake }}-module",
    version=__version__,
    author="CZ.NIC, z.s.p.o. (http://www.nic.cz/)",
    author_email="my.email@nic.cz",
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
    description=DESCRIPTION,
    long_description=open("README.rst").read(),
    install_requires=[
        "foris-controller @ git+https://gitlab.labs.nic.cz/turris/foris-controller/foris-controller.git"
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest", "foris-controller-testtools", "foris-client", "ubus", "paho-mqtt"],
    entry_points={
        "foris_controller_announcer": [
            "{{ cookiecutter.name_snake }} = foris_controller_{{ cookiecutter.name_snake }}_module.announcer:make_time_message"
        ]
    },
    dependency_links=[
        "git+https://gitlab.labs.nic.cz/turris/foris-controller/foris-controller-testtools.git#egg=foris-controller-testtools",
        "git+https://gitlab.labs.nic.cz/turris/foris-controller/foris-client.git#egg=foris-client",
    ],
    include_package_data=True,
    zip_safe=False,
)
