# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2014 Alexandre Rossi <alexandre.rossi@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


"""
This is a transition module to provide python2/python3 support.
"""


import sys


PY3RUNNING = sys.version_info >= (3,)


if not PY3RUNNING:
    import gettext
    gettext.install__stdlib = gettext.install
    def gettext_install(*args, **kwargs):
        kwargs['unicode'] = True
        gettext.install__stdlib(*args, **kwargs)
    gettext.install = gettext_install


# vim: ts=4 sw=4 expandtab
