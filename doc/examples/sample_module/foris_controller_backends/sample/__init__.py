import logging
import random
#import json

from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.uci import UciBackend, get_option_named

logger = logging.getLogger(__name__)


class SampleUci():
    ###
    slices = 10
    ###

    def get_slices(self):
        #with UciBackend() as backend:
        #    data = backend.read("sample")
        #return int(get_option_named(data, "sample", "data", "slices"))
        ###
        return SampleUci.slices
        ###

    def set_slices(self, slices):
        #with UciBackend() as backend:
        #    backend.set_option("sample", "data", "slices", slices)
        ###
        SampleUci.slices = slices
        ###
        return True


class SampleCmds(BaseCmdLine):
    ###
    data = [list(e) for e in enumerate([random.randrange(100) for _ in range(SampleUci.slices)])]
    ###

    def list(self):
        #return json.loads(self._run_command("<command_to_obtain_data>")[1])
        ###
        del SampleCmds.data[0]
        while len(SampleCmds.data) < SampleUci.slices:
            SampleCmds.data.append([SampleCmds.data[-1][0] + 1, random.randrange(100)])
        while len(SampleCmds.data) > SampleUci.slices:
            del SampleCmds.data[0]
        return SampleCmds.data
        ###
