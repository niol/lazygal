import os, glob, shutil, time, datetime
import Image, EXIF


THEME_DIR = os.path.join(os.path.dirname(__file__), 'themes')
THEME_SHARED_FILE_PREFIX = 'SHARED_'


class Template:

    def __init__(self, tpl_file):
        self.tpl_file = tpl_file

        f = open(tpl_file, 'r')
        self.tpl = f.read()
        f.close()

    def instanciate(self, values):
        return self.tpl % values

    def dump(self, values, dest):
        page = open(dest, 'w')
        page.write(self.instanciate(values))
        page.close()


class File:

    def __init__(self, source, album, album_dest_dir):
        self.source = source
        self.album = album
        self.album_dest_dir = album_dest_dir
        filename, self.extension = os.path.splitext(self.source)
        self.filename = os.path.basename(filename)

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
        return os.path.getmtime(self.source)

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
            if osize_name == size_name:
                # No link if we're on the current page
                osize_index_link = osize_name
            else:
                osize_info = {}
                osize_info['osize_name'] = osize_name
                osize_page_name = self.get_osize_name_noext(osize_name,
                                                            filename,
                                                            no_def_ozise_suffix)
                osize_info['osize_link'] = osize_page_name + '.html'
                osize_index_link = self.album.templates['osize_link'].\
                                                        instanciate(osize_info)
            osize_index_links.append(osize_index_link)

        return ' | '.join(osize_index_links)


class ImageFile(File):

    def __init__(self, source, dir, album, album_dest_dir):
        File.__init__(self, source, album, album_dest_dir)
        self.dir = dir
        self.destdir = self.dir.dest
        self.generated_sizes = [('thumb', album.thumb_size)]\
                               + album.browse_sizes

        self.tags = None
        self.date_taken = None

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
            im.thumbnail(size, Image.ANTIALIAS)

            # Use EXIF data to rotate target image if available and required
            rotation = self.get_required_rotation()
            if rotation != 0:
                im = im.rotate(rotation)

            im.save(osize_path) 
            self.album.log("\t\tGenerated " + osize_path)
        return os.path.basename(osize_path)

    def get_size(self, img):
        im = Image.open(img)
        return im.size

    def __load_exif_data(self):
        if not self.tags:
            f = open(self.source, 'rb')
            self.tags = EXIF.process_file(f)

    def get_date_taken(self):
        self.__load_exif_data()
        try:
            exif_date = str(self.tags['Image DateTime'])
            date, time = exif_date.split(' ')
            year, month, day = date.split(':')
            hour, minute, second = time.split(':')
            self.date_taken =\
                         datetime.datetime(int(year), int(month), int(day),
                                           int(hour), int(minute), int(second))
        except (KeyError, ValueError):
            # No date available in EXIF, or bad format, use file mtime
            self.date_taken = datetime.datetime.fromtimestamp(\
                                               self.get_source_mtime())
        return self.date_taken

    def get_required_rotation(self):
        self.__load_exif_data()

        if self.tags.has_key('Image Orientation'):
            orientation_code = int(self.tags['Image Orientation'].values[0])
            # FIXME : This hsould really go in the EXIF library
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

    def gen_other_img_link(self, img, size_name, template):
        if img:
            link_vals = {}
            link_vals['link'] = img.get_othersize_bpage_name(size_name)
            link_vals['thumb'] = img.get_othersize_img_link('thumb')

            thumb = img.get_othersize_path_noext('thumb') + img.extension
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = self.get_size(thumb)

            return template.instanciate(link_vals)
        else:
            return ''

    def generate_browse_page(self, size_name, prev, next):
        page_file = '.'.join([self.get_othersize_path_noext(size_name),
                              'html'])

        if self.source_newer(page_file):
            page_template = self.album.templates['page-image']

            tpl_values = {}
            tpl_values['img_src'] = self.get_othersize_img_link(size_name)
            tpl_values['name'] = self.filename
            tpl_values['dir'] = self.get_album_dir()
            tpl_values['image_name'] = self.filename

            browse_image = self.get_othersize_path_noext(size_name)\
                           + self.extension
            tpl_values['img_width'],\
                tpl_values['img_height'] = self.get_size(browse_image)

            img_date = self.get_date_taken()
            tpl_values['image_date'] = img_date.strftime("on %d/%m/%Y at %H:%M")

            tpl_values['prev_link'] = self.gen_other_img_link(prev,
                                         size_name,
                                         self.album.templates['prev_link'])
            tpl_values['next_link'] = self.gen_other_img_link(next,
                                         size_name,
                                         self.album.templates['next_link'])
            tpl_values['index_link'] = self.dir.get_index_filename(size_name)
            tpl_values['osize_links'] = self.get_osize_links(size_name,
                                                             self.filename)
            tpl_values['rel_root'] = self.rel_root()

            page_template.dump(tpl_values, page_file)
            self.album.log("Generated HTML" + page_file)

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
        File.__init__(self, source, album, album_dest_dir)
        self.dest = os.path.join(album_dest_dir, self.strip_root())
        self.dirnames = dirnames
        self.dirnames.sort()
        self.filenames = filenames
        self.supported_files = []

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

    def generate(self):
        generated_files = []

        if not self.source_newer(self.dest):
            self.album.log("\tSkipping because of mtime")
            return

        if not os.path.isdir(self.dest):
            os.mkdir(self.dest)
            self.album.log("\tCreated dir " + self.dest)

        for filename in self.filenames:
            file_path = os.path.join(self.source, filename)
            if self.album.is_ext_supported(filename):
                self.album.log("\tProcessing " + filename)
                file = ImageFile(file_path, self,
                                 self.album, self.album_dest_dir)
                gen_files = file.generate_other_sizes()
                generated_files.extend(gen_files)
                self.supported_files.append(file)
                self.album.log("\tFinished processing " + filename)
            else:
                self.album.log("\tIgnoring " + filename +\
                               " : format not supported", 1)

        self.supported_files.sort(lambda x, y: x.compare_date_taken(y))
        for file in self.supported_files:
            prev = self.find_prev(file)
            next = self.find_next(file)
            gen_files = file.generate_browse_pages(prev, next)
            generated_files.extend(gen_files)

        index_pages = self.generate_index_pages()
        generated_files.extend(index_pages)

        self.clean_dest(generated_files)

    def get_index_filename(self, size_name):
        return self.get_osize_name_noext(size_name, 'index', True) + '.html'

    def generate_index_page(self, size_name):
        values = {}

        values['ozise_index_links'] = self.get_osize_links(size_name,
                                                           'index', True)

        subgal_links = []
        for dir in self.dirnames:
            dir_info = {'name': dir, 'link': dir + '/'}
            subgal_links.append(self.album.templates['subgal_link'].\
                                                        instanciate(dir_info))
        values['subgals'] = "\n".join(subgal_links)

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

            image_links.append(self.album.templates['image_link'].\
                                                       instanciate(file_info))
        values['images'] = "\n".join(image_links)
        values['rel_root'] = self.rel_root()

        title = self.strip_root()
        if title == "":
            # Easy title for root directory
            title = os.path.basename(os.path.dirname(self.dest))
        values['title'] = title.replace('_', ' ')

        page_file = os.path.join(self.dest, self.get_index_filename(size_name))
        self.album.templates['page-index'].dump(values, page_file)
        self.album.log("\tDumped HTML " + page_file)
        return os.path.basename(page_file)

    def generate_index_pages(self):
        generated_pages = []
        for size_name, size in self.album.browse_sizes:
            page = self.generate_index_page(size_name)
            generated_pages.append(page)
        return generated_pages
    
    def clean_dest(self, generated_files):
        for dest_file in os.listdir(self.dest):
            if dest_file not in generated_files and\
               dest_file not in self.dirnames:
                self.album.log("\t\tCleanup: " + dest_file + " should be removed")


