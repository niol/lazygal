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
import posixpath
import sys
import logging

import genshi

from . import make
from . import pathutils
from . import genfile
from . import feeds
from . import tplvars


class WebalbumPage(genfile.WebalbumFile):

    def __init__(self, dir, size_name, base_name):
        self.dir = dir
        self.size_name = size_name

        page_filename = self._add_size_qualifier(base_name + ".html", self.size_name)
        super().__init__(os.path.join(dir.path, page_filename), dir)

        self.page_template = None

    def set_template(self, tpl_ident):
        self.page_template = self.load_tpl(tpl_ident)

    def load_tpl(self, tpl_ident):
        tpl = self.dir.album.theme.tpl_loader.load(tpl_ident)
        self.add_file_dependency(tpl.path)
        for subtpl in tpl.subtemplates():
            self.add_file_dependency(subtpl.path)
        return tpl

    def init_tpl_values(self):
        tpl_values = {}
        tpl_values.update(self.dir.tpl_vars)
        return tpl_values

    def _get_osize_links(self, filename):
        osize_index_links = []
        for osize_name in self.dir.browse_sizes:
            osize_info = {}
            if osize_name == self.size_name:
                # No link if we're on the current page
                osize_info["name"] = osize_name
            else:
                osize_info["name"] = osize_name
                osize_info["link"] = self._add_size_qualifier(
                    filename + ".html", osize_name
                )
                osize_info["link"] = pathutils.url_quote(osize_info["link"])
            osize_index_links.append(osize_info)

        return osize_index_links

    def _add_size_qualifier(self, path, size_name=None):
        if size_name is None:
            size_name = self.size_name

        return self.dir._add_size_qualifier(path, size_name)

    def _do_not_escape(self, value):
        return genshi.core.Markup(value)


class WebalbumBrowsePage(WebalbumPage):

    def __init__(self, dir, size_name, webalbum_media):
        self.webalbum_media = webalbum_media
        self.media = self.webalbum_media.media
        super().__init__(dir, size_name, self.media.name)

        self.add_dependency(self.webalbum_media.resized[size_name])
        if (
            self.webalbum_media.original
            and self.webalbum_media.original not in self.deps
        ):
            self.add_dependency(self.webalbum_media.original)

        # Depends on source directory in case an image was deleted
        self.add_dependency(self.dir.source_dir)

        # Depend on the comment file if it exists.
        if self.webalbum_media.media.comment_file_path is not None:
            self.add_file_dependency(self.webalbum_media.media.comment_file_path)

        self.add_dependency(self.dir.sort_task)

        self.set_template("browse.thtml")
        self.load_tpl(self.media.type + ".thtml")

    def add_extra_vals(self, tpl_values):
        tpl_values.update(tplvars.media_vars(self, self.webalbum_media).full())

    def build(self):
        page_rel_path = self.rel_path(self.dir.flattening_dir)
        logging.info(_("  XHTML %s"), page_rel_path)
        logging.debug("(%s)", self._path)

        tpl_values = self.init_tpl_values()

        # Breadcrumbs
        tpl_values["webgal_path"] = tplvars.Webgal(self, self.dir).path()

        tpl_values["name"] = self.media.filename
        tpl_values["mediatype"] = self.media.type
        tpl_values["dir"] = self.dir.source_dir.strip_root()

        prev = self.webalbum_media.previous
        if prev:
            tpl_values["prev_link"] = tplvars.Media(self, prev).link()

        next = self.webalbum_media.next
        if next:
            tpl_values["next_link"] = tplvars.Media(self, next).link()

        tpl_values["index_link"] = self._add_size_qualifier(
            "index.html", self.size_name
        )
        if self.dir.should_be_flattened():
            index_rel_dir = self.dir.flattening_dir.source_dir.rel_path(
                self.dir.source_dir
            )
            tpl_values["index_link"] = index_rel_dir + tpl_values["index_link"]

        tpl_values["osize_links"] = self._get_osize_links(self.media.name)
        tpl_values["rel_root"] = (
            pathutils.url_path(self.dir.source_dir.rel_root()) + "/"
        )

        if self.dir.feed is not None:
            tpl_values["feed_url"] = os.path.relpath(self.dir.feed.path, self.dir.path)
            tpl_values["feed_url"] = pathutils.url_path(tpl_values["feed_url"])
            tpl_values["feed_url"] = pathutils.url_quote(tpl_values["feed_url"])
        else:
            tpl_values["feed_url"] = None

        self.add_extra_vals(tpl_values)

        self.page_template.dump(tpl_values, self._path)


