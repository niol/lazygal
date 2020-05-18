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
import locale
import logging
import gc
import genshi
import sys
import re
import fnmatch
import shutil

from .config import LazygalConfig
from .config import USER_CONFIG_PATH, LazygalConfigDeprecated
from .sourcetree import SOURCEDIR_CONFIGFILE
from .pygexiv2 import GExiv2

from . import make
from . import pathutils
from . import sourcetree
from . import pindex
from . import tpl
from . import newsize
from . import metadata
from . import genpage
from . import genmedia
from . import genfile
from . import mediautils
from . import theme


from lazygal import INSTALL_MODE, INSTALL_PREFIX
if INSTALL_MODE == 'source':
    DATAPATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
elif INSTALL_MODE == 'installed':
    DATAPATH = os.path.join(INSTALL_PREFIX, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print(_('Could not find themes dir, check your installation!'))
        sys.exit(1)


DEST_SHARED_DIRECTORY_NAME = 'shared'


class SubgalSort(make.MakeTask):
    """
    This task sorts the medias within a gallery according to the chosen rule.
    """

    def __init__(self, webgal_dir):
        make.MakeTask.__init__(self)
        self.set_dep_only()
        self.webgal_dir = webgal_dir

    def build(self):
        logging.info(_("  SORTING pics and subdirs"))

        order = self.webgal_dir.subgal_sort_by['order']
        if order == 'exif':
            subgal_sortkey = lambda x: x.source_dir.latest_media_stamp()
        elif order == 'mtime':
            subgal_sortkey = lambda x: x.source_dir.get_mtime()
        elif order == 'numeric':
            subgal_sortkey = lambda x: x.source_dir.name_numeric()
        elif order == 'dirname' or order == 'filename':  # Backward compat
            subgal_sortkey = lambda x: x.source_dir.filename
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")
                             % self.webgal_dir.subgal_sort_by[0])
        self.webgal_dir.subgals.sort(key=subgal_sortkey,
            reverse=self.webgal_dir.subgal_sort_by['reverse'])

        order = self.webgal_dir.pic_sort_by['order']
        if order == 'exif':
            sortkey = lambda x: x.media.sortkey()
        elif order == 'mtime':
            sortkey = lambda x: x.media.get_mtime()
        elif order == 'numeric':
            sortkey = lambda x: x.media.name_numeric()
        elif order == 'filename':
            sortkey = lambda x: x.media.filename
        else:
            raise ValueError(_("Unknown sorting criterion '%s'")
                             % self.webgal_dir.pic_sort_by[0])
        self.webgal_dir.medias.sort(key=sortkey,
            reverse=self.webgal_dir.pic_sort_by['reverse'])

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

        self.__last_page_number = -1

    def next_page_number(self):
        self.__last_page_number += 1
        return self.__last_page_number

    def how_many_pages(self):
        return self.__last_page_number + 1

    def build(self):
        logging.info(_("  BREAKING web gallery into multiple pages"))

        if self.webgal_dir.thumbs_per_page == 0:
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
                dir.call_populate_deps()
                galleries.append((dir, dir.medias))
        else:
            subgals = self.webgal_dir.subgals
        self.webgal_dir.add_index_page(subgals, galleries)

    def __fill_loose_pagination(self):
        """
        Loose pagination not breaking subgals (chosen if subgals are flattened).
        """
        subgals = []  # No subgal links as they are flattened

        galleries = []
        how_many_medias = 0
        subgals_it = iter([self.webgal_dir] + self.webgal_dir.get_all_subgals())
        for subgal in subgals_it:
            how_many_medias += subgal.pindex.get_media_count()
            galleries.append((subgal, subgal.medias))
            if how_many_medias > self.webgal_dir.thumbs_per_page:
                self.webgal_dir.add_index_page(subgals, galleries)
                galleries = []
                how_many_medias = 0

        if galleries:
            self.webgal_dir.add_index_page(subgals, galleries)

    def __fill_real_pagination(self):
        medias_amount = len(self.webgal_dir.medias)
        how_many_pages = medias_amount // self.webgal_dir.thumbs_per_page
        if medias_amount == 0\
                or medias_amount % self.webgal_dir.thumbs_per_page > 0:
            how_many_pages = how_many_pages + 1

        for page_number in range(0, how_many_pages):
            step = page_number * self.webgal_dir.thumbs_per_page
            end_index = step + self.webgal_dir.thumbs_per_page
            shown_medias = self.webgal_dir.medias[step:end_index]
            galleries = [(self.webgal_dir, shown_medias)]

            # subgal links only for first page
            if page_number == 0:
                subgals = self.webgal_dir.subgals
            else:
                subgals = []

            self.webgal_dir.add_index_page(subgals, galleries)


