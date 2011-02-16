# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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
This module provides a simple wrapper to the pyexiv2 API which changed between
version 0.1 and 0.2. The goal is to provide a wrapper compatible with the
latest API.
"""


import sys
import datetime

import pyexiv2
import Image as PILImage


def decode_exif_user_comment(raw, imgpath):
    """
    Before pyexvi2 0.3, the EXIF user comment was not decoded to a unicode
    string. This function does exactly that and is used for earlier versions
    of pyexiv2.
    """
    # This field can contain charset information
    if raw.startswith('charset='):
        tokens = raw.split(' ')
        csetfield = tokens[0]
        text = ' '.join(tokens[1:])
        ignore, cset = csetfield.split('=')
        cset = cset.strip('"')
    else:
        cset = None
        text = raw

    if cset == 'Unicode':
        encoding = None
        # Starting from 0.20, exiv2 converts unicode comments to UTF-8
        try:
            text.decode('utf-8')
        except UnicodeDecodeError:
            # Decoding failed, maybe we can assume we are with exiv2 << 0.20
            im = PILImage.open(imgpath)
            endianess = im.app['APP1'][6:8]
            if endianess == 'MM':
                encoding = 'utf-16be'
            elif endianess == 'II':
                encoding = 'utf-16le'
            else:
                raise ValueError
        else:
            encoding = 'utf-8'
    elif cset == 'Ascii':
        encoding = 'ascii'
    elif cset == 'Jis':
        encoding = 'shift_jis'
    else:
        # Fallback to utf-8 as this is mostly the default for Linux
        # distributions.
        encoding = 'utf-8'

    # Return the decoded string according to the found encoding.
    try:
        return text.decode(encoding)
    except UnicodeDecodeError:
        return text.decode(encoding, 'replace')


# This is required at import time for inheritances below.
if 'ImageMetadata' in dir(pyexiv2):
    Pyexvi2ImageMetadata = pyexiv2.ImageMetadata
else:
    # This is for the interpreter to be happy, but if pyexiv2.ImageMetadata
    # does not exist, we are with pyexiv2 << 0.2, and the old API, so we won't
    # be using classes that inherot from Pyexvi2ImageMetadata.
    Pyexvi2ImageMetadata = object


class _ImageMetadata_0_2_2(Pyexvi2ImageMetadata):

    def __init__(self, imgpath):
        super(_ImageMetadata_0_2_2, self).__init__(imgpath)
        self.imgpath = imgpath

    def __getitem__(self, key):
        tag = super(_ImageMetadata_0_2_2, self).__getitem__(key)
        if key == 'Exif.Photo.UserComment':
            tag.value = decode_exif_user_comment(tag.value, self.imgpath)
        return tag


class _ImageMetadata_0_2(_ImageMetadata_0_2_2):

    def get_jpeg_comment(self):
        # comment appeared in pyexiv2 0.2.2, so use PIL
        im = PILImage.open(self.imgpath)
        try:
            return im.app['COM'].strip('\x00')
        except KeyError:
            return ''

    comment = property(get_jpeg_comment)


class _ImageTag_0_1(object):

    def __init__(self, tag, imgpath, md, key):
        self._tag = tag
        self._imgpath = imgpath
        self._metadata = md
        self._key = key

    def __getattr__(self, name):
        if name == 'value':
            return self.get_value()
        elif name == 'raw_value':
            return self._tag
        else:
            raise AttributeError

    def __str__(self):
        return str(self._tag)

    def get_exif_date(self):
        '''
        Parses date from EXIF information.
        '''
        exif_date = str(self._metadata[self._key])
        date, time = exif_date.split(' ')
        year, month, day = date.split('-')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                                 int(hour), int(minute), int(second))

    def get_int(self):
        return int(self._tag)

    def get_interpreted_value(self):
        return self._metadata.interpretedExifValue(self._key)

    def get_decoded_utf8(self):
        return self.get_interpreted_value().decode('utf-8')

    def get_decoded_exif_user_comment(self):
        return decode_exif_user_comment(self._tag, self._imgpath)

    TAG_PYTRANSLATORS = {
        'Exif.Photo.DateTimeDigitized' : 'get_exif_date',
        'Exif.Photo.DateTimeOriginal'  : 'get_exif_date',
        'Exif.Photo.UserComment'       : 'get_decoded_exif_user_comment',
        'Exif.Image.DateTime'          : 'get_exif_date',
        'Exif.Image.Orientation'       : 'get_int',
        'Exif.Pentax.LensType'         : 'get_interpreted_value',
        'Exif.Nikon3.Lens'             : 'get_interpreted_value',
        'Exif.Nikon3.LensType'         : 'get_interpreted_value',
        'Exif.Minolta.LensID'          : 'get_interpreted_value',
        'Exif.Photo.Flash'             : 'get_decoded_utf8',
    }

    def get_value(self):
        if self._key in _ImageTag_0_1.TAG_PYTRANSLATORS.keys():
            translator = getattr(self.__class__,
                                 _ImageTag_0_1.TAG_PYTRANSLATORS[self._key])
            return translator(self)
        else:
            return self._tag


class _ImageMetadata_0_1(object):

    def __init__(self, imgpath):
        self.imgpath = imgpath
        self._metadata = pyexiv2.Image(self.imgpath.encode(sys.getfilesystemencoding()))

    def __getitem__(self, key):
        return _ImageTag_0_1(self._metadata[key], self.imgpath,
                             self._metadata, key)

    def __setitem__(self, key, value):
        self._metadata[key] = value

    def __delitem__(self, key):
        del self._metadata[key]

    def read(self):
        self._metadata.readMetadata()

    def write(self):
        self._metadata.writeMetadata()

    def __try_copy_tag_to(self, tag_key, dest_imgtags):
        try:
            dest_imgtags._metadata[tag_key] = self[tag_key]
        except (ValueError, TypeError):
            pass

    def copy(self, dest_imgtags):
        try:
            self._metadata.copyMetadataTo(dest_imgtags._metadata)
        except (ValueError, TypeError):
            # Sometimes pyexiv2 (<< 0.2) fails during the copy on a badly
            # formatted tag, so we try a manual copy here for each tag.
            for tag_key in self.exif_keys:
                self.__try_copy_tag_to(tag_key, dest_imgtags)
            for tag_key in self.iptc_keys:
                self.__try_copy_tag_to(tag_key, dest_imgtags)

    def get_comment(self): return self._metadata.getComment()
    def set_comment(self, value): self._metadata.setComment(value)
    comment = property(get_comment, set_comment)

    def get_exif_keys(self): return self._metadata.exifKeys()
    exif_keys = property(get_exif_keys)

    def get_iptc_keys(self): return self._metadata.iptcKeys()
    iptc_keys = property(get_iptc_keys)


if 'ImageMetadata' in dir(pyexiv2):
    if 'comment' in dir(pyexiv2.ImageMetadata):
        # pyexiv2 (>= 0.2.2)
        if pyexiv2.version_info >= (0, 3, 0):
            ImageMetadata = pyexiv2.ImageMetadata
        else:
            ImageMetadata = _ImageMetadata_0_2_2
    else:
        # pyexiv2 (>= 0.2, << 0.2.2)
        ImageMetadata = _ImageMetadata_0_2
elif 'Image' in dir(pyexiv2):
    # pyexiv2 (<< 0.2)
    ImageMetadata = _ImageMetadata_0_1
else:
    raise ImportError('Unrecognized pyexiv2 version.')


# vim: ts=4 sw=4 expandtab
