import importlib
import logging
import os

from foris_schema import ForisValidator

logger = logging.getLogger("message_router")

from .exceptions import IncorrectMessageType, ModuleNotFound

validator = ForisValidator([
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "modules", "schemas"),
])


class Router(object):
    def __init__(self, backend):
        self.backend = backend

    def validate(self, message, module=None, idx=None):
        validator.validate(message, module, idx)

    def process_message(self, message):
        # validate input message
        logger.debug("Starting to validate input message.")
        self.validate(message)
        logger.debug("Input message validated.")

        # find the module
        if message["kind"] != "request":
            raise IncorrectMessageType(
                "Only requests are allowed to be processed. (kind=%s)" % message["kind"])

        try:
            module = importlib.import_module(".modules.%s" % message["module"], "foris_controller")
        except ImportError:
            raise ModuleNotFound(message["module"])

        module_instance = module.Class(self.backend)
        data = module_instance.perform_action(message["action"], message.get("data", {}))
        reply = {
            "kind": "reply",
            "module": message["module"],
            "action": message["action"],
            "data": data,
        }

        logger.debug("Starting to validate output message.")
        self.validate(reply)
        logger.debug("Output message validated.")

        return reply
