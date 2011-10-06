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

import os, sys
import glob
import locale
import logging
import gc
import genshi

from config import LazygalConfig, DEFAULT_CONFIG, LazygalConfigDeprecated
from sourcetree import SOURCEDIR_CONFIGFILE

import make
import pathutils
import sourcetree, tpl, newsize, metadata
import genpage, genmedia, genfile


from lazygal import INSTALL_MODE, INSTALL_PREFIX
if INSTALL_MODE == 'source':
    DATAPATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
elif INSTALL_MODE == 'installed':
    DATAPATH = os.path.join(INSTALL_PREFIX, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print _('Could not find themes dir, check your installation!')
        sys.exit(1)


THEME_DIR = os.path.join(DATAPATH, 'themes')
USER_THEME_DIR = os.path.expanduser(os.path.join('~', '.lazygal', 'themes'))
THEME_SHARED_FILE_PREFIX = 'SHARED_'
DEST_SHARED_DIRECTORY_NAME = 'shared'


class SubgalSort(make.MakeTask):
    """
    This task sorts the medias within a gallery according to the chosen rule.
    """

    def __init__(self, webgal_dir):
        make.MakeTask.__init__(self)
        self.set_dep_only()
        self.webgal_dir = webgal_dir
        self.album = self.webgal_dir.album

    def build(self):
        logging.info(_("  SORTING pics and subdirs"))

        if self.album.subgal_sort_by[0] == 'exif':
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_latest_exif(y.source_dir)
        elif self.album.subgal_sort_by[0] == 'mtime':
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_mtime(y.source_dir)
        elif self.album.subgal_sort_by[0] == 'dirname'\
        or self.album.subgal_sort_by[0] == 'filename': # Backward compatibility
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_filename(y.source_dir)
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")\
                             % self.album.subgal_sort_by[0])
        self.webgal_dir.subgals.sort(subgal_sorter,
                                     reverse=self.album.subgal_sort_by[1])

        if self.album.pic_sort_by[0] == 'exif':
            sorter = lambda x, y: x.media.compare_to_sort(y.media)
        elif self.album.pic_sort_by[0] == 'mtime':
            sorter = lambda x, y: x.media.compare_mtime(y.media)
        elif self.album.pic_sort_by[0] == 'filename':
            sorter = lambda x, y: x.media.compare_filename(y.media)
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")\
                             % self.album.pic_sort_by[0])
        self.webgal_dir.medias.sort(sorter, reverse=self.album.pic_sort_by[1])

        # chain medias
        previous = None
        for media in self.webgal_dir.medias:
            if previous:
                previous.set_next(media)
                media.set_previous(previous)
            previous = media


class SubgalBreak(make.MakeTask):
    """
    This task breaks galleries into multiple pages.
    """

    def __init__(self, webgal_dir):
        make.MakeTask.__init__(self)
        self.webgal_dir = webgal_dir
        self.album = self.webgal_dir.album

        self.__last_page_number = -1

    def next_page_number(self):
        self.__last_page_number += 1
        return self.__last_page_number

    def how_many_pages(self):
        return self.__last_page_number + 1

    def build(self):
        logging.info(_("  BREAKING web gallery into multiple pages"))

        if self.album.thumbs_per_page == 0:
            self.__fill_no_pagination()
        else:
            if self.webgal_dir.flatten_below():
                self.__fill_loose_pagination()
            else:
                self.__fill_real_pagination()

    def __fill_no_pagination(self):
        galleries = []
        galleries.append((self.webgal_dir, self.webgal_dir.medias))
        if self.webgal_dir.flatten_below():
            subgals = []
            for dir in self.webgal_dir.get_all_subgals():
                galleries.append((dir, dir.medias))
        else:
            subgals = self.webgal_dir.subgals
        self.webgal_dir.add_index_page(subgals, galleries)

    def __fill_loose_pagination(self):
        """
        Loose pagination not breaking subgals (chosen if subgals are flattened).
        """
        subgals = [] # No subgal links as they are flattened

        galleries = []
        how_many_medias = 0
        subgals_it = iter([self.webgal_dir] + self.webgal_dir.get_all_subgals())
        try:
            while True:
                subgal = subgals_it.next()
                how_many_medias += subgal.source_dir.get_media_count()
                galleries.append((subgal, subgal.medias))
                if how_many_medias > self.webgal_dir.album.thumbs_per_page:
                    self.webgal_dir.add_index_page(subgals, galleries)
                    galleries = []
                    how_many_medias = 0
        except StopIteration:
            if len(galleries) > 0:
                self.webgal_dir.add_index_page(subgals, galleries)

    def __fill_real_pagination(self):
        how_many_pages = len(self.webgal_dir.medias)\
                          // self.webgal_dir.album.thumbs_per_page + 1
        for page_number in range(0, how_many_pages):
            step = page_number * self.webgal_dir.album.thumbs_per_page
            end_index = step + self.webgal_dir.album.thumbs_per_page
            shown_medias = self.webgal_dir.medias[step:end_index]
            galleries = [(self.webgal_dir, shown_medias)]

            # subgal links only for first page
            if page_number == 0:
                subgals = self.webgal_dir.subgals
            else:
                subgals = []

            self.webgal_dir.add_index_page(subgals, galleries)


class WebalbumMediaTask(make.GroupTask):

    def __init__(self, webgal, media, album):
        super(WebalbumMediaTask, self).__init__()

        self.album = album
        self.webgal = webgal
        self.media = media

        self.previous = None
        self.next = None

        self.original = None
        self.resized = {}
        self.browse_pages = {}

        for size_name in self.album.browse_sizes:
            if self.album.newsizers[size_name] == 'original':
                self.resized[size_name] = self.get_original()
            else:
                self.resized[size_name] = self.get_resized(size_name)
            self.add_dependency(self.resized[size_name])

            if self.album.original and not self.album.orig_base:
                self.add_dependency(self.get_original())

            self.browse_pages[size_name] = self.get_browse_page(size_name)

    def set_next(self, media):
        self.next = media
        if media:
            for bpage in self.browse_pages.values():
                if media.thumb: bpage.add_dependency(media.thumb)

    def set_previous(self, media):
        self.previous = media
        if media:
            for bpage in self.browse_pages.values():
                if media.thumb: bpage.add_dependency(media.thumb)

    def get_original_or_symlink(self):
        if not self.album.orig_symlink:
            return genfile.MediaOriginal(self.webgal, self.media)
        else:
            return genfile.SymlinkMediaOriginal(self.webgal, self.media)

    def get_original(self):
        if not self.original:
            self.original = self.get_original_or_symlink()
        return self.original


class WebalbumImageTask(WebalbumMediaTask):
    """
    This task builds all items related to one picture.
    """

    def __init__(self, webgal, image, album):
        super(WebalbumImageTask, self).__init__(webgal, image, album)

        self.thumb = genmedia.ImageOtherSize(self.webgal, self.media,
                                             genmedia.THUMB_SIZE_NAME)
        self.add_dependency(self.thumb)

    def get_resized(self, size_name):
        if self.album.newsizers[size_name] == 'original':
            return self.get_original_or_symlink()
        else:
            return genmedia.ImageOtherSize(self.webgal, self.media, size_name)

    def get_browse_page(self, size_name):
        return genpage.WebalbumImagePage(self.webgal, size_name, self)


class WebalbumVideoTask(WebalbumMediaTask):
    """
    This task builds all items related to one video.
    """

    def __init__(self, webgal, video, album):
        self.webvideo = None

        super(WebalbumVideoTask, self).__init__(webgal, video, album)

        self.thumb = genmedia.VideoThumb(self.webgal, self.media,
                                         genmedia.THUMB_SIZE_NAME)

        self.add_dependency(self.webvideo)

    def get_browse_page(self, size_name):
        return genpage.WebalbumVideoPage(self.webgal, size_name, self)

    def get_resized(self, size_name):
        if not self.webvideo:
            self.webvideo = genmedia.WebVideo(self.webgal, self.media)
        return self.webvideo


class WebalbumDir(make.FileMakeObject):
    """
    This is a built web gallery with its files, thumbs and reduced pics.
    """

    def __init__(self, dir, subgals, album, album_dest_dir):
        self.source_dir = dir
        self.path = os.path.join(album_dest_dir, self.source_dir.strip_root())
        if self.path.endswith('/'): self.path = os.path.dirname(self.path)

        super(WebalbumDir, self).__init__(self.path)

        self.add_dependency(self.source_dir)
        self.subgals = subgals
        self.album = album
        self.feed = None

        self.flattening_dir = None

        # Create the directory if it does not exist
        if not os.path.isdir(self.path):
            logging.info(_("  MKDIR %%WEBALBUMROOT%%/%s")\
                         % self.source_dir.strip_root())
            logging.debug("(%s)" % self.path)
            os.makedirs(self.path, mode = 0755)
            # Directory did not exist, mark it as so
            self.stamp_delete()

        self.medias = []
        self.sort_task = SubgalSort(self)
        self.sort_task.add_dependency(self.source_dir)
        for media in self.source_dir.medias:
            self.sort_task.add_dependency(media)

            if media.type == 'image':
                media_task = WebalbumImageTask(self, media, self.album)
            elif media.type == 'video':
                media_task = WebalbumVideoTask(self, media, self.album)
            else:
                raise NotImplementedError("Unknown media type '%s'"\
                                          % media.type)
            self.medias.append(media_task)
            self.add_dependency(media_task)

        self.dirzip = None

        self.index_pages = []

        if not self.should_be_flattened():
            self.break_task = SubgalBreak(self)

            if self.album.thumbs_per_page > 0:
                # FIXME: If pagination is 'on', galleries need to be sorted
                # before being broken on multiple pages, and thus this slows
                # down a lot the checking of a directory's need to be built.
                self.break_task.add_dependency(self.sort_task)

            # This task is special because it populates dependencies. This is
            # why it needs to be built before a build check.
            self.break_task.make()

            self.webgal_pic = genmedia.WebalbumPicture(self)
            self.add_dependency(self.webgal_pic)
        else:
            self.break_task = None

    def add_index_page(self, subgals, galleries):
        page_number = self.break_task.next_page_number()
        pages = []
        for size_name in self.album.browse_sizes:
            page = genpage.WebalbumIndexPage(self, size_name, page_number,
                                             subgals, galleries)
            self.add_dependency(page)
            pages.append(page)
        self.index_pages.append(pages)

    def register_output(self, output):
        # We only care about output in the current directory
        if os.path.dirname(output) == self.path:
            super(WebalbumDir, self).register_output(output)

    def register_feed(self, feed):
        self.feed = feed

    def get_subgal_count(self):
        if self.flatten_below():
            return 0
        else:
            len(self.source_dir.subdirs)

    def get_all_subgals(self):
        all_subgals = list(self.subgals) # We want a copy here.
        for subgal in self.subgals:
            all_subgals.extend(subgal.get_all_subgals())
        return all_subgals

    def get_all_medias_tasks(self):
        all_medias = list(self.medias) # We want a copy here.
        for subgal in self.subgals:
            all_medias.extend(subgal.get_all_medias_tasks())
        return all_medias

    def should_be_flattened(self, path=None):
        if path is None: path = self.source_dir.path
        return self.album.dir_flattening_depth is not False\
        and self.source_dir.get_album_level(path) > self.album.dir_flattening_depth

    def flatten_below(self):
        if self.album.dir_flattening_depth is False:
            return False
        elif len(self.source_dir.subdirs) > 0:
            # As all subdirs are at the same level, if one should be flattened,
            # all should.
            return self.subgals[0].should_be_flattened()
        else:
            return False

    def rel_path_to_src(self, target_srcdir_path):
        '''
        Returns the relative path to go from this directory to
        target_srcdir_path.
        '''
        return self.source_dir.rel_path(self.source_dir.path,
                                        target_srcdir_path)

    def rel_path(self, path):
        '''
        Returns the relative path to go from this directory to the path supplied
        as argument.
        '''
        return pathutils.relative_path(self.path, path)

    def flattening_srcpath(self, srcdir_path):
        '''
        Returns the source path in which srcdir_path should flattened, that is
        the path of the gallery index that will point to srcdir_path's pictures.
        '''
        if self.should_be_flattened(srcdir_path):
            cur_path = srcdir_path
            while self.should_be_flattened(cur_path):
                cur_path, dummy = os.path.split(cur_path)
            return cur_path
        else:
            return ''

    def list_foreign_files(self):
        foreign_files = []

        # Check dest for junk files
        extra_files = []
        if self.source_dir.is_album_root():
            extra_files.append(os.path.join(self.path,
                                            DEST_SHARED_DIRECTORY_NAME))

        dirnames = [d.name for d in self.source_dir.subdirs]
        expected_dirs = map(lambda dn: os.path.join(self.path, dn), dirnames)
        for dest_file in os.listdir(self.path):
            dest_file = os.path.join(self.path, dest_file)
            if not isinstance(dest_file, unicode):
                # FIXME: No clue why this happens, but it happens!
                dest_file = dest_file.decode(sys.getfilesystemencoding())
            if dest_file not in self.output_items and\
               dest_file not in expected_dirs and\
               dest_file not in extra_files:
                foreign_files.append(dest_file)

        return foreign_files

    def build(self):
        for dest_file in self.list_foreign_files():
            self.album.cleanup(dest_file)

    def make(self, force=False):
        needed_build = self.needs_build()

        super(WebalbumDir, self).make(force or needed_build)

        # Although we should have modified the directory contents and thus its
        # mtime, it is possible that the directory mtime has not been updated
        # if we regenerated without adding/removing pictures (to take into
        # account a rotation for example). This is why we force directory mtime
        # update here if something has been built.
        if needed_build: os.utime(self.path, None)


class SharedFiles(make.FileMakeObject):

    def __init__(self, album, dest_dir):
        self.path = os.path.join(dest_dir, DEST_SHARED_DIRECTORY_NAME)
        self.album = album

        # Create the shared files directory if it does not exist
        if not os.path.isdir(self.path):
            logging.info(_("MKDIR %SHAREDDIR%"))
            logging.debug("(%s)" % self.path)
            os.makedirs(self.path, mode = 0755)

        super(SharedFiles, self).__init__(self.path)

        self.expected_shared_files = []
        for shared_file in glob.glob(\
          os.path.join(self.album.tpl_dir, THEME_SHARED_FILE_PREFIX + '*')):
            shared_file_name = os.path.basename(shared_file).\
                                     replace(THEME_SHARED_FILE_PREFIX, '')
            shared_file_dest = os.path.join(self.path,
                                            shared_file_name)

            if self.album.tpl_loader.is_known_template_type(shared_file):
                sf = genpage.SharedFileTemplate(album, shared_file,
                                                shared_file_dest)
                self.expected_shared_files.append(sf.path)
            else:
                sf = genfile.SharedFileCopy(shared_file, shared_file_dest)
                self.expected_shared_files.append(shared_file_dest)

            self.add_dependency(sf)

    def build(self):
        # Cleanup themes files which are not in themes anymore.
        for present_file in os.listdir(self.path):
            file_path = os.path.join(self.path, present_file)
            if file_path not in self.expected_shared_files:
                self.album.cleanup(file_path)


class Album:

    def __init__(self, source_dir, config=None):
        self.source_dir = os.path.abspath(source_dir)
        self.source_dir = self.source_dir.decode(sys.getfilesystemencoding())

        self.config = LazygalConfig()
        self.config.load(DEFAULT_CONFIG) # Config defaults
        sourcedir_configfile = os.path.join(source_dir, SOURCEDIR_CONFIGFILE)
        if os.path.isfile(sourcedir_configfile): # Album root config
            try:
                self.config.read(sourcedir_configfile)
            except LazygalConfigDeprecated:
                logging.error(_("'%s' uses a deprecated syntax: please refer to lazygal.conf(5) manual page.") % sourcedir_configfile)
                sys.exit(1)
        if config is not None: # Supplied config
            self.config.load(config)

        if self.config.getboolean('runtime', 'quiet'):
            logging.getLogger().setLevel(logging.ERROR)
        if self.config.getboolean('runtime', 'debug'):
            logging.getLogger().setLevel(logging.DEBUG)

        self.clean_dest = self.config.getboolean('global', 'clean-destination')

        self.browse_sizes = []
        self.newsizers = {}
        self.__parse_browse_sizes(self.config.get('webgal', 'image-size'))
        self.__parse_size(genmedia.THUMB_SIZE_NAME,
                          self.config.get('webgal', 'thumbnail-size'))
        self.default_size_name = self.browse_sizes[0]

        self.tpl_loader = None
        self.tpl_vars = {}

        self.set_theme(self.config.get('global', 'theme'),
                       self.config.get('webgal', 'default-style'))

        self.set_original(self.config.getboolean('webgal', 'original'),
                          self.config.getstr('webgal', 'original-baseurl'),
                          self.config.getboolean('webgal', 'original-symlink'))

        self.thumbs_per_page = self.config.getint('webgal', 'thumbs-per-page')
        self.dir_flattening_depth = self.config.getint('global', 'dir-flattening-depth')
        self.dirzip = self.config.getboolean('webgal', 'dirzip')

        self.quality = self.config.getint('webgal', 'jpeg-quality')
        self.save_options = {}
        if self.config.getboolean('webgal', 'jpeg-optimize'):
            self.save_options['optimize'] = True
        if self.config.getboolean('webgal', 'jpeg-progressive'):
            self.save_options['progressive'] = True

        self.pic_sort_by = self.__parse_sort(self.config.get('webgal', 'sort-medias'))
        self.subgal_sort_by = self.__parse_sort(self.config.get('webgal', 'sort-subgals'))

        self.set_webalbumpic(self.config.get('webgal', 'webalbumpic-bg'))

    def __parse_browse_sizes(self, sizes_string):
        for single_def in sizes_string.split(','):
            name, string_size = single_def.split('=')
            if name == '':
                raise ValueError(_("Sizes is a comma-separated list of size names and specs:\n\t e.g. \"small=640x480,medium=1024x768\"."))
            if name == genmedia.THUMB_SIZE_NAME:
                raise ValueError(_("Size name '%s' is reserved for internal processing.") % genmedia.THUMB_SIZE_NAME)
            self.__parse_size(name, string_size)
            self.browse_sizes.append(name)

    def __parse_size(self, size_name, size_string):
        if size_string == '0x0':
            self.newsizers[size_name] = 'original'
        else:
            try:
                self.newsizers[size_name] = newsize.get_newsizer(size_string)
            except newsize.NewsizeStringParseError:
                raise ValueError(_("'%s' for size '%s' does not describe a known size syntax.") % (size_string, size_name, ))

    def __parse_sort(self, sort_string):
        try:
            sort_method, reverse = sort_string.split(':')
        except ValueError:
            sort_method = sort_string
            reverse = False
        if reverse == 'reverse':
            return sort_method, True
        else:
            return sort_method, False

    def set_theme(self, theme=tpl.DEFAULT_TEMPLATE, default_style=None):
        self.theme = theme

        # First try user directory
        self.tpl_dir = os.path.join(USER_THEME_DIR, self.theme)
        if not os.path.exists(self.tpl_dir):
            # Fallback to system themes
            self.tpl_dir = os.path.join(THEME_DIR, self.theme)
            if not os.path.exists(self.tpl_dir):
                raise ValueError(_('Theme %s not found') % self.theme)

        self.tpl_loader = tpl.TplFactory(os.path.join(THEME_DIR,
                                                      tpl.DEFAULT_TEMPLATE),
                                         self.tpl_dir)

        styles = self.get_avail_styles(self.theme, default_style)
        self.tpl_vars.update({'styles' : styles})
        self.set_tpl_vars()

        # Load styles templates
        for style in styles:
            style_filename = style['filename']
            try:
                self.tpl_loader.load(style_filename)
            except ValueError:
                # Not a known emplate ext, ignore
                pass

    def set_tpl_vars(self):
        # Load tpl vars from config
        tpl_vars = None
        if self.config.has_section('template-vars'):
            tpl_vars = {}
            for option in self.config.options('template-vars'):
                value = self.config.get('template-vars', option)
                value = value.decode(locale.getpreferredencoding())
                tpl_vars[option] = genshi.core.Markup(value)

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
                style['rel'] = 'stylesheet'
            else:
                style['rel'] = 'alternate stylesheet'
            styles.append(style)
        return styles

    def set_original(self, original=False, orig_base=None, orig_symlink=False):
        self.original = original or orig_symlink
        self.orig_symlink = orig_symlink
        if self.original and orig_base and not orig_symlink:
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

    def _add_size_qualifier(self, path, size_name, force_extension=None):
        filename, extension = os.path.splitext(path)
        if force_extension is not None:
            extension = force_extension

        if size_name == self.default_size_name and extension == '.html':
            # Do not append default size name to HTML page filename
            return path
        elif size_name in self.browse_sizes\
        and self.newsizers[size_name] == 'original'\
        and extension != '.html':
            # Do not append size_name to unresized images.
            return path
        else:
            return "%s_%s%s" % (filename, size_name, extension)

    def _str_humanize(self, text):
        dash_replaced = text.replace('_', ' ')
        return dash_replaced

    def is_in_sourcetree(self, path):
        return pathutils.is_subdir_of(self.source_dir, path)

    def cleanup(self, file_path):
        text = ''
        if self.clean_dest and not os.path.isdir(file_path):
            os.unlink(file_path)
            text = ''
        else:
            text = _('you should ')
        logging.info(_('  %sRM %s') % (text, file_path))

    def walk(self, top, walked=None):
        '''
        This is a wrapper around os.walk() from the standard library:
        - browsing with topdown=False
        - following symbolic links on directories
        - whith barriers in place against walking twice the same directory,
          which may happen when two directory trees have symbolic links to
          each other's contents.
        '''
        if walked is None: walked = []

        for root, dirs, files in os.walk(top, topdown=False):
            walked.append(os.path.realpath(root))

            # Follow symlinks if they have not been walked yet
            for d in dirs:
                d_path = os.path.join(root, d)
                if os.path.islink(d_path):
                    if os.path.realpath(d_path) not in walked:
                        for x in self.walk(d_path, walked):
                            yield x
                    else:
                        logging.warning(_("Not following symlink '%s' because directory has already been processed.") % d_path)

            yield root, dirs, files

    def generate_default_metadata(self):
        '''
        Generate default metada files if no exists.
        '''
        logging.debug(_("Generating metadata in %s") % self.source_dir)

        for root, dirnames, filenames in self.walk(self.source_dir):
            filenames.sort() # This is required for the ignored files
                             # checks to be reliable.
            source_dir = sourcetree.Directory(root, [], filenames, self)
            logging.info(_("[Entering %%ALBUMROOT%%/%s]") % source_dir.strip_root())
            logging.debug("(%s)" % source_dir.path)

            metadata.DefaultMetadata(source_dir, self).make()

    def generate(self, dest_dir=None):
        if dest_dir is None:
            dest_dir = self.config.getstr('global', 'destdir')
        else:
            dest_dir = dest_dir.decode(sys.getfilesystemencoding())
        sane_dest_dir = os.path.abspath(os.path.expanduser(dest_dir))

        pub_url = self.config.getstr('global', 'puburl')
        check_all_dirs = self.config.getboolean('runtime', 'check-all-dirs')

        if self.is_in_sourcetree(sane_dest_dir):
            raise ValueError(_("Fatal error, web gallery directory is within source tree."))

        logging.debug(_("Generating to %s") % sane_dest_dir)

        if pub_url:
            feed = genpage.WebalbumFeed(self, sane_dest_dir, pub_url)
        else:
            feed = None

        dir_heap = {}
        for root, dirnames, filenames in self.walk(self.source_dir):

            if root in dir_heap:
                subdirs, subgals = dir_heap[root]
                del dir_heap[root] # No need to keep it there
            else:
                subdirs = []
                subgals = []

            source_dir = sourcetree.Directory(root, subdirs, filenames, self)

            if source_dir.should_be_skipped():
                logging.debug(_("(%s) has been skipped") % source_dir.path)
                continue
            if source_dir.path == os.path.join(sane_dest_dir,
                                               DEST_SHARED_DIRECTORY_NAME):
                logging.error(_("(%s) has been skipped because its name collides with the shared material directory name") % source_dir.path)
                continue

            logging.info(_("[Entering %%ALBUMROOT%%/%s]") % source_dir.strip_root())
            logging.debug("(%s)" % source_dir.path)

            if source_dir.get_all_medias_count() < 1:
                logging.debug(_("(%s) and childs have no known medias, skipped")
                              % source_dir.path)
                continue

            destgal = WebalbumDir(source_dir, subgals, self, sane_dest_dir)

            if not source_dir.is_album_root():
                container_dirname = os.path.dirname(root)
                if container_dirname not in dir_heap:
                    dir_heap[container_dirname] = ([], [])
                container_subdirs, container_subgals = dir_heap[container_dirname]
                container_subdirs.append(source_dir)
                container_subgals.append(destgal)

            if feed and source_dir.is_album_root():
                feed.set_title(source_dir.human_name)
                md = destgal.source_dir.metadata.get()
                if 'album_description' in md.keys():
                    feed.set_description(md['album_description'])
                destgal.register_output(feed.path)

            if feed:
                feed.push_dir(destgal)
                destgal.register_feed(feed)

            if check_all_dirs:
                destgal.make()
            elif destgal.needs_build():
                destgal.make(force=True) # avoid another needs_build() call in make()
            else:
                logging.debug(_("  SKIPPED because of mtime, touch source or use --check-all-dirs to override."))

            # Force some memory cleanups, this is usefull for big albums.
            del destgal
            gc.collect()

            logging.info(_("[Leaving  %%ALBUMROOT%%/%s]") % source_dir.strip_root())

        if feed:
            feed.make()

        # Force to check for unexpected files
        SharedFiles(self, sane_dest_dir).make(True)


# vim: ts=4 sw=4 expandtab
