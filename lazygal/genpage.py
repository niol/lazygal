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
import posixpath
import pathutils
import sys
import logging
import urllib
import locale

import genshi

import make
import pathutils
import genfile, genmedia, feeds
import timeutils


class WebalbumPage(genfile.WebalbumFile):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self._add_size_qualifier(base_name + '.html',
                                                 self.size_name)
        self.page_path = os.path.join(dir.path, page_filename)
        genfile.WebalbumFile.__init__(self, self.page_path, dir)

        self.page_template = None

    def set_template(self, tpl_ident):
        self.page_template = self.load_tpl(tpl_ident)

    def load_tpl(self, tpl_ident):
        tpl = self.dir.album.tpl_loader.load(tpl_ident)
        self.add_file_dependency(tpl.path)
        for subtpl in tpl.subtemplates():
            self.add_file_dependency(subtpl.path)
        return tpl

    def init_tpl_values(self):
        tpl_values = {}
        tpl_values.update(self.dir.tpl_vars)
        return tpl_values

    def _gen_other_media_link(self, media, dir=None):
        if media:
            link_vals = {}

            link_vals['type'] = media.media.type

            link_vals['link'] = media.browse_pages[self.size_name].rel_path(dir)
            link_vals['link'] = self.url_quote(link_vals['link'])

            link_vals['thumb'] = media.thumb.rel_path(dir)
            link_vals['thumb'] = self.url_quote(link_vals['thumb'])

            if not media.media.broken:
                link_vals['thumb_width'],\
                    link_vals['thumb_height'] = media.thumb.get_size()

            link_vals['thumb_name'] = self.dir.album._str_humanize(media.media.name)

            return link_vals
        else:
            return None

    def _get_osize_links(self, filename):
        osize_index_links = []
        for osize_name in self.dir.browse_sizes:
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

    def _get_webgal_id(self, srcdir_path):
        if self.dir.should_be_flattened(srcdir_path):
            rawid = self.dir.source_dir.rel_path(self.dir.flattening_srcpath(srcdir_path), srcdir_path)
        else:
            rawid = os.path.basename(srcdir_path)
        return rawid.replace(' /\\', '_')

    def _get_webgal_link(self, srcdir_path):
        link_target = self._add_size_qualifier('index.html', self.size_name)

        if self.dir.should_be_flattened(srcdir_path):
            # Add anchor target to get straight to gallery listing
            link_target = link_target + '#' + self._get_webgal_id(srcdir_path)

        # Add relative path to link if needed
        index_path = None
        if self.dir.should_be_flattened(srcdir_path):
            index_path = self.dir.flattening_srcpath(srcdir_path)
        if srcdir_path != self.dir.source_dir.path:
            index_path = srcdir_path
        if index_path is not None:
            index_path = self.dir.rel_path_to_src(index_path)
            index_path = pathutils.url_path(index_path)
            link_target = posixpath.join(index_path, link_target)

        return self.url_quote(link_target)

    def _gen_webgal_path(self):
        wg_path = []
        for dirmd in self.dir.source_dir.parents_metadata():
            wg = {}
            wg['link'] = self._get_webgal_link(dirmd.dir_path)
            wg['name'] = dirmd.get_title()
            wg['root'] = dirmd.dir_path == self.dir.album.source_dir
            wg['current'] = dirmd.dir_path == self.dir.source_dir.path
            wg_path.append(wg)

        wg_path.reverse()
        return wg_path

    def _add_size_qualifier(self, path, size_name):
        return self.dir._add_size_qualifier(path, size_name)

    def _do_not_escape(self, value):
        return genshi.core.Markup(value)

    def url_quote(self, url):
        return urllib.quote(url.encode(sys.getfilesystemencoding()), safe=':/#')

    UNIT_PREFIXES = (('T', 2**40), ('G', 2**30), ('M', 2**20), ('K', 2**10),)

    def format_filesize(self, size_bytes):
        for unit_prefix, limit in self.UNIT_PREFIXES:
            if size_bytes >= limit:
                return '%.1f %siB'\
                       % (round(float(size_bytes) / limit, 1), unit_prefix)
        return '%.1f B' % size_bytes


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

        # Depend on the comment file if it exists.
        if self.webalbum_media.media.comment_file_path is not None:
            self.add_file_dependency(self.webalbum_media.media.comment_file_path)

        self.add_dependency(self.dir.sort_task)

        self.set_template('browse.thtml')
        self.load_tpl(self.media.type+'.thtml')

    def build(self):
        page_rel_path = self.rel_path(self.dir.flattening_dir)
        logging.info(_("  XHTML %s") % page_rel_path)
        logging.debug("(%s)" % self.page_path)

        tpl_values = self.init_tpl_values()

        # Breadcrumbs
        tpl_values['webgal_path'] = self._gen_webgal_path()

        tpl_values['name'] = self.media.filename
        tpl_values['mediatype'] = self.media.type
        tpl_values['dir'] = self.dir.source_dir.strip_root()

        prev = self.webalbum_media.previous
        if prev:
            tpl_values['prev_link']  = self._gen_other_media_link(prev)

        next = self.webalbum_media.next
        if next:
            tpl_values['next_link'] = self._gen_other_media_link(next)

        tpl_values['index_link'] = self._add_size_qualifier('index.html',
                                                            self.size_name)
        if self.dir.should_be_flattened():
            index_rel_dir = self.dir.flattening_dir.source_dir.rel_path(self.dir.source_dir)
            tpl_values['index_link'] = index_rel_dir + tpl_values['index_link']

        tpl_values['osize_links'] = self._get_osize_links(self.media.name)
        tpl_values['rel_root'] = self.dir.source_dir.rel_root() + '/'

        if self.dir.feed is not None:
            tpl_values['feed_url'] = os.path.relpath(self.dir.feed.path,
                                                     self.dir.path)
            tpl_values['feed_url'] = pathutils.url_path(tpl_values['feed_url'])
            tpl_values['feed_url'] = self.url_quote(tpl_values['feed_url'])
        else:
            tpl_values['feed_url'] = None

        if self.dir.original:
            if self.dir.orig_base:
                tpl_values['original_link'] = os.path.join(\
                    self.dir.source_dir.rel_root(),
                    self.dir.orig_base,
                    self.dir.source_dir.strip_root(),
                    self.media.filename)
            else:
                tpl_values['original_link'] = self.media.filename
            tpl_values['original_link'] =\
                self.url_quote(tpl_values['original_link'])

        self.add_extra_vals(tpl_values)

        self.page_template.dump(tpl_values, self.page_path)


