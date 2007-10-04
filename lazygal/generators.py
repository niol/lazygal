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

import os, glob, shutil, time, datetime, sys
import Image
from genshi.template import TemplateLoader, MarkupTemplate

import __init__, metadata


DATAPATH = os.path.join(os.path.dirname(__file__), '..')
if not os.path.exists(os.path.join(DATAPATH, 'themes')):
    DATAPATH = os.path.join(sys.exec_prefix, 'share', 'lazygal')
    if not os.path.exists(os.path.join(DATAPATH, 'themes')):
        print 'Could not find themes dir, check your installation!'

THEME_DIR = os.path.join(DATAPATH, 'themes')
USER_THEME_DIR = os.path.expanduser(os.path.join('~', '.lazygal', 'themes'))
THEME_SHARED_FILE_PREFIX = 'SHARED_'
DEST_SHARED_DIRECTORY_NAME = 'shared'

class Template(MarkupTemplate):

    def dump(self, values, dest):
        values['gen_date'] = time.strftime("%A, %d %B %Y %H:%M %Z")
        values['lazygal_version'] = __init__.__version__
        page = open(dest, 'w')
        page.write(self.generate(t=values).render('xhtml'))
        page.close()


class File:

    def __init__(self, source, album, album_dest_dir):
        self.source = source
        self.album = album
        self.album_dest_dir = album_dest_dir
        filename, self.extension = os.path.splitext(self.source)
        self.filename = os.path.basename(filename)

    def path_to_unicode(self, path):
        return path.decode(sys.getfilesystemencoding())

    def strip_root(self, path=None):
        found = False
        album_path = ""

        if not path:
            head = self.source
        else:
            head = path

        while not found:
            if head == self.album.source_dir:
                found = True
            elif head == "":
                raise Exception("Root not found")
            else:
                head, tail = os.path.split(head)
                if album_path == "":
                    album_path = tail
                else:
                    album_path = os.path.join(tail, album_path)

        return album_path

    def rel_root(self):
        if os.path.isdir(self.source):
            cur_path = self.source
        else:
            cur_path = os.path.dirname(self.source)

        rel_root = ""

        while cur_path != self.album.source_dir:
            cur_path, tail = os.path.split(cur_path)
            rel_root = os.path.join('..', rel_root)
        return rel_root

    def get_album_dir(self):
        if os.path.isdir(self.source):
            return self.strip_root(self.source)
        else:
            return self.strip_root(os.path.dirname(self.source))

    def get_source_mtime(self):
        mtime = os.path.getmtime(self.source)
        if mtime == 0:
            # If mtime is not set (can happen), we need to make this newer
            # than non existing destination file. This is kind of hack, but I
            # guess there won't be much albums from 1.1.1970 which would be
            # broken by this.
            mtime = 1
        return mtime

    def get_dest_mtime(self, dest_file):
        try:
            return os.path.getmtime(dest_file)
        except OSError:
            # Let's tell that the file is very old if it does not exist
            return 0

    def source_newer(self, dest_file):
        return self.get_source_mtime() > self.get_dest_mtime(dest_file)

    def get_osize_name_noext(self, size_name=None,
                                   filename=None,
                                   no_def_ozise_suffix=False):
        if not size_name:
            size_name = self.album.default_size_name
        if not filename:
            filename = self.filename

        if no_def_ozise_suffix and size_name == self.album.default_size_name:
            return filename
        else:
            return '_'.join([filename, size_name])

    def get_osize_links(self, size_name, filename, no_def_ozise_suffix=False):
        osize_index_links = []
        for osize_name, ozise in self.album.browse_sizes:
            osize_info = {}
            if osize_name == size_name:
                # No link if we're on the current page
                osize_info['name'] = osize_name
            else:
                osize_info['name'] = osize_name
                osize_page_name = self.get_osize_name_noext(osize_name,
                                                            filename,
                                                            no_def_ozise_suffix)
                osize_info['link'] = osize_page_name + '.html'
            osize_index_links.append(osize_info)

        return osize_index_links


