# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2010 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import sys
import urllib
import locale

import genshi

import make
import genfile, genmedia, feeds


class WebalbumPage(genfile.WebalbumFile):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self._add_size_qualifier(base_name + '.html',
                                                 self.size_name)
        self.page_path = os.path.join(dir.path, page_filename)
        genfile.WebalbumFile.__init__(self, self.page_path, dir)

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
                                                     genmedia.THUMB_SIZE_NAME)
            link_vals['thumb'] = self.url_quote(link_vals['thumb'])

            if not img.broken:
                thumb = os.path.join(dir.path,
                                     self._add_size_qualifier(img.filename,
                                                     genmedia.THUMB_SIZE_NAME))
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

    def __init__(self, dir, size_name, webalbum_media):
        self.webalbum_media = webalbum_media
        self.media = self.webalbum_media.media
        WebalbumPage.__init__(self, dir, size_name, self.media.name)

        self.add_dependency(self.webalbum_media.resized[size_name])
        if webalbum_media.original:
            self.add_dependency(self.webalbum_media.original)

        # Depends on source directory in case an image was deleted
        self.add_dependency(self.dir.source_dir)

        self.add_dependency(self.dir.sort_task)


class WebalbumImagePage(WebalbumBrowsePage):

    def __init__(self, dir, size_name, webalbum_image):
        WebalbumBrowsePage.__init__(self, dir, size_name, webalbum_image)
        self.image = self.media
        self.set_template(self.dir.album.templates['browseimage.thtml'])

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

        if not self.image.broken:
            tpl_values['img_width'],\
            tpl_values['img_height'] = self.image.get_size(browse_image_path)

        img_date = self.image.get_date_taken()
        # strftime does not work with unicode...
        time_format = _("on %d/%m/%Y at %H:%M").encode(locale.getpreferredencoding())
        time_str = img_date.strftime(time_format)
        tpl_values['image_date'] = time_str.decode(locale.getpreferredencoding())

        prev = self.webalbum_media.previous
        if prev:
            tpl_values['prev_link']  = self._gen_other_img_link(prev.media)

        next = self.webalbum_media.next
        if next:
            tpl_values['next_link'] = self._gen_other_img_link(next.media)

        tpl_values['index_link'] = self._add_size_qualifier('index.html',
                                                            self.size_name)
        if self.dir.should_be_flattened():
            index_rel_dir = self.dir.flattening_dir.source_dir.rel_path(self.dir.source_dir)
            tpl_values['index_link'] = index_rel_dir + tpl_values['index_link']

        tpl_values['osize_links'] = self._get_osize_links(self.image.name)
        tpl_values['rel_root'] = self.dir.source_dir.rel_root()

        image_info = self.image.info()
        tpl_values['camera_name'] = image_info.get_camera_name()
        tpl_values['lens_name'] = image_info.get_lens_name()
        tpl_values['flash'] = image_info.get_flash()
        tpl_values['exposure'] = image_info.get_exposure()
        tpl_values['iso'] = image_info.get_iso()
        tpl_values['fnumber'] = image_info.get_fnumber()
        tpl_values['focal_length'] = image_info.get_focal_length()
        tpl_values['comment'] = image_info.get_comment()

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

    def __init__(self, dir, size_name, page_number, subgals, galleries):
        page_paginated_name = self._get_paginated_name(page_number)
        WebalbumPage.__init__(self, dir, size_name, page_paginated_name)

        self.page_number = page_number
        self.subgals = subgals
        self.galleries = galleries

        for dir, images in self.galleries:
            self.add_dependency(dir.source_dir.metadata)
            if dir is not self.dir:
                dir.flattening_dir = self.dir
                self.add_dependency(dir)

            self.add_dependency(dir.source_dir)
            self.add_dependency(dir.sort_task)

            for image in images:
                self.add_dependency(image.thumb)
                self.add_dependency(image.browse_pages[size_name])
                # Ensure dir depends on browse page (usefull for cleanup checks
                # when dir is flattenend).
                dir.add_dependency(image.browse_pages[size_name])

            if self.dir.album.dirzip and dir.source_dir.get_media_count() > 1:
                self.add_dependency(genfile.WebalbumArchive(dir))

        self.set_template(self.dir.album.templates['dirindex.thtml'])

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
        for onum in range(0, self.dir.break_task.how_many_pages()):
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
        if dir.source_dir.metadata:
            dir_info.update(dir.source_dir.metadata.get())
            if 'album_description' in dir_info.keys():
                dir_info['album_description'] =\
                    self._do_not_escape(dir_info['album_description'])

        if 'album_name' not in dir_info.keys():
            dir_info['album_name'] = dir.source_dir.human_name

        if self.dir.album.dirzip and dir.dirzip:
            archive_rel_path = dir.dirzip._rel_path(self.dir)
            dir_info['dirzip'] = self.url_quote(archive_rel_path)

        dir_info['is_main'] = dir is self.dir

        dir_info['image_count'] = dir.source_dir.get_media_count('image')
        dir_info['subgal_count'] = len(dir.source_dir.subdirs)

        return dir_info

    def _get_subgal_links(self):
        subgal_links = []
        for subgal in self.dir.subgals:
            dir_info = self._get_dir_info(subgal)
            dir_info['link'] = '/'.join([subgal.source_dir.name,
                                         self._get_related_index_fn()])
            dir_info['link'] = self.url_quote(dir_info['link'])
            dir_info['album_picture'] = os.path.join(subgal.source_dir.name,
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
        for subdir, medias in self.galleries:
            info = self._get_dir_info(subdir)
            img_links = map(lambda x: self._gen_other_img_link(x.media, subdir),
                            medias)
            values['images'].append((info, img_links, ))

        values.update(self._get_dir_info())

        values['rel_root'] = self.dir.source_dir.rel_root()
        values['rel_path'] = self.dir.source_dir.strip_root()

        self.page_template.dump(values, self.page_path)


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
        if webalbumdir.source_dir.get_media_count() > 0:
            self.add_dependency(webalbumdir)
            self.__add_item(webalbumdir)

    def __add_item(self, webalbumdir):
        url = os.path.join(self.pub_url, webalbumdir.source_dir.strip_root())

        desc_values = {}
        desc_values['album_pic_path'] = os.path.join(url,
                                          self.album.get_webalbumpic_filename())
        desc_values['subgal_count'] = webalbumdir.get_subgal_count()
        desc_values['picture_count'] = webalbumdir.source_dir.get_media_count('image')
        desc_values['desc'] = webalbumdir.source_dir.desc
        desc = self.item_template.instanciate(desc_values)

        self.feed.push_item(webalbumdir.source_dir.title, url, desc,
                            webalbumdir.source_dir.get_mtime())

    def build(self):
        self.album.log(_("FEED %s") % os.path.basename(self.path), 'info')
        self.album.log("(%s)" % self.path)
        self.feed.dump(self.path)


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


# vim: ts=4 sw=4 expandtab
