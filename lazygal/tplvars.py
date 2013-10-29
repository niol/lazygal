# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2013 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import re
import posixpath

import pathutils


class TemplateVariables(object):

    def __init__(self, page):
        self.page = page


class Media(TemplateVariables):

    def __init__(self, page, webalbum_media):
        super(Media, self).__init__(page)
        self.webalbum_media = webalbum_media
        self.media = webalbum_media.media

    def link(self):
        if self.webalbum_media:
            link_vals = {}

            link_vals['type'] = self.media.type

            if self.page.dir.album.theme.kind == 'static':
                link_vals['link'] = self.webalbum_media.browse_pages[self.page.size_name].rel_path(self.page.dir, url=True)
            elif self.page.dir.album.theme.kind == 'dynamic':
                link_vals['link'] = self.webalbum_media.resized[self.page.size_name].rel_path(self.page.dir, url=True)
            link_vals['link'] = self.page.url_quote(link_vals['link'])

            link_vals['thumb'] = self.webalbum_media.thumb.rel_path(self.page.dir, url=True)
            link_vals['thumb'] = self.page.url_quote(link_vals['thumb'])

            if not self.media.broken:
                link_vals['thumb_width'],\
                    link_vals['thumb_height'] = self.webalbum_media.thumb.get_size()

            link_vals['thumb_name'] = self.page.dir.album._str_humanize(self.media.name)

            return link_vals
        else:
            return None


class Image(Media):

    def full(self):
        tpl_values = self.link()
        tpl_values['img_src'] = self.webalbum_media.resized[self.page.size_name].filename
        tpl_values['img_src'] = self.page.url_quote(tpl_values['img_src'])

        tpl_values['image_name'] = self.media.filename

        tpl_values['img_width'], tpl_values['img_height'] = self.webalbum_media.resized[self.page.size_name].get_size()

        if self.page.dir.config.getboolean('webgal', 'publish-metadata'):
            tpl_values['publish_metadata'] = True
            img_date = self.media.get_date_taken()
            tpl_values['image_date'] = img_date.strftime(_("on %d/%m/%Y at %H:%M"))
            tpl_values['image_datetime'] = img_date

            image_info = self.media.info()
            if image_info:
                comment = image_info.get_comment()
                if comment == '' or comment is None:
                    tpl_values['comment'] = None
                else:
                    tpl_values['comment'] = self.page._do_not_escape(comment)

                tpl_values['camera_name'] = image_info.get_camera_name()
                tpl_values['lens_name'] = image_info.get_lens_name()
                tpl_values['flash'] = image_info.get_flash()
                tpl_values['exposure'] = image_info.get_exposure()
                tpl_values['iso'] = image_info.get_iso()
                tpl_values['fnumber'] = image_info.get_fnumber()
                tpl_values['focal_length'] = image_info.get_focal_length()
                tpl_values['authorship'] = image_info.get_authorship()

        return tpl_values


class Video(Media):

    def full(self):
        tpl_values = self.link()
        tpl_values['video_src'] = self.webalbum_media.resized[self.page.size_name].filename
        tpl_values['video_src'] = self.page.url_quote(tpl_values['video_src'])
        return tpl_values


def media_vars(page, webalbum_media):
    cls = None
    if webalbum_media.media.type == 'image':
        cls = Image
    elif webalbum_media.media.type == 'video':
        cls = Video
    else:
        raise NotImplementedError
    return cls(page, webalbum_media)


class SrcPath(TemplateVariables):

    def __init__(self, page, srcpath):
        super(SrcPath, self).__init__(page)
        self.srcpath = srcpath

    def should_be_flattened(self):
        return self.page.dir.should_be_flattened(self.srcpath)

    def id(self):
        if self.should_be_flattened():
            rawid = self.page.dir.source_dir.rel_path(self.page.dir.flattening_srcpath(self.srcpath), self.srcpath)
        else:
            rawid = os.path.basename(self.srcpath)
        return re.sub(r'[/ \\]', '_', rawid)

    def link(self):
        link_target = self.page._add_size_qualifier('index.html')

        if self.should_be_flattened():
            # Add anchor target to get straight to gallery listing
            link_target = link_target + '#' + self.id()

        # Add relative path to link if needed
        index_path = None
        if self.should_be_flattened():
            index_path = self.page.dir.flattening_srcpath(self.srcpath)
        elif self.srcpath != self.page.dir.source_dir.path:
            index_path = self.srcpath
        if index_path is not None:
            index_path = self.page.dir.rel_path_to_src(index_path)
            index_path = pathutils.url_path(index_path)
            link_target = posixpath.join(index_path, link_target)

        return self.page.url_quote(link_target)

    def path(self):
        wg_path = []
        for dirmd in self.page.dir.source_dir.parents_metadata():
            wg = {}
            wg['link'] = SrcPath(self.page, dirmd.dir_path).link()
            wg['name'] = dirmd.get_title()
            wg['root'] = dirmd.dir_path == self.page.dir.album.source_dir
            wg['current'] = dirmd.dir_path == self.page.dir.source_dir.path
            wg_path.append(wg)

        wg_path.reverse()
        return wg_path


class Webgal(SrcPath):

    def __init__(self, page, webgal):
        super(Webgal, self).__init__(page, webgal.source_dir.path)
        self.webgal = webgal

    def info(self):
        dir_info = {}
        if self.webgal.source_dir.metadata:
            dir_info.update(self.webgal.source_dir.metadata.get())
            if 'album_description' in dir_info.keys():
                dir_info['album_description'] =\
                    self.page._do_not_escape(dir_info['album_description'])

        if 'album_name' not in dir_info:
            dir_info['album_name'] = self.webgal.source_dir.human_name

        if self.webgal.dirzip:
            archive_rel_path = self.webgal.dirzip.rel_path(self.page.dir,
                                                           url=True)
            dir_info['dirzip'] = self.page.url_quote(archive_rel_path)
            dir_info['dirzip_size'] = self.page.format_filesize(self.webgal.dirzip.size())

        dir_info['is_main'] = self.webgal is self.page.dir

        dir_info['image_count'] = self.webgal.get_media_count('image')
        dir_info['subgal_count'] = len(self.webgal.source_dir.subdirs)

        dir_info['id'] = self.page.url_quote(self.id())

        return dir_info

    def link_info(self):
        link_info = self.info()
        link_info['link'] = self.link()
        link_info['album_picture'] = \
                posixpath.join(self.webgal.source_dir.name,
                               self.webgal.get_webalbumpic_filename())
        link_info['album_picture'] = self.page.url_quote(link_info['album_picture'])
        return link_info


# vim: ts=4 sw=4 expandtab