class ImageFile(File):

    def __init__(self, filename, dir, album, album_dest_dir):
        File.__init__(self, os.path.join(dir.source, filename),
                      album, album_dest_dir)
        self.dir = dir
        self.destdir = self.dir.dest
        self.generated_sizes = [('thumb', album.thumb_size)]\
                               + album.browse_sizes

        self.exif = None

    def get_othersize_path_noext(self, size_name):
        thumb_name = self.get_osize_name_noext(size_name)
        return os.path.join(self.destdir, thumb_name)

    def get_othersize_bpage_name(self, size_name = None):
        return self.get_osize_name_noext(size_name) + '.html'

    def get_othersize_img_link(self, size_name = None):
        return self.get_osize_name_noext(size_name) + self.extension

    def generate_size(self, size_name, size):
        osize_path = self.get_othersize_path_noext(size_name) + self.extension

        if self.source_newer(osize_path):
            im = Image.open(self.source)

            # Use EXIF data to rotate target image if available and required
            rotation = self.get_required_rotation()
            if rotation != 0:
                im = im.rotate(rotation)

            im.thumbnail(size, Image.ANTIALIAS)

            im.save(osize_path, quality = self.album.quality)
            self.album.log("\t\tGenerated %s" % osize_path)
        return os.path.basename(osize_path)

    def get_size(self, img):
        im = Image.open(img)
        return im.size

    def __load_exif_data(self):
        if not self.exif:
            self.exif = metadata.ExifTags(self.source)

    def get_date_taken(self):
        '''
        Get real time when photo has been taken. We prefer EXIF fields
        as those were filled by camera, Image DateTime can be update by
        software when editing photos later.
        '''
        self.__load_exif_data()

        try:
            self.date_taken = self.exif.get_date('EXIF DateTimeDigitized')
        except (KeyError, ValueError):
            try:
                self.date_taken = self.exif.get_date('EXIF DateTimeOriginal')
            except (KeyError, ValueError):
                try:
                    self.date_taken = self.exif.get_date('Image DateTime')
                except (KeyError, ValueError):
                    # No date available in EXIF, or bad format, use file mtime
                    self.date_taken = datetime.datetime.fromtimestamp(\
                                                       self.get_source_mtime())
        return self.date_taken

    def get_required_rotation(self):
        self.__load_exif_data()

        if self.exif['Image Orientation']:
            orientation_code = int(self.exif['Image Orientation'].values[0])
            # FIXME : This should really go in the EXIF library
            if orientation_code == 8:
                return 90
            elif orientation_code == 6:
                return 270
            else:
                return 0
        else:
            return 0

    def compare_date_taken(self, other_img):
        date1 = time.mktime(self.get_date_taken().timetuple())
        date2 = time.mktime(other_img.get_date_taken().timetuple())
        delta = date1 - date2
        return int(delta)

    def gen_other_img_link(self, img, size_name):
        if img:
            link_vals = {}
            link_vals['link'] = img.get_othersize_bpage_name(size_name)
            link_vals['thumb'] = img.get_othersize_img_link('thumb')

            thumb = img.get_othersize_path_noext('thumb') + img.extension
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = self.get_size(thumb)

            return link_vals
        else:
            return None

    def generate_browse_page(self, size_name, prev, next):
        page_file = '.'.join([self.get_othersize_path_noext(size_name),
                              'html'])

        page_template = self.album.templates['browse']

        tpl_values = {}
        tpl_values['img_src'] = self.get_othersize_img_link(size_name)
        tpl_values['name'] = self.filename
        tpl_values['dir'] = self.get_album_dir()
        tpl_values['image_name'] = self.filename

        browse_image = self.get_othersize_path_noext(size_name) + self.extension
        tpl_values['img_width'],\
        tpl_values['img_height'] = self.get_size(browse_image)

        img_date = self.get_date_taken()
        tpl_values['image_date'] = img_date.strftime("on %d/%m/%Y at %H:%M")

        tpl_values['prev_link'] = self.gen_other_img_link(prev, size_name)
        tpl_values['next_link'] = self.gen_other_img_link(next, size_name)
        tpl_values['index_link'] = self.dir.get_index_filename(size_name)
        tpl_values['osize_links'] = self.get_osize_links(size_name,
                                                         self.filename)
        tpl_values['rel_root'] = self.rel_root()

        tpl_values['camera_name'] = self.exif.get_camera_name()
        tpl_values['flash'] = self.exif.get_flash()
        tpl_values['exposure'] = self.exif.get_exposure()
        tpl_values['iso'] = self.exif.get_iso()
        tpl_values['fnumber'] = self.exif.get_fnumber()
        tpl_values['focal_length'] = self.exif.get_focal_length()
        tpl_values['comment'] = self.exif.get_comment()

        page_template.dump(tpl_values, page_file)
        self.album.log("\t\tDumped HTML %s" % page_file)

        return os.path.basename(page_file)

    def generate_other_sizes(self):
        generated_files = []
        for size_name, size in self.generated_sizes:
            osize_file = self.generate_size(size_name, size)
            generated_files.append(osize_file)
        return generated_files

    def generate_browse_pages(self, prev, next):
        generated_files = []
        for size_name, size in self.album.browse_sizes:
            page = self.generate_browse_page(size_name, prev, next)
            generated_files.append(page)
        return generated_files


