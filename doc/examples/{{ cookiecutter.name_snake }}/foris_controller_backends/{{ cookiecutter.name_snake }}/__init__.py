{{ cookiecutter.license_short }}

import logging
import random

# import json

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.uci import UciBackend, get_option_named

logger = logging.getLogger(__name__)


class {{ cookiecutter.name_camel }}Uci:
    ###
    slices = 10
    ###

    def get_slices(self):
        # with UciBackend() as backend:
        #    data = backend.read("{{ cookiecutter.name_snake }}")
        # return int(get_option_named(data, "{{ cookiecutter.name_snake }}", "data", "slices"))
        ###
        return {{ cookiecutter.name_camel }}Uci.slices
        ###

    def set_slices(self, slices):
        # with UciBackend() as backend:
        #    backend.set_option("{{ cookiecutter.name_snake }}", "data", "slices", slices)
        ###
        {{ cookiecutter.name_camel }}Uci.slices = slices
        ###
        return True


class {{ cookiecutter.name_camel }}Cmds(BaseCmdLine):
    ###
    data = [list(e) for e in enumerate([random.randrange(100) for _ in range({{ cookiecutter.name_camel }}Uci.slices)])]
    ###

    def list(self):
        # return json.loads(self._run_command("<command_to_obtain_data>")[1])
        ###
        del {{ cookiecutter.name_camel }}Cmds.data[0]
        while len({{ cookiecutter.name_camel }}Cmds.data) < {{ cookiecutter.name_camel }}Uci.slices:
            {{ cookiecutter.name_camel }}Cmds.data.append([{{ cookiecutter.name_camel }}Cmds.data[-1][0] + 1, random.randrange(100)])
        while len({{ cookiecutter.name_camel }}Cmds.data) > {{ cookiecutter.name_camel }}Uci.slices:
            del {{ cookiecutter.name_camel }}Cmds.data[0]
        return {{ cookiecutter.name_camel }}Cmds.data
        ###
