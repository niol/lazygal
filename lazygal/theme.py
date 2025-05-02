# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2019 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import glob
import logging
import json
import codecs
import locale

from . import pathutils


DEFAULT_THEME = "nojs"
USER_THEME_DIR = os.path.expanduser(os.path.join("~", ".lazygal", "themes"))
THEME_SHARED_FILE_PREFIX = "SHARED_"
THEME_MANIFEST = "manifest.json"


class Theme(object):

    def __init__(self, themes_dir, name):
        self.name = name
        self.themes_dir = themes_dir

        # First try user directory
        self.tpl_dir = os.path.join(USER_THEME_DIR, self.name)
        if not os.path.exists(self.tpl_dir):
            # Fallback to system themes
            self.tpl_dir = os.path.join(themes_dir, self.name)
            if not os.path.exists(self.tpl_dir):
                raise ValueError(_("Theme %s not found") % self.name)
        self.tpl_dir = os.path.abspath(self.tpl_dir)

        self.__load_manifest()

    def prepare_tpl_loader(self, tplfactory):
        self.tpl_loader = tplfactory(
            os.path.join(self.themes_dir, DEFAULT_THEME), self.tpl_dir
        )

        # Load styles templates
        for style in self.get_avail_styles():
            style_filename = style["filename"]
            try:
                self.tpl_loader.load(style_filename)
            except ValueError:
                # Not a known emplate ext, ignore
                pass

        # find out theme kind
        try:
            self.tpl_loader.load("dynindex.thtml")
        except:
            self.kind = "static"
        else:
            self.kind = "dynamic"

    def __load_manifest(self):
        theme_manifest_path = os.path.join(self.tpl_dir, THEME_MANIFEST)
        theme_manifest = {}
        try:
            with codecs.open(
                theme_manifest_path, "r", locale.getpreferredencoding()
            ) as f:
                theme_manifest.update(json.load(f))
        except IOError:
            logging.debug(_("Theme %s does not have a %s"), self.name, THEME_MANIFEST)
        except ValueError:
            logging.error(_("Theme %s : %s parsing error"), self.name, THEME_MANIFEST)
            raise

        if "shared" not in theme_manifest:
            theme_manifest["shared"] = []

        self.shared_files = []

        for s in theme_manifest["shared"]:
            shared = s.copy()
            if type(s["path"]) is not list:
                s["path"] = [s["path"]]

            for path in s["path"]:
                if not path.startswith("/"):
                    path = os.path.join(self.tpl_dir, path)

                if os.path.isfile(path):
                    shared["source"] = os.path.abspath(path)

            if "dest" in s:
                shared["dest"] = s["dest"]
                if shared["dest"].endswith("/"):  # this is a directory
                    shared["dest"] = os.path.join(
                        shared["dest"], os.path.basename(shared["source"])
                    )
            else:
                shared["dest"] = os.path.basename(s["source"])

            shared["abs_dest"] = os.path.join(self.tpl_dir, shared["dest"])

            self.shared_files.append(shared)

        for s in glob.glob(os.path.join(self.tpl_dir, THEME_SHARED_FILE_PREFIX + "*")):
            dest_fn = os.path.basename(s)[len(THEME_SHARED_FILE_PREFIX) :]
            self.shared_files.append(
                {
                    "source": s,
                    "path": [s],
                    "dest": dest_fn,
                    "abs_dest": os.path.join(self.tpl_dir, dest_fn),
                }
            )

    def get_missing_external_assets(self):
        return [s for s in self.shared_files if "source" not in s]

    def check_shared_files(self):
        missing = self.get_missing_external_assets()
        if missing:
            raise ValueError(
                _(
                    "Theme %s: %s reference error: "
                    "files not found:\n%s"
                    "\n\nThe following actions may fix this:\n"
                    "\t- Running ./setup.py dl_assets\n"
                    "\t- Installing deps from your distribution"
                )
                % (
                    self.name,
                    THEME_MANIFEST,
                    "\n".join(["\t" + m["abs_dest"] for m in missing]),
                )
            )

    def get_avail_styles(self, default_style=None):
        style_files_mask = os.path.join(
            self.tpl_dir, THEME_SHARED_FILE_PREFIX + "*" + "css"
        )
        styles = []
        found_default = default_style is None
        for style_tpl_file in glob.glob(style_files_mask):
            style = {}
            tpl_filename = os.path.basename(style_tpl_file).split(".")[0]
            style["filename"] = tpl_filename[len(THEME_SHARED_FILE_PREFIX) :]
            style["name"] = style["filename"].replace("_", " ")
            if default_style is not None:
                if style["filename"] == default_style:
                    style["rel"] = "stylesheet"
                    found_default = True
                else:
                    style["rel"] = "alternate stylesheet"
            styles.append(style)

        if not found_default:
            logging.error(_("Unknown default style '%s'") % default_style)

        return styles


def get_themes():
    source_theme_dir = os.path.join(os.path.dirname(__file__), "..", "themes")
    return [Theme(source_theme_dir, tn) for tn in os.listdir(source_theme_dir)]


# vim: ts=4 sw=4 expandtab
