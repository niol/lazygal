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


import datetime, locale


class unicode_datetime(datetime.datetime):

    def strftime(self, format):
        enc = locale.getpreferredencoding()
        return datetime.datetime.strftime(self, format.encode(enc)).decode(enc)


def unicodify_datetime(dt):
    return unicode_datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                            dt.second, dt.microsecond, dt.tzinfo)


# vim: ts=4 sw=4 expandtab
