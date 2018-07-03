import logging

from foris_controller.handler_base import BaseOpenwrtHandler
from foris_controller.utils import logger_wrapper

from foris_controller_backends.sample import SampleCmds, SampleUci

from .. import Handler

logger = logging.getLogger(__name__)


class OpenwrtSampleHandler(Handler, BaseOpenwrtHandler):

    cmds = SampleCmds()
    uci = SampleUci()

    @logger_wrapper(logger)
    def get_slices(self):
        return OpenwrtSampleHandler.uci.get_slices()

    @logger_wrapper(logger)
    def set_slices(self, value):
        return OpenwrtSampleHandler.uci.set_slices(value)

    @logger_wrapper(logger)
    def list(self):
        return OpenwrtSampleHandler.cmds.list()
