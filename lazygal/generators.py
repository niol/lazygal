# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2008 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, glob, sys, string
import zipfile
import locale

import Image
import genshi

import __init__
from lazygal import make, sourcetree, tpl, metadata, feeds, eyecandy


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


class ImageOriginal(make.FileCopy):

    def __init__(self, dir, source_image):
        self.dir = dir
        self.path = os.path.join(self.dir.path, source_image.filename)
        make.FileCopy.__init__(self, source_image.path, self.path)

    def build(self):
        self.dir.album.log("  CP %s" % os.path.basename(self.path),
                           'info')
        self.dir.album.log("(%s)" % self.path)
        make.FileCopy.build(self)


class ImageOtherSize(make.FileMakeObject):

    def __init__(self, dir, source_image, size_name):
        self.dir = dir
        self.source_image = source_image
        self.osize_path = os.path.join(self.dir.path,
               self.dir.album._add_size_qualifier(self.source_image.filename,
                                                  size_name))
        make.FileMakeObject.__init__(self, self.osize_path)

        self.size_name = size_name
        if self.size_name == 'thumb':
            self.size = self.dir.album.thumb_size
        else:
            self.size = self.dir.album.browse_sizes[size_name]

        self.add_dependency(self.source_image)

    def build(self):
        self.dir.album.log("  RESIZE %s" % os.path.basename(self.osize_path),
                           'info')
        self.dir.album.log("(%s)" % self.osize_path)

        im = Image.open(self.source_image.path)

        # Use EXIF data to rotate target image if available and required
        rotation = self.source_image.info().get_required_rotation()
        if rotation != 0:
            im = im.rotate(rotation)

        im.thumbnail(self.size, Image.ANTIALIAS)

        im.save(self.osize_path, quality = self.dir.album.quality)


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
        pics = map(lambda path: self.album._add_size_qualifier(path, 'thumb'),
                   lightdir.get_all_images_paths())

        for pic in pics:
            self.add_file_dependency(pic)

        if lightdir.album_picture:
            md_dirpic_thumb = self.album._add_size_qualifier(\
                                           lightdir.album_picture, 'thumb')
            md_dirpic_thumb = os.path.join(lightdir.path, md_dirpic_thumb)
        else:
            md_dirpic_thumb = None
        self.dirpic = eyecandy.PictureMess(pics, md_dirpic_thumb,
                                           bg=self.album.webalbumpic_bg)

    def build(self):
        self.album.log(_("  DIRPIC %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        self.dirpic.write(self.path)


class WebalbumArchive(make.FileMakeObject):

    def __init__(self, lightdir):
        self.path = os.path.join(lightdir.path,
                                 lightdir.source_dir.name + '.zip')
        make.FileMakeObject.__init__(self, self.path)

        self.dir = lightdir
        self.album = self.dir.album

        self.dir.dirzip = self

        self.add_dependency(self.dir.source_dir)

        self.pics = map(lambda x: os.path.join(self.dir.source_dir.path, x),
                        self.dir.images_names)
        for pic in self.pics:
            self.add_file_dependency(pic)

    def build(self):
        self.album.log(_("  ZIP %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)

        archive = zipfile.ZipFile(self.path, mode='w')
        for pic in self.pics:
            inzip_filename = os.path.join(self.dir.source_dir.name,
                                          os.path.basename(pic))
            # zipfile dislikes unicode
            inzip_fn = inzip_filename.encode(locale.getpreferredencoding())
            archive.write(pic, inzip_fn)
        archive.close()


class WebalbumPage(make.FileMakeObject):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self._add_size_qualifier(base_name + '.html',
                                                 self.size_name)
        self.page_path = os.path.join(self.dir.path, page_filename)
        make.FileMakeObject.__init__(self, self.page_path)

    def _gen_other_img_link(self, img):
        if img:
            link_vals = {}
            link_vals['link'] = self._add_size_qualifier(img.name + '.html',
                                                         self.size_name)
            link_vals['thumb'] = self._add_size_qualifier(img.name\
                                                          + img.extension,
                                                          'thumb')

            thumb = os.path.join(self.dir.path,
                                 self._add_size_qualifier(img.filename, 'thumb'))
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = img.get_size(thumb)

            link_vals['thumb_name'] = self.dir.album._str_humanize(img.name)

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
                osize_info['link'] = self._add_size_qualifier(filename\
                                                              + '.html',
                                                              osize_name)
            osize_index_links.append(osize_info)

        return osize_index_links

    def _add_size_qualifier(self, path, size_name):
        return self.dir.album._add_size_qualifier(path, size_name)

    def _do_not_escape(self, value):
        return genshi.core.Markup(value)


class WebalbumBrowsePage(WebalbumPage):

    def __init__(self, dir, size_name, image_file):
        self.image = image_file
        WebalbumPage.__init__(self, dir, size_name, self.image.name)

        self.add_dependency(ImageOtherSize(self.dir,
                                           self.image,
                                           self.size_name))

        # Depends on source directory in case an image was deleted
        self.add_dependency(self.dir.source_dir)

        if self.dir.album.original:
            self.add_dependency(ImageOriginal(self.dir, self.image))

        self.page_template = self.dir.album.templates['browse.thtml']
        self.add_file_dependency(self.page_template.path)

    def prepare(self):
        for prevnext in [self.image.previous_image, self.image.next_image]:
            if prevnext:
                self.add_dependency(ImageOtherSize(self.dir, prevnext, 'thumb'))

    def build(self):
        self.dir.album.log(_("  XHTML %s") % os.path.basename(self.page_path),
                           'info')
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
        # strftime does not work with utf-8...
        time_format = _("on %d/%m/%Y at %H:%M").encode(locale.getpreferredencoding())
        time_str = img_date.strftime(time_format)
        tpl_values['image_date'] = time_str.decode(locale.getpreferredencoding())

        tpl_values['prev_link'] =\
            self._gen_other_img_link(self.image.previous_image)
        tpl_values['next_link'] =\
            self._gen_other_img_link(self.image.next_image)
        tpl_values['index_link'] = self._add_size_qualifier('index.html',
                                                            self.size_name)
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
            tpl_values['original_link'] = self.image.filename

        self.page_template.dump(tpl_values, self.page_path)


class WebalbumIndexPage(WebalbumPage):

    FILENAME_BASE_STRING = 'index'

    def __init__(self, dir, size_name, page_number=0):
        page_paginated_name = self._get_paginated_name(page_number)
        WebalbumPage.__init__(self, dir, size_name, page_paginated_name)

        self.page_number = page_number

        if self.dir.album.thumbs_per_page == 0:
            # No pagination
            self.images = dir.images
            self.dirnames = dir.source_dir.dirnames
            self.subdirs = dir.subdirs
        else:
            step = self.page_number * self.dir.album.thumbs_per_page
            self.images = dir.images[step:step+self.dir.album.thumbs_per_page]

            # subgal links only for first page
            if self.page_number == 0:
                self.dirnames = dir.source_dir.dirnames
                self.subdirs = dir.subdirs
            else:
                self.dirnames = []
                self.subdirs = []

        for image in self.images:
            thumb_dep = ImageOtherSize(self.dir, image, 'thumb')
            self.add_dependency(thumb_dep)
            image_dep = WebalbumBrowsePage(self.dir, size_name, image)
            self.add_dependency(image_dep)

        for subdir in self.subdirs:
            self.add_dependency(subdir)
            self.add_dependency(subdir.metadata)

        self.page_template = self.dir.album.templates['dirindex.thtml']
        self.add_file_dependency(self.page_template.path)

        self.add_dependency(dir.metadata)

    def _get_paginated_name(self, page_number=None):
        if page_number == None:
            page_number = self.page_number
        assert page_number != None

        if page_number < 1:
            return WebalbumIndexPage.FILENAME_BASE_STRING
        else:
            return '_'.join([WebalbumIndexPage.FILENAME_BASE_STRING,
                             str(page_number)])

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
            onum_index_links.append(onum_info)

        return onum_index_links

    def build(self):
        self.dir.album.log(_("  XHTML %s") % os.path.basename(self.page_path),
                           'info')
        self.dir.album.log("(%s)" % self.page_path)

        values = {}

        values['osize_index_links'] = self._get_osize_links(self._get_paginated_name())
        values['onum_index_links'] = self._get_onum_links()

        subgal_links = []
        for subdir in self.subdirs:
            dir_info = {'name': subdir.human_name,
                        'link': subdir.source_dir.name + '/'}
            dir_info.update(self.dir.metadata.get(subdir.source_dir.name))
            dir_info['album_picture'] = os.path.join(subdir.source_dir.name,
                                     self.dir.album.get_webalbumpic_filename())
            if 'album_description' in dir_info.keys():
                dir_info['album_description'] =\
                             self._do_not_escape(dir_info['album_description'])
            subgal_links.append(dir_info)
        values['subgal_links'] = subgal_links
        if self.dir.metadata:
            values.update(self.dir.metadata.get())
            if 'album_description' in values.keys():
                values['album_description'] =\
                             self._do_not_escape(values['album_description'])

        values['images'] = map(self._gen_other_img_link, self.images)

        values['rel_root'] = self.dir.source_dir.rel_root()
        values['rel_path'] = self.dir.source_dir.strip_root()
        values['title'] = self.dir.human_name

        if self.dir.album.dirzip and self.dir.dirzip:
            values['dirzip'] = os.path.basename(self.dir.dirzip.path)

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

        self.image_count = len(self.images_names)
        self.subgal_count = len(self.subdirs)

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

    def get_all_images_paths(self):
        all_images_paths = map(lambda fn: os.path.join(self.path, fn),
                               self.images_names)
        for subdir in self.subdirs:
            all_images_paths.extend(subdir.get_all_images_paths())
        return all_images_paths

    def build(self):
        # This one does not build anything.
        pass


class WebalbumDir(LightWebalbumDir):

    def __init__(self, dir, subdirs, album, album_dest_dir, clean_dest):
        LightWebalbumDir.__init__(self, dir, subdirs, album, album_dest_dir)

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

        self.images = map(lambda fn:\
                 sourcetree.ImageFile(os.path.join(self.source_dir.path, fn),
                                      album),
                                      self.images_names)

        self.how_many_pages = None
        if self.album.thumbs_per_page == 0\
        or self.image_count <= self.album.thumbs_per_page:
            # No pagination (requested or needed)
            self.how_many_pages = 1
        else:
            # Pagination requested and needed
            how_many_pages = self.image_count / self.album.thumbs_per_page
            if self.image_count % self.album.thumbs_per_page > 0:
                how_many_pages = how_many_pages + 1
            assert how_many_pages > 1
            self.how_many_pages = how_many_pages

        for size_name in self.album.browse_sizes.keys():
            for page_number in range(0, self.how_many_pages):
                self.add_dependency(WebalbumIndexPage(self, size_name,
                                                      page_number))

        self.add_dependency(WebalbumPicture(self))
        if self.album.dirzip and self.image_count > 1:
            self.add_dependency(WebalbumArchive(self))

    def prepare(self):
        self.images.sort(lambda x, y: x.compare_date_taken(y))

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

        for dest_file in os.listdir(self.path):
            dest_file = os.path.join(self.path, dest_file)
            if not isinstance(dest_file, unicode):
                # No clue why this happens, but it happens!
                dest_file = dest_file.decode(sys.getfilesystemencoding())
            if dest_file not in self.output_items and\
               dest_file not in self.source_dir.dirnames:
                text = ''
                if dest_file not in extra_files:
                    rmv_candidate = os.path.join(self.path, dest_file)
                    if self.clean_dest and not os.path.isdir(rmv_candidate):
                        os.unlink(rmv_candidate)
                        text = ""
                    else:
                        text = _("you should ")
                    self.album.log(_("  %sRM %s") % (text, dest_file), 'info')

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
        if webalbumdir.image_count > 0:
            self.add_dependency(webalbumdir)
            self.__add_item(webalbumdir)

    def __add_item(self, webalbumdir):
        url = os.path.join(self.pub_url, webalbumdir.source_dir.strip_root())

        desc_values = {}
        desc_values['album_pic_path'] = os.path.join(url,
                                          self.album.get_webalbumpic_filename())
        desc_values['subgal_count'] = webalbumdir.subgal_count
        desc_values['picture_count'] = webalbumdir.image_count
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

    def __init__(self, source_dir, thumb_size, browse_sizes,
                 quality=85, thumbs_per_page=0, dirzip=False):
        self.set_logging()

        self.source_dir = os.path.abspath(source_dir)

        self.thumb_size = thumb_size
        self.browse_sizes = dict(browse_sizes)
        self.quality = quality
        self.default_size_name = browse_sizes[0][0]

        self.templates = {}
        self.tpl_loader = None
        self.tpl_vars = {}
        self.original = False
        self.thumbs_per_page = thumbs_per_page
        self.dirzip = dirzip

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

    def set_original(self, original = False):
        self.original = original

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
            if level == 'error':
                print >> self.log_errpipe, msg
            else:
                print >> self.log_outpipe, msg

    def _is_ext_supported(self, filename):
        filename, extension = os.path.splitext(filename)
        return extension.lower() in ['.jpg']

    def _add_size_qualifier(self, path, size_name):
        filename, extension = os.path.splitext(path)
        if size_name == self.default_size_name and extension == '.html':
            # Do not append default size name to HTML page filename
            return path
        else:
            return "%s_%s%s" % (filename, size_name, extension)

    def _str_humanize(self, text):
        dash_replaced = text.replace('_', ' ')
        return string.capwords(dash_replaced)

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

            self.log(_("[Entering %%ALBUMROOT%%/%s]") % dir.strip_root(),
                     'info')
            self.log("(%s)" % dir.path)

            if dir_heap.has_key(root):
                subdirs = dir_heap[root]
                subdirs.sort(lambda x, y: cmp(x.source_dir.name,
                                              y.source_dir.name))
                del dir_heap[root] # No need to keep it there
            else:
                subdirs = []

            destgal = WebalbumDir(dir, subdirs, self, sane_dest_dir, clean_dest)
            light_destgal = LightWebalbumDir(dir, subdirs, self, sane_dest_dir)
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
