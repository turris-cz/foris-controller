import logging

from foris_controller.module_base import BaseModule
from foris_controller.handler_base import wrap_required_functions


class SampleModule(BaseModule):
    logger = logging.getLogger(__name__)

    def action_get_slices(self, data):
        return {"slices": self.handler.get_slices()}

    def action_set_slices(self, data):
        res = {}
        res = self.handler.set_slices(data["slices"])
        self.notify("set_slices", {"slices": data["slices"]})
        return {"result": res}

    def action_list(self, data):
        return {"records": self.handler.list()}


@wrap_required_functions(["set_slices", "get_slices", "list"])
class Handler(object):
    pass