class WebalbumMediaTask(make.GroupTask):

    def __init__(self, webgal, media):
        super(WebalbumMediaTask, self).__init__()

        self.webgal = webgal
        self.media = media

        self.previous = None
        self.next = None

        self.original = None
        self.resized = {}
        self.browse_pages = {}

        for size_name in self.webgal.browse_sizes:
            self.resized[size_name] = self.get_resized(size_name)
            self.add_dependency(self.resized[size_name])

            if self.webgal.original and not self.webgal.orig_base:
                self.add_dependency(self.get_original())

            if self.webgal.album.theme.kind == 'static':
                self.browse_pages[size_name] = self.get_browse_page(size_name)
                if self.webgal.album.force_gen_pages:
                    self.browse_pages[size_name].stamp_delete()

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
        if not self.webgal.orig_symlink:
            return genfile.CopyMediaOriginal(self.webgal, self.media)
        else:
            return genfile.SymlinkMediaOriginal(self.webgal, self.media)

    def get_original(self):
        if not self.original:
            self.original = self.get_original_or_symlink()
        return self.original

    def get_browse_page(self, size_name):
        return genpage.WebalbumBrowsePage(self.webgal, size_name, self)

    def make(self):
        super(WebalbumMediaTask, self).make()
        self.webgal.media_done()


class WebalbumImageTask(WebalbumMediaTask):
    """
    This task builds all items related to one picture.
    """

    def __init__(self, webgal, image):
        super(WebalbumImageTask, self).__init__(webgal, image)

        self.thumb = genmedia.ImageOtherSize(self.webgal, self.media,
                                             genmedia.THUMB_SIZE_NAME)
        self.add_dependency(self.thumb)

    def get_resized(self, size_name):
        if self.webgal.newsizers[size_name] == 'original':
            return self.get_original_or_symlink()
        else:
            sized = genmedia.ImageOtherSize(self.webgal, self.media, size_name)
            self.media.get_size() # probe size to check if media is broken
            if not self.media.broken\
            and sized.get_size() == sized.source_media.get_size():
                # Do not process if size is the same
                return self.get_original()
            else:
                return sized


class WebalbumVideoTask(WebalbumMediaTask):
    """
    This task builds all items related to one video.
    """

    def __init__(self, webgal, video):
        self.webvideo = None

        super(WebalbumVideoTask, self).__init__(webgal, video)

        self.thumb = genmedia.VideoThumb(self.webgal, self.media,
                                         genmedia.THUMB_SIZE_NAME)

        self.add_dependency(self.webvideo)

    def get_resized(self, size_name):
        if not self.webvideo:
            if self.webgal.newsizers[genmedia.VIDEO_SIZE_NAME] == 'original'\
            and self.media.extension in ('.webm', '.mp4'):
                # do not transcode webm videos
                self.webvideo = self.get_original_or_symlink()
            else:
                self.webvideo = genmedia.WebVideo(self.webgal, self.media,
                                                  genmedia.VIDEO_SIZE_NAME,
                                                  self.webgal.progress)

        return self.webvideo


