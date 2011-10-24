#!/usr/bin/env python
#
# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import sys, os, locale, gettext
import logging
from optparse import OptionParser


# i18n
from lazygal import INSTALL_MODE, INSTALL_PREFIX
if INSTALL_MODE == 'source':
    LOCALES_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                                 'build', 'mo'))
elif INSTALL_MODE == 'installed':
    LOCALES_PATH = os.path.join(INSTALL_PREFIX, 'share', 'locale')
gettext.install('lazygal', LOCALES_PATH, unicode=1)

locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())


import lazygal
from lazygal.generators import Album
import lazygal.config


usage = _("usage: %prog [options] albumdir")
parser = OptionParser(usage=usage)

# The help option must be changed to comply with i18n.
parser.get_option('-h').help = _("Show this help message and exit.")

parser.add_option("", "--quiet",
                  action="store_true",
                  dest="quiet",
                  help=_("Don't output anything except for errors."))
parser.add_option("", "--debug",
                  action="store_true",
                  dest="debug",
                  help=_("Output everything that lazygal is doing."))
parser.add_option("-o", "--output-directory",
                  action="store", type="string",
                  dest="dest_dir",
                  help=_("Directory where web pages, slides and thumbs will be written (default is current directory)."))
parser.add_option("-t", "--theme",
                  action="store", type="string",
                  dest="theme",
                  help=_("Theme name (looked up in theme directory) or theme full path."))
parser.add_option("", "--default-style",
                  action="store", type="string",
                  dest="default_style",
                  help=_("Default style to apply to the theme."))
parser.add_option("", "--template-vars",
                  action="store", type="string",
                  dest="tpl_vars",
                  help=_("Common variables to load all templates with."))
parser.add_option("", "--clean-destination",
                  action="store_true",
                  dest="clean_destination",
                  help=_("Clean destination directory of files that should not be there."))
parser.add_option("-v", "--version",
                  action="store_true",
                  dest="show_version",
                  help=_("Display program version."))
parser.add_option("", "--check-all-dirs",
                  action="store_true",
                  dest="check_all_dirs",
                  help=_("Exhaustively go through all directories regardless of source modification time."))
parser.add_option("", "--dir-flattening-depth",
                  action="store", type="int",
                  dest="dir_flattening_depth",
                  help=_("Level below which the directory tree is flattened. Default is 'No' which disables this feature."))
parser.add_option("-s", "--image-size",
                  action="store", type="string",
                  dest="image_size",
                  help=_("Size of images, define as <name>=SIZE,..., eg. small=800x600,medium=1024x768. The special value 0x0 uses original size. See manual page for SIZE syntax."))
parser.add_option("-T", "--thumbnail-size",
                  action="store", type="string",
                  dest="thumbnail_size",
                  help=_("Size of thumbnails, define as SIZE, eg. 150x113. See manual page for SIZE syntax."))
parser.add_option("-q", "--quality",
                  action="store", type="int",
                  dest="quality",
                  help=_("Quality of generated JPEG images (default is 85)."))
parser.add_option("-O", "--original",
                  action="store_true",
                  dest="original",
                  help=_("Include original photos in output."))
parser.add_option("", "--orig-base",
                  action="store", type="string",
                  dest="orig_base",
                  help=_("Do not copy original photos in output directory, instead link them using submitted relative path as base."))
parser.add_option("", "--orig-symlink",
                  action="store_true",
                  dest="orig_symlink",
                  help=_("Do not copy original photos in output directory, instead create symlinks to their original locations."))
parser.add_option("", "--puburl",
                  action="store", type="string",
                  dest="puburl",
                  help=_("Publication URL (only useful for feed generation)."))
parser.add_option("-m", "--generate-metadata",
                  action="store_true",
                  dest="metadata",
                  help=_("Generate metadata description files where they don't exist instead of generating the web gallery."))
parser.add_option("-n", "--thumbs-per-page",
                  action="store", type="int",
                  dest="thumbs_per_page",
                  help=_("Maximum number of thumbs per index page. This enables index pagination (0 is unlimited)."))
parser.add_option("-z", "--make-dir-zip",
                  action="store_true",
                  dest="dirzip",
                  help=_("Make a zip archive of original pictures for each directory."))