class Directory(File):

    def __init__(self, source, dirnames, filenames, album, album_dest_dir):
        File.__init__(self, self.path_to_unicode(source),
                      album, self.path_to_unicode(album_dest_dir))

        self.dest = os.path.join(album_dest_dir, self.strip_root())
        self.initial_dest_mtime = File.get_dest_mtime(self, self.dest)

        self.dirnames = map(self.path_to_unicode, dirnames)
        self.dirnames.sort()
        self.filenames = map(self.path_to_unicode, filenames)
        self.supported_files = []
        self.metadata = metadata.DirectoryMetadata(self)

    def get_dest_mtime(self, dest_file):
        if dest_file == self.dest:
            return self.initial_dest_mtime
        else:
            return File.get_dest_mtime(self, dest_file)

    def get_source_mtime(self):
        dir_mtime = File.get_source_mtime(self)
        return max(dir_mtime, self.metadata.get_mtime())

    def guess_directory_picture(self, subdir = None):
        '''
        Guesses picture for directory by finding first suitable image.
        '''
        directory = self.source
        relpath = ''
        found = False

        if subdir is not None:
            directory = os.path.join(directory, subdir)
            relpath = subdir

        for root, dirs, files in os.walk(directory):
            subdirs = root[len(directory):]
            if len(subdirs) > 0 and subdirs[0] == '/':
                subdirs = subdirs[1:]
            for file in files:
                if self.album.is_ext_supported(file):
                    picture = os.path.join(relpath, subdirs, file)
                    return picture

        return None

    def find_prev(self, file):
        prev_index = self.supported_files.index(file) - 1
        if prev_index < 0:
            return None
        else:
            return self.supported_files[prev_index]

    def find_next(self, file):
        index = self.supported_files.index(file)
        try:
            return self.supported_files[index+1]
        except IndexError:
            return None

    def generate(self, check_all_dirs, do_clean_dest):
        generated_files = []

        if not check_all_dirs and not self.source_newer(self.dest):
            self.album.log("\tSkipping because of mtime")
            return

        if not os.path.isdir(self.dest):
            os.makedirs(self.dest, mode = 0755)
            self.album.log("\tCreated dir %s" % self.dest)

        for filename in self.filenames:
            if self.album.is_ext_supported(filename):
                self.album.log("\tProcessing %s" % filename)
                file = ImageFile(filename, self,
                                 self.album, self.album_dest_dir)
                gen_files = file.generate_other_sizes()
                generated_files.extend(gen_files)
                self.supported_files.append(file)
                self.album.log("\tFinished processing %s" % filename)
            else:
                self.album.log("\tIgnoring %s : format not supported"
                        % filename, 1)

        self.supported_files.sort(lambda x, y: x.compare_date_taken(y))
        for file in self.supported_files:
            prev = self.find_prev(file)
            next = self.find_next(file)
            gen_files = file.generate_browse_pages(prev, next)
            generated_files.extend(gen_files)

        index_pages = self.generate_index_pages()
        generated_files.extend(index_pages)

        self.check_dest_for_junk(generated_files, do_clean_dest)

        # Although we should have modified the directory contents and thus its
        # mtime, it is possible that the directory mtime has not been updated
        # if we regenerated without adding/removing pictures (to take into
        # account a rotation for example). This is why we force directory mtime
        # update here.
        os.utime(self.dest, None)

    def get_index_filename(self, size_name):
        return self.get_osize_name_noext(size_name, 'index', True) + '.html'

    def generate_index_page(self, size_name):
        values = {}

        values['ozise_index_links'] = self.get_osize_links(size_name,
                                                           'index', True)

        subgal_links = []
        for dir in self.dirnames:
            dir_info = {'name': dir, 'link': dir + '/'}
            dir_info.update(self.metadata.get(dir))
            subgal_links.append(dir_info)
        values['subgal_links'] = subgal_links
        values.update(self.metadata.get())

        image_links = []
        for file in self.supported_files:
            file_info = {}

            link_page = file.get_othersize_bpage_name(size_name)
            file_info['link'] = os.path.basename(link_page)

            thumb = os.path.join(self.dest,
                                 file.get_othersize_img_link('thumb'))
            file_info['thumb'] = os.path.basename(thumb)
            file_info['width'],\
                file_info['height'] = file.get_size(thumb)
            file_info['image_name'] = file.filename

            image_links.append(file_info)
        values['images'] = image_links

        values['rel_root'] = self.rel_root()

        values['rel_path'] = self.strip_root()
        title = values['rel_path']
        if title == "":
            # Easy title for root directory
            title = os.path.basename(os.path.dirname(self.dest))
        values['title'] = title.replace('_', ' ')

        page_file = os.path.join(self.dest, self.get_index_filename(size_name))
        self.album.templates['dirindex'].dump(values, page_file)
        self.album.log("\tDumped HTML %s" % page_file)
        return os.path.basename(page_file)

    def generate_index_pages(self):
        generated_pages = []
        for size_name, size in self.album.browse_sizes:
            page = self.generate_index_page(size_name)
            generated_pages.append(page)
        return generated_pages

    def is_album_root(self):
        return self.source == self.path_to_unicode(self.album.source_dir)

    def check_dest_for_junk(self, generated_files, do_clean_dest):
        for dest_file in os.listdir(self.dest):
            if dest_file not in generated_files and\
               dest_file not in self.dirnames:
                text = ''
                if not (self.is_album_root() and
                        dest_file == DEST_SHARED_DIRECTORY_NAME):
                    if do_clean_dest:
                        os.unlink(os.path.join(self.dest, dest_file))
                        text = "has been"
                    else:
                        text = "should be"
                    self.album.log("\t\tCleanup: %s %s removed" %
                                   (dest_file, text))


