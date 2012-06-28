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
import locale
import logging
import zipfile

import make
import pathutils


class MediaOriginal(make.FileCopy):

    def __init__(self, dir, source_media):
        self.dir = dir
        self.source_media = source_media

        self.filename = source_media.filename

        self.path = os.path.join(self.dir.path, self.filename)
        make.FileCopy.__init__(self, source_media.path, self.path)

    def get_size(self):
        return self.source_media.get_size()

    def build(self):
        logging.info("  CP %s" % self.filename)
        logging.debug("(%s)" % self.path)
        make.FileCopy.build(self)


class SymlinkMediaOriginal(make.FileSymlink):

    def __init__(self, dir, source_media):
        self.dir = dir
        self.source_media = source_media

        self.filename = source_media.filename

        self.path = os.path.join(self.dir.path, self.filename)
        make.FileSymlink.__init__(self, source_media.path, self.path)

    def get_size(self):
        return self.source_media.get_size()

    def build(self):
        logging.info("  SYMLINK %s" % self.filename)
        logging.debug("(%s)" % self.path)
        make.FileSymlink.build(self)


class WebalbumFile(make.FileMakeObject):

    def __init__(self, path, dir):
        make.FileMakeObject.__init__(self, path)
        self.dir = dir
        self.path = path

    def rel_path(self, dir, url=False):
        """
        Returns the path of the current object relative to the supplied dir
        object argument. Force forward slashes if url is True.
        """
        ret = None
        if dir is None or dir is self.dir:
            ret = os.path.basename(self.path)
        else:
            ret = dir.rel_path(self.path)

        if url:
            return pathutils.url_path(ret)
        else:
            return ret


class WebalbumArchive(WebalbumFile):

    def __init__(self, webgal_dir):
        self.path = os.path.join(webgal_dir.path,
                                 webgal_dir.source_dir.name + '.zip')
        WebalbumFile.__init__(self, self.path, webgal_dir)

        self.add_dependency(self.dir.source_dir)

        self.pics = map(lambda x: os.path.join(self.dir.source_dir.path, x),
                        self.dir.source_dir.medias_names)
        for pic in self.pics:
            self.add_file_dependency(pic)

    def build(self):
        zip_rel_path = self.rel_path(self.dir.flattening_dir)
        logging.info(_("  ZIP %s") % zip_rel_path)
        logging.debug("(%s)" % self.path)

        archive = zipfile.ZipFile(self.path, mode='w')
        for pic in self.pics:
            inzip_filename = os.path.join(self.dir.source_dir.name,
                                          os.path.basename(pic))
            # zipfile dislikes unicode
            inzip_fn = inzip_filename.encode(locale.getpreferredencoding())
            archive.write(pic, inzip_fn)
        archive.close()

    def size(self):
        return os.path.getsize(self.path)


class SharedFileCopy(make.FileCopy):

    def __init__(self, src, dst):
        make.FileCopy.__init__(self, src, dst)

    def build(self):
        logging.info(_("CP %%SHAREDDIR%%/%s") % os.path.basename(self.dst))
        logging.debug("(%s)" % self.dst)
        make.FileCopy.build(self)


# vim: ts=4 sw=4 expandtab
