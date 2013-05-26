# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2013 Alexandre Rossi <alexandre.rossi@gmail.com>
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
This is a transition module to provide pyexiv2 compatibility waiting for
a properly supported GExiv2 windows port.
"""


import datetime
import logging


class Metadata_withPyExiv2(object):

    def __init__(self, image_path):
        self.pyexiv2md = pyexiv2.metadata.ImageMetadata(image_path)
        self.pyexiv2md.read()

    def __getitem__(self, key):
        try:
            val = self.pyexiv2md[key].value
        except ValueError:
            return None
        if type(val) is datetime.datetime:
            val = val.strftime('%Y:%m:%d %H:%M:%S')
        return val

    def __setitem__(self, key, value):
        if value == '' or value is None:
            del self.pyexiv2md[key]
            return

        if key in ('Iptc.Application2.Keywords',
                   'Xmp.MicrosoftPhoto.LastKeywordXMP',
                   'Xmp.dc.subject',
                   'Xmp.digiKam.TagsList', ):
            if type(value) is not list:
                value = [value]

        if key in self.pyexiv2md.exif_keys:
            tag = pyexiv2.exif.ExifTag(key)
            if tag.type in ('Long', 'SLong', 'Short', 'SShort', ):
                value = int(value)
            elif tag.type == 'Undefined':
                tag.value = value
                self.pyexiv2md[key] = tag
                return

        self.pyexiv2md[key] = value

    def __contains__(self, key):
        return key in self.pyexiv2md

    def get_tag_interpreted_string(self, key):
        return self.pyexiv2md[key].human_value

    def get_tag_multiple(self, key):
        return self.pyexiv2md[key].value

    def get_exif_tag_rational(self, key):
        return self.pyexiv2md[key].value

    def get_comment(self):
        return self.pyexiv2md.comment

    def get_exif_tags(self):
        return self.pyexiv2md.exif_keys

    def clear_tag(self, key):
        del self.pyexiv2md[key]

    def save_file(self):
        self.pyexiv2md.write()


class GExiv2_withPyExiv2(object):
    Metadata = Metadata_withPyExiv2

    class LogLevel(object):
        ERROR = None

    @staticmethod
    def log_set_level(dummy):
        pass


try:
    from gi.repository import GExiv2
except ImportError:
    import warnings
    logging.warning('Falling back to try using pyexiv2, which is deprecated.')
    import pyexiv2
    warnings.warn("deprecated", DeprecationWarning)
    GExiv2 = GExiv2_withPyExiv2


# vim: ts=4 sw=4 expandtab
