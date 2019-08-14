{{ cookiecutter.license_short }}

import logging

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.{{ cookiecutter.name_snake }} import {{ cookiecutter.name_camel }}Cmds, {{ cookiecutter.name_camel }}Uci

from .. import Handler

logger = logging.getLogger(__name__)


class Openwrt{{ cookiecutter.name_camel }}Handler(Handler, BaseOpenwrtHandler):

    cmds = {{ cookiecutter.name_camel }}Cmds()
    uci = {{ cookiecutter.name_camel }}Uci()

    @logger_wrapper(logger)
    def get_slices(self):
        return Openwrt{{ cookiecutter.name_camel }}Handler.uci.get_slices()

    @logger_wrapper(logger)
    def set_slices(self, value):
        return Openwrt{{ cookiecutter.name_camel }}Handler.uci.set_slices(value)

    @logger_wrapper(logger)
    def list(self):
        return Openwrt{{ cookiecutter.name_camel }}Handler.cmds.list()
