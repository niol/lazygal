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

import os, glob, sys
import re
import urllib
import zipfile
import locale

import Image
# lazygal has her own ImageFile class, so avoid trouble
import ImageFile as PILImageFile
import genshi

import __init__
from lazygal import make
from lazygal import sourcetree, metadata
from lazygal import newsize, tpl, metadata, feeds, eyecandy


DATAPATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if not os.path.exists(os.path.join(DATAPATH, 'themes')):
    DATAPATH = os.path.join(sys.exec_prefix, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print _('Could not find themes dir, check your installation!')

THEME_DIR = os.path.join(DATAPATH, 'themes')
USER_THEME_DIR = os.path.expanduser(os.path.join('~', '.lazygal', 'themes'))
THEME_SHARED_FILE_PREFIX = 'SHARED_'
DEST_SHARED_DIRECTORY_NAME = 'shared'

SOURCEDIR_CONFIGFILE = '.lazygal'

THUMB_SIZE_NAME = 'thumb'


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


class ImageOtherSize(WebalbumFile):

    def __init__(self, dir, source_image, size_name):
        self.dir = dir
        self.source_image = source_image
        path = os.path.join(self.dir.path,
               self.dir.album._add_size_qualifier(self.source_image.filename,
                                                  size_name))
        WebalbumFile.__init__(self, path, dir)

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
                im.save(self.path, quality = self.dir.album.quality, **self.dir.album.save_options)
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


class WebalbumArchive(WebalbumFile):

    def __init__(self, lightdir):
        self.path = os.path.join(lightdir.path,
                                 lightdir.source_dir.name + '.zip')
        WebalbumFile.__init__(self, self.path, lightdir)

        self.album = self.dir.album

        self.dir.dirzip = self

        self.add_dependency(self.dir.source_dir)

        self.pics = map(lambda x: os.path.join(self.dir.source_dir.path, x),
                        self.dir.images_names)
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


class WebalbumPage(WebalbumFile):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self._add_size_qualifier(base_name + '.html',
                                                 self.size_name)
        self.page_path = os.path.join(dir.path, page_filename)
        WebalbumFile.__init__(self, self.page_path, dir)

        self.page_template = None

    def set_template(self, tpl):
        self.page_template = tpl
        self.add_file_dependency(self.page_template.path)
        for subtpl in self.page_template.subtemplates():
            self.add_file_dependency(subtpl.path)

    def _gen_other_img_link(self, img, dir=None):
        if img:
            if dir is None or dir is self.dir:
                dir = self.dir
                img_rel_path = ''
            else:
                img_rel_path = dir.source_dir.rel_path(self.dir.source_dir) + '/'

            link_vals = {}
            link_vals['link'] = img_rel_path
            link_vals['link'] += self._add_size_qualifier(img.name + '.html',
                                                          self.size_name)
            link_vals['link'] = self.url_quote(link_vals['link'])
            link_vals['thumb'] = img_rel_path
            link_vals['thumb'] += self._add_size_qualifier(img.filename,
                                                          THUMB_SIZE_NAME)
            link_vals['thumb'] = self.url_quote(link_vals['thumb'])

            thumb = os.path.join(dir.path,
                                 self._add_size_qualifier(img.filename,
                                                          THUMB_SIZE_NAME))
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = img.get_size(thumb)

            link_vals['thumb_name'] = self.dir.album._str_humanize(img.name)

            return link_vals
        else:
            return None

    def _get_osize_links(self, filename):
        osize_index_links = []
        for osize_name in self.dir.album.browse_size_strings.keys():
            osize_info = {}
            if osize_name == self.size_name:
                # No link if we're on the current page
                osize_info['name'] = osize_name
            else:
                osize_info['name'] = osize_name
                osize_info['link'] = self._add_size_qualifier(filename\
                                                              + '.html',
                                                              osize_name)
                osize_info['link'] = self.url_quote(osize_info['link'])
            osize_index_links.append(osize_info)

        return osize_index_links

    def _add_size_qualifier(self, path, size_name):
        return self.dir.album._add_size_qualifier(path, size_name)

    def _do_not_escape(self, value):
        return genshi.core.Markup(value)

    def url_quote(self, url):
        return urllib.quote(url.encode(sys.getfilesystemencoding()), safe=':/')


class WebalbumBrowsePage(WebalbumPage):

    def __init__(self, dir, size_name, image_file):
        self.image = image_file
        WebalbumPage.__init__(self, dir, size_name, self.image.name)

        if self.dir.album.browse_size_strings[size_name] == '0x0':
            self.add_dependency(ImageOriginal(self.dir, self.image))
        else:
            self.add_dependency(ImageOtherSize(self.dir,
                                               self.image,
                                               self.size_name))
            if self.dir.album.original and not self.dir.album.orig_base:
                self.add_dependency(ImageOriginal(self.dir, self.image))

        # Depends on source directory in case an image was deleted
        self.add_dependency(self.dir.source_dir)

        self.set_template(self.dir.album.templates['browse.thtml'])

    def prepare(self):
        for prevnext in [self.image.previous_image, self.image.next_image]:
            if prevnext:
                self.add_dependency(ImageOtherSize(self.dir, prevnext,
                                                   THUMB_SIZE_NAME))

    def build(self):
        page_rel_path = self._rel_path(self.dir.flattening_dir)
        self.dir.album.log(_("  XHTML %s") % page_rel_path, 'info')
        self.dir.album.log("(%s)" % self.page_path)

        tpl_values = {}
        tpl_values['img_src'] = self._add_size_qualifier(self.image.filename,
                                                         self.size_name)
        tpl_values['name'] = self.image.filename
        tpl_values['dir'] = self.dir.source_dir.strip_root()
        tpl_values['image_name'] = self.image.filename

        browse_image_path = os.path.join(self.dir.path,
                                         self._add_size_qualifier(\
                                           self.image.filename, self.size_name))
        tpl_values['img_width'],\
            tpl_values['img_height'] = self.image.get_size(browse_image_path)

        img_date = self.image.get_date_taken()
        # strftime does not work with unicode...
        time_format = _("on %d/%m/%Y at %H:%M").encode(locale.getpreferredencoding())
        time_str = img_date.strftime(time_format)
        tpl_values['image_date'] = time_str.decode(locale.getpreferredencoding())

        tpl_values['prev_link'] =\
            self._gen_other_img_link(self.image.previous_image)
        tpl_values['next_link'] =\
            self._gen_other_img_link(self.image.next_image)

        tpl_values['index_link'] = self._add_size_qualifier('index.html',
                                                            self.size_name)
        if self.dir.should_be_flattened():
            index_rel_dir = self.dir.flattening_dir.source_dir.rel_path(self.dir.source_dir)
            tpl_values['index_link'] = index_rel_dir + tpl_values['index_link']

        tpl_values['osize_links'] = self._get_osize_links(self.image.name)
        tpl_values['rel_root'] = self.dir.source_dir.rel_root()

        tpl_values['camera_name'] = self.image.info().get_camera_name()
        tpl_values['lens_name'] = self.image.info().get_lens_name()
        tpl_values['flash'] = self.image.info().get_flash()
        tpl_values['exposure'] = self.image.info().get_exposure()
        tpl_values['iso'] = self.image.info().get_iso()
        tpl_values['fnumber'] = self.image.info().get_fnumber()
        tpl_values['focal_length'] = self.image.info().get_focal_length()
        tpl_values['comment'] = self.image.info().get_comment()

        if self.dir.album.original:
            if self.dir.album.orig_base:
                tpl_values['original_link'] = os.path.join(\
                    self.dir.source_dir.rel_root(),
                    self.dir.album.orig_base,
                    self.dir.source_dir.strip_root(),
                    self.image.filename)
            else:
                tpl_values['original_link'] = self.image.filename
            tpl_values['original_link'] =\
                self.url_quote(tpl_values['original_link'])

        self.page_template.dump(tpl_values, self.page_path)


class WebalbumIndexPage(WebalbumPage):

    FILENAME_BASE_STRING = 'index'

    def __init__(self, dir, size_name, page_number=0):
        page_paginated_name = self._get_paginated_name(page_number)
        WebalbumPage.__init__(self, dir, size_name, page_paginated_name)

        self.page_number = page_number

        self.subdirs, self.galleries = self.presented_elements()

        for dir, images in self.galleries:
            self.add_dependency(dir.metadata)
            if dir is not self.dir:
                dir.flattening_dir = self.dir
                self.add_dependency(dir.webgal_dir)

            for image in images:
                thumb_dep = ImageOtherSize(dir, image, THUMB_SIZE_NAME)
                self.add_dependency(thumb_dep)
                browse_page_dep = WebalbumBrowsePage(dir, size_name, image)
                self.add_dependency(browse_page_dep)

            if self.dir.album.dirzip and dir.get_image_count() > 1:
                self.add_dependency(WebalbumArchive(dir))

        self.set_template(self.dir.album.templates['dirindex.thtml'])

    def presented_elements(self):
        galleries = []
        if self.dir.album.thumbs_per_page == 0: # No pagination
            galleries.append((self.dir, self.dir.images))
            if self.dir.flatten_below():
                subdirs = []
                for dir in self.dir.get_all_subdirs():
                    galleries.append((dir, dir.webgal_dir.images))
            else:
                subdirs = self.dir.subdirs
        else:
            if self.dir.flatten_below(): # Loose pagination not breaking subgals
                subdirs = [] # No subdir links as they are flattened

                how_many_images = 0
                subdirs_it = iter([self.dir] + self.dir.get_all_subdirs())
                try:
                    # Skip galleries of previous pages.
                    while how_many_images <\
                          self.page_number * self.dir.album.thumbs_per_page:
                        subdir = subdirs_it.next()
                        how_many_images += subdir.get_image_count()
                    # While we're still complying with image quota, add
                    # galleries.
                    how_many_images = 0
                    while how_many_images < self.dir.album.thumbs_per_page:
                        subdir = subdirs_it.next()
                        how_many_images += subdir.get_image_count()
                        galleries.append((subdir, subdir.webgal_dir.images))
                except StopIteration:
                    pass
            else: # Real pagination
                step = self.page_number * self.dir.album.thumbs_per_page
                images = self.dir.images[step:step+self.dir.album.thumbs_per_page]
                galleries.append((self.dir, images))
                # subgal links only for first page
                if self.page_number == 0:
                    subdirs = self.dir.subdirs
                else:
                    subdirs = []

        return subdirs, galleries

    def _get_paginated_name(self, page_number=None):
        if page_number == None:
            page_number = self.page_number
        assert page_number != None

        if page_number < 1:
            return WebalbumIndexPage.FILENAME_BASE_STRING
        else:
            return '_'.join([WebalbumIndexPage.FILENAME_BASE_STRING,
                             str(page_number)])

    def _get_related_index_fn(self):
        return self._add_size_qualifier(\
                            WebalbumIndexPage.FILENAME_BASE_STRING + '.html',
                            self.size_name)

    def _get_onum_links(self):
        onum_index_links = []
        for onum in range(0, self.dir.how_many_pages):
            onum_info = {}
            if onum == self.page_number:
                # No link if we're on the current page
                onum_info['name'] = onum
            else:
                onum_info['name'] = onum
                filename = self._get_paginated_name(onum)
                onum_info['link'] = self._add_size_qualifier(filename + '.html',
                                                             self.size_name)
                onum_info['link'] = self.url_quote(onum_info['link'])
            onum_index_links.append(onum_info)

        return onum_index_links

    def _get_dir_info(self, dir=None):
        if dir is None:
            dir = self.dir

        dir_info = {}
        if dir.metadata:
            dir_info.update(dir.metadata.get())
            if 'album_description' in dir_info.keys():
                dir_info['album_description'] =\
                    self._do_not_escape(dir_info['album_description'])

        if 'album_name' not in dir_info.keys():
            dir_info['album_name'] = dir.human_name

        if self.dir.album.dirzip and dir.dirzip:
            archive_rel_path = dir.dirzip._rel_path(self.dir)
            dir_info['dirzip'] = self.url_quote(archive_rel_path)

        dir_info['is_main'] = dir is self.dir

        return dir_info

    def _get_subgal_links(self):
        subgal_links = []
        for subdir in self.subdirs:
            dir_info = self._get_dir_info(subdir)
            dir_info['link'] = '/'.join([subdir.source_dir.name,
                                         self._get_related_index_fn()])
            dir_info['link'] = self.url_quote(dir_info['link'])
            dir_info['album_picture'] = os.path.join(subdir.source_dir.name,
                                     self.dir.album.get_webalbumpic_filename())
            subgal_links.append(dir_info)
        return subgal_links

    def build(self):
        self.dir.album.log(_("  XHTML %s") % os.path.basename(self.page_path),
                           'info')
        self.dir.album.log("(%s)" % self.page_path)

        values = {}

        if not self.dir.source_dir.is_album_root():
            # Parent index link not for album root
            values['parent_index_link'] = self._get_related_index_fn()

        values['osize_index_links'] = self._get_osize_links(self._get_paginated_name())
        values['onum_index_links'] = self._get_onum_links()

        if self.dir.flatten_below():
            values['subgal_links'] = []
        else:
            values['subgal_links'] = self._get_subgal_links()

        values['images'] = []
        for subdir, images in self.galleries:
            info = self._get_dir_info(subdir)
            img_links = map(lambda x: self._gen_other_img_link(x, subdir),
                            images)
            values['images'].append((info, img_links, ))

        values.update(self._get_dir_info())

        values['rel_root'] = self.dir.source_dir.rel_root()
        values['rel_path'] = self.dir.source_dir.strip_root()

        self.page_template.dump(values, self.page_path)


class LightWebalbumDir(make.FileMakeObject):
    """This is a lighter WebalbumDir object which considers filenames instead of pictures objects with EXIF data, and does not build anything."""

    def __init__(self, dir, subdirs, album, album_dest_dir):
        self.source_dir = dir
        self.path = os.path.join(album_dest_dir, self.source_dir.strip_root())
        make.FileMakeObject.__init__(self, self.path)

        self.add_dependency(self.source_dir)
        self.subdirs = subdirs
        self.album = album
        self.human_name = self.album._str_humanize(self.source_dir.name)

        self.webgal_dir = None
        self.flattening_dir = None

        self.images_names = []
        for filename in self.source_dir.filenames:
            if self.album._is_ext_supported(filename):
                self.images_names.append(filename)
            elif filename not in (metadata.MATEW_METADATA,
                                  SOURCEDIR_CONFIGFILE):
                if self.__class__.__name__ != 'LightWebalbumDir':
                    self.album.log(_("  Ignoring %s, format not supported.")\
                                   % filename, 'info')
                    self.album.log("(%s)" % os.path.join(self.source_dir.path,
                                                         filename))

        self.metadata = metadata.DirectoryMetadata(self.source_dir)
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
            self.album_picture = md['album_picture']
        else:
            self.album_picture = None

        self.dirzip = None

    def get_image_count(self):
        return len(self.images_names)

    def get_subgal_count(self):
        if self.flatten_below():
            return 0
        else:
            len(self.subdirs)

    def get_all_images_count(self):
        all_images_count = len(self.images_names)
        for subdir in self.subdirs:
            all_images_count += subdir.get_all_images_count()
        return all_images_count

    def get_all_images_paths(self):
        all_images_paths = map(lambda fn: os.path.join(self.path, fn),
                               self.images_names)
        for subdir in self.subdirs:
            all_images_paths.extend(subdir.get_all_images_paths())
        return all_images_paths

    def get_all_subdirs(self):
        all_subdirs = list(self.subdirs) # We want a copy here.
        for subdir in self.subdirs:
            all_subdirs.extend(subdir.get_all_subdirs())
        return all_subdirs

    def should_be_flattened(self):
        return self.album.dir_flattening_depth is not False\
        and self.source_dir.get_album_level() > self.album.dir_flattening_depth

    def flatten_below(self):
        if self.album.dir_flattening_depth is False:
            return False
        elif len(self.subdirs) > 0:
            # As all subdirs are at the same level, if one should be flattened,
            # all should.
            return self.subdirs[0].should_be_flattened()
        else:
            return False

    def build(self):
        # This one does not build anything.
        pass


class WebalbumDir(LightWebalbumDir):

    def __init__(self, light_webgal_dir, album_dest_dir, clean_dest):
        LightWebalbumDir.__init__(self, light_webgal_dir.source_dir,
                                        light_webgal_dir.subdirs,
                                        light_webgal_dir.album,
                                        album_dest_dir)
        self.webgal_dir = self
        light_webgal_dir.webgal_dir = self

        # mtime for directories must be saved, because the WebalbumDir gets
        # updated as its dependencies are built.
        self.__mtime = LightWebalbumDir.get_mtime(self)

        self.clean_dest = clean_dest

        # Create the directory if it does not exist
        if not os.path.isdir(self.path):
            self.album.log(_("  MKDIR %%WEBALBUMROOT%%/%s")\
                           % self.source_dir.strip_root(), 'info')
            self.album.log("(%s)" % self.path)
            os.makedirs(self.path, mode = 0755)

        self.images = []
        for fn in self.images_names:
            image = sourcetree.ImageFile(os.path.join(self.source_dir.path, fn),
                                         self.album)
            self.images.append(image)

        if not self.should_be_flattened():
            self.__init_index_pages_build()

    def __init_index_pages_build(self):
        self.how_many_pages = None
        if self.album.thumbs_per_page == 0\
        or (not self.flatten_below()\
            and self.get_image_count() <= self.album.thumbs_per_page)\
        or (self.flatten_below()\
            and self.get_all_images_count() <= self.album.thumbs_per_page):
            # No pagination (requested or needed)
            self.how_many_pages = 1
        else:
            # Pagination requested and needed
            if self.flatten_below(): # Loose pagination not breaking subgals
                how_many_pages = 0
                image_count = 0
                new_page = True
                for subdir in [self] + self.get_all_subdirs():
                    if new_page:
                        how_many_pages += 1
                        new_page = False
                    image_count += subdir.get_image_count()
                    if image_count >= self.album.thumbs_per_page:
                        image_count = 0
                        new_page = True
            else: # Real pagination
                how_many_pages = self.get_image_count()\
                                 / self.album.thumbs_per_page
                if self.get_image_count() % self.album.thumbs_per_page > 0:
                    how_many_pages = how_many_pages + 1
            assert how_many_pages > 1
            self.how_many_pages = how_many_pages

        for size_name in self.album.browse_size_strings.keys():
            for page_number in range(0, self.how_many_pages):
                self.add_dependency(WebalbumIndexPage(self, size_name,
                                                      page_number))

        self.add_dependency(WebalbumPicture(self))

    def prepare(self):
        if self.album.subgal_sort_by[0] == 'mtime':
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_mtime(y.source_dir)
        elif self.album.subgal_sort_by[0] == 'filename':
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_filename(y.source_dir)
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")\
                             % self.album.subgal_sort_by[0])
        self.subdirs.sort(subgal_sorter, reverse=self.album.subgal_sort_by[1])

        if self.album.pic_sort_by[0] == 'exif':
            sorter = lambda x, y: x.compare_to_sort(y)
        elif self.album.pic_sort_by[0] == 'mtime':
            sorter = lambda x, y: x.compare_mtime(y)
        elif self.album.pic_sort_by[0] == 'filename':
            sorter = lambda x, y: x.compare_filename(y)
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")\
                             % self.album.pic_sort_by[0])
        self.images.sort(sorter, reverse=self.album.pic_sort_by[1])

        # chain images
        previous_image = None
        for image in self.images:
            if previous_image:
                previous_image.next_image = image
                image.previous_image = previous_image
            previous_image = image

    def get_mtime(self):
        # Use the saved mtime that was initialized once, in self.__init__()
        return self.__mtime

    def build(self):
        # Check dest for junk files
        extra_files = []
        if self.source_dir.is_album_root():
            extra_files.append(os.path.join(self.path,
                                            DEST_SHARED_DIRECTORY_NAME))

        expected_dirs = map(lambda dn: os.path.join(self.path, dn),
                            self.source_dir.dirnames)
        for dest_file in os.listdir(self.path):
            dest_file = os.path.join(self.path, dest_file)
            if not isinstance(dest_file, unicode):
                # No clue why this happens, but it happens!
                dest_file = dest_file.decode(sys.getfilesystemencoding())
            if dest_file not in self.output_items and\
               dest_file not in expected_dirs:
                text = ''
                if dest_file not in extra_files:
                    rmv_candidate = os.path.join(self.path, dest_file)
                    if self.clean_dest and not os.path.isdir(rmv_candidate):
                        os.unlink(rmv_candidate)
                        text = ""
                    else:
                        text = _("you should")
                    self.album.log(_("  %s RM %s") % (text, dest_file), 'info')

    def make(self, force=False):
        make.FileMakeObject.make(self, force)

        # Although we should have modified the directory contents and thus its
        # mtime, it is possible that the directory mtime has not been updated
        # if we regenerated without adding/removing pictures (to take into
        # account a rotation for example). This is why we force directory mtime
        # update here.
        os.utime(self.path, None)


class WebalbumFeed(make.FileMakeObject):

    def __init__(self, album, dest_dir, pub_url):
        self.album = album
        self.pub_url = pub_url
        if not self.pub_url:
            self.pub_url = 'http://example.com'
        if not self.pub_url.endswith('/'):
            self.pub_url = self.pub_url + '/'

        self.path = os.path.join(dest_dir, 'index.xml')
        make.FileMakeObject.__init__(self, self.path)
        self.feed = feeds.RSS20(self.pub_url)
        self.item_template = self.album.templates['feeditem.thtml']

    def set_title(self, title):
        self.feed.title = title

    def set_description(self, description):
        self.feed.description = description

    def push_dir(self, webalbumdir):
        if webalbumdir.get_image_count() > 0:
            self.add_dependency(webalbumdir)
            self.__add_item(webalbumdir)

    def __add_item(self, webalbumdir):
        url = os.path.join(self.pub_url, webalbumdir.source_dir.strip_root())

        desc_values = {}
        desc_values['album_pic_path'] = os.path.join(url,
                                          self.album.get_webalbumpic_filename())
        desc_values['subgal_count'] = webalbumdir.get_subgal_count()
        desc_values['picture_count'] = webalbumdir.get_image_count()
        desc_values['desc'] = webalbumdir.desc
        desc = self.item_template.instanciate(desc_values)

        self.feed.push_item(webalbumdir.title, url, desc,
                            webalbumdir.source_dir.get_mtime())

    def build(self):
        self.album.log(_("FEED %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        self.feed.dump(self.path)


class SharedFileCopy(make.FileCopy):

    def __init__(self, album, src, dst):
        make.FileCopy.__init__(self, src, dst)
        self.album = album

    def build(self):
        self.album.log(_("CP %%SHAREDDIR%%/%s") %\
                       os.path.basename(self.dst), 'info')
        self.album.log("(%s)" % self.dst)
        make.FileCopy.build(self)


class SharedFileTemplate(make.FileMakeObject):

    def __init__(self, album, shared_tpl_name, shared_file_dest_tplname):
        self.album = album
        self.tpl = self.album.templates[os.path.basename(shared_tpl_name)]

        # Remove the 't' from the beginning of ext
        filename, ext = os.path.splitext(shared_file_dest_tplname)
        if ext.startswith('.t'):
            self.path = filename + '.' + ext[2:]
        else:
            raise ValueError(_('We have a template with an extension that does not start with a t. Abording.'))

        make.FileMakeObject.__init__(self, self.path)
        self.add_file_dependency(shared_tpl_name)

    def build(self):
        self.album.log(_("TPL %%SHAREDDIR%%/%s")\
                       % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        self.tpl.dump({}, self.path)


class SharedFiles(make.FileSimpleDependency):

    def __init__(self, album, dest_dir):
        self.path = os.path.join(dest_dir, DEST_SHARED_DIRECTORY_NAME)
        make.FileSimpleDependency.__init__(self, self.path)

        # Create the shared files directory if it does not exist
        if not os.path.isdir(self.path):
            album.log(_("MKDIR %SHAREDDIR%"), 'info')
            album.log("(%s)" % self.path)
            os.makedirs(self.path, mode = 0755)

        for shared_file in glob.glob(\
          os.path.join(album.tpl_dir, THEME_SHARED_FILE_PREFIX + '*')):
            shared_file_name = os.path.basename(shared_file).\
                                     replace(THEME_SHARED_FILE_PREFIX, '')
            shared_file_dest = os.path.join(self.path,
                                            shared_file_name)

            if album.tpl_loader.is_known_template_type(shared_file):
                self.add_dependency(SharedFileTemplate(album,
                                                       shared_file,
                                                       shared_file_dest))
            else:
                self.add_dependency(SharedFileCopy(album,
                                                   shared_file,
                                                   shared_file_dest))


class Album:

    def __init__(self, source_dir, thumb_size_string, browse_size_strings,
                 optimize=False, progressive=False, quality=85,
                 dir_flattening_depth=False, thumbs_per_page=0,
                 dirzip=False,
                 pic_sort_by=('exif', False),
                 subgal_sort_by=('filename', False)):
        self.set_logging()

        self.source_dir = os.path.abspath(source_dir)
        self.source_dir = self.source_dir.decode(sys.getfilesystemencoding())

        self.thumb_size_string = thumb_size_string
        self.browse_size_strings = dict(browse_size_strings)
        self.newsizers = {}
        for size_name, size_string in self.browse_size_strings.items():
            self.newsizers[size_name] = newsize.get_newsizer(size_string)
        self.newsizers[THUMB_SIZE_NAME] = newsize.get_newsizer(self.thumb_size_string)

        self.default_size_name = browse_size_strings[0][0]
        self.quality = quality

        self.templates = {}
        self.tpl_loader = None
        self.tpl_vars = {}
        self.original = False
        self.orig_base = None
        self.thumbs_per_page = thumbs_per_page
        self.dir_flattening_depth = dir_flattening_depth
        self.dirzip = dirzip
        self.save_options = {}
        if optimize:
            self.save_options['optimize'] = True
        if progressive:
            self.save_options['progressive'] = True

        self.pic_sort_by = pic_sort_by
        self.subgal_sort_by = subgal_sort_by

    def set_theme(self, theme='default', default_style=None):
        self.theme = theme
        self.templates.clear()

        # First try user directory
        self.tpl_dir = os.path.join(USER_THEME_DIR, self.theme)
        if not os.path.exists(self.tpl_dir):
            # Fallback to system themes
            self.tpl_dir = os.path.join(THEME_DIR, self.theme)
            if not os.path.exists(self.tpl_dir):
                raise ValueError(_('Theme %s not found') % self.theme)

        self.tpl_loader = tpl.TplFactory(self.tpl_dir)
        self.tpl_vars.update({'styles' : self.get_avail_styles(self.theme,
                                                               default_style)})
        self.set_tpl_vars()

        for tpl_file in os.listdir(self.tpl_dir):
            if self.tpl_loader.is_known_template_type(tpl_file):
                filename = os.path.basename(tpl_file)
                self.templates[filename] = self.tpl_loader.load(tpl_file)
                self.templates[filename].path = os.path.join(self.tpl_dir,
                                                             tpl_file)

    def set_tpl_vars(self, tpl_vars=None):
        if tpl_vars is not None:
            self.tpl_vars.update(tpl_vars)
        if self.tpl_loader is not None:
            self.tpl_loader.set_common_values(self.tpl_vars)

    def get_avail_styles(self, theme, default_style):
        style_files_mask = os.path.join(self.tpl_dir,
                                        THEME_SHARED_FILE_PREFIX + '*' + 'css')
        styles = []
        for style_tpl_file in glob.glob(style_files_mask):
            style = {}
            tpl_filename = os.path.basename(style_tpl_file).split('.')[0]
            style['filename'] = tpl_filename[len(THEME_SHARED_FILE_PREFIX):]
            style['name'] = self._str_humanize(style['filename'])
            if style['filename'] == default_style:
                style['alternate'] = False
            else:
                style['alternate'] = True
            styles.append(style)
        return styles

    def set_original(self, original=False, orig_base=None):
        self.original = original
        if self.original and orig_base:
            self.orig_base = orig_base
        else:
            self.orig_base = None

    def set_webalbumpic(self, bg='transparent'):
        self.webalbumpic_bg = bg

    def get_webalbumpic_filename(self):
        if self.webalbumpic_bg == 'transparent':
            ext = '.png' # JPEG does not have an alpha channel
        else:
            ext = '.jpg'
        return WebalbumPicture.BASEFILENAME + ext

    log_levels = ['debug', 'info', 'error']

    def set_logging(self, level='info', outpipe=sys.stdout,
                                           errpipe=sys.stderr):
        self.log_level = level
        self.log_outpipe = outpipe
        self.log_errpipe = errpipe

    def log(self, msg, level='debug'):
        if self.log_levels.index(level)\
           >= self.log_levels.index(self.log_level):
            msg = msg.encode(locale.getpreferredencoding())
            if level == 'error':
                print >> self.log_errpipe, msg
            else:
                print >> self.log_outpipe, msg

    def _is_ext_supported(self, filename):
        filename, extension = os.path.splitext(filename)
        return extension.lower() in ['.jpg', '.jpeg']

    def _add_size_qualifier(self, path, size_name):
        filename, extension = os.path.splitext(path)
        if size_name == self.default_size_name and extension == '.html':
            # Do not append default size name to HTML page filename
            return path
        elif size_name in self.browse_size_strings.keys()\
        and self.browse_size_strings[size_name] == '0x0'\
        and extension != '.html':
            # Do not append size_name to unresized images.
            return path
        else:
            return "%s_%s%s" % (filename, size_name, extension)

    def _str_humanize(self, text):
        dash_replaced = text.replace('_', ' ')
        return dash_replaced

    def is_in_sourcetree(self, path):
        head = path
        old_head = None
        while head != old_head:
            if head == self.source_dir:
                return True
            old_head = head
            head, tail = os.path.split(head)
        return False

    def generate_default_medatada(self):
        '''
        Generate default metada files if no exists.
        '''
        self.log(_("Generating metadata in %s") % self.source_dir)

        for root, dirnames, filenames in os.walk(self.source_dir):
            dir = sourcetree.Directory(root, dirnames, filenames, self)
            self.log(_("[Entering %%ALBUMROOT%%/%s]") % dir.strip_root(),
                     'info')
            self.log("(%s)" % dir.path)

            md = metadata.DirectoryMetadata(dir)

            md_data = md.get()
            if 'album_description' in md_data.keys() or 'album_name' in md_data.keys():
                self.log(_("  SKIPPED because metadata exists."))
            else:
                md.generate()

    def generate(self, dest_dir, pub_url=None,
                 check_all_dirs=False, clean_dest=False):
        sane_dest_dir = os.path.abspath(dest_dir)

        if self.is_in_sourcetree(sane_dest_dir):
            raise ValueError(_("Fatal error, web gallery directory is within source tree."))

        self.log(_("Generating to %s") % sane_dest_dir)

        if pub_url and feeds.HAVE_ETREE:
            feed = WebalbumFeed(self, sane_dest_dir, pub_url)
        else:
            feed = None

        dir_heap = {}
        for root, dirnames, filenames in os.walk(self.source_dir,
                                                 topdown=False):

            dir = sourcetree.Directory(root, dirnames, filenames, self)

            if dir.should_be_skipped():
                self.log(_("(%s) has been skipped") % dir.path)
                continue
            if dir.path == os.path.join(sane_dest_dir,
                                        DEST_SHARED_DIRECTORY_NAME):
                self.log(_("(%s) has been skipped because its name collides with the shared material directory name") % dir.path, 'error')
                continue

            self.log(_("[Entering %%ALBUMROOT%%/%s]") % dir.strip_root(),
                     'info')
            self.log("(%s)" % dir.path)

            if dir_heap.has_key(root):
                subdirs = dir_heap[root]
                del dir_heap[root] # No need to keep it there
            else:
                subdirs = []

            light_destgal = LightWebalbumDir(dir, subdirs, self, sane_dest_dir)

            if light_destgal.get_all_images_count() < 1:
                self.log(_("(%s) and childs have no photos, skipped")
                           % dir.path)
                continue

            destgal = WebalbumDir(light_destgal, sane_dest_dir, clean_dest)

            if not dir.is_album_root():
                container_dirname = os.path.dirname(root)
                if not dir_heap.has_key(container_dirname):
                    dir_heap[container_dirname] = []
                dir_heap[container_dirname].append(light_destgal)

            if feed and dir.is_album_root():
                feed.set_title(dir.name)
                md = destgal.metadata.get()
                if 'album_description' in md.keys():
                    feed.set_description(md['album_description'])
                destgal.register_output(feed.path)

            if feed:
                feed.push_dir(light_destgal)
            if destgal.needs_build() or check_all_dirs:
                destgal.make()
            else:
                self.log(_("  SKIPPED because of mtime, touch source or use --check-all-dirs to override."))

        if feed:
            feed.make()

        SharedFiles(self, sane_dest_dir).make()


# vim: ts=4 sw=4 expandtab