class WebalbumImagePage(WebalbumBrowsePage):

    def __init__(self, dir, size_name, webalbum_image):
        WebalbumBrowsePage.__init__(self, dir, size_name, webalbum_image)
        self.image = self.media

    def add_extra_vals(self, tpl_values):
        tpl_values['img_src'] = self._add_size_qualifier(self.image.filename,
                                                         self.size_name)
        tpl_values['img_src'] = self.url_quote(tpl_values['img_src'])

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
        tpl_values['image_datetime'] = timeutils.unicodify_datetime(img_date)

        image_info = self.image.info()
        if image_info:
            comment = image_info.get_comment()
            if comment == '' or comment is None:
                tpl_values['comment'] = None
            else:
                tpl_values['comment'] = self._do_not_escape(comment)
            if self.dir.config.getboolean('webgal', 'publish-metadata'):
                tpl_values['camera_name'] = image_info.get_camera_name()
                tpl_values['lens_name'] = image_info.get_lens_name()
                tpl_values['flash'] = image_info.get_flash()
                tpl_values['exposure'] = image_info.get_exposure()
                tpl_values['iso'] = image_info.get_iso()
                tpl_values['fnumber'] = image_info.get_fnumber()
                tpl_values['focal_length'] = image_info.get_focal_length()
                tpl_values['authorship'] = image_info.get_authorship()


class WebalbumVideoPage(WebalbumBrowsePage):

    def __init__(self, webgal, size_name, webalbum_video):
        WebalbumBrowsePage.__init__(self, webgal, size_name, webalbum_video)
        self.video = self.media

    def add_extra_vals(self, tpl_values):
        tpl_values['video_src'] = self.video.name + '.webm'
        tpl_values['video_src'] = self.url_quote(tpl_values['video_src'])


