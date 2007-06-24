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

    def __init__(self, album):
        self.album = album

    def get_extension(self, file_path):
        filename, ext = os.path.splitext(file_path)
        return ext

    def get_filename(self, file_path):
        filename, ext = os.path.splitext(file_path)
        return os.path.basename(filename)

    def strip_root(self, path):
        found = False
        album_path = ""
        head = path

        while not found:
            if head == self.album.source_dir:
                found = True
            elif head == "":
                raise Exception("Root not found")
            else:
                head, tail = os.path.split(head)
                album_path = os.path.join(tail, album_path)

        return album_path

    def rel_root(self, path):
        if os.path.isdir(path):
            cur_path = path
        else:
            cur_path = os.path.dirname(path)

        rel_root = ""

        while cur_path != self.album.source_dir:
            print cur_path
            cur_path, tail = os.path.split(cur_path)
            rel_root = os.path.join('..', rel_root)
        return rel_root

    def get_dest_path(self, path, dest_dir):
        return os.path.join(dest_dir, self.strip_root(path))

    def get_album_dir(self, path):
        return self.strip_root(os.path.dirname(path))

    def get_source_mtime(self, path):
        return os.path.getmtime(path)

    def get_dest_mtime(self, source_path, dest_dir, dest_file = None):
        if not dest_file:
            dest_file = self.get_dest_path(source_path, dest_dir)

        try:
            return os.path.getmtime(dest_file)
        except:
            # Let's tell that the file is very old
            return 0

    def source_newer(self, source_path, dest_dir, dest_file = None):
        return self.get_source_mtime(source_path) >\
               self.get_dest_mtime(source_path, dest_dir, dest_file)


class ImageFile(File):

    def __init__(self, album):
        File.__init__(self, album)
        self.generated_sizes = [('thumb', album.thumb_size)]\
                               + album.browse_sizes

    def is_ext_supported(self, file):
        return self.get_extension(file) in ['.jpg']

    def get_othersize_path_noext(self, file, dest_dir, size_name):
        thumb_name = self.get_othersize_name_noext(file, size_name)
        thumb_dir = self.get_dest_path(os.path.dirname(file), dest_dir)
        return os.path.join(thumb_dir, thumb_name)

    def get_othersize_name_noext(self, img, size_name = None):
        if not size_name:
            size_name = self.album.default_size_name
        return '_'.join([self.get_filename(img), size_name])

    def get_othersize_bpage_name(self, img, size_name = None):
        return self.get_othersize_name_noext(img, size_name) + '.html'

    def get_othersize_img_link(self, img, size_name = None):
        return self.get_othersize_name_noext(img, size_name)\
               + self.get_extension(img)

    def generate_size(self, source, dest_dir, size_name, size):
        osize_path = self.get_othersize_path_noext(source, dest_dir, size_name)\
                     + self.get_extension(source)

        if self.source_newer(source, dest_dir, osize_path):
            im = Image.open(source)
            im.thumbnail(size, Image.ANTIALIAS)
            im.save(osize_path) 
            self.album.log("\t\tGenerated " + osize_path)
        return os.path.basename(osize_path)

    def get_size(self, img):
        im = Image.open(img)
        return im.size

    def get_date_taken(self, img, dir = None):
        if dir:
            img = os.path.join(dir, img)
        f = open(img, 'rb')
        tags = EXIF.process_file(f)
        exif_date = str(tags['Image DateTime'])
        date, time = exif_date.split(' ')
        year, month, day = date.split(':')
        hour, minute, second = time.split(':')
        return datetime.datetime(int(year), int(month), int(day),
                                 int(hour), int(minute), int(second))

    def compare_date_taken(self, img1, img2, dir = None):
        if dir:
            img1 = os.path.join(dir, img1)
            img2 = os.path.join(dir, img2)
        date1 = time.mktime(self.get_date_taken(img1).timetuple())
        date2 = time.mktime(self.get_date_taken(img2).timetuple())
        delta = date1 - date2
        return int(delta)

    def gen_other_img_link(self, img, dest_dir, size_name, template):
        if img:
            link_vals = {}
            link_vals['link'] = self.get_othersize_bpage_name(img, size_name)

            link_vals['thumb'] = self.get_othersize_img_link(img, 'thumb')

            thumb = self.get_othersize_path_noext(img, dest_dir, 'thumb') +\
                    self.get_extension(img)
            link_vals['thumb_width'],\
                link_vals['thumb_height'] = self.get_size(thumb)

            return template.instanciate(link_vals)
        else:
            return ''

    def generate_browse_page(self, image, dest_dir, size_name, prev, next):
        page_file = '.'.join([self.get_othersize_path_noext(image, dest_dir,
                                                            size_name),
                              'html'])

        if self.source_newer(image, dest_dir, page_file):
            page_template = self.album.templates['page-image']

            tpl_values = {}
            tpl_values['img_src'] = self.get_othersize_img_link(image,
                                                                size_name)
            tpl_values['name'] = os.path.basename(image)
            tpl_values['dir'] = self.get_album_dir(image)
            tpl_values['image_name'] = self.get_filename(image)

            browse_image = self.get_othersize_path_noext(image, dest_dir,
                                                         size_name)\
                           + self.get_extension(image)
            tpl_values['img_width'],\
                tpl_values['img_height'] = self.get_size(browse_image)

            tpl_values['image_date'] = self.get_date_taken(image)\
                  .strftime("on %d/%m/%Y at %H:%M")

            tpl_values['prev_link'] = self.gen_other_img_link(prev, dest_dir,
                                         size_name,
                                         self.album.templates['prev_link'])
            tpl_values['next_link'] = self.gen_other_img_link(next, dest_dir,
                                         size_name,
                                         self.album.templates['next_link'])
            tpl_values['rel_root'] = self.rel_root(image)

            page_template.dump(tpl_values, page_file)
            self.album.log("Generated HTML" + page_file)

        return os.path.basename(page_file)

    def generate_other_sizes(self, file, dest_dir):
        generated_files = []
        for size_name, size in self.generated_sizes:
            osize_file = self.generate_size(file, dest_dir, size_name, size)
            generated_files.append(osize_file)
        return generated_files

    def generate_browse_pages(self, file, dest_dir, prev, next):
        generated_files = []
        for size_name, size in self.album.browse_sizes:
            page = self.generate_browse_page(file, dest_dir,
                                             size_name, prev, next)
            generated_files.append(page)
        return generated_files


