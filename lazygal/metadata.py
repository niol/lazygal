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

import os, sys, datetime, locale
import Image

import pyexiv2

from lazygal import make


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'


class _ImageInfoTags(object):

    def __init__(self, image_path):
        self.image_path = image_path

    def get_date(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        try:
            return self.get_tag_value('Exif.Photo.DateTimeDigitized')
        except (IndexError, ValueError, KeyError):
            try:
                return self.get_tag_value('Exif.Photo.DateTimeOriginal')
            except (IndexError, ValueError, KeyError):
                try:
                    return self.get_tag_value('Exif.Image.DateTime')
                except (IndexError, ValueError, KeyError):
                    # No date available in EXIF
                    return None

    def get_required_rotation(self):
        try:
            orientation_code = self.get_tag_value('Exif.Image.Orientation')
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
            model = str(self._metadata['Exif.Image.Model']).strip()
            # Terminate string at \x00
            pos = model.find('\x00')
            if pos != -1:
                model = model[:14]
            try:
                vendor = str(self._metadata['Exif.Image.Make']).strip()
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

    def get_lens_name(self):
        '''
        Return name of used lenses. This usually makes sense only for
        SLR cameras and uses various maker notes. Currently supported
        for Pentax, Nikon and Minolta (as soon as Exiv2 supports others,
        support can be added here.
        '''

        try:
            return self.get_tag_value('Exif.Pentax.LensType')
        except (IndexError, ValueError, KeyError):
            try:
                ret = self.get_tag_value('Exif.Nikon3.Lens')
                try:
                    ret2 = self.get_tag_value('Exif.Nikon3.LensType')
                except (IndexError, ValueError, KeyError):
                    return ret
                else:
                    return '%s %s' % (ret, ret2)
            except (IndexError, ValueError, KeyError):
                try:
                    return self.get_tag_value('Exif.Minolta.LensID')
                except (IndexError, ValueError, KeyError):
                    return ''

    def get_exif_string(self, name):
        '''
        Reads string from EXIF information.
        '''
        return str(self.get_tag_value(name)).strip(' ')

    def get_exif_float(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction).
        '''
        val = self.get_exif_float_value(name)
        return str(round(val, 1))

    def get_exif_float_value(self, name):
        '''
        Reads float number from EXIF information (where it is stored as
        fraction or int).
        '''
        val = self.get_tag_value(name)
        if type(val) == int:
            return float(val)
        elif type(val) == tuple:
            return float(val[0]) / float(val[1])
        else:
            return float(val.numerator) / float(val.denominator)

    def _fallback_to_encoding(self, encoded_string, encoding='utf-8'):
        try:
            return encoded_string.decode(encoding)
        except UnicodeDecodeError:
            return encoded_string.decode(encoding, 'replace')

    def get_exif_usercomment(self):
        ret = self.get_exif_string('Exif.Photo.UserComment')
        # This field can contain charset information
        # FIXME : All this stuff should really go in pyexiv2.
        if ret.startswith('charset='):
            tokens = ret.split(' ')
            csetfield = tokens[0]
            text = ' '.join(tokens[1:])
            ignore, cset = csetfield.split('=')
            cset = cset.strip('"')
        else:
            cset = None
            text = ret

        if cset == 'Unicode':
            im = Image.open(self.image_path)
            endian = im.app['APP1'][6:8]
            if endian == 'MM':
                encoding = 'utf-16be'
            elif endian == 'II':
                encoding = 'utf-16le'
            else:
                raise ValueError

        elif cset == 'Ascii':
            encoding = 'ascii'
        elif cset == 'Jis':
            encoding = 'shift_jis'
        else:
            # Fallback to utf-8 as this is mostly the default for Linux
            # distributions.
            encoding = 'utf-8'

        return self._fallback_to_encoding(text, encoding).strip('\0')

    def get_comment(self):
        try:
            ret = self.get_exif_usercomment()
            if ret == '':
                raise ValueError
        except (ValueError, KeyError):
            try:
                ret = self.get_exif_string('Exif.Image.ImageDescription')
            except (ValueError, KeyError):
                try:
                    ret = self.get_exif_string('Iptc.Application2.ObjectName')
                except (ValueError, KeyError):
                    ret = self.get_jpeg_comment()
        return ret

    def get_flash(self):
        try:
            return self.get_tag_value('Exif.Photo.Flash')
        except KeyError:
            return ''

    def get_exposure(self):
        try:
            exposure = self.get_tag_value('Exif.Photo.ExposureTime')
            if type(exposure) == tuple:
                if exposure[1] == 1:
                    return "%d s" % exposure[0]
                else:
                    return "%d/%d s" % (exposure[0], exposure[1])
            else:
                if exposure.denominator == 1:
                    return "%d s" % exposure.numerator
                else:
                    return "%d/%d s" % (exposure.numerator, exposure.denominator)
        except (ValueError, KeyError):
            return ''

    def get_iso(self):
        try:
            return self.get_exif_string('Exif.Photo.ISOSpeedRatings')
        except KeyError:
            return ''

    def get_fnumber(self):
        try:
            val = self.get_exif_float('Exif.Photo.FNumber')
        except KeyError:
            return ''
        else:
            return 'f/%s' % val

    def get_focal_length(self):
        try:
            flen = self.get_exif_float('Exif.Photo.FocalLength')
        except KeyError:
            return ''
        else:
            flen = '%s mm' % flen

        try:
            flen35 = self.get_exif_float('Exif.Photo.FocalLengthIn35mmFilm')
        except KeyError:
            pass
        else:
            flen += _(' (35 mm equivalent: %s mm)') % flen35
            return flen

        try:
            try:
                iwidth = float(str(self._metadata['Exif.Photo.ImageWidth']))
            except IndexError:
                iwidth = float(str(self._metadata['Exif.Photo.PixelXDimension']))
            fresunit = str(self._metadata['Exif.Photo.FocalPlaneResolutionUnit'])
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
            lenstr = '%.01f' % (foclength / ccdwidth * 36 + 0.5)

            flen += _(' (35 mm equivalent: %s mm)') % lenstr
        except (IndexError, KeyError):
            return flen

        return flen


class _Tags_PyExiv2_Legacy(_ImageInfoTags):
    """
    Wrapper for pyexiv2 0.1
    """

    def __init__(self, image_path):
        _ImageInfoTags.__init__(self, image_path)

        self._metadata = pyexiv2.Image(image_path.encode(sys.getfilesystemencoding()))
        self._metadata.readMetadata()

    def get_exif_date(self, name):
        '''
        Parses date from EXIF information.
        '''
        exif_date = str(self._metadata[name])
        date, time = exif_date.split(' ')
        year, month, day = date.split('-')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                                 int(hour), int(minute), int(second))

    def get_int(self, name):
        return int(self._metadata[name])

    def get_interpreted_value(self, name):
        return self._metadata.interpretedExifValue(name)

    def get_decoded_utf8(self, name):
        return self.get_interpreted_value(name).decode('utf-8')

    TAG_PYTRANSLATORS = {
        'Exif.Photo.DateTimeDigitized' : 'get_exif_date',
        'Exif.Photo.DateTimeOriginal'  : 'get_exif_date',
        'Exif.Image.DateTime'          : 'get_exif_date',
        'Exif.Image.Orientation'       : 'get_int',
        'Exif.Pentax.LensType'         : 'get_interpreted_value',
        'Exif.Nikon3.Lens'             : 'get_interpreted_value',
        'Exif.Nikon3.LensType'         : 'get_interpreted_value',
        'Exif.Minolta.LensID'          : 'get_interpreted_value',
        'Exif.Photo.Flash'             : 'get_decoded_utf8',
    }

    def get_tag_value(self, name, raw=False):
        if not raw and name in _Tags_PyExiv2_Legacy.TAG_PYTRANSLATORS.keys():
            translator = getattr(self.__class__,
                                 _Tags_PyExiv2_Legacy.TAG_PYTRANSLATORS[name])
            return translator(self, name)
        else:
            return self._metadata[name]

    def get_jpeg_comment(self):
        try:
            return self._fallback_to_encoding(self._metadata.getComment())
        except (KeyError, AttributeError):
            return ''


class _Tags_PyExiv2(_ImageInfoTags):
    """
    Wrapper for pyexiv2 0.2
    """

    def __init__(self, image_path):
        _ImageInfoTags.__init__(self, image_path)

        self._metadata = pyexiv2.ImageMetadata(image_path)
        self._metadata.read()

    def get_tag_value(self, name, raw=False):
        if raw:
            return self._metadata[name].raw_value
        else:
            return self._metadata[name].value

    def get_jpeg_comment(self):
        try:
            return self._fallback_to_encoding(self._metadata.comment)
        except AttributeError:
            try:
                # comment appeared in pyexiv2 0.2.2, so use PIL if this does
                # not work.
                im = Image.open(self.image_path)
                return self._fallback_to_encoding(im.app['COM'])
            except (KeyError, AttributeError):
                return ''


if 'ImageMetadata' in dir(pyexiv2):
    # pyexiv2 0.2
    ImageInfoTags = _Tags_PyExiv2
elif 'Image' in dir(pyexiv2):
    # pyexiv2 0.1
    ImageInfoTags = _Tags_PyExiv2_Legacy
else:
    raise ImportError('Unrecognized pyexiv2 version.')


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

        self.description_filename = os.path.join(self.directory_path, MATEW_METADATA)
        if os.path.isfile(self.description_filename):
            self.description_file = self.description_filename
            self.add_file_dependency(self.description_filename)
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
            raise NoMetadata(_('Could not open metadata file %s') % path)

        f = file(path, 'r')
        for line in f:
            for tag in MATEW_TAGS.keys():
                tag_text = MATEW_TAGS[tag]
                tag_len = len(tag_text)
                if line[:tag_len] == tag_text:
                    data = line[tag_len:]
                    data = data.strip()
                    # Strip quotes
                    if data[0] == '"':
                        data = data[1:]
                    if data[-1] == '"':
                        data = data[:-1]
                    if tag == 'album_picture':
                        if subdir is not None:
                            data = os.path.join(subdir, data)
                        data = os.path.join(self.dir.path, data)
                    metadata[tag] = data.decode(locale.getpreferredencoding())
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
            try:
                picture = self.dir.get_all_medias_paths()[0]
            except IndexError:
                picture = None
            if picture is not None:
                result['album_picture'] = picture

        return result


class DefaultMetadata(make.FileMakeObject):
    """
    This is a the building of the default metadata file in the source directory.
    """

    def __init__(self, source_dir, album):
        self.source_dir = source_dir

        metadata_path = os.path.join(self.source_dir.path, MATEW_METADATA)
        super(DefaultMetadata, self).__init__(metadata_path)

        self.album = album

    def build(self):
        md = DirectoryMetadata(self.source_dir)

        md_data = md.get()
        if 'album_description' in md_data.keys()\
        or 'album_name' in md_data.keys():
            self.log(_("  SKIPPED because metadata exists."))
        elif self.source_dir.get_all_medias_count() < 1:
            self.log(_("  SKIPPED because directory does not contain images."))
        else:
            self.generate(md_data)

    def generate(self, md):
        '''
        Generates new metadata file with default values.
        '''

        self.album.log(_("GEN %s") % self._path, 'info')

        f = file(self._path, 'w')
        f.write('# Directory metadata for lazygal, Matew format\n')
        f.write('Album name "%s"\n' % self.source_dir.human_name);
        f.write('Album description ""\n');
        f.write('Album image identifier "%s"\n' % md['album_picture']);
        f.close()


# vim: ts=4 sw=4 expandtab
