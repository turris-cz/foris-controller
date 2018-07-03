import logging

from foris_controller.handler_base import BaseMockHandler
from foris_controller.utils import logger_wrapper

from .. import Handler

logger = logging.getLogger(__name__)


class MockSampleHandler(Handler, BaseMockHandler):
    slices = 10
    data = [list(e) for e in enumerate(range(10))]

    @logger_wrapper(logger)
    def get_slices(self):
        return MockSampleHandler.slices

    @logger_wrapper(logger)
    def set_slices(self, value):
        MockSampleHandler.slices = value
        return True

    @logger_wrapper(logger)
    def list(self):
        return MockSampleHandler.data[:MockSampleHandler.slices]
