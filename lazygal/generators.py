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

import os, sys
import glob
import locale
import gc

import make
import sourcetree, tpl, feeds, newsize, metadata
import genpage, genmedia, genfile


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

        if self.should_be_flattened():
            light_webgal_dir.webgal_dir = self
        else:
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
                self.add_dependency(genpage.WebalbumIndexPage(self, size_name,
                                                              page_number))

        self.add_dependency(genmedia.WebalbumPicture(self))

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
                self.add_dependency(genpage.SharedFileTemplate(album,
                                                        shared_file,
                                                        shared_file_dest))
            else:
                self.add_dependency(genfile.SharedFileCopy(album,
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
        self.newsizers[genmedia.THUMB_SIZE_NAME] = newsize.get_newsizer(self.thumb_size_string)

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
        return genmedia.WebalbumPicture.BASEFILENAME + ext

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
            feed = genpage.WebalbumFeed(self, sane_dest_dir, pub_url)
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

            # Force some memory cleanups, this is usefull for big albums.
            del destgal
            gc.collect()

        if feed:
            feed.make()

        SharedFiles(self, sane_dest_dir).make()


# vim: ts=4 sw=4 expandtab