class WebalbumDir(make.GroupTask):
    """
    This is a built web gallery with its files, thumbs and reduced pics.
    """

    def __init__(self, dir, subgals, album, album_dest_dir, progress=None):
        self.source_dir = dir
        self.path = os.path.join(album_dest_dir, self.source_dir.strip_root())
        if self.path.endswith(os.sep): self.path = os.path.dirname(self.path)

        super(WebalbumDir, self).__init__()

        self.progress = progress

        self.add_dependency(self.source_dir)
        self.subgals = subgals
        for srcdir in self.source_dir.subdirs:
            self.add_dependency(srcdir)
        self.album = album
        self.feed = None

        self.flattening_dir = None

        self.config = LazygalConfig()
        self.config.load(self.album.config)
        self.__configure()

        self.pindex = pindex.PersistentIndex(self)
        self.add_dependency(self.pindex)

    def populate_deps(self):
        super(WebalbumDir, self).populate_deps()

        for s in self.subgals:
            if not s.has_media_below():
                self.subgals.remove(s)

        self.medias = []
        self.sort_task = SubgalSort(self)
        self.sort_task.add_dependency(self.source_dir)
        for media in self.source_dir.medias:
            if self.tagfilters and media.info() is not None:
                # tag-filtering is requested
                res = True
                for tagf in self.tagfilters:
                    # concatenate the list of tags as a string of words,
                    # space-separated.  to ensure that we match the full
                    # keyword and not only a subpart of it, we also surround
                    # the matching pattern with spaces

                    # we look for tag words, partial matches are not wanted
                    regex = re.compile(r"\b" + tagf + r"\b")

                    kwlist = ' '.join(media.info().get_keywords())
                    if re.search(regex, kwlist) is None:
                        res = False
                        break
                if res is False:
                    self.media_done()
                    continue

            self.sort_task.add_dependency(media)

            media_task = None
            if media.type == 'image':
                media_task = WebalbumImageTask(self, media)
            elif media.type == 'video':
                if not self.config.get('webgal', 'novideo'):
                    media_task = WebalbumVideoTask(self, media)
                else:
                    logging.warning(_('Video support disabled: ignoring %s.')
                                    % media.filename)
            else:
                raise NotImplementedError("Unknown media type '%s'"
                                          % media.type)

            if media_task:
                self.medias.append(media_task)
                self.add_dependency(media_task)

        # Create the directory if it does not exist
        if not os.path.isdir(self.path) and self.has_media_below():
            logging.info(_("  MKDIR %%WEBALBUMROOT%%/%s"),
                         self.source_dir.strip_root())
            logging.debug("(%s)", self.path)
            os.makedirs(self.path)

        if self.pindex.dirzip():
            self.dirzip = genfile.WebalbumArchive(self)
            self.add_dependency(self.dirzip)
            self.pindex.add_dependency(self.dirzip)

        self.index_pages = []

        if self.has_media_below() and not self.should_be_flattened():
            self.break_task = SubgalBreak(self)

            if self.thumbs_per_page > 0:
                self.break_task.add_dependency(self.sort_task)

            # This task is special because it populates dependencies. This is
            # why it needs to be built before a build check.
            self.break_task.make()

            self.webgal_pic = genmedia.WebalbumPicture(self)
            self.add_dependency(self.webgal_pic)
        else:
            self.break_task = None

    def __parse_browse_sizes(self, sizes_defs):
        fixed_sizes_defs = sizes_defs
        if isinstance(sizes_defs, dict):
            # simpler defs
            fixed_sizes_defs = []
            first = True
            for name, defs in sizes_defs.items():
                fixed_sizes_defs.append({
                    "name" : name,
                    "defs" : defs,
                    "default" : first,
                })
                first = False

        for size_defs in fixed_sizes_defs:
            name = size_defs['name']
            if name == genmedia.THUMB_SIZE_NAME:
                raise ValueError(_("Size name '%s' is reserved for internal processing.") % genmedia.THUMB_SIZE_NAME)
            self.__parse_size(name, size_defs['defs'])
            self.browse_sizes.append(name)
            if 'default' in size_defs and size_defs['default']:
                self.default_size_name = name

    def __parse_size(self, size_name, size_string):
        if size_string == '0x0':
            self.newsizers[size_name] = 'original'
        elif size_string in self.newsizers:
            pass # size reference, do nothing
        else:
            try:
                self.newsizers[size_name] = newsize.get_newsizer(size_string)
            except newsize.NewsizeStringParseError:
                raise ValueError(_("'%s' for size '%s' does not describe a known size syntax.") % (size_string, size_name, ))

    def __load_tpl_vars(self):
        # Load tpl vars from config
        tpl_vars = {}
        if self.config.has_section('template-vars'):
            tpl_vars = {}
            for option in self.config.options('template-vars'):
                value = self.config.get('template-vars', option)
                tpl_vars[option] = genshi.core.Markup(value)

        return tpl_vars

    def __configure(self):
        config_dirs = self.source_dir.parent_paths()[:-1]  # strip root dir
        config_dirs.reverse()  # from root to deepest
        config_files = list(map(lambda d: os.path.join(d, SOURCEDIR_CONFIGFILE),
                                config_dirs))
        logging.debug(_("  Trying loading gallery configs: %s"),
                      ', '.join(map(self.source_dir.strip_root,
                                    config_files)))
        for c in config_files:
            self.config.load_any(c)

        self.browse_sizes = []
        self.newsizers = {}
        self.__parse_browse_sizes(self.config.get('webgal', 'image-size'))
        self.__parse_size(genmedia.THUMB_SIZE_NAME,
                          self.config.get('webgal', 'thumbnail-size'))
        self.__parse_size(genmedia.VIDEO_SIZE_NAME,
                          self.config.get('webgal', 'video-size'))

        self.tpl_vars = self.__load_tpl_vars()
        styles = self.album.theme.get_avail_styles(
            self.config.get('webgal', 'default-style'))
        self.tpl_vars.update({'styles': styles})

        self.set_original(self.config.get('webgal', 'original'),
                          self.config.get('webgal', 'original-baseurl'),
                          self.config.get('webgal', 'original-symlink'))

        self.thumbs_per_page = self.config.get('webgal', 'thumbs-per-page')

        self.quality = self.config.get('webgal', 'jpeg-quality')
        self.save_options = {}
        if self.config.get('webgal', 'jpeg-optimize'):
            self.save_options['optimize'] = True
        if self.config.get('webgal', 'jpeg-progressive'):
            self.save_options['progressive'] = True

        self.pic_sort_by = self.config.get('webgal', 'sort-medias')
        self.subgal_sort_by = self.config.get('webgal', 'sort-subgals')
        self.tagfilters = self.config.get('webgal', 'filter-by-tag')

        self.webalbumpic_bg = self.config.get('webgal', 'webalbumpic-bg')
        self.webalbumpic_type = self.config.get('webgal', 'webalbumpic-type')
        try:
            self.webalbumpic_size = list(map(int, self.config.get('webgal', 'webalbumpic-size').split('x')))
            if len(self.webalbumpic_size) != 2:
                raise ValueError
        except ValueError:
            logging.error(_('Bad syntax for webalbumpic-size.'))
            sys.exit(1)
        self.keep_gps = self.config.get('webgal', 'keep-gps')

    def set_original(self, original=False, orig_base=None, orig_symlink=False):
        self.original = original or orig_symlink
        self.orig_symlink = orig_symlink
        if self.original and orig_base and not orig_symlink:
            self.orig_base = orig_base
        else:
            self.orig_base = None

    def get_webalbumpic_filename(self):
        if self.webalbumpic_bg == 'transparent':
            ext = '.png'  # JPEG does not have an alpha channel
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

    def add_index_page(self, subgals, galleries):
        page_number = self.break_task.next_page_number()
        pages = []
        for size_name in self.browse_sizes:
            page = genpage.WebalbumIndexPage(self, size_name, page_number,
                                             subgals, galleries)
            if self.album.force_gen_pages:
                page.stamp_delete()
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
            return len(self.source_dir.subdirs)

    def get_all_subgals(self):
        all_subgals = list(self.subgals)  # We want a copy here.
        for subgal in self.subgals:
            all_subgals.extend(subgal.get_all_subgals())
        return all_subgals

    def has_media(self):
        if self.tagfilters:
            return True if self.medias else False
        else:
            return True if self.source_dir.medias else False

    def has_media_below(self):
        if self.has_media():
            return True
        for subgal in self.subgals:
            if subgal.has_media_below():
                return True
        return False

    def should_be_flattened(self, path=None):
        if path is None: path = self.source_dir.path
        return self.album.dir_flattening_depth is not False\
            and self.source_dir.get_album_level(path) > self.album.dir_flattening_depth

    def flatten_below(self):
        if self.album.dir_flattening_depth is False:
            return False
        elif self.source_dir.subdirs:
            # As all subdirs are at the same level, if one should be flattened,
            # all should.
            return self.subgals[0].should_be_flattened()
        else:
            return False

    def rel_path_to_src(self, target_srcdir_path):
        """
        Returns the relative path to go from this directory to
        target_srcdir_path.
        """
        return self.source_dir.rel_path(self.source_dir.path,
                                        target_srcdir_path)

    def rel_path(self, path):
        """
        Returns the relative path to go from this directory to the path
        supplied as argument.
        """
        return os.path.relpath(path, self.path)

    def flattening_srcpath(self, srcdir_path):
        """
        Returns the source path in which srcdir_path should flattened, that is
        the path of the gallery index that will point to srcdir_path's
        pictures.
        """
        if self.should_be_flattened(srcdir_path):
            cur_path = srcdir_path
            while self.should_be_flattened(cur_path):
                cur_path, dummy = os.path.split(cur_path)
            return cur_path
        else:
            return ''

    def list_foreign_files(self):
        self.call_populate_deps()

        if not os.path.isdir(self.path):
            return []

        foreign_files = []

        # Check dest for junk files
        extra_files = []
        if self.source_dir.is_album_root():
            extra_files.append(os.path.join(self.path,
                                            DEST_SHARED_DIRECTORY_NAME))

        dirnames = [d.source_dir.name for d in self.subgals]
        expected_dirs = list(map(lambda dn: os.path.join(self.path, dn),
                             dirnames))
        for dest_file in os.listdir(self.path):
            dest_file = os.path.join(self.path, dest_file)
            if dest_file not in self.output_items and\
                dest_file not in expected_dirs and\
                    dest_file not in extra_files:
                foreign_files.append(dest_file)

        return foreign_files

    def skip_media(self, src_media):
        return False

    def needs_build_quick(self):
        """
        Faster check if needs to be built.
        """
        if self._deps_populated or self.tagfilters:
            return self.needs_build()

        return self.pindex.needs_build()

    def build(self):
        for dest_file in self.list_foreign_files():
            self.album.cleanup(dest_file, self.path)

    def make(self, force=False):
        super(WebalbumDir, self).make(force)
        self.update_build_status()

    def media_done(self):
        if self.progress is not None:
            self.progress.media_done()


