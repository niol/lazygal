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
import gc

import make
import sourcetree, tpl, newsize, metadata, mediautils
import genpage, genmedia, genfile

from sourcetree import SOURCEDIR_CONFIGFILE


DATAPATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if not os.path.exists(os.path.join(DATAPATH, 'themes')):
    DATAPATH = os.path.join(sys.exec_prefix, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print _('Could not find themes dir, check your installation!')

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
        self.album.log(_("  SORTING pics and subdirs"), 'info')

        if self.album.subgal_sort_by[0] == 'mtime':
            subgal_sorter = lambda x, y:\
                                x.source_dir.compare_mtime(y.source_dir)
        elif self.album.subgal_sort_by[0] == 'filename':
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
        self.album.log(_("  BREAKING web gallery into multiple pages"), 'info')

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
                          / self.webgal_dir.album.thumbs_per_page + 1
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
        make.MakeTask.__init__(self)

        self.album = album
        self.webgal = webgal
        self.media = media

        self.previous = None
        self.next = None

        self.original = None
        self.resized = {}
        self.browse_pages = {}

        for size_name in self.album.browse_size_strings.keys():
            if self.album.browse_size_strings[size_name] == '0x0':
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


class WebalbumImageTask(WebalbumMediaTask):
    """
    This task builds all items related to one picture.
    """

    def __init__(self, webgal, image, album):
        WebalbumMediaTask.__init__(self, webgal, image, album)

        self.thumb = genmedia.ImageOtherSize(self.webgal, self.media,
                                             genmedia.THUMB_SIZE_NAME)
        self.add_dependency(self.thumb)

    def get_original_or_symlink(self):
        if not self.album.orig_symlink:
            return genfile.ImageOriginal(self.webgal, self.media)
        else:
            return genfile.SymlinkImageOriginal(self.webgal, self.media)

    def get_original(self):
        if not self.original:
            self.original = self.get_original_or_symlink()
        return self.original

    def get_resized(self, size_name):
        if self.album.browse_size_strings[size_name] == '0x0':
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

        WebalbumMediaTask.__init__(self, webgal, video, album)

        self.thumb = None # none yet

        self.add_dependency(self.webvideo)

    def get_original(self):
        return self.get_resized("0x0")

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

    def __init__(self, dir, subgals, album, album_dest_dir, clean_dest):
        self.__mtime = None

        self.source_dir = dir
        self.path = os.path.join(album_dest_dir, self.source_dir.strip_root())
        make.FileMakeObject.__init__(self, self.path)

        self.add_dependency(self.source_dir)
        self.subgals = subgals
        self.album = album

        self.flattening_dir = None

        # mtime for directories must be saved, because the WebalbumDir gets
        # updated as its dependencies are built.
        self.__mtime = self.get_mtime()

        self.clean_dest = clean_dest

        # Create the directory if it does not exist
        if not os.path.isdir(self.path):
            self.album.log(_("  MKDIR %%WEBALBUMROOT%%/%s")\
                           % self.source_dir.strip_root(), 'info')
            self.album.log("(%s)" % self.path)
            os.makedirs(self.path, mode = 0755)

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
                raise NotImplementedError("Unknonwn media type '%s'"\
                                          % media.type)
            self.medias.append(media_task)
            self.add_dependency(media_task)

        self.dirzip = None

        if not self.should_be_flattened():
            self.break_task = SubgalBreak(self)
            self.add_dependency(self.break_task)

            if self.album.thumbs_per_page > 0:
                # FIXME: If pagination is 'on', galleries need to be sorted
                # before being broken on multiple pages, and thus this slows
                # down a lot the checking of a directory's need to be built.
                self.break_task.add_dependency(self.sort_task)

            self.webgal_pic = genmedia.WebalbumPicture(self)
            self.add_dependency(self.webgal_pic)

    def add_index_page(self, subgals, galleries):
        page_number = self.break_task.next_page_number()
        for size_name in self.album.browse_size_strings.keys():
            page = genpage.WebalbumIndexPage(self, size_name, page_number,
                                             subgals, galleries)
            self.add_dependency(page)

    def get_mtime(self):
        # Use the saved mtime that was initialized once, in self.__init__()
        return self.__mtime or super(WebalbumDir, self).get_mtime()

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

    def should_be_flattened(self):
        return self.album.dir_flattening_depth is not False\
        and self.source_dir.get_album_level() > self.album.dir_flattening_depth

    def flatten_below(self):
        if self.album.dir_flattening_depth is False:
            return False
        elif len(self.source_dir.subdirs) > 0:
            # As all subdirs are at the same level, if one should be flattened,
            # all should.
            return self.subgals[0].should_be_flattened()
        else:
            return False

    def build(self):
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
                text = ''
                if self.clean_dest and not os.path.isdir(dest_file):
                    os.unlink(dest_file)
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

    def __init__(self, source_dir,
                 thumb_size_string='150x113', browse_size_strings=None,
                 optimize=False, progressive=False, quality=85,
                 dir_flattening_depth=False, thumbs_per_page=0,
                 dirzip=False,
                 pic_sort_by=('exif', False),
                 subgal_sort_by=('filename', False)):
        self.set_logging()

        self.source_dir = os.path.abspath(source_dir)
        self.source_dir = self.source_dir.decode(sys.getfilesystemencoding())

        self.thumb_size_string = thumb_size_string
        if browse_size_strings is not None:
            self.browse_size_strings = dict(browse_size_strings)
            self.default_size_name = browse_size_strings[0][0]
        else:
            self.browse_size_strings = {'small': '800x600',
                                        'medium': '1024x768'}
            self.default_size_name = 'small'

        self.newsizers = {}
        for size_name, size_string in self.browse_size_strings.items():
            self.newsizers[size_name] = newsize.get_newsizer(size_string)
        self.newsizers[genmedia.THUMB_SIZE_NAME] = newsize.get_newsizer(self.thumb_size_string)

        self.quality = quality

        self.tpl_loader = None
        self.tpl_vars = {}
        self.original = False
        self.orig_base = None
        self.orig_symlink = False
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

        self.transcoder = None
        self.videothumb = None

        self.set_webalbumpic()

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
            if self.tpl_loader.is_known_template_type(style_filename):
                self.tpl_loader.load(style_filename)

    def get_transcoder(self):
        if self.transcoder is None:
            if mediautils.HAVE_GST:
                self.transcoder = mediautils.OggTheoraTranscoder()
            else:
                self.transcoder = False
        return self.transcoder

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

    def set_original(self, original=False, orig_base=None, orig_symlink=False):
        self.original = original
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
                self.log_errpipe.flush()
            else:
                print >> self.log_outpipe, msg
                self.log_outpipe.flush()

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

    def generate_default_metadata(self):
        '''
        Generate default metada files if no exists.
        '''
        self.log(_("Generating metadata in %s") % self.source_dir)

        for root, dirnames, filenames in os.walk(self.source_dir):
            filenames.sort() # This is required for the ignored files
                             # checks to be reliable.
            source_dir = sourcetree.Directory(root, [], filenames, self)
            self.log(_("[Entering %%ALBUMROOT%%/%s]") % source_dir.strip_root(),
                     'info')
            self.log("(%s)" % source_dir.path)

            metadata.DefaultMetadata(source_dir, self).make()

    def generate(self, dest_dir, pub_url=None,
                 check_all_dirs=False, clean_dest=False):
        dest_dir = dest_dir.decode(sys.getfilesystemencoding())
        sane_dest_dir = os.path.abspath(dest_dir)

        if self.is_in_sourcetree(sane_dest_dir):
            raise ValueError(_("Fatal error, web gallery directory is within source tree."))

        self.log(_("Generating to %s") % sane_dest_dir)

        if pub_url:
            feed = genpage.WebalbumFeed(self, sane_dest_dir, pub_url)
        else:
            feed = None

        dir_heap = {}
        for root, dirnames, filenames in os.walk(self.source_dir,
                                                 topdown=False):

            if dir_heap.has_key(root):
                subdirs, subgals = dir_heap[root]
                del dir_heap[root] # No need to keep it there
            else:
                subdirs = []
                subgals = []

            source_dir = sourcetree.Directory(root, subdirs, filenames, self)

            if source_dir.should_be_skipped():
                self.log(_("(%s) has been skipped") % source_dir.path)
                continue
            if source_dir.path == os.path.join(sane_dest_dir,
                                               DEST_SHARED_DIRECTORY_NAME):
                self.log(_("(%s) has been skipped because its name collides with the shared material directory name") % source_dir.path, 'error')
                continue

            self.log(_("[Entering %%ALBUMROOT%%/%s]") % source_dir.strip_root(),
                     'info')
            self.log("(%s)" % source_dir.path)

            if source_dir.get_all_medias_count() < 1:
                self.log(_("(%s) and childs have no known medias, skipped")
                           % source_dir.path)
                continue

            destgal = WebalbumDir(source_dir, subgals, self,
                                  sane_dest_dir, clean_dest)

            if not source_dir.is_album_root():
                container_dirname = os.path.dirname(root)
                if not dir_heap.has_key(container_dirname):
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
            if destgal.needs_build() or check_all_dirs:
                destgal.make()
            else:
                self.log(_("  SKIPPED because of mtime, touch source or use --check-all-dirs to override."))

            # Force some memory cleanups, this is usefull for big albums.
            del destgal
            gc.collect()

            self.log(_("[Leaving  %%ALBUMROOT%%/%s]") % source_dir.strip_root(),
                     'info')

        if feed:
            feed.make()

        SharedFiles(self, sane_dest_dir).make()


# vim: ts=4 sw=4 expandtab