parser.add_option("", "--webalbum-pic-bg",
                  action="store", type="string",
                  dest="webalbumpic_bg",
                  help=_("Webalbum picture background color. Default is transparent, and implies the PNG format. Any other value, e.g. red, white, blue, uses JPEG."))
parser.add_option("", "--pic-sort-by",
                  action="store", metavar=_('ORDER'),
                  dest="pic_sort_by", help=_("Sort order for images in a folder: filename, mtime, or exif. Add ':reverse' to reverse the chosen order."))
parser.add_option("", "--subgal-sort-by",
                  action="store", metavar=_('ORDER'),
                  dest="subgal_sort_by", help=_("Sort order for sub galleries in a folder: dirname or mtime. Add ':reverse' to reverse the chosen order."))
(options, args) = parser.parse_args()

if options.show_version:
    print _('lazygal version %s') % lazygal.__version__
    sys.exit(0)

if len(args) != 1:
    parser.print_help()
    sys.exit(_("Bad command line."))

source_dir = args[0].decode(sys.getfilesystemencoding())
if not os.path.isdir(source_dir):
    print _("Directory %s does not exist.") % source_dir
    sys.exit(1)


cmdline_config = lazygal.config.BetterConfigParser()
for section in lazygal.config.DEFAULT_CONFIG.sections():
    cmdline_config.add_section(section)


if options.quiet: cmdline_config.set('runtime', 'quiet', 'Yes')
if options.debug: cmdline_config.set('runtime', 'debug', 'Yes')
if options.check_all_dirs:
    cmdline_config.set('runtime', 'check-all-dirs', 'Yes')

if options.dest_dir is not None:
    cmdline_config.set('global', 'destdir',
                       options.dest_dir.decode(sys.getfilesystemencoding()))
if options.clean_destination:
    cmdline_config.set('global', 'clean-destination', 'Yes')
if options.dir_flattening_depth is not None:
    cmdline_config.set('global', 'dir-flattening-depth',
                       options.dir_flattening_depth)
if options.puburl is not None:
    cmdline_config.set('global', 'puburl', options.puburl)
if options.theme is not None:
    cmdline_config.set('global', 'theme', options.theme)

if options.default_style is not None:
    cmdline_config.set('webgal', 'default-style', options.default_style)
if options.webalbumpic_bg is not None:
    cmdline_config.set('webgal', 'webalbumpic-bg', options.webalbumpic_bg)
if options.image_size is not None:
    cmdline_config.set('webgal', 'image-size', options.image_size)
if options.thumbnail_size is not None:
    cmdline_config.set('webgal', 'thumbnail-size', options.thumbnail_size)
if options.thumbs_per_page is not None:
    cmdline_config.set('webgal', 'thumbs-per-page', options.thumbs_per_page)
if options.pic_sort_by is not None:
    cmdline_config.set('webgal', 'sort-medias', options.pic_sort_by)
if options.subgal_sort_by is not None:
    cmdline_config.set('webgal', 'sort-subgals', options.pic_sort_by)
if options.original:
    cmdline_config.set('webgal', 'original', 'Yes')
if options.orig_base is not None:
    cmdline_config.set('webgal', 'original-baseurl', options.orig_base)
if options.orig_symlink:
    try:
        _ = os.symlink
    except AttributeError:
        print _("Option --orig-symlink is not available on this platform.")
        sys.exit(1)
    else:
        cmdline_config.set('webgal', 'original-symlink', 'Yes')
if options.dirzip:
    cmdline_config.set('webgal', 'dirzip', 'Yes')
if options.quality is not None:
    cmdline_config.set('webgal', 'jpeg-quality', options.quality)

if options.tpl_vars is not None:
    cmdline_config.add_section('template-vars')
    tpl_vars_defs = options.tpl_vars.split(',')
    for single_def in tpl_vars_defs:
        name, value = single_def.split('=')
        cmdline_config.set('template-vars',
                           name, value.decode(sys.stdin.encoding))

logging.basicConfig(format='%(message)s', level=logging.INFO)

try:
    album = Album(source_dir, cmdline_config)
except ValueError, e:
    print unicode(e)
    sys.exit(1)

if options.metadata:
    album.generate_default_metadata()
else:
    try:
        album.generate()
    except KeyboardInterrupt:
        print >> sys.stderr, _("Interrupted.")
        sys.exit(1)


# vim: ts=4 sw=4 expandtab