class SharedFiles(make.FileMakeObject):

    def __init__(self, album, dest_dir, tpl_vars):
        self.path = os.path.join(dest_dir, DEST_SHARED_DIRECTORY_NAME)
        self.album = album

        # Create the shared files directory if it does not exist
        if not os.path.isdir(self.path):
            logging.info(_("MKDIR %SHAREDDIR%"))
            logging.debug("(%s)", self.path)
            os.makedirs(self.path)

        super(SharedFiles, self).__init__(self.path)

        self.expected_shared_files = []
        for shared in self.album.theme.shared_files:
            shared_file_dest = os.path.join(self.path, shared['dest'])

            if self.album.theme.tpl_loader.is_known_template_type(shared['source']):
                sf = genpage.SharedFileTemplate(album, shared['source'],
                                                shared_file_dest,
                                                tpl_vars)
                if self.album.force_gen_pages:
                    sf.stamp_delete()
            else:
                sf = genfile.SharedFileCopy(shared['source'], shared_file_dest)
            self.expected_shared_files.append(sf.path)

            self.add_dependency(sf)

    def build(self):
        # Cleanup themes files which are not in themes anymore.
        for present_file in os.listdir(self.path):
            file_path = os.path.join(self.path, present_file)
            if file_path not in self.expected_shared_files:
                self.album.cleanup(file_path, self.path)


