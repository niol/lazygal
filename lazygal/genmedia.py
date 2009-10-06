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


import os

import Image
# lazygal has her own ImageFile class, so avoid trouble
import ImageFile as PILImageFile

import make
import genfile
import eyecandy


THUMB_SIZE_NAME = 'thumb'


class ImageOtherSize(genfile.WebalbumFile):

    def __init__(self, dir, source_image, size_name):
        self.dir = dir
        self.source_image = source_image
        path = os.path.join(self.dir.path,
               self.dir.album._add_size_qualifier(self.source_image.filename,
                                                  size_name))
        genfile.WebalbumFile.__init__(self, path, dir)

        self.newsizer = self.dir.album.newsizers[size_name]

        self.add_dependency(self.source_image)

    def build(self):
        img_rel_path = self._rel_path(self.dir.flattening_dir)
        self.dir.album.log(_("  RESIZE %s") % img_rel_path, 'info')

        self.dir.album.log("(%s)" % self.path)

        im = Image.open(self.source_image.path)

        new_size = self.newsizer.dest_size(im.size)

        im.draft(None, new_size)
        im = im.resize(new_size, Image.ANTIALIAS)

        # Use EXIF data to rotate target image if available and required
        rotation = self.source_image.info().get_required_rotation()
        if rotation != 0:
            im = im.rotate(rotation)

        calibrated = False
        while not calibrated:
            try:
                im.save(self.path, quality=self.dir.album.quality,
                                   **self.dir.album.save_options)
            except IOError, e:
                if str(e).startswith('encoder error'):
                    PILImageFile.MAXBLOCK = 2 * PILImageFile.MAXBLOCK
                    continue
                else:
                    raise
            calibrated = True


class WebalbumPicture(make.FileMakeObject):

    BASEFILENAME = 'index'

    def __init__(self, lightdir):
        self.album = lightdir.album
        self.path = os.path.join(lightdir.path,
                                 self.album.get_webalbumpic_filename())
        make.FileMakeObject.__init__(self, self.path)

        self.add_dependency(lightdir.source_dir)

        # Use already generated thumbs for better performance (lighter to
        # rotate, etc.).
        pics = map(lambda path: self.album._add_size_qualifier(path,
                                                               THUMB_SIZE_NAME),
                   lightdir.get_all_images_paths())

        for pic in pics:
            self.add_file_dependency(pic)

        if lightdir.album_picture:
            md_dirpic_thumb = self.album._add_size_qualifier(\
                                           lightdir.album_picture,
                                           THUMB_SIZE_NAME)
            md_dirpic_thumb = os.path.join(lightdir.path, md_dirpic_thumb)
        else:
            md_dirpic_thumb = None
        self.dirpic = eyecandy.PictureMess(pics, md_dirpic_thumb,
                                           bg=self.album.webalbumpic_bg)

    def build(self):
        self.album.log(_("  DIRPIC %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        self.dirpic.write(self.path)


# vim: ts=4 sw=4 expandtab
