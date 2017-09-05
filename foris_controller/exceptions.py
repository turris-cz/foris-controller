#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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


class BackendCommandFailed(Exception):
    def __init__(self, retval, args):
        """ exception which indicates the command failed

        :param args: argumenst of the command
        :type args: iterable
        :param retval: reval of the commend
        :type output: int
        """
        super(BackendCommandFailed, self).__init__("Retval=%d for %s" % (retval, args))


class FailedToParseCommandOutput(Exception):
    def __init__(self, args, output):
        """ exception which indicates the output of the cmd was somehow incorrect

        :param args: argumenst of the command
        :type args: iterable
        :param output: program output
        :type output: str
        """
        super(FailedToParseCommandOutput, self).__init__("%s: %s" % (args, output))


class FailedToParseFileContent(Exception):
    def __init__(self, path, content):
        """ exception which inicates the there's something wrong with the content of a file

        :param path: path to file
        :type path: str
        :param content: the content of the file
        :type content: str
        """
        super(FailedToParseFileContent, self).__init__("%s: %s" % (path, content))
