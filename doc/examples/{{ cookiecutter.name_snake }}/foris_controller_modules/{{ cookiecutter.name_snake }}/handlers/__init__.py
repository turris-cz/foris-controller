{{ cookiecutter.license_short }}

from .mock import Mock{{ cookiecutter.name_camel }}Handler
from .openwrt import Openwrt{{ cookiecutter.name_camel }}Handler

__all__ = ["Mock{{ cookiecutter.name_camel }}Handler", "Openwrt{{ cookiecutter.name_camel }}Handler"]
