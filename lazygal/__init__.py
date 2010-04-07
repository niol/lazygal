# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2010 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, re


__all__ = [
        'generators',
        ]

def get_darcs_lastdate():
    try:
        lazygal_dir = os.path.join(os.path.dirname(__file__), '..')
        inventory = os.path.join(lazygal_dir, '_darcs', 'inventory')
        sk = max(0, os.path.getsize(inventory)-200)
        inventoryf = open(inventory, 'r')
        inventoryf.seek(sk)
        last_lines = inventoryf.readlines()
        inventoryf.close()

        date_re = re.compile("\\*\\*\\d+")
        last_date = None
        for last_line in last_lines:
            perhaps_match = date_re.search(last_line)
            if perhaps_match != None:
                last_date = perhaps_match.group()[2:]

        if not last_date:
            raise IOError

        return "+darcs%s" % last_date[:8]
    except (IOError, OSError):
        return ''


__version__ = '0.4.1' + get_darcs_lastdate()

# vim: ts=4 sw=4 expandtab
