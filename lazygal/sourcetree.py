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
            cur_path = self.path
        else:
            cur_path = os.path.dirname(self.path)

        rel_root = ""

        while cur_path != self.album.source_dir:
            cur_path, tail = os.path.split(cur_path)
            rel_root = os.path.join('..', rel_root)
        return rel_root

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
        self.__exif = None
        self.previous_image = None
        self.next_image = None

    def info(self):
        if not self.__exif:
            self.__exif = metadata.ExifTags(self.path)
        return self.__exif

    def get_size(self, img_path=None):
        if not img_path:
            img_path = self.path
        im = Image.open(img_path)
        size = im.size
        del im
        return size

    def has_exif_date(self):
        exif_date = self.info().get_date()
        if exif_date:
            return True
        else:
            return False

    def get_date_taken(self):
        exif_date = self.info().get_date()
        if exif_date:
            self.date_taken = exif_date
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

    def __init__(self, source, dirnames, filenames, album):
        File.__init__(self, self._path_to_unicode(source), album)

        # No breaking up of filename and extension for directories
        self.name = self.filename
        self.extension = None

        self.dirnames = map(self._path_to_unicode, dirnames)
        self.filenames = map(self._path_to_unicode, filenames)

    def guess_directory_picture(self, subdir = None):
        '''
        Guesses picture for directory by finding first suitable image.
        '''
        directory = self.path
        relpath = ''

        if subdir is not None:
            directory = os.path.join(directory, subdir)
            relpath = subdir

        for root, dirs, files in os.walk(directory):
            subdirs = root[len(directory):]
            if len(subdirs) > 0 and subdirs[0] == '/':
                subdirs = subdirs[1:]
            for file in files:
                if self.album._is_ext_supported(file):
                    picture = os.path.join(relpath, subdirs, file)
                    return picture

        return None

    def is_album_root(self):
        return self.path == self._path_to_unicode(self.album.source_dir)


# vim: ts=4 sw=4 expandtab
