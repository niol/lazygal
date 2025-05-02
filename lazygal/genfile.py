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

from . import make
from . import pathutils


class WebalbumFile(make.FileMakeObject):

    def __init__(self, path, dir):
        super().__init__(path)
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


class MediaOriginal(WebalbumFile):

    def __init__(self, dir, source_media):
        self.filename = source_media.filename
        path = os.path.join(dir.path, self.filename)
        super().__init__(path, dir)

        self.source_media = source_media

        self.set_dep_only()

    def get_size(self):
        return self.source_media.get_size()


class CopyMediaOriginal(MediaOriginal):

    def __init__(self, dir, source_media):
        super().__init__(dir, source_media)
        self.add_dependency(make.FileCopy(self.source_media.path, self.path))

    def build(self):
        logging.info("  CP %s", self.filename)
        logging.debug("(%s)", self.path)


class SymlinkMediaOriginal(MediaOriginal):

    def __init__(self, dir, source_media):
        super().__init__(dir, source_media)
        self.add_dependency(make.FileSymlink(self.source_media.path, self.path))

    def build(self):
        logging.info("  SYMLINK %s", self.filename)
        logging.debug("(%s)", self.path)


class WebalbumArchive(WebalbumFile):

    def __init__(self, webgal_dir):
        self.filename = webgal_dir.source_dir.name + ".zip"
        self.path = os.path.join(webgal_dir.path, self.filename)
        super().__init__(self.path, webgal_dir)

        self.add_dependency(self.dir.source_dir)
        self.pics = list(
            map(
                lambda x: os.path.join(self.dir.source_dir.path, x.media.filename),
                self.dir.medias,
            )
        )
        for pic in self.pics:
            self.add_file_dependency(pic)

    def build(self):
        zip_rel_path = self.rel_path(self.dir.flattening_dir)
        logging.info(_("  ZIP %s"), zip_rel_path)
        logging.debug("(%s)", self.path)

        with zipfile.ZipFile(self.path, "w") as archive:
            for pic in self.pics:
                inzip_fn = os.path.join(self.dir.source_dir.name, os.path.basename(pic))
                archive.write(pic, inzip_fn)

    def size(self):
        return os.path.getsize(self.path)


class SharedFileCopy(make.FileCopy):

    def __init__(self, src, dst):
        super().__init__(src, dst)

    def build(self):
        logging.info(_("CP %%SHAREDDIR%%/%s"), os.path.basename(self.path))
        logging.debug("(%s)", self.path)
        super().build()


# vim: ts=4 sw=4 expandtab
