#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2011 Michal Čihař, Mickaël Royer, Alexandre Rossi
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

from distutils.core import setup, Command
import distutils.sysconfig
import distutils.command.build_scripts
import distutils.command.build
from distutils.dep_util import newer
from distutils.spawn import find_executable
import re
import os
import sys
import glob
import lazygal
from stat import ST_MODE


class test_lazygal(Command):

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import lazygaltest
        lazygaltest.run()


class build_manpages(Command):
    manpages = None
    db2mans = [
        # debian
        "/usr/share/sgml/docbook/stylesheet/xsl/nwalsh/manpages/docbook.xsl",
        # gentoo
        "/usr/share/sgml/docbook/xsl-stylesheets/manpages/docbook.xsl",
        ]
    mandir = "./"
    executable = find_executable('xsltproc')

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.manpages = glob.glob(os.path.join(self.mandir, "*.xml"))

    def __get_man_section(self, filename):
        # filename should be file.mansection.xml
        return filename.split('.')[-2]

    def run(self):
        data_files = self.distribution.data_files
        db2man = None
        for path in self.__class__.db2mans:
            if os.path.exists(path):
                db2man = path
                continue

        for xmlmanpage in self.manpages:
            manpage = xmlmanpage[:-4] # remove '.xml' at the end
            section = manpage[-1:]
            if newer(xmlmanpage, manpage):
                cmd = (self.executable, "--nonet", "-o", self.mandir, db2man,
                       xmlmanpage)
                self.spawn(cmd)

            targetpath = os.path.join("share", "man", 'man%s' % section)
            data_files.append((targetpath, (manpage, ), ))


class build_i18n_lazygal(Command):
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
            mo_dir =  os.path.join("build", "mo", lang, "LC_MESSAGES")
            mo_file = os.path.join(mo_dir, "%s.mo" % self.po_package)
            if not os.path.exists(mo_dir):
                os.makedirs(mo_dir)

            cmd = ["msgfmt", po_file, "-o", mo_file]
            self.spawn(cmd)

            targetpath = os.path.join("share/locale", lang, "LC_MESSAGES")
            data_files.append((targetpath, (mo_file,)))


class build_lazygal(distutils.command.build.build):

    def __has_manpages(self, command):
        has_db2man = False
        for path in build_manpages.db2mans:
            if os.path.exists(path): has_db2man = True
        return 'build_manpages' in self.distribution.cmdclass\
            and has_db2man and build_manpages.executable != None

    def __has_i18n(self, command):
        return 'build_i18n' in self.distribution.cmdclass

    def finalize_options(self):
        distutils.command.build.build.finalize_options(self)
        self.sub_commands.append(("build_i18n", self.__has_i18n))
        self.sub_commands.append(("build_manpages", self.__has_manpages))


# check if Python is called on the first line with this expression
first_line_re = re.compile('^#!.*python[0-9.]*([ \t].*)?$')

class build_scripts_lazygal(distutils.command.build_scripts.build_scripts, object):
    '''
    This is mostly distutils copy, it just renames script according
    to platform (.py for Windows, without extension for others)
    '''
    def copy_scripts (self):
        """Copy each script listed in 'self.scripts'; if it's marked as a
        Python script in the Unix way (first line matches 'first_line_re',
        ie. starts with "\#!" and contains "python"), then adjust the first
        line to refer to the current Python interpreter as we copy.
        """
        self.mkpath(self.build_dir)
        outfiles = []
        for script in self.scripts:
            adjust = 0
            script = distutils.util.convert_path(script)
            outfile = os.path.join(self.build_dir, os.path.splitext(os.path.basename(script))[0])
            if sys.platform == 'win32':
                outfile += os.extsep + 'py'
            outfiles.append(outfile)

            if not self.force and not distutils.dep_util.newer(script, outfile):
                distutils.log.debug("not copying %s (up-to-date)", script)
                continue

            # Always open the file, but ignore failures in dry-run mode --
            # that way, we'll get accurate feedback if we can read the
            # script.
            try:
                f = open(script, "r")
            except IOError:
                if not self.dry_run:
                    raise
                f = None
            else:
                first_line = f.readline()
                if not first_line:
                    self.warn("%s is an empty file (skipping)" % script)
                    continue

                match = first_line_re.match(first_line)
                if match:
                    adjust = 1
                    post_interp = match.group(1) or ''

            if adjust:
                distutils.log.info("copying and adjusting %s -> %s", script,
                         self.build_dir)
                if not self.dry_run:
                    outf = open(outfile, "w")
                    if not distutils.sysconfig.python_build:
                        outf.write("#!%s%s\n" %
                                   (os.path.normpath(sys.executable),
                                    post_interp))
                    else:
                        outf.write("#!%s%s\n" %
                                   (os.path.join(
                            distutils.sysconfig.get_config_var("BINDIR"),
                            "python" + distutils.sysconfig.get_config_var("EXE")),
                                    post_interp))
                    outf.writelines(f.readlines())
                    outf.close()
                if f:
                    f.close()
            else:
                f.close()
                self.copy_file(script, outfile)

        if os.name == 'posix':
            for file in outfiles:
                if self.dry_run:
                    distutils.log.info("changing mode of %s", file)
                else:
                    oldmode = os.stat(file)[ST_MODE] & 07777
                    newmode = (oldmode | 0555) & 07777
                    if newmode != oldmode:
                        distutils.log.info("changing mode of %s from %o to %o",
                                 file, oldmode, newmode)
                        os.chmod(file, newmode)

    # copy_scripts ()


# list themes to install
theme_data = []
themes = glob.glob(os.path.join('themes', '*'))
for theme in themes:
    themename = os.path.basename(theme)
    theme_data.append(
            (os.path.join('share','lazygal','themes', themename),
                glob.glob(os.path.join('themes', themename, '*'))))

setup(name = 'lazygal',
    version = lazygal.__version__,
    description = 'Static web gallery generator',
    long_description = '',
    author = 'Alexandre Rossi',
    author_email = 'alexandre.rossi@gmail.com',
    maintainer = 'Alexandre Rossi',
    maintainer_email = 'alexandre.rossi@gmail.com',
    platforms = ['Linux', 'Mac OSX', 'Windows XP/2000/NT', 'Windows 95/98/ME'],
    keywords = ['gallery', 'exif', 'photo', 'image'],
    url = 'http://sousmonlit.dyndns.org/~niol/playa/oss/projects/lazygal',
    download_url = 'http://sousmonlit.dyndns.org/~niol/playa/oss/projects/lazygal',
    license = 'GPL',
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Win32 (MS Windows)',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: Microsoft :: Windows :: Windows 95/98/2000',
        'Operating System :: Microsoft :: Windows :: Windows NT/2000',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Topic :: Utilities',
        'Natural Language :: English',
    ],
    packages = ['lazygal'],
    package_data = {'lazygal': ['defaults.conf'], },
    scripts = ['lazygal.py'],
    # Override certain command classes with our own ones
    cmdclass = {
        'build'         : build_lazygal,
        'build_scripts' : build_scripts_lazygal,
        'build_i18n'    : build_i18n_lazygal,
        'build_manpages': build_manpages,
        'test'          : test_lazygal,
        },
    data_files = theme_data
    )

# vim: ts=4 sw=4 expandtab
