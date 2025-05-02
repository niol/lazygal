#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2007-2012 Michal Čihař, Mickaël Royer, Alexandre Rossi
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


import glob
import gettext
import json
import locale
import os
import os.path
import re
import shutil
import stat
import sys
import urllib.request


import setuptools
import setuptools.command.build_py


import lazygal


gettext.install("lazygal")


def newer(fpath1, fpath2):
    if os.path.isfile(fpath2):
        return os.path.getmtime(fpath1) > os.path.getmtime(fpath2)
    else:
        return True


class test_lazygal(setuptools.Command):

    description = "Run the test suite"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import lazygaltest

        lazygaltest.run()


class dl_assets(setuptools.Command):

    description = "Download extra assets if not provided by the system"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import lazygal.theme

        for t in lazygal.theme.get_themes():
            for a in t.get_missing_external_assets():
                asset_file = urllib.request.urlopen(a["url"])
                setuptools.log.info(
                    "downloading %s into %s" % (a["url"], a["abs_dest"])
                )
                with open(a["abs_dest"], "wb") as output:
                    output.write(asset_file.read())


class sample_album(setuptools.Command):

    description = "Generate a sample album for testing purposes"
    user_options = [("outdir=", None, "Output directory")]

    def initialize_options(self):
        self.outdir = None

    def finalize_options(self):
        assert self.outdir is not None, "Output directory is mandatory"

    def run(self):
        import lazygaltest

        lazygaltest.sample_album(self.outdir)


class build_manpages(setuptools.Command):

    description = "Build manpages"
    user_options = []

    manpages = None
    mandir = os.path.join(os.path.dirname(__file__), "man")
    executable = shutil.which("pandoc")

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.manpages = glob.glob(os.path.join(self.mandir, "*.md"))

    def __get_man_section(self, filename):
        # filename should be file.mansection.md
        return filename.split(".")[-2]

    def run(self):
        data_files = self.distribution.data_files

        for manpagesrc in self.manpages:
            manpage = os.path.splitext(manpagesrc)[0]  # remove '.md' at the end
            section = manpage[-1:]
            if newer(manpagesrc, manpage):
                cmd = [self.executable, "-s", "-t", "man", "-o", manpage, manpagesrc]
                self.spawn(cmd)

            targetpath = os.path.join("share", "man", "man%s" % section)
            data_files.append(
                (
                    targetpath,
                    (manpage,),
                )
            )


class build_i18n_lazygal(setuptools.Command):

    description = "Build i18n files"
    user_options = []
    po_package = None
    po_directory = None
    po_files = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.po_directory = "locale"
        self.po_package = "lazygal"
        self.po_files = glob.glob(os.path.join(self.po_directory, "*.po"))

    def run(self):
        data_files = self.distribution.data_files

        for po_file in self.po_files:
            lang = os.path.basename(po_file[:-3])
            mo_dir = os.path.join("build", "mo", lang, "LC_MESSAGES")
            mo_file = os.path.join(mo_dir, "%s.mo" % self.po_package)
            if not os.path.exists(mo_dir):
                os.makedirs(mo_dir)

            cmd = ["msgfmt", po_file, "-o", mo_file]
            self.spawn(cmd)

            targetpath = os.path.join("share/locale", lang, "LC_MESSAGES")
            data_files.append((targetpath, (mo_file,)))


class build_lazygal(setuptools.command.build_py.build_py):

    def __has_manpages(self, command):
        return (
            "build_manpages" in self.distribution.cmdclass
            and build_manpages.executable is not None
        )

    def __has_i18n(self, command):
        return "build_i18n" in self.distribution.cmdclass

    def run(self):
        if build_manpages.executable is not None:
            self.run_command("build_manpages")
        self.run_command("build_i18n")
        super(build_lazygal, self).run()


# list themes to install
theme_data = []
themes = glob.glob(os.path.join("themes", "*"))
for theme in themes:
    themename = os.path.basename(theme)
    theme_data.append(
        (
            os.path.join("share", "lazygal", "themes", themename),
            glob.glob(os.path.join("themes", themename, "*")),
        )
    )


setuptools.setup(
    name="lazygal",
    version=lazygal.__version__,
    description="Static web gallery generator",
    long_description="",
    author="Alexandre Rossi",
    author_email="alexandre.rossi@gmail.com",
    maintainer="Alexandre Rossi",
    maintainer_email="alexandre.rossi@gmail.com",
    platforms=["Linux", "Mac OSX", "Windows XP/2000/NT", "Windows 95/98/ME"],
    keywords=["gallery", "exif", "photo", "image"],
    url="https://sml.zincube.net/~niol/repositories.git/lazygal/about/",
    download_url="https://sml.zincube.net/~niol/repositories.git/lazygal/",
    license="GPL",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: Microsoft :: Windows :: Windows 95/98/2000",
        "Operating System :: Microsoft :: Windows :: Windows NT/2000",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Topic :: Utilities",
        "Natural Language :: English",
    ],
    packages=["lazygal"],
    package_data={
        "lazygal": ["defaults.json"],
    },
    entry_points={
        "console_scripts": [
            "lazygal = lazygal.cmdline:main",
        ]
    },
    cmdclass={
        "build_py": build_lazygal,
        "build_i18n": build_i18n_lazygal,
        "build_manpages": build_manpages,
        "dl_assets": dl_assets,
        "test": test_lazygal,
        "sample_album": sample_album,
    },
    data_files=theme_data,
)

# vim: ts=4 sw=4 expandtab
