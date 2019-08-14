{{ cookiecutter.license_short }}

import logging

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class Mock{{ cookiecutter.name_camel }}Handler(Handler, BaseMockHandler):
    slices = 10
    data = [list(e) for e in enumerate(range(10))]

    @logger_wrapper(logger)
    def get_slices(self):
        return Mock{{ cookiecutter.name_camel }}Handler.slices

    @logger_wrapper(logger)
    def set_slices(self, value):
        Mock{{ cookiecutter.name_camel }}Handler.slices = value
        return True

    @logger_wrapper(logger)
    def list(self):
        return Mock{{ cookiecutter.name_camel }}Handler.data[: Mock{{ cookiecutter.name_camel }}Handler.slices]
