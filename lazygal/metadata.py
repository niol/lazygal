# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2007-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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

from __future__ import division

import os
import locale
import logging
import codecs
import datetime

from lazygal.pygexiv2 import GExiv2
from PIL import Image as PILImage

from lazygal import make

from fractions import Fraction

FILE_METADATA_ENCODING = locale.getpreferredencoding()


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'

FILE_METADATA = ('album-name', 'album-description', 'album-picture', )
FILE_METADATA_MEDIA_SUFFIX = '.comment'

FALLBACK_ENCODING = 'utf-8' # encoding used when guessing

# As per http://www.exiv2.org/tags.html
VENDOR_EXIF_CODES = (
    'Exif.Canon.LensModel',
    'Exif.Minolta.LensID',
    'Exif.Nikon3.Lens',
    'Exif.Nikon3.LensType',
    'Exif.OlympusEq.LensModel',
    'Exif.OlympusEq.LensType',
    'Exif.Panasonic.LensType',
    'Exif.Pentax.LensType',
    'Exif.Samsung2.LensType',
    'Exif.Sigma.LensRange',
    'Exif.Sony1.LensID',
    )

GEXIV2_DATE_FORMAT = '%Y:%m:%d %H:%M:%S'
GExiv2.log_set_level(GExiv2.LogLevel.MUTE) # hide exiv2 errors


