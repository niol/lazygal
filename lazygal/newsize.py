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


import types
import re
import math


class NewsizeStringParseError(Exception): pass


class _Newsize(object):

    def __init__(self, resize_string):
        self.resize_string = resize_string

    def matches(self):
        match = re.match(self.regexp, self.resize_string)
        if match:
            return match
        else:
            raise NewsizeStringParseError

    def dest_size(self, orig_size):
        raise NotImplementedError


class Scale(_Newsize):

    regexp = "^(?P<scale>\\d+)%$"

    def dest_size(self, orig_size):
        match = self.matches()
        scale = int(match.group('scale'))
        return tuple(map(lambda x: x*scale//100, orig_size))


class XYScale(_Newsize):

    regexp = "^(?P<xscale>\\d+)%(?P<yscale>\\d+)%$"

    def dest_size(self, orig_size):
        match = self.matches()
        xscale = int(match.group('xscale'))
        yscale = int(match.group('yscale'))
        x, y = orig_size
        return (x * xscale // 100, y * yscale // 100)


class Width(_Newsize):

    regexp = "^(?P<width>\\d+)$"

    def dest_size(self, orig_size):
        match = self.matches()
        width = int(match.group('width'))
        x, y = orig_size
        height = y * width // x
        return (width, height)


class Height(_Newsize):

    regexp = "^x(?P<height>\\d+)$"

    def dest_size(self, orig_size):
        match = self.matches()
        height = int(match.group('height'))
        x, y = orig_size
        width = x * height // y
        return (width, height)


class _WidthHeight(_Newsize):

    def requested_widthheight(self):
        match = self.matches()
        width = int(match.group('width'))
        height = int(match.group('height'))
        return width, height

    def appropriate_widthheight(self, orig_size, width, height, constraint):
        x, y = orig_size
        new_height = y * width // x
        if constraint(new_height, height):
            return (width, new_height)
        else:
            new_width = x * height // y
            # y * width / x >= height,
            # therefore x * height / y = new_width <= width
            # with contraint being '<='.
            assert constraint(new_width, width)
            return (new_width, height)


class MaximumWidthHeight(_WidthHeight):

    regexp = "^(?P<width>\\d+)x(?P<height>\\d+)$"

    def dest_size(self, orig_size):
        width, height = self.requested_widthheight()
        return self.appropriate_widthheight(orig_size, width, height,
                                            lambda x,y: x <= y)


class MinimumWidthHeight(_WidthHeight):

    regexp = "^(?P<width>\\d+)x(?P<height>\\d+)\\^$"

    def dest_size(self, orig_size):
        width, height = self.requested_widthheight()
        return self.appropriate_widthheight(orig_size, width, height,
                                            lambda x,y: x >= y)


class MandatoryWidthHeight(_WidthHeight):

    regexp = "^(?P<width>\\d+)x(?P<height>\\d+)!$"

    def dest_size(self, orig_size):
        width, height = self.requested_widthheight()
        return (width, height)


class WidthHeightIfLarger(_WidthHeight):

    regexp = "^(?P<width>\\d+)x(?P<height>\\d+)\\>$"

    def dest_size(self, orig_size):
        width, height = self.requested_widthheight()
        x, y = orig_size
        if x > width or y > height:
            return self.appropriate_widthheight(orig_size, width, height,
                                                lambda x,y: x <= y)
        else:
            return orig_size


class WidthHeightIfSmaller(_WidthHeight):

    regexp = "^(?P<width>\\d+)x(?P<height>\\d+)\\<$"

    def dest_size(self, orig_size):
        width, height = self.requested_widthheight()
        x, y = orig_size
        if x < width and y < height:
            return self.appropriate_widthheight(orig_size, width, height,
                                                lambda x,y: x >= y)
        else:
            return orig_size


class Area(_Newsize):

    regexp = "^(?P<area>\\d+)@$"

    def dest_size(self, orig_size):
        match = self.matches()
        area = int(match.group('area'))
        x, y = orig_size
        # { x0 * y0 = area
        # { x / x0 = y / y0
        # x * y0 / area = y / y0
        # y0 = sqrt( y * area / x )
        # x0 = sqrt( x * area / y )
        return (int(math.sqrt(x * area // y)), int(math.sqrt(y * area // x)))


resize_patterns = []
for name, obj in globals().items():
    if not name.startswith('_')\
    and isinstance(obj, (type, types.ClassType)) and issubclass(obj, _Newsize):
        resize_patterns.append(obj)


def get_newsizer(resize_string):
    for newsizer_class in resize_patterns:
        newsizer = newsizer_class(resize_string)
        try:
            newsizer.matches()
        except NewsizeStringParseError:
            # This is not the syntax used
            pass
        else:
            return newsizer
    raise NewsizeStringParseError


def is_known_newsizer(resize_string):
    for newsizer_class in resize_patterns:
        try:
            newsizer_class(resize_string).matches()
        except NewsizeStringParseError:
            # This is not the syntax used
            pass
        else:
            return True
    raise NewsizeStringParseError


# vim: ts=4 sw=4 expandtab
