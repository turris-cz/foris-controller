from setuptools import setup

from foris_controller_sample_module import __version__

DESCRIPTION = """
Sample module for foris-controller
"""

setup(
    name='foris-controller-sample-module',
    version=__version__,
    author='CZ.NIC, z.s.p.o. (http://www.nic.cz/)',
    author_email='stepan.henek@nic.cz',
    packages=[
        'foris_controller_sample_module',
        'foris_controller_backends',
        'foris_controller_backends.sample',
        'foris_controller_modules',
        'foris_controller_modules.sample',
        'foris_controller_modules.sample.handlers',
    ],
    package_data={
        'foris_controller_modules.sample': ['schema', 'schema/*.json'],
    },
    scripts=[],
    description=DESCRIPTION,
    long_description=open('README.rst').read(),
    install_requires=[
        "foris-controller @ git+https://gitlab.labs.nic.cz/turris/foris-controller.git",
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'foris-controller-testtools',
        'foris-client',
    ],
    extras_require={
        'testsuite': [
            "foris-controller-testtools @ git+https://gitlab.labs.nic.cz/turris/foris-controller-testtools.git",
            "foris-client @ git+https://gitlab.labs.nic.cz/turris/foris-client.git",
        ]
    },
    include_package_data=True,
    zip_safe=False,
)