def decode_exif_user_comment(raw, imgpath):
    """
    GExiv2 does not decode EXIF user comment.
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
        try:
            text.decode('utf-8')
        except UnicodeDecodeError:
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
        encoding = FALLBACK_ENCODING

    # Return the decoded string according to the found encoding.
    try:
        return text.decode(encoding)
    except UnicodeDecodeError:
        return text.decode(encoding, 'replace')


class FileMetadata(object):

    def __init__(self, path):
        self.path = path

    def contents(self, splitter=None):
        try:
            with codecs.open(self.path, 'r', FILE_METADATA_ENCODING) as f:
                # Not sure why codecs.open() does not skip the UTF-8 BOM. Maybe
                # this is because the BOM is not required and utf-8-sig handles
                # this in a better way. Anyway, the following code skips the
                # UTF-8 BOM if it is present.
                if FILE_METADATA_ENCODING == 'utf-8':
                    maybe_bom = f.read(1).encode(FILE_METADATA_ENCODING)
                    if maybe_bom != codecs.BOM_UTF8: f.seek(0)

                c = f.read()
        except IOError:
            return None

        if splitter is not None:
            return map(lambda s: s.strip(), c.split(splitter))
        else:
            return c.strip()


class ImageInfoTags(object):

    def __init__(self, image_path):
        self.image_path = image_path
        self._metadata = GExiv2.Metadata(self.image_path)

    def get_date(self):
        """
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be updated by
        software when editing photos later.
        """
        for tag in ('Exif.Photo.DateTimeOriginal',
                    'Exif.Image.DateTimeDigitized',
                    'Exif.Image.DateTime',
                   ):
            try:
                dt_str = self._metadata[tag]
                dt = datetime.datetime.strptime(dt_str, GEXIV2_DATE_FORMAT)
            except (KeyError, ValueError) as StrptimeError:
                # ValueError: bypass errors such as "time data '0000:00:00
                # 00:00:00' does not match format '%Y:%m:%d %H:%M:%S'"
                pass
            else:
                return dt

    def get_required_rotation(self):
        try:
            orientation_code = int(self._metadata['Exif.Image.Orientation'])
            if orientation_code == 8:
                return 90
            elif orientation_code == 3:
                return 180
            elif orientation_code == 6:
                return 270
            else:  # Should be orientation_code == 1 but catch all
                return 0
        except KeyError:
            return 0

    def get_camera_name(self):
        """
        Gets vendor and model name from EXIF and tries to construct
        camera name out of this. This is a bit fuzzy, because diferent
        vendors put different information to both tags.
        """
        try:
            model = self._metadata['Exif.Image.Model'].strip()
            # Terminate string at \x00
            pos = model.find('\x00')
            if pos != -1:
                model = model[:14]
            try:
                vendor = self._metadata['Exif.Image.Make'].strip()
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
                return ' '.join([vendor, model])
            except KeyError:
                return model
        except KeyError:
            return ''

    def get_lens_name(self):
        """
        Return name of used lenses. This usually makes sense only for
        SLR cameras and uses various maker notes.
        """
        interpret = self._metadata.get_tag_interpreted_string
        vendor_values = []
        for key in VENDOR_EXIF_CODES:
            try:
                v = self._metadata.get_tag_interpreted_string(key)
                if v is None:
                    raise KeyError
            except KeyError:
                pass
            else:
                vendor_values.append(v.strip())
        return ' '.join([s for s in vendor_values if s])

    def get_exif_string(self, name):
        """
        Reads string from EXIF information.
        """
        return self._metadata[name].strip(' ')

    def get_exif_float(self, name):
        """
        Reads float number from EXIF information (where it is stored as
        fraction).
        """
        val = self.get_exif_float_value(name)
        return str(round(val, 1))

    def get_exif_float_value(self, name):
        """
        Reads float number from EXIF information (where it is stored as
        fraction or int).
        """
        val = self._metadata.get_exif_tag_rational(name)
        return val.numerator / val.denominator

    def _fallback_to_encoding(self, encoded_string, encoding=FALLBACK_ENCODING):
        if encoded_string is None: raise ValueError
        if type(encoded_string) is unicode: return encoded_string
        try:
            return encoded_string.decode(encoding)
        except UnicodeDecodeError:
            return encoded_string.decode(encoding, 'replace')

    def get_exif_usercomment(self):
        ret = self._metadata['Exif.Photo.UserComment'].strip(' \0\x00')
        if type(ret) is not unicode: # the EXIF lib did not do the work for us
            ret = decode_exif_user_comment(ret, self.image_path)
        if ret == 'User comments':
            return ''
        return ret

    def get_file_comment(self):
        fmd = FileMetadata(self.image_path + FILE_METADATA_MEDIA_SUFFIX)
        return fmd.contents()

    def get_comment(self):
        try:
            ret = self.get_file_comment()
            if ret is None:
                ret = self.get_exif_usercomment()
                if ret == '':
                    raise ValueError
        except (ValueError, KeyError):
            try:
                ret = self._metadata['Exif.Image.ImageDescription']
                ret = self._fallback_to_encoding(ret)
            except (ValueError, KeyError):
                try:
                    ret = self._metadata['Iptc.Application2.ObjectName']
                    ret = self._fallback_to_encoding(ret)
                except (ValueError, KeyError):
                    ret = self.get_jpeg_comment()
        return ret

    def get_flash(self):
        try:
            flash_info = self._metadata.get_tag_interpreted_string('Exif.Photo.Flash')
            return self._fallback_to_encoding(flash_info)
        except (ValueError, KeyError):
            return ''

    def get_exposure(self):
        try:
            return str(
                self._metadata.get_exif_tag_rational('Exif.Photo.ExposureTime'))
        except (ValueError, KeyError):
            return ''

    def get_iso(self):
        try:
            return self._metadata['Exif.Photo.ISOSpeedRatings']
        except KeyError:
            return ''

    def get_fnumber(self):
        try:
            val = float(self._metadata.get_exif_tag_rational('Exif.Photo.FNumber'))
        except (KeyError, TypeError):
            return ''
        else:
            return 'f/{}'.format(val)

    def get_focal_length(self):
        try:
            flen = self._metadata.get_exif_tag_rational('Exif.Photo.FocalLength')
        except KeyError:
            return ''
        else:
            flen = '%s mm' % flen

        try:
            flen35 = self._metadata.get_exif_tag_rational('Exif.Photo.FocalLengthIn35mmFilm')
        except KeyError:
            pass
        else:
            flen += _(' (35 mm equivalent: %s mm)') % flen35
            return flen

        try:
            try:
                iwidth = self.get_exif_float_value('Exif.Photo.ImageWidth')
            except (IndexError, KeyError):
                iwidth = self.get_exif_float_value('Exif.Photo.PixelXDimension')

            fresunit = self._metadata['Exif.Photo.FocalPlaneResolutionUnit']
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
            try:
                lenstr = '%.01f' % (foclength / ccdwidth * 36 + 0.5)
            except ZeroDivisionError:
                raise ValueError

            flen += _(' (35 mm equivalent: %s mm)') % lenstr
        except (IndexError, KeyError, ValueError):
            return flen

        return flen

    def get_jpeg_comment(self):
        try:
            comment = self._metadata.get_comment()
            if comment is None or '\x00' in comment:
                raise ValueError  # ignore missing or broken JPEG comments
            return self._fallback_to_encoding(comment.strip(' '))
        except ValueError:
            return ''

    def get_authorship(self):
        try:
            author = self._metadata['Exif.Image.Artist']
            return self._fallback_to_encoding(author)
        except KeyError:
            return ''

    def get_keywords(self):
        """
        Returns all the image tags in a list.

        Try to find the maximum number of keywords. Photo applications store
        keywords in various places. For a comprehensive list, see
        http://redmine.yorba.org/projects/shotwell/wiki/PhotoTags
        """
        kw = list()
        for key in ('Iptc.Application2.Keywords',
                    'Xmp.MicrosoftPhoto.LastKeywordXMP',
                    'Xmp.dc.subject',
                    'Xmp.digiKam.TagsList', ):
            try:
                values = self._metadata.get_tag_multiple(key)
            except KeyError:
                pass
            else:
                for value in values:
                    kw.append(self._fallback_to_encoding(value))
        # FIXME
        # Reading the metadata Xmp.lr.hierarchicalSubject produces error
        # messages:
        #   "No namespace info available for XMP prefix `lr'"
        #kw += self._metadata.get_tag_multiple('Xmp.lr.hierarchicalSubject')

        #remove duplicates
        kw = set(kw)

        return kw


class NoMetadata(Exception):
    """
    Exception indicating that no meta data has been found.
    """
    pass


class DirectoryMetadata(make.GroupTask):

    def __init__(self, dir_path):
        super(DirectoryMetadata, self).__init__()

        self.dir_path = dir_path
        self.add_file_dependency(self.dir_path)

        self.description_filename = os.path.join(self.dir_path, MATEW_METADATA)
        if os.path.isfile(self.description_filename):
            self.description_file = self.description_filename
            self.add_file_dependency(self.description_filename)
        else:
            self.description_file = None

            # Add dependency to "file metadata" files if they exist.
            for file_md_fn in FILE_METADATA:
                file_md_path = os.path.join(self.dir_path, file_md_fn)
                if os.path.isfile(file_md_path):
                    self.add_file_dependency(file_md_path)

    def get_matew_metadata(self, metadata, subdir=None):
        """
        Return dictionary with meta data parsed from Matew like format.
        """
        if subdir is None:
            path = self.description_file
        else:
            path = os.path.join(self.dir_path, subdir, MATEW_METADATA)

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
                    data = data.decode(FILE_METADATA_ENCODING)

                    if tag == 'album_picture':
                        if subdir is not None:
                            data = os.path.join(subdir, data)
                        data = os.path.join(self.dir_path, data)

                    metadata[tag] = data
                    break

        return metadata

    def get_file_metadata(self, metadata, subdir=None):
        """
        Returns the file metadata that could be found in the directory.
        """

        if subdir is None: subdir = self.dir_path

        if 'album_name' not in metadata.keys():
            fmd = FileMetadata(os.path.join(subdir, 'album-name')).contents()
            if fmd is not None:
                metadata['album_name'] = fmd

        if 'album_description' not in metadata.keys():
            fmd = FileMetadata(os.path.join(subdir, 'album-description')).contents()
            if fmd is not None:
                metadata['album_description'] = fmd

        if 'album_picture' not in metadata.keys():
            fmd = FileMetadata(os.path.join(subdir, 'album-picture')).contents(splitter='\n')
            if fmd is not None:
                metadata['album_picture'] = os.path.join(subdir, fmd[0])

        return metadata

    def get(self, subdir=None, dir=None):
        """
        Returns directory meta data. First tries to parse known formats
        and then fall backs to built in defaults.
        """

        result = {}

        try:
            result = self.get_matew_metadata(result, subdir)
        except NoMetadata:
            pass

        result = self.get_file_metadata(result, subdir)

        # Add album picture
        if 'album_picture' not in result:
            try:
                if dir is not None:
                    picture = dir.get_all_medias_paths()[0]
                else:
                    raise IndexError
            except IndexError:
                picture = None
            if picture is not None:
                result['album_picture'] = picture

        return result

    def get_title(self):
        try:
            return self.get()['album_name']
        except KeyError:
            return os.path.basename(self.dir_path).replace('_', ' ')


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
        md = DirectoryMetadata(self.source_dir.path)

        md_data = md.get(None, self.source_dir)
        if 'album_description' in md_data.keys()\
                or 'album_name' in md_data.keys():
            logging.debug(_("  SKIPPED because metadata exists."))
        elif self.source_dir.get_all_medias_count() < 1:
            logging.debug(_("  SKIPPED because directory does not contain images."))
        else:
            self.generate(md_data)

    def generate(self, md):
        """
        Generates new metadata file with default values.
        """

        logging.info(_("GEN %s") % self._path)

        f = file(self._path, 'w')
        f.write(codecs.BOM_UTF8)
        f.write('# Directory metadata for lazygal, Matew format\n')
        f.write('Album name "%s"\n'
                % self.source_dir.human_name.encode('utf-8'))
        f.write('Album description ""\n')
        f.write('Album image identifier "%s"\n'
                % md['album_picture'].encode('utf-8'))
        f.close()


# vim: ts=4 sw=4 expandtab