class Album:

    def __init__(self, source_dir, thumb_size, browse_sizes, debug=False):
        self.source_dir = os.path.abspath(source_dir)

        self.thumb_size = thumb_size
        self.browse_sizes = browse_sizes
        self.default_size_name = self.browse_sizes[0][0]

        self.templates = {}

    def set_theme(self, theme):
        self.theme = theme
        self.templates.clear()

        for tpl_file in glob.glob(os.path.join(THEME_DIR, self.theme, "*.tpl")):
            filename, ext = os.path.splitext(os.path.basename(tpl_file))
            self.templates[filename] = Template(tpl_file)

    def log(self, msg, level=0):
        """Log message to stdout : 0 is debug, 1 is warning, 2 is info."""
        print msg

    def is_ext_supported(self, filename):
        filename, extension = os.path.splitext(filename)
        return extension in ['.jpg']

    def generate(self, dest_dir):
        sane_dest_dir = os.path.abspath(dest_dir)
        self.log("Generating to " + sane_dest_dir)

        self.copy_shared(sane_dest_dir)

        for root, dirnames, filenames in os.walk(self.source_dir):
            self.log("Entering " + root)
            dir = Directory(root, dirnames, filenames, self, sane_dest_dir)
            dir.generate()
            self.log("Leaving " + root)

    def copy_shared(self, dest_dir):
        shared_stuff_dir = os.path.join(dest_dir, 'shared')

        if not os.path.isdir(shared_stuff_dir):
            os.mkdir(shared_stuff_dir)

        for shared_file in glob.glob(\
          os.path.join(THEME_DIR, self.theme, THEME_SHARED_FILE_PREFIX + '*')):
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
                self.log("Copied or updated " + shared_file_dest, 0)


# vim: ts=4 sw=4 expandtab