class WebalbumIndexPage(WebalbumPage):

    FILENAME_BASE_STRING = 'index'

    def __init__(self, dir, size_name, page_number, subgals, galleries):
        page_paginated_name = self._get_paginated_name(page_number)
        WebalbumPage.__init__(self, dir, size_name, page_paginated_name)

        self.page_number = page_number
        self.subgals = subgals
        self.galleries = galleries

        for dir, medias in self.galleries:
            self.add_dependency(dir.source_dir.metadata)
            if dir is not self.dir:
                dir.flattening_dir = self.dir

            self.add_dependency(dir.source_dir)
            self.add_dependency(dir.sort_task)

            for media in medias:
                if media.thumb: self.add_dependency(media.thumb)
                self.add_dependency(media.browse_pages[size_name])
                # Ensure dir depends on browse page (usefull for cleanup checks
                # when dir is flattenend).
                dir.add_dependency(media.browse_pages[size_name])

            if self.dir.dirzip is not None:
                self.add_dependency(self.dir.dirzip)

        for subgal in self.subgals:
            self.add_dependency(subgal.source_dir)

        self.set_template('dirindex.thtml')

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

        if dir.dirzip:
            archive_rel_path = dir.dirzip.rel_path(self.dir)
            dir_info['dirzip'] = self.url_quote(archive_rel_path)
            dir_info['dirzip_size'] = self.format_filesize(dir.dirzip.size())

        dir_info['is_main'] = dir is self.dir

        dir_info['image_count'] = dir.source_dir.get_media_count('image')
        dir_info['subgal_count'] = len(dir.source_dir.subdirs)

        dir_info['id'] = self.url_quote(self._get_webgal_id(dir.source_dir.path))

        return dir_info

    def _get_subgal_links(self):
        subgal_links = []
        for subgal in self.dir.subgals:
            dir_info = self._get_dir_info(subgal)
            dir_info['link'] = '/'.join([subgal.source_dir.name,
                                         self._get_related_index_fn()])
            dir_info['link'] = self.url_quote(dir_info['link'])
            dir_info['album_picture'] = os.path.join(subgal.source_dir.name,
                                            self.dir.get_webalbumpic_filename())
            dir_info['album_picture'] = self.url_quote(dir_info['album_picture'])
            subgal_links.append(dir_info)
        return subgal_links

    def build(self):
        logging.info(_("  XHTML %s") % os.path.basename(self.page_path))
        logging.debug("(%s)" % self.page_path)

        values = self.init_tpl_values()

        # Breadcrumbs (current is static, see dirindex.thtml, that's why the
        # last item of the list is removed).
        values['webgal_path'] = self._gen_webgal_path()[:-1]

        if not self.dir.source_dir.is_album_root():
            # Parent index link not for album root
            values['parent_index_link'] = self._get_related_index_fn()

        values['osize_index_links'] = self._get_osize_links(self._get_paginated_name())
        values['onum_index_links'] = self._get_onum_links()

        if self.dir.flatten_below():
            values['subgal_links'] = []
        else:
            values['subgal_links'] = self._get_subgal_links()

        values['medias'] = []
        for subdir, medias in self.galleries:
            info = self._get_dir_info(subdir)
            media_links = [self._gen_other_media_link(media, subdir)
                           for media in medias]
            values['medias'].append((info, media_links, ))

        values.update(self._get_dir_info())

        values['rel_root'] = self.dir.source_dir.rel_root() + '/'
        values['rel_path'] = self.dir.source_dir.strip_root()

        if self.dir.feed is not None:
            values['feed_url'] = os.path.relpath(self.dir.feed.path,
                                                 self.dir.path)
            values['feed_url'] = pathutils.url_path(values['feed_url'])
            values['feed_url'] = self.url_quote(values['feed_url'])
        else:
            values['feed_url'] = None

        self.page_template.dump(values, self.page_path)


class WebalbumFeed(make.FileMakeObject):

    def __init__(self, album, dir_path, pub_url):
        self.path = os.path.join(dir_path, 'index.xml')
        super(WebalbumFeed, self).__init__(self.path)

        self.album = album
        self.pub_url = pub_url
        if not self.pub_url:
            self.pub_url = 'http://example.com'
        if not self.pub_url.endswith('/'):
            self.pub_url = self.pub_url + '/'

        self.feed = feeds.RSS20(self.pub_url)
        self.item_template = self.album.tpl_loader.load('feeditem.thtml')

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
                                         webalbumdir.get_webalbumpic_filename())
        desc_values['subgal_count'] = webalbumdir.get_subgal_count()
        desc_values['picture_count'] = webalbumdir.source_dir.get_media_count('image')
        desc_values['desc'] = webalbumdir.source_dir.desc
        desc = self.item_template.instanciate(desc_values)

        self.feed.push_item(webalbumdir.source_dir.title, url, desc,
                            webalbumdir.source_dir.get_mtime())

    def build(self):
        logging.info(_("FEED %s") % os.path.basename(self.path))
        logging.debug("(%s)" % self.path)
        self.feed.dump(self.path)


class SharedFileTemplate(make.FileMakeObject):

    def __init__(self, album, shared_tpl_name, shared_file_dest_tplname,
                       tpl_vars):
        self.album = album
        self.tpl = self.album.tpl_loader.load(shared_tpl_name)
        self.tpl_vars = tpl_vars

        # Remove the 't' from the beginning of ext
        filename, ext = os.path.splitext(shared_file_dest_tplname)
        if ext.startswith('.t'):
            self.path = filename + '.' + ext[2:]
        else:
            raise ValueError(_('We have a template with an extension that does not start with a t. Aborting.'))

        make.FileMakeObject.__init__(self, self.path)
        self.add_file_dependency(shared_tpl_name)

    def build(self):
        logging.info(_("TPL %%SHAREDDIR%%/%s") % os.path.basename(self.path))
        logging.debug("(%s)" % self.path)
        self.tpl.dump(self.tpl_vars, self.path)


# vim: ts=4 sw=4 expandtab
