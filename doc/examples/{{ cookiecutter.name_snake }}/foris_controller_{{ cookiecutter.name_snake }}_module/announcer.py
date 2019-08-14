{{ cookiecutter.license_short }}

import datetime
import time
import typing


def time_message() -> dict:
    return {
        "module": "{{ cookiecutter.name_snake }}",
        "action": "announce_time",
        "kind": "notification",
        "data": {"timestamp": time.mktime(datetime.datetime.utcnow().timetuple())},
    }


def make_time_message() -> typing.Tuple[int, typing.Callable[[], typing.Optional[dict]]]:

    # returns announcer period announcement will be triggered every n-th second
    return (2, time_message)