class DummyProgress(object):

    def dir_done(self):                   pass
    def media_done(self, how_many=1):     pass
    def set_task_progress(self, percent): pass
    def set_task_done(self):              pass
    def updated(self):                    pass


class AlbumGenProgress(object):

    def __init__(self, dirs_total, medias_total):
        self._dirs_total = dirs_total
        self._dirs_done = 0

        self._medias_total = medias_total
        self._medias_done = 0

        self._task_percent = None

    def dir_done(self):
        self._dirs_done = self._dirs_done + 1
        self.updated()

    def media_done(self, how_many=1):
        self._medias_done = self._medias_done + how_many
        self.updated()

    def set_task_progress(self, percent):
        self._task_percent = percent
        self.updated()

    def set_task_done(self):
        self._task_percent = None
        self.updated()

    def __str__(self):
        msg = []

        if self._dirs_total > 0:
            msg.append("dir %d/%d (%d%%)" \
                  % (self._dirs_done, self._dirs_total,
                     100 * self._dirs_done // self._dirs_total,
                    ))

        if self._medias_total > 0:
            msg.append("media %d/%d (%d%%)" \
                       % (self._medias_done, self._medias_total,
                          100 * self._medias_done // self._medias_total,
                         ))

        if self._task_percent is not None:
            msg.append(_("current task %d%%") % self._task_percent)

        return _("Progress: %s") % ', '.join(msg)

    def updated(self):
        pass


