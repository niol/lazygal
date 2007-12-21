# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, glob, shutil, sys
import Image

from lazygal import make, sourcetree, tpl, metadata


DATAPATH = os.path.join(os.path.dirname(__file__), '..')
if not os.path.exists(os.path.join(DATAPATH, 'themes')):
    DATAPATH = os.path.join(sys.exec_prefix, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print 'Could not find themes dir, check your installation!'

THEME_DIR = os.path.join(DATAPATH, 'themes')
USER_THEME_DIR = os.path.expanduser(os.path.join('~', '.lazygal', 'themes'))
THEME_SHARED_FILE_PREFIX = 'SHARED_'
DEST_SHARED_DIRECTORY_NAME = 'shared'


class ImageOriginal(make.FileMakeObject):

    def __init__(self, dir, source_image):
        self.dir = dir
        self.source_image = source_image
        self.path = os.path.join(self.dir.path, self.source_image.filename)
        make.FileMakeObject.__init__(self, self.path)

    def build(self):
        shutil.copy(self.source_image.path, self.path)


class ImageOtherSize(make.FileMakeObject):

    def __init__(self, dir, source_image, size_name):
        self.dir = dir
        self.source_image = source_image
        self.osize_path = os.path.join(self.dir.path,
                   self.dir._add_size_qualifier(self.source_image.filename,
                                                size_name))
        make.FileMakeObject.__init__(self, self.osize_path)

        self.size_name = size_name
        if self.size_name == 'thumb':
            self.size = self.dir.album.thumb_size
        else:
            self.size = self.dir.album.browse_sizes[size_name]

        self.add_dependency(self.source_image)

    def build(self):
        im = Image.open(self.source_image.path)

        # Use EXIF data to rotate target image if available and required
        rotation = self.source_image.exif.get_required_rotation()
        if rotation != 0:
            im = im.rotate(rotation)

        im.thumbnail(self.size, Image.ANTIALIAS)

        im.save(self.osize_path, quality = self.dir.album.quality)
        self.dir.album.log("    Generated %s" % self.osize_path)


class WebalbumPage(make.FileMakeObject):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self.dir._add_size_qualifier(base_name + '.html',
                                                     self.size_name)
        self.page_path = os.path.join(self.dir.path, page_filename)
        make.FileMakeObject.__init__(self, self.page_path)

    def _gen_other_img_link(self, img):
        if img:
            link_vals = {}
            link_vals['link'] = self.dir._add_size_qualifier(img.name + '.html',
                                                             self.size_name)
            link_vals['thumb'] = self.dir._add_size_qualifier(img.name\
                                                              + img.extension,
                                                              'thumb')

            thumb = os.path.join(self.dir.path,
                                 self.dir._add_size_qualifier(img.filename,
                                                              'thumb'))
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = img.get_size(thumb)

            return link_vals
        else:
            return None

    def _get_osize_links(self, filename):
        osize_index_links = []
        for osize_name in self.dir.album.browse_sizes.keys():
            osize_info = {}
            if osize_name == self.size_name:
                # No link if we're on the current page
                osize_info['name'] = osize_name
            else:
                osize_info['name'] = osize_name
                osize_info['link'] = self.dir._add_size_qualifier(filename + '.html', osize_name)
            osize_index_links.append(osize_info)

        return osize_index_links


class WebalbumBrowsePage(WebalbumPage):

    def __init__(self, dir, size_name, image_file):
        self.image = image_file
        WebalbumPage.__init__(self, dir, size_name, self.image.name)

        self.add_dependency(ImageOtherSize(self.dir,
                                           self.image,
                                           self.size_name))

        for prevnext in [self.image.previous_image, self.image.next_image]:
            if prevnext:
                self.add_dependency(ImageOtherSize(self.dir, prevnext, 'thumb'))
                # FIXME : The following line should not be needed
                ImageOtherSize(self.dir, prevnext, 'thumb').make()

        if self.dir.album.original:
            self.add_dependency(ImageOriginal(self.dir, self.image))

        self.page_template = self.dir.album.templates['browse.thtml']
        self.add_file_dependency(self.page_template.path)

    def make(self, force=False):
        self.dir.album.log("  - Processing %s" % self.image.filename)
        WebalbumPage.make(self, force)
        self.dir.album.log("  - Finished processing %s" % self.image.filename)

    def build(self):
        tpl_values = {}
        tpl_values['img_src'] = self.dir._add_size_qualifier(self.image.filename, self.size_name)
        tpl_values['name'] = self.image.filename
        tpl_values['dir'] = self.dir.source_dir.strip_root()
        tpl_values['image_name'] = self.image.filename

        browse_image_path = os.path.join(self.dir.path,
                               self.dir._add_size_qualifier(self.image.filename,
                                                            self.size_name))
        tpl_values['img_width'],\
            tpl_values['img_height'] = self.image.get_size(browse_image_path)

        img_date = self.image.get_date_taken()
        tpl_values['image_date'] = img_date.strftime("on %d/%m/%Y at %H:%M")

        tpl_values['prev_link'] =\
            self._gen_other_img_link(self.image.previous_image)
        tpl_values['next_link'] =\
            self._gen_other_img_link(self.image.next_image)
        tpl_values['index_link'] = self.dir._add_size_qualifier('index.html',
                                                                self.size_name)
        tpl_values['osize_links'] = self._get_osize_links(self.image.filename)
        tpl_values['rel_root'] = self.dir.source_dir.rel_root()

        tpl_values['camera_name'] = self.image.exif.get_camera_name()
        tpl_values['flash'] = self.image.exif.get_flash()
        tpl_values['exposure'] = self.image.exif.get_exposure()
        tpl_values['iso'] = self.image.exif.get_iso()
        tpl_values['fnumber'] = self.image.exif.get_fnumber()
        tpl_values['focal_length'] = self.image.exif.get_focal_length()
        tpl_values['comment'] = self.image.exif.get_comment()

        if self.dir.album.original:
            tpl_values['original_link'] = self.image.filename\
                                          + self.image.extension

        self.page_template.dump(tpl_values, self.page_path)
        self.dir.album.log("  - Generated %s"\
                           % os.path.basename(self.page_path))


class WebalbumIndexPage(WebalbumPage):

    def __init__(self, dir, size_name, images, metadatas, subdirs):
        WebalbumPage.__init__(self, dir, size_name, 'index')

        self.images = images
        previous_image = None
        for image in self.images:
            thumb_dep = ImageOtherSize(self.dir, image, 'thumb')
            self.add_dependency(thumb_dep)
            image_dep = WebalbumBrowsePage(self.dir, size_name, image)
            self.add_dependency(image_dep)

            # chain images
            if previous_image:
                previous_image.next_image = image
                image.previous_image = previous_image
            previous_image = image

        self.metadata = None
        for metadata_file in metadatas:
            self.add_file_dependency(os.path.join(self.dir.path, metadata_file))
            # FIXME : This won't work if multiple formats are supported
            self.metadata = metadata.DirectoryMetadata(self.dir.source_dir)

        self.dirnames = subdirs
        for dirname in self.dirnames:
            self.add_file_dependency(os.path.join(self.dir.path, dirname))

        self.page_template = self.dir.album.templates['dirindex.thtml']
        self.add_file_dependency(self.page_template.path)

    def build(self):
        values = {}

        values['ozise_index_links'] = self._get_osize_links('index')

        subgal_links = []
        for dir in self.dirnames:
            dir_info = {'name': dir, 'link': dir + '/'}
            if self.metadata:
                dir_info.update(self.metadata.get(dir))
            subgal_links.append(dir_info)
        values['subgal_links'] = subgal_links
        if self.metadata:
            values.update(self.metadata.get())

        values['images'] = map(self._gen_other_img_link, self.images)

        values['rel_root'] = self.dir.source_dir.rel_root()

        values['rel_path'] = self.dir.source_dir.strip_root()
        title = values['rel_path']
        if title == "":
            # Easy title for root directory
            title = os.path.basename(self.dir.path)
        values['title'] = title.replace('_', ' ')

        self.page_template.dump(values, self.page_path)
        self.dir.album.log("  - Generated %s" %\
                           os.path.basename(self.page_path))


class WebalbumDir(make.FileMakeObject):

    def __init__(self, dir, album, album_dest_dir, clean_dest):
        self.source_dir = dir
        self.path = os.path.join(album_dest_dir, self.source_dir.strip_root())

        make.FileMakeObject.__init__(self, self.path)

        # mtime for directories must be saved, because the WebalbumDir gets
        # updated as its dependencies are built.
        self.__mtime = make.FileMakeObject.get_mtime(self)

        # Create the directory if it does not exist
        if not os.path.isdir(self.path):
            os.makedirs(self.path, mode = 0755)
            self.source_dir.album.log("  - Created %s" % self.path)

        self.clean_dest = clean_dest
        self.album = album

        self.add_dependency(self.source_dir)

        images = []
        metadatas = []
        for filename in self.source_dir.filenames:
            if self.album._is_ext_supported(filename):
                image = sourcetree.ImageFile(os.path.join(self.source_dir.path,
                                                          filename),
                                             album)
                images.append(image)
            elif filename == metadata.MATEW_METADATA:
                metadatas.append(os.path.join(self.source_dir.path, filename))
            else:
                self.album.log("Ignoring %s, format not supported."\
                               % os.path.join(self.source_dir.path, filename),
                               'warning')
        images.sort(lambda x, y: x.compare_date_taken(y))

        for size_name in self.album.browse_sizes.keys():
            self.add_dependency(WebalbumIndexPage(self,
                                                  size_name,
                                                  images,
                                                  metadatas,
                                                  self.source_dir.dirnames))

    def get_mtime(self):
        # Use the saved mtime that was initialized once, in self.__init__()
        return self.__mtime

    def _add_size_qualifier(self, path, size_name):
        filename, extension = os.path.splitext(path)
        if size_name == self.source_dir.album.default_size_name\
        and extension == '.html':
            # Do not append default size name to HTML page filename
            return path
        else:
            return "%s_%s%s" % (filename, size_name, extension)

    def build(self):
        # Check dest for junk files
        for dest_file in os.listdir(self.path):
            dest_file = os.path.join(self.path, dest_file)
            if dest_file not in self.output_items and\
               dest_file not in self.source_dir.dirnames:
                text = ''
                if not (self.source_dir.is_album_root() and
                        dest_file == os.path.join(self.path,
                                                  DEST_SHARED_DIRECTORY_NAME)):
                    rmv_candidate = os.path.join(self.path, dest_file)
                    if self.clean_dest and not os.path.isdir(rmv_candidate):
                        os.unlink(rmv_candidate)
                        text = "has been"
                    else:
                        text = "should be"
                    self.album.log("  - %s %s removed" %
                                   (dest_file, text), 'warning')

    def make(self, force=False):
        make.FileMakeObject.make(self, force)

        # Although we should have modified the directory contents and thus its
        # mtime, it is possible that the directory mtime has not been updated
        # if we regenerated without adding/removing pictures (to take into
        # account a rotation for example). This is why we force directory mtime
        # update here.
        os.utime(self.path, None)


class Album:

    def __init__(self, source_dir, thumb_size, browse_sizes,
                 quality=85, debug=False):
        self.set_logging()

        self.source_dir = os.path.abspath(source_dir)

        self.thumb_size = thumb_size
        self.browse_sizes = dict(browse_sizes)
        self.quality = quality
        self.default_size_name = browse_sizes[0][0]

        self.templates = {}
        self.tpl_loader = None
        self.tpl_vars = None
        self.original = False

    def set_theme(self, theme):
        self.theme = theme
        self.templates.clear()

        # First try user directory
        self.tpl_dir = os.path.join(USER_THEME_DIR, self.theme)
        if not os.path.exists(self.tpl_dir):
            # Fallback to system themes
            self.tpl_dir = os.path.join(THEME_DIR, self.theme)
            if not os.path.exists(self.tpl_dir):
                raise ValueError('Theme %s not found' % self.theme)

        self.tpl_loader = tpl.TplFactory([self.tpl_dir])
        self.set_tpl_vars()

        for tpl_file in os.listdir(self.tpl_dir):
            if self.tpl_loader.is_known_template_type(tpl_file):
                filename = os.path.basename(tpl_file)
                self.templates[filename] = self.tpl_loader.load(tpl_file)

    log_levels = ['debug', 'warning', 'error']

    def set_tpl_vars(self, tpl_vars=None):
        if tpl_vars is not None:
            self.tpl_vars = tpl_vars
        if self.tpl_loader is not None and self.tpl_vars is not None:
            self.tpl_loader.set_common_values(self.tpl_vars)

    def set_logging(self, level='warning', outpipe=sys.stdout,
                                           errpipe=sys.stderr):
        self.log_level = level
        self.log_outpipe = outpipe
        self.log_errpipe = errpipe

    def set_original(self, original = False):
        self.original = original

    def log(self, msg, level='debug'):
        if self.log_levels.index(level)\
           >= self.log_levels.index(self.log_level):
            txt = "%s: %s" % (level, msg)
            if level == 'error':
                print >> self.log_errpipe, txt
            else:
                print >> self.log_outpipe, txt

    def _is_ext_supported(self, filename):
        filename, extension = os.path.splitext(filename)
        return extension.lower() in ['.jpg']

    def generate(self, dest_dir, check_all_dirs=False, clean_dest=False):
        sane_dest_dir = os.path.abspath(dest_dir)
        self.log("* Generating to %s" % sane_dest_dir)

        for root, dirnames, filenames in os.walk(self.source_dir):
            self.log("* Entering %s" % root)

            dir = sourcetree.Directory(root, dirnames, filenames, self)
            destgal = WebalbumDir(dir, self, sane_dest_dir, clean_dest)

            if not destgal.needs_build() and not check_all_dirs:
                self.log("Skipping %s because of mtime, use --check-all-dirs or touch source directory to override." % root,
                             'warning')
            else:
                destgal.make()

            self.log("* Leaving %s" % root)

        self.copy_shared(sane_dest_dir)

    def copy_shared(self, dest_dir):
        shared_stuff_dir = os.path.join(dest_dir, DEST_SHARED_DIRECTORY_NAME)

        if not os.path.isdir(shared_stuff_dir):
            os.mkdir(shared_stuff_dir)

        for shared_file in glob.glob(\
          os.path.join(self.tpl_dir, THEME_SHARED_FILE_PREFIX + '*')):
            shared_file_name = os.path.basename(shared_file).\
                                     replace(THEME_SHARED_FILE_PREFIX, '')
            shared_file_dest = os.path.join(shared_stuff_dir,
                                            shared_file_name)

            try:
                dest_mtime = os.path.getmtime(shared_file_dest)
            except OSError:
                dest_mtime = 0

            if self.tpl_loader.is_known_template_type(shared_file):
                tpl = self.templates[os.path.basename(shared_file)]

                # Remove the 't' from the beginning of ext
                filename, ext = os.path.splitext(shared_file_dest)
                if ext.startswith('.t'):
                    real_dest = filename + '.' + ext[2:]
                else:
                    raise ValueError('We have a template with an extension that does not start with a t. Abording.')
                tpl.dump({}, real_dest)
                self.log("* Generated or updated %s" % shared_file_dest)
            else:
                if os.path.getmtime(shared_file) > dest_mtime:
                    shutil.copy(shared_file, shared_file_dest)
                    self.log("* Copied or updated %s" % shared_file_dest)


# vim: ts=4 sw=4 expandtab
