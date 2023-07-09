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
import logging

from PIL import Image as PILImage
# lazygal has her own ImageFile class, so avoid trouble
from PIL import ImageFile as PILImageFile
PILImageFile.MAXBLOCK = 1024 * 1024  # default is 64k, not enough for big pics

from . import make
from . import genfile
from . import eyecandy
from . import mediautils
from .metadata import GExiv2


THUMB_SIZE_NAME = 'thumb'
VIDEO_SIZE_NAME = 'video'


class ResizedMedia(genfile.WebalbumFile):

    force_extension = None

    def __init__(self, webgal, source_media, size_name):
        self.webgal = webgal
        self.source_media = source_media
        self.filename = self.webgal._add_size_qualifier(self.source_media.filename,
                                                        size_name,
                                                        self.force_extension)
        path = os.path.join(self.webgal.path, self.filename)
        super().__init__(path, webgal)

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
        logging.info("  %s %s", self.VERB, media_rel_path)
        logging.debug("(%s)", self.path)

        if not self.source_media.broken:
            self.do_build()


class ImageOtherSize(ResizedMedia):

    def __init__(self, webgal, source_image, size_name):
        if 'alphachannel' in source_image.md \
        and source_image.md['alphachannel']:
            self.force_extension = '.png'
        else:
            self.force_extension = '.jpg'
        super().__init__(webgal, source_image, size_name)

        self.rotation = None

    def get_verb(self): return _('RESIZE')
    VERB = property(get_verb)

    def resize(self, im):
        new_size = self.get_size()

        im.draft(None, new_size)
        return im.resize(new_size, PILImage.LANCZOS)

    def save(self, im):
        if 'alphachannel' in self.source_media.md \
        and self.source_media.md['alphachannel']:
            self.save_png(im)
        else:
            self.save_jpeg(im)

    def save_png(self, im):
        with open(self.path, 'w+b') as im_fp:
            im.save(im_fp, 'png', quality=self.webgal.quality,
                    **self.webgal.save_options)

    def save_jpeg(self, im):
        calibrated = False
        while not calibrated:
            with open(self.path, 'w+b') as im_fp:
                try:
                    im.save(im_fp, 'jpeg', quality=self.webgal.quality,
                            **self.webgal.save_options)
                except IOError as e:
                    if str(e).startswith('encoder error'):
                        PILImageFile.MAXBLOCK = 2 * PILImageFile.MAXBLOCK
                        continue
                    else:
                        raise
            calibrated = True

    def get_rotation(self):
        if self.rotation is None:
            if 'rotation' in self.source_media.md['metadata']:
                self.rotation = self.source_media.md['metadata']['rotation']
            else:
                self.rotation = 0
        return self.rotation

    def get_size(self):
        if self.size is None:
            orig_size = self.source_media.get_size()
            if orig_size == (0, 0, ): # broken pic
                self.size = orig_size
            elif self.get_rotation() in (90, 270, ):
                # swap coords
                orig_size = (orig_size[1], orig_size[0], )
                self.size = self.newsizer.dest_size(orig_size)
                self.unrotated_size = (self.size[1], self.size[0], )
            else:
                self.size = self.newsizer.dest_size(orig_size)
                self.unrotated_size = self.size
        return self.size

    def get_image(self):
        with open(self.source_media.path, 'rb') as im_fp:
            im = PILImage.open(im_fp)
            im.load()
            return im

    TRANSPOSE_METHODS = {
        90 : PILImage.ROTATE_90,
        180: PILImage.ROTATE_180,
        270: PILImage.ROTATE_270,
    }

    def resize(self, im):
        rotation = self.get_rotation()
        self.get_size()

        im.draft(None, self.unrotated_size)
        im = im.resize(self.unrotated_size, PILImage.LANCZOS)

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

    def copy_metadata(self):
        imgtags = GExiv2.Metadata(self.source_media.path)
        dest_imgtags = GExiv2.Metadata(self.path)
        for tag in imgtags.get_exif_tags():
            try:
                dest_imgtags[tag] = imgtags[tag]
            except UnicodeDecodeError:
                logging.warning(_("Could not copy metadata tag '%s'"), tag)

        new_size = self.get_size()
        dest_imgtags['Exif.Photo.PixelXDimension'] = str(new_size[0])
        dest_imgtags['Exif.Photo.PixelYDimension'] = str(new_size[1])

        if self.get_rotation() != 0:
            # Smaller image has been rotated in order to be displayed correctly
            # in a web browser. Fix orientation tag accordingly.
            dest_imgtags['Exif.Image.Orientation'] = '1'

        # Those are removed from published pics due to pivacy concerns,
        # unless explicitly told to keep them in. Option to retain GPS
        # tags can only be set from command line.
        if not self.webgal.keep_gps:
            for tag in self.PRIVATE_IMAGE_TAGS:
                try:
                    dest_imgtags.clear_tag(tag)
                except KeyError:
                    pass
        try:
            dest_imgtags.save_file()
        except Exception as e:
            logging.error(_("Could not copy metadata in reduced picture: %s"), e)

    def do_build(self):
        try:
            im = self.resize(self.get_image())
        except OSError:
            self.source_media.set_broken()
            # Make the system believe the file was built a long time ago.
            self.stamp_build(0)
            self.clean_output()
        else:
            self.save(im)
            if self.webgal.config.get('webgal', 'publish-metadata'):
                self.copy_metadata()