class WebalbumIndexPage(WebalbumPage):

    FILENAME_BASE_STRING = "index"

    def __init__(self, dir, size_name, page_number, subgals, galleries):
        page_paginated_name = self._get_paginated_name(page_number)
        super().__init__(dir, size_name, page_paginated_name)

        self.page_number = page_number
        self.subgals = subgals
        self.galleries = galleries

        for dir, medias in self.galleries:
            self.add_dependency(dir.source_dir.metadata)
            if dir is not self.dir:
                dir.flattening_dir = self.dir

            self.add_dependency(dir.pindex)
            self.add_dependency(dir.webassets)
            self.add_dependency(dir.sort_task)

            if size_name in dir.browse_sizes:
                for media in medias:
                    if media.thumb:
                        self.add_dependency(media.thumb)
                    if self.dir.album.theme.kind == "static":
                        self.add_dependency(media.browse_pages[size_name])
                        # Ensure dir depends on browse page (usefull for cleanup
                        # checks when dir is flattenend).
                        if self.dir.should_be_flattened():
                            dir.add_dependency(media.browse_pages[size_name])
            else:
                logging.warning(
                    _(
                        "  Size '%s' is not available in '%s' due to configuration: medias won't be shown on index."
                    ),
                    size_name,
                    dir.path,
                )

        if self.dir.album.theme.kind == "static":
            self.set_template("dirindex.thtml")
        elif self.dir.album.theme.kind == "dynamic":
            self.set_template("dynindex.thtml")

    def _get_paginated_name(self, page_number=None):
        if page_number is None:
            page_number = self.page_number
        assert page_number is not None

        if page_number < 1:
            return WebalbumIndexPage.FILENAME_BASE_STRING
        else:
            return "_".join([WebalbumIndexPage.FILENAME_BASE_STRING, str(page_number)])

    def _get_related_index_fn(self):
        return self._add_size_qualifier(
            WebalbumIndexPage.FILENAME_BASE_STRING + ".html", self.size_name
        )

    def _get_onum_links(self):
        onum_index_links = []
        for onum in range(0, self.dir.break_task.how_many_pages()):
            onum_info = {
                "name": onum + 1,
            }
            if onum != self.page_number:  # No link if we're on the current page
                filename = self._get_paginated_name(onum)
                onum_info["link"] = self._add_size_qualifier(
                    filename + ".html", self.size_name
                )
                onum_info["link"] = pathutils.url_quote(onum_info["link"])
            onum_index_links.append(onum_info)

        return onum_index_links

    def _get_subgal_links(self):
        subgal_links = []
        for subgal in self.dir.subgals:
            dir_info = tplvars.Webgal(self, subgal).link_info()
            subgal_links.append(dir_info)
        return subgal_links

    def build(self):
        logging.info(_("  XHTML %s"), os.path.basename(self._path))
        logging.debug("(%s)", self._path)

        values = self.init_tpl_values()

        # Breadcrumbs (current is static, see dirindex.thtml, that's why the
        # last item of the list is removed).
        values["webgal_path"] = tplvars.Webgal(self, self.dir).path()[:-1]

        if not self.dir.source_dir.is_album_root():
            # Parent index link not for album root
            values["parent_index_link"] = self._get_related_index_fn()

        values["osize_index_links"] = self._get_osize_links(self._get_paginated_name())
        values["onum_index_links"] = self._get_onum_links()

        if self.dir.flatten_below():
            values["subgal_links"] = []
        else:
            values["subgal_links"] = self._get_subgal_links()

        values["medias"] = []
        for subdir, medias in self.galleries:
            info = tplvars.Webgal(self, subdir).info()
            if self.size_name in subdir.browse_sizes:
                media_links = [
                    tplvars.media_vars(self, media).full() for media in medias
                ]
            else:
                # This happens when this dir index size is not available in the
                # subdir.
                media_links = []
            values["medias"].append(
                (
                    info,
                    media_links,
                )
            )

        values.update(tplvars.Webgal(self, self.dir).info())

        values["rel_root"] = pathutils.url_path(self.dir.source_dir.rel_root()) + "/"
        values["rel_path"] = pathutils.url_path(self.dir.source_dir.strip_root())

        if self.dir.feed is not None:
            values["feed_url"] = os.path.relpath(self.dir.feed.path, self.dir.path)
            values["feed_url"] = pathutils.url_path(values["feed_url"])
            values["feed_url"] = pathutils.url_quote(values["feed_url"])
        else:
            values["feed_url"] = None

        self.page_template.dump(values, self._path)


