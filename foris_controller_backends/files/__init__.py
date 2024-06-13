#
# foris-controller
# Copyright (C) 2017-2024 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

import logging
import os
import re
import shutil
import typing

from pathlib import Path

from foris_controller.app import app_info
from foris_controller.exceptions import FailedToParseFileContent
from foris_controller.utils import RWLock

logger = logging.getLogger(__name__)

server_uplink_lock = RWLock(app_info["lock_backend"])

FILE_ROOT = os.environ.get("FORIS_FILE_ROOT", "")
if FILE_ROOT:
    logger.debug("File root is set to '%s'.", FILE_ROOT)


def inject_file_root(path: typing.Union[Path, str]) -> Path:
    """merge path with file root if set (path has to be absolute) relative paths are kept"""
    path = Path(path)
    if FILE_ROOT:
        if path.is_absolute():
            return FILE_ROOT / path.relative_to("/")
    return path


def path_exists(path: typing.Union[Path, str]):
    """Checks whether a path exists"""
    return inject_file_root(path).exists()


def makedirs(path: typing.Union[Path, str], mask: int = 0o0755, exist_ok: bool = True):
    """Creates directories on the given path
    :param path: path to be created
    :param mask: last dir mask
    :param exist_ok: don't raise exception when directory exists
    """
    inject_file_root(path).mkdir(mask, parents=True, exist_ok=exist_ok)


class BaseFile:
    def _file_content(self, path: typing.Union[Path, str]) -> str:
        """Returns a content of a file
        """
        path = inject_file_root(path)
        logger.debug("Trying to read file '%s'", path)
        with path.open() as f:
            content = f.read()
        logger.debug("File '%s' was successfully read.", path)
        logger.debug("content: %s" % content)
        return content

    def _read_and_parse(
        self, path: typing.Union[Path, str], regex: str, groups: typing.Tuple[int, ...] = (1,), log_error: bool = True
    ) -> typing.Tuple[str, ...]:
        """Reads and parses a content of the file by regex,
            raises an exception when the output doesn't match regex

        :param path: path to the file
        :param regex: regular expression to match
        :param groups: groups which will be returned from the matching regex
        :returns: matching strings
        """
        content = self._file_content(path)
        match = re.search(regex, content, re.MULTILINE)
        if not match:
            if log_error:
                logger.error("Failed to parse content of the file '%s'", path)
            raise FailedToParseFileContent(path, content)
        return match.group(*groups)

    def _store_to_file(self, path: typing.Union[Path, str], content: str) -> str:
        """Inserts a content into the file
        :returns: file content
        """
        path = inject_file_root(path)
        logger.debug("Trying to write to file '%s'", path)
        with path.open("w") as f:
            f.write(content)
            f.flush()
        logger.debug("File '%s' was successfully updated.", path)
        logger.debug("content: %s", content)
        return content

    def delete_directory(self, path: typing.Union[Path, str]):
        """Deletes a directory on path (or raises an exception)

        :param path: path to the file

        """
        path = inject_file_root(path)
        logger.debug("Trying to delete '%s'", path)
        shutil.rmtree(path)
        logger.debug("'%s' was successfully deleted", path)

    def delete_file(self, path: typing.Union[Path, str]):
        """Deletes a file on path (or raises an exception)

        :param path: path to the file

        """
        path = inject_file_root(path)
        logger.debug("Trying to delete '%s'", path)
        path.unlink()
        logger.debug("'%s' was successfully deleted", path)


class BaseMatch(object):
    @staticmethod
    def list_files(file_matches):
        """Reads all files in which matches the request (glob will be used for matching)
        :param file_matches: list of expressions to match

        :returns: list of files that matches
        :rtype: list
        """
        res = []
        for file_match in file_matches:
            match = inject_file_root(file_match)
            # make path relative
            if match.is_absolute():
                match = match.relative_to("/")
            logger.debug("Listing '%s'", match)
            res.extend(Path("/").glob(str(match)))
        return res
