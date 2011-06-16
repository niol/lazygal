# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, locale
import codecs
import datetime
import Image

from lazygal import pyexiv2api as pyexiv2
from lazygal import make


MATEW_TAGS = {
    'album_name': 'Album name',
    'album_description': 'Album description',
    'album_picture': 'Album image identifier',
}
MATEW_METADATA = 'album_description'

FILE_METADATA = ('album-name', 'album-description', 'album-picture', )
FILE_METADATA_MEDIA_SUFFIX = '.comment'


class FileMetadata(object):

    def __init__(self, path):
        self.path = path

    def contents(self, splitter=None):
        try:
            with codecs.open(self.path, 'r',
                             locale.getpreferredencoding()) as f:

                # Not sure why codecs.open() does not skip the UTF-8 BOM. Maybe
                # this is because the BOM is not required and utf-8-sig handles
                # this in a better way. Anyway, the following code skips the
                # UTF-8 BOM if it is present.
                maybe_bom = f.read(1).encode(locale.getpreferredencoding())
                if maybe_bom != codecs.BOM_UTF8: f.seek(0)

                c = f.read()
        except IOError:
            return None

        if splitter is not None:
            return map(lambda s: s.strip('\n '), c.split(splitter))
        else:
            return c.strip('\n ')


class ImageInfoTags(object):

    def __init__(self, image_path):
        self.image_path = image_path
        self._metadata = pyexiv2.ImageMetadata(self.image_path)
        self._metadata.read()

    def get_tag_value(self, name):
        if name.startswith('Iptc.'):
            # Iptc tags are always lists, so, for now, return the first
            # element.
            return self._metadata[name].values[0]
        else:
            return self._metadata[name].value

    def get_date(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        for date_tag in ('Exif.Photo.DateTimeDigitized',
                         'Exif.Photo.DateTimeOriginal',
                         'Exif.Image.DateTime',
                        ):
            try:
                date = self.get_tag_value(date_tag)
                if type(date) is not datetime.datetime:
                    # Sometimes, pyexiv2 sends a string. It seems to happen on
                    # malformed tags.
                    raise ValueError
            except (IndexError, ValueError, KeyError):
                pass
            else:
                return date

        # No date could be found in the picture metadata
        return None

    def get_required_rotation(self):
        try:
            orientation_code = self.get_tag_value('Exif.Image.Orientation')
            if orientation_code == 8:
                return 90
            elif orientation_code == 3:
                return 180
            elif orientation_code == 6:
                return 270
            else: # Should be orientation_code == 1 but catch all
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
            model = self.get_tag_value('Exif.Image.Model').strip()
            # Terminate string at \x00
            pos = model.find('\x00')
            if pos != -1:
                model = model[:14]
            try:
                vendor = self.get_tag_value('Exif.Image.Make').strip()
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
        return self.get_tag_value('Exif.Photo.UserComment').strip(' \0\x00')

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
                ret = self.get_exif_string('Exif.Image.ImageDescription')
                ret = self._fallback_to_encoding(ret)
            except (ValueError, KeyError):
                try:
                    ret = self.get_exif_string('Iptc.Application2.ObjectName')
                    ret = self._fallback_to_encoding(ret)
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

    def get_jpeg_comment(self):
        try:
            return self._fallback_to_encoding(self._metadata.comment.strip(' '))
        except AttributeError:
            return ''

    def get_authorship(self):
        try:
            return self.get_exif_string('Exif.Image.Artist')
        except KeyError:
            return ''


class NoMetadata(Exception):
    '''
    Exception indicating that no meta data has been found.
    '''
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

    def get_matew_metadata(self, metadata, subdir = None):
        '''
        Return dictionary with meta data parsed from Matew like format.
        '''
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
                    if tag == 'album_picture':
                        if subdir is not None:
                            data = os.path.join(subdir, data)
                        data = os.path.join(self.dir_path, data)
                    metadata[tag] = data.decode(locale.getpreferredencoding())
                    break

        return metadata

    def get_file_metadata(self, metadata, subdir=None):
        '''
        Returns the file metadata that could be found in the directory.
        '''

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
        '''
        Returns directory meta data. First tries to parse known formats
        and then fall backs to built in defaults.
        '''

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
            self.album.log(_("  SKIPPED because metadata exists."))
        elif self.source_dir.get_all_medias_count() < 1:
            self.album.log(_("  SKIPPED because directory does not contain images."))
        else:
            self.generate(md_data)

    def generate(self, md):
        '''
        Generates new metadata file with default values.
        '''

        self.album.log(_("GEN %s") % self._path, 'info')

        f = file(self._path, 'w')
        f.write(codecs.BOM_UTF8)
        f.write('# Directory metadata for lazygal, Matew format\n')
        f.write('Album name "%s"\n'\
                % self.source_dir.human_name.encode('utf-8'));
        f.write('Album description ""\n');
        f.write('Album image identifier "%s"\n'\
                % md['album_picture'].encode('utf-8'));
        f.close()


# vim: ts=4 sw=4 expandtab
