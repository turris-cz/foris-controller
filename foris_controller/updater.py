#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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


import os
from importlib import import_module

# UPDATER module can be customized for testing purposes
# by overriding env variable FC_UPDATER_MODULE
updater_module = os.environ.get("FC_UPDATER_MODULE", "svupdater")

svupdater = import_module(updater_module, "svupdater")
svupdater_exceptions = import_module("%s.exceptions" % updater_module, "svupdater.exceptions")
svupdater_hook = import_module("%s.hook" % updater_module, "svupdater.hook")
svupdater_approvals = import_module("%s.approvals" % updater_module, "svupdater.approvals")
svupdater_l10n = import_module("%s.l10n" % updater_module, "svupdater.l10n")
svupdater_lists = import_module("%s.lists" % updater_module, "svupdater.lists")
svupdater_autorun = import_module("%s.autorun" % updater_module, "svupdater.autorun")
svupdater_branch = import_module("%s.branch" % updater_module, "svupdater.branch")
