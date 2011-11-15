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
import logging

import Image as PILImage
# lazygal has her own ImageFile class, so avoid trouble
import ImageFile as PILImageFile
PILImageFile.MAXBLOCK = 1024*1024 # default is 64k, not enough for big pics

import make
import genfile
import eyecandy
import mediautils
from lazygal import pyexiv2api as pyexiv2


THUMB_SIZE_NAME = 'thumb'


class ResizedImage(genfile.WebalbumFile):

    force_extension = None

    def __init__(self, webgal, source_media, size_name):
        self.webgal = webgal
        self.source_media = source_media
        path = os.path.join(self.webgal.path,
               self.webgal._add_size_qualifier(self.source_media.filename,
                                               size_name,
                                               self.force_extension))
        genfile.WebalbumFile.__init__(self, path, webgal)

        self.newsizer = self.webgal.newsizers[size_name]
        self.size = None

        self.add_dependency(self.source_media)

    def get_size(self):
        if self.size is None:
            self.size = self.newsizer.dest_size(self.source_media.get_size())
        return self.size

    def get_verb(self):
        raise NotImplementedError
    VERB = property(get_verb)

    def build(self):
        media_rel_path = self.rel_path(self.webgal.flattening_dir)
        logging.info("  %s %s" % (self.VERB, media_rel_path))
        logging.debug("(%s)" % self.path)

        im = self.resize(self.get_image())
        self.save(im)

    def get_image(self):
        raise NotImplementedError

    def call_build(self):
        try:
            self.build()
        except IOError:
            if not self.source_media.broken:
                logging.error(_("  %s is BROKEN, skipped")\
                              % self.source_media.filename)
                self.source_media.broken = True

            # Make the system believe the file was built a long time ago.
            self.stamp_build(0)
        else:
            self.stamp_build()

    def resize(self, im):
        new_size = self.get_size()

        im.draft(None, new_size)
        return im.resize(new_size, PILImage.ANTIALIAS)

    def save(self, im):
        calibrated = False
        while not calibrated:
            try:
                im.save(self.path, quality=self.webgal.quality,
                                   **self.webgal.save_options)
            except IOError, e:
                if str(e).startswith('encoder error'):
                    PILImageFile.MAXBLOCK = 2 * PILImageFile.MAXBLOCK
                    continue
                else:
                    raise
            calibrated = True


class ImageOtherSize(ResizedImage):

    def __init__(self, webgal, source_image, size_name):
        super(ImageOtherSize, self).__init__(webgal, source_image, size_name)
        self.rotation = None

    def get_verb(self): return _('RESIZE')
    VERB = property(get_verb)

    def get_rotation(self):
        if self.rotation is None:
            source_media_md = self.source_media.info()
            if source_media_md is not None:
                self.rotation = source_media_md.get_required_rotation()
            else:
                self.rotation = 0
        return self.rotation

    def get_size(self):
        if self.size is None:
            orig_size = self.source_media.get_size()
            if self.get_rotation() in (90, 270, ):
                # swap coords
                orig_size = (orig_size[1], orig_size[0], )
                self.size = self.newsizer.dest_size(orig_size)
                self.unrotated_size = (self.size[1], self.size[0], )
            else:
                self.size = self.newsizer.dest_size(orig_size)
                self.unrotated_size = self.size
        return self.size

    def get_image(self):
        return PILImage.open(self.source_media.path)

    TRANSPOSE_METHODS = {
        90  : PILImage.ROTATE_90,
        180 : PILImage.ROTATE_180,
        270 : PILImage.ROTATE_270,
    }

    def resize(self, im):
        rotation = self.get_rotation()
        new_size = self.get_size()

        im.draft(None, self.unrotated_size)
        im = im.resize(self.unrotated_size, PILImage.ANTIALIAS)

        # Use EXIF data to rotate target image if available and required
        if rotation != 0:
            im = im.transpose(self.TRANSPOSE_METHODS[rotation])

        return im

    PRIVATE_IMAGE_TAGS = (
        'Exif.GPSInfo.GPSLongitude',
        'Exif.GPSInfo.GPSLatitude',
        'Exif.GPSInfo.GPSDestLongitude',
        'Exif.GPSInfo.GPSDestLatitude',
    )

    def save(self, im):
        super(ImageOtherSize, self).save(im)

        # Copy exif tags to reduced img

        imgtags = pyexiv2.ImageMetadata(self.source_media.path)
        imgtags.read()
        dest_imgtags = pyexiv2.ImageMetadata(self.path)
        dest_imgtags.read()
        imgtags.copy(dest_imgtags)

        new_size = self.get_size()
        dest_imgtags['Exif.Photo.PixelXDimension'] = new_size[0]
        dest_imgtags['Exif.Photo.PixelYDimension'] = new_size[1]

        if self.get_rotation() != 0:
            # Smaller image has been rotated in order to be displayed correctly
            # in a web browser. Fix orientation tag accordingly.
            dest_imgtags['Exif.Image.Orientation'] = 1

        # Those are removed from published pics due to pivacy concerns
        for tag in self.PRIVATE_IMAGE_TAGS:
            try:
                del dest_imgtags[tag]
            except KeyError:
                pass
        try:
            dest_imgtags.write()
        except ValueError, e:
            logging.error(_("Could not copy metadata in reduced picture: %s") % e)


