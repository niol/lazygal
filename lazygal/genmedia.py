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


import os

import Image
# lazygal has her own ImageFile class, so avoid trouble
import ImageFile as PILImageFile

import make
import genfile
import eyecandy
import mediautils
from lazygal import pyexiv2api as pyexiv2


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

        try:
            if not self.source_image.broken:
                im = Image.open(self.source_image.path)
                self.__build_other_size(im)
        except IOError:
            self.dir.album.log(_("  %s is BROKEN, skipped")\
                               % self.source_image.filename,
                               'error')
            self.source_image.broken = True
            raise

    def call_build(self):
        try:
            self.build()
        except IOError:
            # Make the system believe the file was built a long time ago.
            self.stamp_build(0)
        else:
            self.stamp_build()

    PRIVATE_IMAGE_TAGS = (
        'Exif.GPSInfo.GPSLongitude',
        'Exif.GPSInfo.GPSLatitude',
        'Exif.GPSInfo.GPSDestLongitude',
        'Exif.GPSInfo.GPSDestLatitude',
    )

    def __build_other_size(self, im):
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

        # Copy exif tags to reduced img
        imgtags = pyexiv2.ImageMetadata(self.source_image.path)
        imgtags.read()
        dest_imgtags = pyexiv2.ImageMetadata(self.path)
        dest_imgtags.read()
        imgtags.copy(dest_imgtags)
        dest_imgtags['Exif.Photo.PixelXDimension'] = new_size[0]
        dest_imgtags['Exif.Photo.PixelYDimension'] = new_size[1]
        # Those are removed from published pics due to pivacy concerns
        for tag in self.PRIVATE_IMAGE_TAGS:
            try:
                del dest_imgtags[tag]
            except KeyError:
                pass
        try:
            dest_imgtags.write()
        except ValueError, e:
            self.dir.album.log(_("Could not copy metadata in reduced picture: %s") % e, 'error')


class WebalbumPicture(make.FileMakeObject):

    BASEFILENAME = 'index'

    def __init__(self, webgal_dir):
        self.album = webgal_dir.album
        self.path = os.path.join(webgal_dir.path,
                                 self.album.get_webalbumpic_filename())
        make.FileMakeObject.__init__(self, self.path)

        self.add_dependency(webgal_dir.source_dir)

        # Use already generated thumbs for better performance (lighter to
        # rotate, etc.).
        thumbs = [image.thumb\
                  for image in webgal_dir.get_all_medias_tasks()
                  if image.thumb and not image.media.broken]

        for thumb in thumbs:
            self.add_dependency(thumb)

        if webgal_dir.source_dir.album_picture:
            albumpic_path = os.path.join(webgal_dir.source_dir.path,
                                         webgal_dir.source_dir.album_picture)
            if not os.path.isfile(albumpic_path):
                self.album.log(_("Supplied album picture %s does not exist.")\
                               % webgal_dir.source_dir.album_picture,
                               'error')

            md_dirpic_thumb = self.album._add_size_qualifier(\
                                           webgal_dir.source_dir.album_picture,
                                           THUMB_SIZE_NAME)
            md_dirpic_thumb = os.path.join(webgal_dir.path, md_dirpic_thumb)
        else:
            md_dirpic_thumb = None

        pics = [thumb.path for thumb in thumbs]
        self.dirpic = eyecandy.PictureMess(pics, md_dirpic_thumb,
                                           bg=self.album.webalbumpic_bg)

    def build(self):
        self.album.log(_("  DIRPIC %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        try:
            self.dirpic.write(self.path)
        except ValueError, ex:
            self.album.log(str(ex), 'error')



class WebVideo(genfile.WebalbumFile):

    def __init__(self, webgal, source_video):
        self.webgal = webgal
        self.source_video = source_video
        path = os.path.join(self.webgal.path, source_video.name+'.ogg')
        genfile.WebalbumFile.__init__(self, path, webgal)

        self.add_dependency(self.source_video)

    def build(self):
        vid_rel_path = self._rel_path(self.webgal.flattening_dir)
        self.webgal.album.log(_("  TRANSCODE %s") % vid_rel_path, 'info')

        transcoder = self.webgal.album.get_transcoder()
        try:
            transcoder.convert(self.source_video.path, self.path)
        except mediautils.TranscodeError, e:
            self.dir.album.log(_("  %s is BROKEN, skipped")\
                               % self.source_video.filename,
                               'error')
            self.dir.album.log(e, 'info')


# vim: ts=4 sw=4 expandtab
