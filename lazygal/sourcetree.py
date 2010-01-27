# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2009 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, sys, datetime, time
import Image

from lazygal import make, metadata


SOURCEDIR_CONFIGFILE = '.lazygal'


class File(make.FileSimpleDependency):

    def __init__(self, path, album):
        make.FileSimpleDependency.__init__(self, path)

        self.path = path
        self.album = album
        self.filename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.filename)

    def _path_to_unicode(self, path):
        if type(path) is unicode:
            return path
        else:
            return path.decode(sys.getfilesystemencoding())

    def strip_root(self, path=None):
        found = False
        album_path = ""

        if not path:
            head = self.path
        else:
            head = path

        while not found:
            if head == self.album.source_dir:
                found = True
            elif head == "/":
                raise Exception(_("Root not found"))
            else:
                head, tail = os.path.split(head)
                if album_path == "":
                    album_path = tail
                else:
                    album_path = os.path.join(tail, album_path)

        return album_path

    def rel_root(self):
        if os.path.isdir(self.path):
            path = self.path
        else:
            path = os.path.dirname(self.path)
        return self.rel_path(path, self.album.source_dir)

    def rel_path(self, from_dir, path=None):
        try:
            from_dir = from_dir.path
        except AttributeError:
            pass

        if path is None:
            path = self.path

        if not os.path.isdir(path):
            path, fn = os.path.split(path)
        else:
            fn = None

        rel_path = ""
        common_path = from_dir
        while common_path != self.album.source_dir\
        and not self.is_subdir_of(common_path, path):
            common_path, tail = os.path.split(common_path)
            rel_path = os.path.join('..', rel_path)
            if common_path == '/':
                raise Exception(_("Root not found"))

        if self.is_subdir_of(common_path, path):
            rel_path = os.path.join(rel_path, path[len(common_path)+1:])

        if fn:
            rel_path = os.path.join(rel_path, fn)

        return rel_path

    def is_subdir_of(self, dir, path=None):
        if path is None:
            path = self.path

        try:
            return path.startswith(dir.path)
        except AttributeError:
            return path.startswith(dir)

    def get_album_level(self):
        if os.path.isdir(self.path):
            cur_path = self.path
        else:
            cur_path = os.path.dirname(self.path)

        album_level = 0
        while cur_path != self.album.source_dir:
            cur_path, tail = os.path.split(cur_path)
            album_level += 1
        return album_level

    SKIPPED_DIRS = ('.svn', '_darcs', '.bzr', '.git', '.hg', 'CVS', )

    def should_be_skipped(self):
        head = None
        tail = self.strip_root()
        while head != '':
            head, tail = os.path.split(tail)
            if tail in Directory.SKIPPED_DIRS:
                return True
        return False

    def compare_mtime(self, other_file):
        return int(self.get_mtime() - other_file.get_mtime())

    def compare_filename(self, other_file):
        return cmp(self.filename, other_file.filename)


class ImageFile(File):

    def __init__(self, path, album):
        File.__init__(self, path, album)
        self.broken = False

        self.date_taken = None
        self.exif_date = None
        self.__date_probed = False

    def info(self):
        exif = metadata.ExifTags(self.path)
        self.exif_date = exif.get_date()
        self.__date_probed = True
        return exif

    def get_size(self, img_path=None):
        if not img_path:
            img_path = self.path
        im = Image.open(img_path)
        size = im.size
        return size

    def has_exif_date(self):
        if not self.__date_probed:
            self.info()

        if self.exif_date:
            return True
        else:
            return False

    def get_date_taken(self):
        if not self.__date_probed:
            self.info()

        if self.exif_date:
            self.date_taken = self.exif_date
        else:
            # No date available in EXIF, or bad format, use file mtime
            self.date_taken = datetime.datetime.fromtimestamp(self.get_mtime())
        return self.date_taken

    def compare_date_taken(self, other_img):
        date1 = time.mktime(self.get_date_taken().timetuple())
        date2 = time.mktime(other_img.get_date_taken().timetuple())
        delta = date1 - date2
        return int(delta)

    def compare_no_exif_date(self, other_img):
        # Comparison between 'no EXIF' and 'EXIF' sorts EXIF after.
        if self.has_exif_date():
            return 1
        else:
            return -1

    def compare_to_sort(self, other_img):
        if self.has_exif_date() and other_img.has_exif_date():
            return self.compare_date_taken(other_img)
        elif not self.has_exif_date() and not other_img.has_exif_date():
            return self.compare_filename(other_img)
        else:
            # One of the picture has no EXIF date, so we arbitrary sort it
            # before the one with EXIF.
            return self.compare_no_exif_date(other_img)


class Directory(File):

    def __init__(self, source, subdirs, filenames, album):
        File.__init__(self, self._path_to_unicode(source), album)

        # No breaking up of filename and extension for directories
        self.name = self.filename
        self.extension = None

        self.subdirs = subdirs
        self.filenames = map(self._path_to_unicode, filenames)

        self.human_name = self.album._str_humanize(self.name)

        self.images = []
        self.images_names = []
        for filename in self.filenames:
            if self.album._is_ext_supported(filename):
                image_path = os.path.join(self.path, filename)
                image = ImageFile(image_path, self.album)
                try:
                    # Try to preload image EXIF to detect broken images.
                    # (this is not a problem for performance because EXIF info
                    # is probed anyway later)
                    image.info()
                except IOError:
                    self.album.log(_("  %s is BROKEN, skipped")\
                                   % image.filename,
                                   'error')
                    image.broken = True
                else:
                    self.images_names.append(filename)
                    self.images.append(image)
            elif filename not in (metadata.MATEW_METADATA,
                                  SOURCEDIR_CONFIGFILE):
                self.album.log(_("  Ignoring %s, format not supported.")\
                               % filename, 'info')
                self.album.log("(%s)" % os.path.join(self.path, filename))

        self.metadata = metadata.DirectoryMetadata(self)
        md = self.metadata.get()
        if 'album_name' in md.keys():
            self.title = md['album_name']
        else:
            self.title = self.human_name
        if 'album_description' in md.keys():
            self.desc = md['album_description']
        else:
            self.desc = None

        if 'album_picture' in md.keys():
            self.album_picture = self.rel_path(self, md['album_picture'])
        else:
            self.album_picture = None

    def is_album_root(self):
        return self.path == self._path_to_unicode(self.album.source_dir)

    def get_image_count(self):
        return len(self.images_names)

    def get_all_images_count(self):
        all_images_count = len(self.images_names)
        for subdir in self.subdirs:
            all_images_count += subdir.get_all_images_count()
        return all_images_count

    def get_all_images(self):
        all_images = list(self.images) # We want a copy here.
        for subdir in self.subdirs:
            all_images.extend(subdir.get_all_images())
        return all_images

    def get_all_images_paths(self):
        all_images_paths = map(lambda im: os.path.join(self.path, im.filename),
                               self.get_all_images())
        return all_images_paths

    def get_all_subdirs(self):
        all_subdirs = list(self.subdirs) # We want a copy here.
        for subdir in self.subdirs:
            all_subdirs.extend(subdir.get_all_subdirs())
        return all_subdirs


# vim: ts=4 sw=4 expandtab