class VideoThumb(ResizedMedia):

    force_extension = '.jpg'

    def get_verb(self): return _('VIDEOTHUMB')
    VERB = property(get_verb)

    def do_build(self):
        try:
            mediautils.VideoThumbnailer(self.source_media.path) \
                .convert(self.path, self.get_size())
        except mediautils.VideoError as e:
            logging.error(_("  creating %s thumbnail failed, skipped"),
                          self.source_media.filename)
            logging.info(str(e))
            self.clean_output()


class WebalbumPicture(make.FileMakeObject):

    BASEFILENAME = 'index'

    def __init__(self, webgal_dir):
        self.path = os.path.join(webgal_dir.path,
                                 webgal_dir.get_webalbumpic_filename())
        super().__init__(self.path)

        self.add_dependency(webgal_dir.source_dir)

        medias = [m for m in webgal_dir.source_dir.get_all_medias()
                  if m.type == 'image']

        # Add video thumbs
        for m in webgal_dir.medias:
            if m.media.type == 'video':
                medias.append(m.thumb)

        for m in medias:
            self.add_dependency(m)

        if webgal_dir.source_dir.album_picture:
            albumpic_path = os.path.join(webgal_dir.source_dir.path,
                                         webgal_dir.source_dir.album_picture)
            if not os.path.isfile(albumpic_path):
                logging.error(_("Supplied album picture %s does not exist."),
                              albumpic_path)

            md_dirpic_thumb = webgal_dir._add_size_qualifier(
                webgal_dir.source_dir.album_picture, THUMB_SIZE_NAME)
            md_dirpic_thumb = os.path.join(webgal_dir.path, md_dirpic_thumb)
        else:
            md_dirpic_thumb = None

        pic_paths = [p.path for p in medias]

        multipic_repr = eyecandy.WEBALBUMPIC_TYPES[webgal_dir.webalbumpic_type]

        # Use 800x600 as a random value to obtain a 4:3 aspect ratio (if
        # thumb size preserves aspect ratio)
        self.dirpic = multipic_repr(pic_paths, md_dirpic_thumb,
                                    bg=webgal_dir.webalbumpic_bg,
                                    result_size=webgal_dir.webalbumpic_size)

    def build(self):
        logging.info(_("  DIRPIC %s"), os.path.basename(self.path))
        logging.debug("(%s)", self.path)
        try:
            self.dirpic.write(self.path)
        except ValueError as ex:
            logging.error(str(ex))


class WebVideo(genfile.WebalbumFile):

    def __init__(self, webgal, source_video, size_name, progress):
        self.progress = progress
        self.webgal = webgal
        self.source_video = source_video
        self.filename = self.webgal._add_size_qualifier(self.source_video.filename,
                                                        size_name, '.webm')
        path = os.path.join(self.webgal.path, self.filename)
        super().__init__(path, webgal)

        newsizer = self.webgal.newsizers[size_name]
        if newsizer == 'original':
            self.new_width, self.new_height = (None, None)
        else:
            self.new_width, self.new_height = newsizer.dest_size(self.source_video.get_size())

        self.add_dependency(self.source_video)

    def build(self):
        vid_rel_path = self.rel_path(self.webgal.flattening_dir)
        logging.info(_("  TRANSCODE %s"), vid_rel_path)

        try:
            transcoder = mediautils.WebMTranscoder(self.source_video.path)
            if self.new_width is not None and self.new_height is not None:
                transcoder.scale((self.new_width, self.new_height))
            transcoder.set_progress(self.progress)
            transcoder.convert(self.path)
        except mediautils.VideoError as e:
            logging.error(_("  transcoding %s failed, skipped"),
                          self.source_video.filename)
            logging.info(str(e))
            self.source_video.set_broken()
            self.clean_output()
        finally:
            self.progress.set_task_done()


# vim: ts=4 sw=4 expandtab
