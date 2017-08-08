import importlib
import logging
import os

from jsonschema import ValidationError
from foris_schema import ForisValidator

logger = logging.getLogger("message_router")

validator = ForisValidator([
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "modules", "schemas"),
])


class Router(object):
    def _build_error_msg(self, orig_msg, errors):
        return {
            "module": orig_msg.get("module", "?"),
            "kind": orig_msg.get("kind", "?"),
            "action": orig_msg.get("action", "?"),
            "data": {"errors": errors},
        }

    def __init__(self, backend):
        self.backend = backend

    def validate(self, message, module=None, idx=None):
        validator.validate(message, module, idx)

    def process_message(self, message):
        # validate input message
        logger.debug("Starting to validate input message.")
        try:
            self.validate(message)
        except ValidationError:
            logger.warning("Failed to validate input message.")
            return self._build_error_msg(message, ["Incorrect input."])
        logger.debug("Input message validated.")

        # find the module
        if message["kind"] != "request":
            logger.warning("Wrong message kind (only requests allowed) (=%s)." % message["kind"])
            return self._build_error_msg(
                message, ["Wrong message kind (only request are allowed)."])

        try:
            module = importlib.import_module(
                ".modules.%s" % message["module"], "foris_controller")
        except ImportError:
            logger.error(
                "Failed to import module 'foris_controller.modules.%s'" % message["module"])
            return self._build_error_msg(
                message, [
                    "Internal error (failed to import module '%s')" % message["module"]
                ]
            )

        module_instance = module.Class(self.backend)
        try:
            data = module_instance.perform_action(message["action"], message.get("data", {}))
        except Exception as e:
            logger.error("Internal error occured %s('%s')" % (type(e), str(e)))
            return self._build_error_msg(
                message, [
                    "Internal error %s('%s')" % (type(e), str(e))
                ]
            )

        reply = {
            "kind": "reply",
            "module": message["module"],
            "action": message["action"],
            "data": data,
        }

        logger.debug("Starting to validate output message.")
        try:
            self.validate(reply)
        except ValidationError:
            logger.error("Failed to validate output message.")
            return self._build_error_msg(message, ["Incorrect output %s." % str(reply)])

        logger.debug("Output message validated.")
        return reply
