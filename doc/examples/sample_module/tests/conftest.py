def pytest_addoption(parser):
    parser.addoption(
        "--backend", action="append",
        default=[],
        help=("Set test backend here. available values = (mock, openwrt)")
    )
    parser.addoption(
        "--debug-output", action="store_true",
        default=False,
        help=("Whether show output of foris-controller cmd")
    )


def pytest_generate_tests(metafunc):
    if 'backend' in metafunc.fixturenames:
        backend = set(metafunc.config.option.backend)
        if not backend:
            backend = ['mock']
        metafunc.parametrize("backend_param", backend, scope='module')
