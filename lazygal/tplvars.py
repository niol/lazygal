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

from . import pathutils


FILESIZE_UNIT_PREFIXES = (
    ("T", 2**40),
    ("G", 2**30),
    ("M", 2**20),
    ("K", 2**10),
)


def format_filesize(size_bytes):
    for unit_prefix, limit in FILESIZE_UNIT_PREFIXES:
        if size_bytes >= limit:
            return "%.1f %siB" % (round(float(size_bytes) / limit, 1), unit_prefix)
    return "%.1f B" % size_bytes


class TemplateVariables(object):

    def __init__(self, page):
        self.page = page


class Media(TemplateVariables):

    def __init__(self, page, webalbum_media):
        super().__init__(page)
        self.webalbum_media = webalbum_media
        self.media = webalbum_media.media

    def link(self):
        if self.webalbum_media:
            link_vals = {}

            link_vals["type"] = self.media.type

            if self.page.dir.album.theme.kind == "static":
                link_vals["link"] = self.webalbum_media.browse_pages[
                    self.page.size_name
                ].rel_path(self.page.dir, url=True)
            elif self.page.dir.album.theme.kind == "dynamic":
                link_vals["link"] = self.webalbum_media.resized[
                    self.page.size_name
                ].rel_path(self.page.dir, url=True)
            link_vals["link"] = pathutils.url_quote(link_vals["link"])

            link_vals["thumb"] = self.webalbum_media.thumb.rel_path(
                self.page.dir, url=True
            )
            link_vals["thumb"] = pathutils.url_quote(link_vals["thumb"])

            if not self.media.broken:
                link_vals["thumb_width"], link_vals["thumb_height"] = (
                    self.webalbum_media.thumb.get_size()
                )

            link_vals["thumb_name"] = self.page.dir.album._str_humanize(self.media.name)

            if self.page.dir.original:
                if self.page.dir.orig_base:
                    link_vals["original_link"] = posixpath.join(
                        pathutils.url_path(self.page.dir.source_dir.rel_root()),
                        self.page.dir.orig_base,
                        pathutils.url_path(self.page.dir.source_dir.strip_root()),
                        self.media.filename,
                    )
                else:
                    link_vals["original_link"] = self.media.filename
                link_vals["original_link"] = pathutils.url_quote(
                    link_vals["original_link"]
                )

            return link_vals
        else:
            return None


class Image(Media):

    def full(self):
        tpl_values = self.link()
        tpl_values["img_src"] = self.webalbum_media.resized[
            self.page.size_name
        ].filename
        tpl_values["img_src"] = pathutils.url_quote(tpl_values["img_src"])

        tpl_values["image_name"] = self.media.filename

        tpl_values["img_width"], tpl_values["img_height"] = self.webalbum_media.resized[
            self.page.size_name
        ].get_size()

        if self.page.dir.config.get("webgal", "publish-metadata"):
            tpl_values["publish_metadata"] = True
            tpl_values.update(self.media.md["metadata"])

            if tpl_values["comment"]:
                tpl_values["comment"] = self.page._do_not_escape(tpl_values["comment"])

            if "location" in tpl_values and not self.page.dir.config.get(
                "webgal", "keep-gps"
            ):
                del tpl_values["location"]

        return tpl_values


class Video(Media):

    def full(self):
        tpl_values = self.link()
        tpl_values["video_src"] = self.webalbum_media.resized[
            self.page.size_name
        ].rel_path(self.page.dir, url=True)
        tpl_values["video_src"] = pathutils.url_quote(tpl_values["video_src"])
        return tpl_values


def media_vars(page, webalbum_media):
    cls = None
    if webalbum_media.media.type == "image":
        cls = Image
    elif webalbum_media.media.type == "video":
        cls = Video
    else:
        raise NotImplementedError
    return cls(page, webalbum_media)


class SrcPath(TemplateVariables):

    def __init__(self, page, srcpath):
        super().__init__(page)
        self.srcpath = srcpath

    def should_be_flattened(self):
        return self.page.dir.should_be_flattened(self.srcpath)

    def id(self):
        if self.should_be_flattened():
            rawid = self.page.dir.source_dir.rel_path(
                self.page.dir.flattening_srcpath(self.srcpath), self.srcpath
            )
        else:
            rawid = os.path.basename(self.srcpath)
        return re.sub(r"[/ \\]", "_", rawid)

    def link(self):
        link_target = self.page._add_size_qualifier("index.html")

        # Add anchor target to get straight to gallery listing
        anchor = self.id() if self.should_be_flattened() else ""

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

        return pathutils.url_quote(link_target, anchor=anchor)

    def path(self):
        wg_path = []
        for dirmd in self.page.dir.source_dir.parents_metadata():
            wg = {}
            wg["link"] = SrcPath(self.page, dirmd.dir_path).link()
            wg["name"] = dirmd.get_title()
            wg["root"] = dirmd.dir_path == self.page.dir.album.source_dir
            wg["current"] = dirmd.dir_path == self.page.dir.source_dir.path
            wg_path.append(wg)

        wg_path.reverse()
        return wg_path


class Webgal(SrcPath):

    def __init__(self, page, webgal):
        super().__init__(page, webgal.source_dir.path)
        self.webgal = webgal

    def info(self):
        dir_info = {}
        if self.webgal.source_dir.metadata:
            dir_info.update(self.webgal.source_dir.metadata.get())

        for html_key in ("album_name", "album_description"):
            if html_key in dir_info:
                dir_info[html_key] = self.page._do_not_escape(dir_info[html_key])

        if "album_name" not in dir_info:
            dir_info["album_name"] = self.webgal.source_dir.human_name

        dirzip = self.webgal.webassets.data["dirzip"]
        if dirzip:
            archive_rel_dir = self.webgal.rel_path(self.page.dir.path)
            archive_rel_path = posixpath.join(archive_rel_dir, dirzip["filename"])
            dir_info["dirzip"] = pathutils.url_quote(archive_rel_path)
            dir_info["dirzip_size"] = dirzip["sizestr"]

        dir_info["is_main"] = self.webgal is self.page.dir

        dir_info["image_count"] = self.webgal.pindex.get_media_count("image")
        dir_info["subgal_count"] = len(self.webgal.source_dir.subdirs)

        dir_info["id"] = pathutils.url_quote(self.id())

        return dir_info

    def link_info(self):
        link_info = self.info()
        link_info["link"] = self.link()
        link_info["album_picture"] = posixpath.join(
            self.webgal.source_dir.name, self.webgal.get_webalbumpic_filename()
        )
        link_info["album_picture"] = pathutils.url_quote(link_info["album_picture"])
        return link_info


# vim: ts=4 sw=4 expandtab
