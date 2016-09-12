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


import os
import time
import re
import locale
import logging
import fnmatch
from PIL import Image

from . import py2compat
from . import pathutils, make, metadata
from . import mediautils


SOURCEDIR_CONFIGFILE = '.lazygal'


class File(make.FileSimpleDependency):

    def __init__(self, path, album):
        make.FileSimpleDependency.__init__(self, path)

        self.path = pathutils.path2unicode(path)
        self.album = album
        self.filename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.filename)

    def strip_root(self, path=None):
        if not path:
            path = self.path

        relative_path = os.path.relpath(path, self.album.source_dir)
        if relative_path == '.':
            return ''
        else:
            return relative_path

    def rel_root(self):
        return os.path.relpath(self.album.source_dir, self.path)

    def rel_path(self, from_dir, path=None):
        try:
            from_dir = from_dir.path
        except AttributeError:
            pass

        if path is None:
            path = self.path

        return os.path.relpath(path, from_dir)

    def is_subdir_of(self, dir, path=None):
        if path is None:
            path = self.path

        try:
            dir_path = dir.path
        except AttributeError:
            dir_path = dir

        return pathutils.is_subdir_of(dir_path, path)

    def get_album_level(self, path=None):
        if path is None: path = self.path

        if os.path.isdir(path):
            cur_path = path
        else:
            cur_path = os.path.dirname(path)

        album_level = 0
        while cur_path != self.album.source_dir:
            cur_path, tail = os.path.split(cur_path)
            album_level += 1
            if pathutils.is_root(cur_path):
                raise RuntimeError(_('Root not found'))
        return album_level

    def should_be_skipped(self):
        head = self.strip_root()
        while head != '':
            head, tail = os.path.split(head)
            for pattern in self.album.excludes:
                if fnmatch.fnmatch(tail, pattern):
                    return True
        return False

    def get_datetime(self):
        return py2compat.datetime.fromtimestamp(self.get_mtime())

    def name_numeric(self):
        numeric_part = re.sub("\D", "", self.filename)
        return numeric_part and int(numeric_part) or 0


class MediaFile(File):

    def __init__(self, path, album):
        File.__init__(self, path, album)
        self.broken = False
        self._size = None

        comment_file_path = self.path + metadata.FILE_METADATA_MEDIA_SUFFIX
        if os.path.isfile(comment_file_path):
            self.comment_file_path = comment_file_path
        else:
            self.comment_file_path = None

    def sortkey(self):
        # Comparison between 'no EXIF' and 'EXIF' sorts EXIF after
        # (reliable here means encoded by the camera).
        if self.has_reliable_date():
            return (1, self.get_date_taken().timestamp())
        else:
            return (0, self.filename)


class ImageFile(MediaFile):
    type = 'image'

    def __init__(self, path, album):
        MediaFile.__init__(self, path, album)

        self.date_taken = None
        self.reliable_date = None
        self.__date_probed = False

    def info(self):
        if self.broken: return None
        try:
            exif = metadata.ImageInfoTags(self.path)
        except IOError:
            exif = None
            self.broken = True
        else:
            self.reliable_date = exif.get_date()
        self.__date_probed = True
        return exif

    def get_size(self, img_path=None):
        myself = False
        if not img_path:
            img_path = self.path
            if self._size is not None:
                return self._size
            myself = True

        with open(img_path, 'rb') as im_fp:
            try:
                im = Image.open(im_fp)
            except IOError:
                self.broken = True
                return (None, None)
            else:
                if myself:
                    self._size = im.size
                return im.size

    def has_reliable_date(self):
        if not self.__date_probed:
            self.info()

        if self.reliable_date:
            return True
        else:
            return False

    def get_date_taken(self):
        if not self.__date_probed:
            self.info()

        if self.reliable_date:
            self.date_taken = self.reliable_date
        else:
            # No date available in EXIF, or bad format, use file mtime
            self.date_taken = self.get_datetime()
        return self.date_taken


class VideoFile(MediaFile):
    type = 'video'

    def get_size(self):
        if self._size is None:
            inspector = mediautils.GstVideoInfo(self.path)
            try:
                inspector.inspect()
            except mediautils.VideoError:
                self.broken = True
                return (None, None)
            self._size = inspector.videowidth, inspector.videoheight
        return self._size

    def has_reliable_date(self):
        return False

    def get_date_taken(self):
        return self.get_datetime()

    def info(self):
        return None


