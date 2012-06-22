# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import time, locale


class Datetime(object):

    def __init__(self, timestamp=None, datetime=None):
        if datetime is not None:
            self.timestamp = time.mktime(datetime.timetuple())
        elif timestamp is not None:
            self.timestamp = timestamp
        else:
            self.timestamp = time.time()

    def strftime(self, format):
        # strftime does not work with unicode...
        enc = locale.getpreferredencoding()
        return time.strftime(format.encode(enc),
                             time.localtime(self.timestamp)).decode(enc)


# vim: ts=4 sw=4 expandtab
