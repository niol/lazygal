# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, sys, datetime
import pyexiv2, Image

from lazygal import make


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'


class ExifTags(pyexiv2.Image):

    def __init__(self, image_path):
        pyexiv2.Image.__init__(self,
                               image_path.encode(sys.getfilesystemencoding()))
        self.readMetadata()

        self.image_path = image_path

    def get_exif_date(self, name):
        '''
        Parses date from EXIF information.
        '''
        exif_date = str(self[name])
        date, time = exif_date.split(' ')
        year, month, day = date.split('-')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                           int(hour), int(minute), int(second))

    def get_date(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        try:
            return self.get_exif_date('Exif.Photo.DateTimeDigitized')
        except (IndexError, ValueError, KeyError):
            try:
                return self.get_exif_date('Exif.Photo.DateTimeOriginal')
            except (IndexError, ValueError, KeyError):
                try:
                    return self.get_exif_date('Exif.Image.DateTime')
                except (IndexError, ValueError, KeyError):
                    # No date available in EXIF
                    return None

    def get_required_rotation(self):
        try:
            orientation_code = int(self['Exif.Image.Orientation'])
            if orientation_code == 8:
                return 90
            elif orientation_code == 6:
                return 270
            else:
                return 0
        except KeyError:
            return 0

    def get_camera_name(self):
        '''
        Gets vendor and model name from EXIF and tries to construct
        camera name out of this. This is a bit fuzzy, because diferent
        vendors put different information to both tags.
        '''
        try:
            model = str(self['Exif.Image.Model'])
            try:
                vendor = str(self['Exif.Image.Make'])
                vendor_l = vendor.lower()
                model_l = model.lower()
                # Split vendor to words and check whether they are
                # already in model, for example:
                # Canon/Canon A40
                # PENTAX Corporation/PENTAX K10D
                # Eastman Kodak Company/KODAK DIGITAL SCIENCE DC260 (V01.00)
                for word in vendor_l.split(' '):
                    if model_l.find(word) != -1:
                        return model
                return '%s %s' % (vendor, model)
            except KeyError:
                return model
        except KeyError:
            return ''

    def get_exif_value(self, name):
        '''
        Reads interpreted string from EXIF information, returns empty
        string if key is not found.
        '''
        try:
            return self.interpretedExifValue(name)
        except (IndexError, ValueError, KeyError):
            return ''

    def get_exif_string(self, name):
        '''
        Reads string from EXIF information, returns empty string if key
        is not found.
        '''
        try:
            return str(self[name])
        except (IndexError, ValueError, KeyError):
            return ''

    def get_exif_float(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction). Returns empty string if key is not found.
        '''
        try:
            val = self.get_exif_float_value(name)
            return str(round(val, 1))
        except (IndexError, KeyError):
            return ''

    def get_exif_float_value(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction or int).
        '''
        val = self[name]
        if type(val) == int:
            return float(val)
        else:
            return float(val[0]) / float(val[1])

    def get_jpeg_comment(self):
        '''
        Reads JPEG comment field, returns empty string if key is not
        found.
        '''
        im = Image.open(self.image_path)
        try:
            return im.app['COM']
        except KeyError:
            return ''

    def get_comment(self):
        try:
            ret = self.get_exif_string('Exif.Photo.UserComment')
            if ret == '':
                raise ValueError
            else:
                return ret
        except (ValueError, KeyError):
            return self.get_jpeg_comment()

    def get_flash(self):
        return self.get_exif_value('Exif.Photo.Flash')

    def get_exposure(self):
        try:
            exposure = self['Exif.Photo.ExposureTime']
            if exposure[1] == 1:
                return "%d s" % exposure[0]
            else:
                return "%d/%d s" % (exposure[0], exposure[1])
        except (ValueError, KeyError):
            return ''

    def get_iso(self):
        return self.get_exif_string('Exif.Photo.ISOSpeedRatings')

    def get_fnumber(self):
        val = self.get_exif_float('Exif.Photo.FNumber')
        if val == '':
            return ''
        return 'f/%s' % val

    def get_focal_length(self):
        flen = self.get_exif_float('Exif.Photo.FocalLength')
        if flen == '':
            return ''
        flen = '%s mm' % flen

        flen35 = self.get_exif_float('Exif.Photo.FocalLengthIn35mmFilm')
        if flen35 != '':
            flen += ' (35 mm equivalent: %s mm)' % flen35
            return flen

        try:
            try:
                iwidth = float(str(self['Exif.Photo.ImageWidth']))
            except IndexError:
                iwidth = float(str(self['Exif.Photo.PixelXDimension']))
            fresunit = str(self['Exif.Photo.FocalPlaneResolutionUnit'])
            factors = {'1': 25.4, '2': 25.4, '3': 10, '4': 1, '5': 0.001}
            try:
                fresfactor = factors[fresunit]
            except IndexError:
                fresfactor = 0

            fxres = self.get_exif_float_value('Exif.Photo.FocalPlaneXResolution')
            try:
                ccdwidth = float(iwidth * fresfactor / fxres)
            except ZeroDivisionError:
                return ''

            foclength = self.get_exif_float_value('Exif.Photo.FocalLength')

            flen += ' (35 mm equivalent: %.01f mm)' % (foclength / ccdwidth * 36 + 0.5)
        except (IndexError, KeyError):
            return flen

        return flen


class NoMetadata(Exception):
    '''
    Exception indicating that no meta data has been found.
    '''
    pass


class DirectoryMetadata(make.FileSimpleDependency):

    def __init__(self, dir):
        self.dir = dir
        self.directory_path = self.dir.path
        make.FileSimpleDependency.__init__(self, self.directory_path)

        description = os.path.join(self.directory_path, MATEW_METADATA)
        if os.path.isfile(description):
            self.description_file = description
        else:
            self.description_file = None

    def get_matew_metadata(self, metadata, subdir = None):
        '''
        Return dictionary with meta data parsed from Matew like format.
        '''
        if subdir is None:
            path = self.description_file
        else:
            path = os.path.join(self.directory_path, subdir, MATEW_METADATA)

        if path is None or not os.path.exists(path):
            raise NoMetadata('Could not open metadata file (%s)' % path)

        f = file(path, 'r')
        for line in f:
            for tag in MATEW_TAGS.keys():
                tag_text = MATEW_TAGS[tag]
                tag_len = len(tag_text)
                if line[:tag_len] == tag_text:
                    data = line[tag_len:]
                    data = data.strip()
                    if data[0] == '"':
                        # Strip quotes
                        data = data[1:-1]
                    if tag == 'album_picture':
                        if subdir is not None:
                            data = os.path.join(subdir, data)
                    metadata[tag] = data.decode(sys.stdin.encoding)
                    break

        return metadata

    def get(self, subdir = None):
        '''
        Returns directory meta data. First tries to parse known formats
        and then fall backs to built in defaults.
        '''

        result = {}

        try:
            result = self.get_matew_metadata(result, subdir)
        except NoMetadata:
            pass

        # Add album picture
        if not result.has_key('album_picture'):
            picture = self.dir.guess_directory_picture(subdir)
            if picture is not None:
                result['album_picture'] = picture

        if result.has_key('album_picture'):
            # Convert to thumbnail path
            filename, extension = os.path.splitext(result['album_picture'])
            result['album_picture'] = filename + '_thumb' + extension

        return result


# vim: ts=4 sw=4 expandtab