class WebalbumFeed(make.FileMakeObject):

    def __init__(self, album, dir_path, pub_url):
        self.path = os.path.join(dir_path, "index.xml")
        super().__init__(self.path)

        self.album = album
        self.pub_url = pub_url
        if not self.pub_url:
            self.pub_url = "http://example.com"
        if not self.pub_url.endswith("/"):
            self.pub_url = self.pub_url + "/"

        self.feed = feeds.RSS20(self.pub_url)
        self.item_template = self.album.theme.tpl_loader.load("feeditem.thtml")

        self.webgals = []

    def set_title(self, title):
        self.feed.title = title

    def set_description(self, description):
        self.feed.description = description

    def push_dir(self, webalbumdir):
        self.webgals.append(webalbumdir)

    def __add_item(self, webalbumdir):
        url = os.path.join(self.pub_url, webalbumdir.source_dir.strip_root())

        desc_values = {}
        desc_values["album_pic_path"] = os.path.join(
            url, webalbumdir.get_webalbumpic_filename()
        )
        desc_values["subgal_count"] = webalbumdir.get_subgal_count()
        desc_values["picture_count"] = webalbumdir.pindex.get_media_count("image")
        desc_values["desc"] = webalbumdir.source_dir.desc
        desc = self.item_template.instanciate(desc_values)

        self.feed.push_item(
            webalbumdir.source_dir.title, url, desc, webalbumdir.source_dir.get_mtime()
        )

    def populate_deps(self):
        wouldbe_deps = sorted(self.webgals, key=lambda s: s.get_mtime())[-10:]

        for webalbumdir in wouldbe_deps:
            if webalbumdir.has_media():
                self.add_dependency(webalbumdir.source_dir)
                self.__add_item(webalbumdir)

    def build(self):
        logging.info(_("FEED %s"), os.path.basename(self.path))
        logging.debug("(%s)", self.path)
        self.feed.dump(self.path)


class SharedFileTemplate(make.FileMakeObject):

    def __init__(self, album, shared_tpl_name, shared_file_dest_tplname, tpl_vars):
        self.album = album
        self.tpl = self.album.theme.tpl_loader.load(shared_tpl_name)
        self.tpl_vars = tpl_vars

        # Remove the 't' from the beginning of ext
        filename, ext = os.path.splitext(shared_file_dest_tplname)
        if ext.startswith(".t"):
            self.path = filename + "." + ext[2:]
        else:
            raise ValueError(
                _(
                    "We have a template with an extension that does not start with a t. Aborting."
                )
            )

        super().__init__(self.path)
        self.add_file_dependency(shared_tpl_name)

    def build(self):
        logging.info(_("TPL %%SHAREDDIR%%/%s"), os.path.basename(self.path))
        logging.debug("(%s)", self.path)
        self.tpl.dump(self.tpl_vars, self.path)


# vim: ts=4 sw=4 expandtab