class Album(object):

    def __init__(self, source_dir, config=None):
        self.source_dir = os.path.abspath(source_dir)

        self.config = LazygalConfig(load_defaults=True)

        logging.debug(_("Trying loading user config %s"), USER_CONFIG_PATH)
        self.config.load_any(USER_CONFIG_PATH)

        sourcedir_configfile = os.path.join(source_dir, SOURCEDIR_CONFIGFILE)
        if os.path.isfile(sourcedir_configfile):
            logging.debug(_("Loading root config %s"), sourcedir_configfile)
            try:
                self.config.load_any(sourcedir_configfile)
            except LazygalConfigDeprecated:
                logging.error(_("'%s' uses a deprecated syntax: please refer to lazygal.conf(5) manual page."), sourcedir_configfile)
                sys.exit(1)
        if config is not None:  # Supplied config
            self.config.load(config)

        if self.config.get('runtime', 'quiet'):
            logging.getLogger().setLevel(logging.ERROR)
        if self.config.get('runtime', 'debug'):
            logging.getLogger().setLevel(logging.DEBUG)
            GExiv2.log_set_level(GExiv2.LogLevel.INFO)

        self.clean_dest = self.config.get('global', 'clean-destination')
        self.preserves = (self.config.get('global', 'preserve') +
			 self.config.get('global', 'preserve_args'))
        self.force_gen_pages = self.config.get('global', 'force-gen-pages')

        self.set_theme(self.config.get('global', 'theme'))
        self.excludes = (self.config.get('global', 'exclude') +
                        self.config.get('global', 'exclude_args'))

        self.dir_flattening_depth = self.config.get('global', 'dir-flattening-depth')

        self.__statistics = None

    def set_theme(self, theme_name=theme.DEFAULT_THEME):
        self.theme = theme.Theme(os.path.join(DATAPATH, 'themes'), theme_name)
        self.theme.prepare_tpl_loader(tpl.TplFactory)
        self.theme.check_shared_files()

    def _str_humanize(self, text):
        dash_replaced = text.replace('_', ' ')
        return dash_replaced

    def is_in_sourcetree(self, path):
        return pathutils.is_subdir_of(self.source_dir, path)

    def cleanup(self, file_path, context_path):
        if self.clean_dest:
            # Do not delete something out of dest-dir.
            assert pathutils.is_subdir_of(context_path, file_path)
            tail = os.path.basename(file_path)
            for pattern in self.preserves:
                # Do not delete something the user wants to keep.
                if fnmatch.fnmatch(tail, pattern):
                    logging.info('  PRESERVE %s', tail)
                    return
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.unlink(file_path)
            logging.info('  RM %s', file_path)

    def generate_default_metadata(self):
        """
        Generate default metadata files if no exists.
        """
        logging.debug(_("Generating metadata in %s"), self.source_dir)

        for root, dirnames, filenames in pathutils.walk(self.source_dir):
            filenames.sort()  # This is required for the ignored files
                              # checks to be reliable.
            source_dir = sourcetree.Directory(root, [], filenames, self)
            logging.info(_("[Entering %%ALBUMROOT%%/%s]"), source_dir.strip_root())
            logging.debug("(%s)", source_dir.path)

            metadata.DefaultMetadata(source_dir, self).make()

    def stats(self):
        if self.__statistics is None:
            self.__statistics = {
                'total' : 0,
                'bydir' : {}
            }
            for root, dirnames, filenames in pathutils.walk(self.source_dir):
                dir_medias = len([f for f in filenames\
                                  if sourcetree.MediaHandler.is_known_media(f, self)])
                self.__statistics['total'] = self.__statistics['total']\
                                             + dir_medias
                self.__statistics['bydir'][root] = dir_medias
        return self.__statistics

    def generate(self, dest_dir=None, progress=None):
        if dest_dir is None:
            dest_dir = self.config.get('global', 'output-directory')
        sane_dest_dir = os.path.abspath(os.path.expanduser(dest_dir))

        if not progress:
            progress = DummyProgress()

        pub_url = self.config.get('global', 'puburl')
        check_all_dirs = self.config.get('runtime', 'check-all-dirs')

        if self.is_in_sourcetree(sane_dest_dir):
            raise ValueError(_("Fatal error, web gallery directory is within source tree."))

        logging.debug(_("Generating to %s"), sane_dest_dir)

        if pub_url:
            feed = genpage.WebalbumFeed(self, sane_dest_dir, pub_url)
        else:
            feed = None

        dir_heap = {}
        for root, dirnames, filenames in pathutils.walk(self.source_dir):

            if root in dir_heap:
                subdirs, subgals = dir_heap[root]
                del dir_heap[root]  # No need to keep it there
            else:
                subdirs = []
                subgals = []

            checked_dir = sourcetree.File(root, self)

            if checked_dir.should_be_skipped():
                logging.debug(_("(%s) has been skipped"), checked_dir.path)
                continue
            if checked_dir.path == os.path.join(sane_dest_dir,
                                                DEST_SHARED_DIRECTORY_NAME):
                logging.error(_("(%s) has been skipped because its name collides with the shared material directory name"), checked_dir.path)
                continue

            logging.info(_("[Entering %%ALBUMROOT%%/%s]"), checked_dir.strip_root())
            logging.debug("(%s)", checked_dir.path)

            source_dir = sourcetree.Directory(root, subdirs, filenames, self)

            destgal = WebalbumDir(source_dir, subgals, self, sane_dest_dir,
                                  progress)

            if source_dir.is_album_root():
                # Use root config tpl vars for shared files
                tpl_vars = destgal.tpl_vars

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

            if check_all_dirs or destgal.needs_build_quick():
                destgal.make()
            else:
                progress.media_done(self.stats()['bydir'][destgal.source_dir.path])
                logging.info(_("  SKIPPED because of mtime, touch source or use --check-all-dirs to override."))

            # Force some memory cleanups, this is usefull for big albums.
            del destgal
            gc.collect()

            progress.dir_done()

            logging.info(_("[Leaving  %%ALBUMROOT%%/%s]"), source_dir.strip_root())

        if feed:
            feed.make()

        # Force to check for unexpected files
        SharedFiles(self, sane_dest_dir, tpl_vars).make(True)


# vim: ts=4 sw=4 expandtab