class Directory(File):

    def __init__(self, album):
        File.__init__(self, album)
        self.img_proc = self.album.image_processor

    def find_prev(self, file, files, root):
        index = files.index(file)
        try:
            return os.path.join(root, files[index-1])
        except IndexError:
            return None

    def find_next(self, file, files, root):
        index = files.index(file)
        try:
            return os.path.join(root, files[index+1])
        except IndexError:
            return None

    def generate(self, root, dirs, files, dest_dir):
        generated_files = []
        supported_files = []

        root_dest_dir = self.get_dest_path(root, dest_dir)
        if not os.path.isdir(self.get_dest_path(root, dest_dir)):
            os.mkdir(root_dest_dir)
            self.album.log("\tCreated dir " + root_dest_dir)

        for file in files:
            file_path = os.path.join(root, file)
            if self.img_proc.is_ext_supported(file):
                self.album.log("\tProcessing " + file)
                gen_files = self.img_proc.generate_other_sizes(file_path,
                                                                      dest_dir)
                generated_files.extend(gen_files)
                supported_files.append(file)
                self.album.log("\tFinished processing " + file)
            else:
                self.album.log("\tIgnoring " + file +\
                               " : format not supported", 1)

        supported_files.sort(lambda x, y:
                                self.img_proc.compare_date_taken(x, y, root))
        for file in supported_files:
            file_path = os.path.join(root, file)
            prev = self.find_prev(file, supported_files, root)
            next = self.find_next(file, supported_files, root)
            gen_files = self.img_proc.generate_browse_pages(file_path,
                                                            dest_dir,
                                                            prev, next)
            generated_files.extend(gen_files)

        page = self.generate_index_page(root, dirs, supported_files, dest_dir)
        generated_files.append(page)

        return generated_files

    def generate_index_page(self, root, dirs, files, dest_dir):
        values = {}

        subgal_links = []
        for dir in dirs:
            dir_info = {'name': dir, 'link': dir + '/'}
            subgal_links.append(self.album.templates['subgal_link'].\
                                                        instanciate(dir_info))
        values['subgals'] = "\n".join(subgal_links)

        image_links = []
        for file in files:
            file_path = os.path.join(root, file)
            file_info = {}

            default_size_name = self.album.browse_sizes[0][0]
            link_page = self.album.image_processor.\
                  get_othersize_path_noext(file_path,
                                           dest_dir, default_size_name)\
                                + '.html'
            file_info['link'] = os.path.basename(link_page)

            thumb = self.album.image_processor.\
                         get_othersize_path_noext(file_path,
                                                  dest_dir, 'thumb')\
                    + self.get_extension(file)
            file_info['thumb'] = os.path.basename(thumb)
            file_info['width'],\
                file_info['height'] = self.album.\
                                  image_processor.get_size(thumb)
            file_info['image_name'] = os.path.basename(file)

            image_links.append(self.album.templates['image_link'].\
                                                       instanciate(file_info))
        values['images'] = "\n".join(image_links)
        values['title'] = self.strip_root(root)
        values['rel_root'] = self.rel_root(root)

        page_file = os.path.join(self.get_dest_path(root, dest_dir),
                                 'index.html')
        self.album.templates['page-index'].dump(values, page_file)
        self.album.log("\tDumped HTML " + page_file)
        return os.path.basename(page_file)
    
    def clean_dest(self, root, dirs, generated_files, dest_dir):
        for dest_file in os.listdir(self.get_dest_path(root, dest_dir)):
            if dest_file not in generated_files and\
               dest_file not in dirs:
                self.album.log("\t\tCleanup: " + dest_file + " should be removed")


class Album:

    def __init__(self, source_dir, thumb_size, browse_sizes, debug=False):
        self.source_dir = os.path.abspath(source_dir)

        self.thumb_size = thumb_size
        self.browse_sizes = browse_sizes
        self.default_size_name = self.browse_sizes[0][0]

        self.templates = {}
        self.image_processor = ImageFile(self)
        self.dir_processor = Directory(self)

    def set_theme(self, theme):
        self.theme = theme
        self.templates.clear()

        for tpl_file in glob.glob(os.path.join(THEME_DIR, self.theme, "*.tpl")):
            filename, ext = os.path.splitext(os.path.basename(tpl_file))
            self.templates[filename] = Template(tpl_file)

    def log(self, msg, level=0):
        """Log message to stdout : 0 is debug, 1 is warning, 2 is info."""
        print msg

    def generate(self, dest_dir):
        sane_dest_dir = os.path.abspath(dest_dir)
        self.log("Generating to " + sane_dest_dir)

        for root, dirs, files in os.walk(self.source_dir):
            self.log("Entering " + root)
            generated_files = self.dir_processor.\
                                     generate(root, dirs, files, sane_dest_dir)
            self.dir_processor.clean_dest(root, dirs,
                                          generated_files, sane_dest_dir)
            self.log("Leaving " + root)

        self.copy_shared(dest_dir)

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
