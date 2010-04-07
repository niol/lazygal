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


import os
import locale
import zipfile

import make


class ImageOriginal(make.FileCopy):

    def __init__(self, dir, source_image, size_name=None):
        self.dir = dir

        dest_name = source_image.filename
        if size_name:
            dest_name = self.dir.album._add_size_qualifier(dest_name, size_name)

        self.path = os.path.join(self.dir.path, dest_name)
        make.FileCopy.__init__(self, source_image.path, self.path)

    def build(self):
        self.dir.album.log("  CP %s" % os.path.basename(self.path),
                           'info')
        self.dir.album.log("(%s)" % self.path)
        make.FileCopy.build(self)


class WebalbumFile(make.FileMakeObject):

    def __init__(self, path, dir):
        make.FileMakeObject.__init__(self, path)
        self.dir = dir
        self.path = path

    def _rel_path(self, dir=None):
        rel_path = os.path.basename(self.path)
        if dir is None or dir is self.dir:
            return rel_path
        else:
            dir_in = dir.source_dir
            rel_dir_in = self.dir.source_dir.rel_path(dir_in)
            return os.path.join(rel_dir_in, rel_path)


class WebalbumArchive(WebalbumFile):

    def __init__(self, webgal_dir):
        self.path = os.path.join(webgal_dir.path,
                                 webgal_dir.source_dir.name + '.zip')
        WebalbumFile.__init__(self, self.path, webgal_dir)

        self.album = self.dir.album

        self.dir.dirzip = self

        self.add_dependency(self.dir.source_dir)

        self.pics = map(lambda x: os.path.join(self.dir.source_dir.path, x),
                        self.dir.source_dir.images_names)
        for pic in self.pics:
            self.add_file_dependency(pic)

    def build(self):
        zip_rel_path = self._rel_path(self.dir.flattening_dir)
        self.album.log(_("  ZIP %s") % zip_rel_path, 'info')
        self.album.log("(%s)" % self.path)

        archive = zipfile.ZipFile(self.path, mode='w')
        for pic in self.pics:
            inzip_filename = os.path.join(self.dir.source_dir.name,
                                          os.path.basename(pic))
            # zipfile dislikes unicode
            inzip_fn = inzip_filename.encode(locale.getpreferredencoding())
            archive.write(pic, inzip_fn)
        archive.close()


class SharedFileCopy(make.FileCopy):

    def __init__(self, album, src, dst):
        make.FileCopy.__init__(self, src, dst)
        self.album = album

    def build(self):
        self.album.log(_("CP %%SHAREDDIR%%/%s") %\
                       os.path.basename(self.dst), 'info')
        self.album.log("(%s)" % self.dst)
        make.FileCopy.build(self)


# vim: ts=4 sw=4 expandtab