class VideoThumb(ResizedImage):

    force_extension = '.jpg'

    def get_verb(self): return _('VIDEOTHUMB')
    VERB = property(get_verb)

    def get_image(self):
        try:
            thumb = mediautils.VideoThumbnailer(self.source_media.path).get_thumb()
        except mediautils.TranscodeError, e:
            logging.error(_("  creating %s thumbnail failed, skipped")\
                          % self.source_video.filename)
            logging.info(str(e))
        else:
            return thumb


class WebalbumPicture(make.FileMakeObject):

    BASEFILENAME = 'index'

    def __init__(self, webgal_dir):
        self.path = os.path.join(webgal_dir.path,
                                 webgal_dir.get_webalbumpic_filename())
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
                logging.error(_("Supplied album picture %s does not exist.")\
                              % webgal_dir.source_dir.album_picture)

            md_dirpic_thumb = webgal_dir._add_size_qualifier(\
                                           webgal_dir.source_dir.album_picture,
                                           THUMB_SIZE_NAME)
            md_dirpic_thumb = os.path.join(webgal_dir.path, md_dirpic_thumb)
        else:
            md_dirpic_thumb = None

        pics = [thumb.path for thumb in thumbs]

        # Use 800x600 as a random value to obtain a 4:3 aspect ratio (if
        # thumb size preserves aspect ratio)
        self.dirpic = eyecandy.PictureMess(pics, md_dirpic_thumb,
                bg=webgal_dir.webalbumpic_bg,
                result_size=webgal_dir.webalbumpic_size)

    def build(self):
        logging.info(_("  DIRPIC %s") % os.path.basename(self.path))
        logging.debug("(%s)" % self.path)
        try:
            self.dirpic.write(self.path)
        except ValueError, ex:
            logging.error(str(ex))


class WebVideo(genfile.WebalbumFile):

    def __init__(self, webgal, source_video):
        self.webgal = webgal
        self.source_video = source_video
        path = os.path.join(self.webgal.path, source_video.name + '.webm')
        genfile.WebalbumFile.__init__(self, path, webgal)

        self.add_dependency(self.source_video)

    def build(self):
        vid_rel_path = self.rel_path(self.webgal.flattening_dir)
        logging.info(_("  TRANSCODE %s") % vid_rel_path)

        try:
            mediautils.WebMTranscoder(self.source_video.path).convert(self.path)
        except mediautils.TranscodeError, e:
            logging.error(_("  transcoding %s failed, skipped")\
                          % self.source_video.filename)
            logging.info(str(e))
            os.unlink(self.path)


# vim: ts=4 sw=4 expandtab