class Album:

    def __init__(self, source_dir, thumb_size, browse_sizes,
                 quality=85, debug=False):
        self.source_dir = os.path.abspath(source_dir)

        self.thumb_size = thumb_size
        self.browse_sizes = browse_sizes
        self.quality = quality
        self.default_size_name = self.browse_sizes[0][0]

        self.templates = {}

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

        tpl_loader = TemplateLoader([self.tpl_dir])
        for tpl_file in glob.glob(os.path.join(self.tpl_dir, "*.thtml")):
            filename, ext = os.path.splitext(os.path.basename(tpl_file))
            self.templates[filename] = tpl_loader.load(tpl_file,
                                                       cls=Template)

    def log(self, msg, level=0):
        """Log message to stdout : 0 is debug, 1 is warning, 2 is info."""
        print msg

    def is_ext_supported(self, filename):
        filename, extension = os.path.splitext(filename)
        return extension.lower() in ['.jpg']

    def generate(self, dest_dir, check_all_dirs=False, clean_dest=False):
        sane_dest_dir = os.path.abspath(dest_dir)
        self.log("Generating to %s" % sane_dest_dir)

        for root, dirnames, filenames in os.walk(self.source_dir):
            self.log("Entering %s" % root)
            dir = Directory(root, dirnames, filenames, self, sane_dest_dir)
            dir.generate(check_all_dirs, clean_dest)
            self.log("Leaving %s" % root)

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

            if os.path.getmtime(shared_file) > dest_mtime:
                shutil.copy(shared_file, shared_file_dest)
                self.log("Copied or updated %s" % shared_file_dest, 0)


# vim: ts=4 sw=4 expandtab