class MediaHandler(object):

    FORMATS = {'.jpeg': ImageFile,
               '.jpg' : ImageFile,
               '.png' : ImageFile,
               '.mov' : VideoFile,
               '.avi' : VideoFile,
               '.mp4' : VideoFile,
               '.3gp' : VideoFile,
               '.webm': VideoFile,
               }

    def __init__(self, album):
        self.album = album

    @staticmethod
    def is_known_media(path, album):
        tail = os.path.basename(path)
        for pattern in album.excludes:
            if fnmatch.fnmatch(tail, pattern):
                return False
        filename, extension = os.path.splitext(path)
        extension = extension.lower()
        return extension in MediaHandler.FORMATS.keys()

    NO_VIDEO_SUPPORT_WARNING_ISSUED = False

    @staticmethod
    def warn_no_video_support():
        if not MediaHandler.NO_VIDEO_SUPPORT_WARNING_ISSUED:
            logging.warning(_('Video support is disabled: could not load GStreamer'))

    def get_media(self, path):
        tail = os.path.basename(path)
        for pattern in self.album.excludes:
            if fnmatch.fnmatch(tail, pattern):
                return None
        filename, extension = os.path.splitext(path)
        extension = extension.lower()
        if extension in MediaHandler.FORMATS.keys():
            media_class = MediaHandler.FORMATS[extension]
            if media_class == VideoFile and not mediautils.HAVE_GST:
                MediaHandler.warn_no_video_support()
                return None
            return media_class(path, self.album)
        else:
            return None


class Directory(File):

    def __init__(self, source, subdirs, filenames, album):
        File.__init__(self, source, album)

        # No breaking up of filename and extension for directories
        self.name = self.filename
        self.extension = None

        self.subdirs = subdirs
        self.filenames = map(pathutils.path2unicode, filenames)

        self.human_name = self.album._str_humanize(self.name)

        media_handler = MediaHandler(self.album)
        self.medias = []
        self.medias_names = []
        for filename in self.filenames:
            media_path = os.path.join(self.path, filename)

            if not os.path.isfile(media_path):
                logging.info(_("  Ignoring %s, cannot open file (broken symlink?)."),
                             filename)
                logging.debug("(%s)", os.path.join(self.path, filename))
                continue

            media = media_handler.get_media(media_path)
            if media:
                self.medias_names.append(filename)
                self.medias.append(media)
            elif not self.is_metadata(filename) and\
                    filename != SOURCEDIR_CONFIGFILE:
                logging.info(_("  Ignoring %s, format not supported."),
                             filename)
                logging.debug("(%s)", os.path.join(self.path, filename))

        self.metadata = metadata.DirectoryMetadata(self.path)
        md = self.metadata.get(None, self)
        if 'album_name' in md.keys():
            self.title = md['album_name']
        else:
            self.title = self.human_name
        if 'album_description' in md.keys():
            self.desc = md['album_description']
        else:
            self.desc = None

        if 'album_picture' in md.keys():
            self.album_picture = md['album_picture']
        else:
            self.album_picture = None

    def is_album_root(self):
        return self.path == pathutils.path2unicode(self.album.source_dir)

    def parent_paths(self):
        parent_paths = [self.path]

        found = False
        head = self.path

        while not found:
            if head == self.album.source_dir:
                found = True
            elif pathutils.is_root(head):
                raise RuntimeError(_("Root not found"))
            else:
                head, tail = os.path.split(head)
                parent_paths.append(os.path.join(self.path, head))

        return parent_paths

    def parents_metadata(self):
        return map(metadata.DirectoryMetadata, self.parent_paths())

    def is_metadata(self, filename):
        if filename == metadata.MATEW_METADATA: return True
        if filename in metadata.FILE_METADATA: return True

        # Check for media metadata
        related_media = filename[:-len(metadata.FILE_METADATA_MEDIA_SUFFIX)]
        # As the list self.medias_names is being constructed while this
        # check takes place, the following is only reliable if the filenames
        # list is sorted (thus t.jpg.comment is after t.jpg, and t.jpg is
        # already in self.medias_names), which is the case.
        if related_media in self.medias_names: return True

        return False

    def get_media_count(self, media_type=None):
        if media_type is None:
            return len(self.medias_names)
        else:
            typed_media_count = 0
            for media in self.medias:
                if media.type == media_type:
                    typed_media_count += 1
            return typed_media_count

    def get_all_medias_count(self, media_type=None):
        all_medias_count = self.get_media_count(media_type)
        for subdir in self.subdirs:
            all_medias_count += subdir.get_all_medias_count(media_type)
        return all_medias_count

    def get_all_medias(self):
        all_medias = list(self.medias)  # We want a copy here.
        for subdir in self.subdirs:
            all_medias.extend(subdir.get_all_medias())
        return all_medias

    def get_all_medias_paths(self):
        return [m.path for m in self.get_all_medias()]

    def get_all_subdirs(self):
        all_subdirs = list(self.subdirs)  # We want a copy here.
        for subdir in self.subdirs:
            all_subdirs.extend(subdir.get_all_subdirs())
        return all_subdirs

    def latest_media_stamp(self):
        """
        Returns the latest media date:
            - first considering all pics that have an EXIF date
            - if none have a reliable date, use file mtimes.
        """
        all_medias = self.get_all_medias()
        media_stamp_max = None
        for m in all_medias:
            if m.has_reliable_date():
                media_stamp = m.get_date_taken().timestamp()
                if media_stamp_max is None or media_stamp > media_stamp_max:
                    media_stamp_max = media_stamp

        if media_stamp_max is None:
            # none of the media had a reliable date, use mtime instead
            for m in all_medias:
                media_stamp = m.get_datetime().timestamp()
                if media_stamp_max is None or media_stamp > media_stamp_max:
                    media_stamp_max = media_stamp

        return media_stamp_max


# vim: ts=4 sw=4 expandtab
