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
import Image, EXIF


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'


class ExifTags:

    def __init__(self, image_path):
        self.image_path = image_path
        f = open(self.image_path, 'rb')
        self.tags = EXIF.process_file(f)

    def __getitem__(self, name):
        return self.tags[name]

    def get_date(self, name):
        '''
        Parses date from EXIF information.
        '''
        exif_date = str(self.tags[name])
        date, time = exif_date.split(' ')
        year, month, day = date.split(':')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                           int(hour), int(minute), int(second))

    def get_date_taken(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        try:
            self.date_taken = self.get_exif_date('EXIF DateTimeDigitized')
        except (KeyError, ValueError):
            try:
                self.date_taken = self.get_exif_date('EXIF DateTimeOriginal')
            except (KeyError, ValueError):
                try:
                    self.date_taken = self.get_exif_date('Image DateTime')
                except (KeyError, ValueError):
                    # No date available in EXIF, or bad format, use file mtime
                    self.date_taken = datetime.datetime.fromtimestamp(\
                                                       self.get_source_mtime())
        return self.date_taken

    def get_required_rotation(self):
        self.__load_exif_data()

        if self.tags.has_key('Image Orientation'):
            orientation_code = int(self.tags['Image Orientation'].values[0])
            # FIXME : This hsould really go in the EXIF library
            if orientation_code == 8:
                return 90
            elif orientation_code == 6:
                return 270
            else:
                return 0
        else:
            return 0

    def get_camera_name(self):
        '''
        Gets vendor and model name from EXIF and tries to construct
        camera name out of this. This is a bit fuzzy, because diferent
        vendors put different information to both tags.
        '''
        try:
            model = str(self.tags['Image Model'])
            try:
                vendor = str(self.tags['Image Make'])
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

    def get_exif_string(self, name):
        '''
        Reads string from EXIF information, returns empty string if key
        is not found.
        '''
        try:
            return str(self.tags[name])
        except KeyError:
            return ''

    def get_exif_float(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction). Returns empty string if key is not found.
        '''
        try:
            val = str(self.tags[name]).split('/')
            if len(val) == 1:
                val.append('1')
            return str(round(float(val[0]) / float(val[1]), 1))
        except KeyError:
            return ''

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
        ret = self.get_exif_string('UserComment')
        if ret != '':
            return ret
        return self.get_jpeg_comment()

    def get_flash(self):
        return self.get_exif_string('EXIF Flash')

    def get_exposure(self):
        return self.get_exif_string('EXIF ExposureTime')

    def get_iso(self):
        return self.get_exif_string('EXIF ISOSpeedRatings')

    def get_fnumber(self):
        val = self.get_exif_float('EXIF FNumber')
        if val == '':
            return ''
        return 'f/%s' % val

    def get_focal_length(self):
        flen = self.get_exif_float('EXIF FocalLength')
        if flen == '':
            return ''

        try:
            iwidth = float(str(self.tags['EXIF ExifImageWidth']))
            fresunit = str(self.tags['EXIF FocalPlaneResolutionUnit'])
            factors = {'1': 25.4, '2': 25.4, '3': 10, '4': 1, '5': 0.001}
            try:
                fresfactor = factors[fresunit]
            except:
                fresfactor = 0

            fxrestxt = str(self.tags['EXIF FocalPlaneXResolution'])
            if "/" in fxrestxt:
                fxres = float(eval(fxrestxt))
            else:
                fxres = float(fxrestxt)
            try:
                ccdwidth = float(iwidth * fresfactor / fxres)
            except ZeroDivisionError:
                return ''

            val = str(self.tags['EXIF FocalLength']).split('/')
            if len(val) == 1: val.append('1')
            foclength = float(val[0]) / float(val[1])
            flen += ' (35 mm equivalent: %d mm)' % int(foclength / ccdwidth * 36 + 0.5)
        except KeyError:
            return flen

        return flen


class NoMetadata(Exception):
    '''
    Exception indicating that no meta data has been found.
    '''
    pass


class DirectoryMetadata:

    def __init__(self, dir):
        self.dir = dir
        self.directory_path = self.dir.source

        description = os.path.join(self.directory_path, MATEW_METADATA)
        if os.path.isfile(description):
            self.description_file = description
        else:
            self.description_file = None

    def get_mtime(self):
        if self.description_file:
            return os.path.getmtime(self.description_file)
        else:
            return 0

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
            result['album_picture'] =  result['album_picture'].replace('.', '_thumb.')

        return result


# vim: ts=4 sw=4 expandtab
