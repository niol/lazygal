#!/usr/bin/env python3
#
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


import gettext
import locale
import logging
import os
import sys
from optparse import OptionParser


# i18n
from lazygal import INSTALL_MODE, INSTALL_PREFIX
if INSTALL_MODE == 'source':
    LOCALES_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                                 'build', 'mo'))
elif INSTALL_MODE == 'installed':
    LOCALES_PATH = os.path.join(INSTALL_PREFIX, 'share', 'locale')
gettext.install('lazygal', LOCALES_PATH)

locale.setlocale(locale.LC_ALL, '')


import lazygal
from lazygal.generators import Album
import lazygal.config
import lazygal.eyecandy
import lazygal.log


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
parser.add_option("-f", "--force-gen-pages",
                  action="store_true",
                  dest="force_gen_pages",
                  help=_("Force rebuild of all pages."))
parser.add_option("", "--clean-destination",
                  action="store_true",
                  dest="clean_destination",
                  help=_("Clean destination directory of files that should not be there."))
parser.add_option("", "--preserve", type="string",
                  action="append", metavar=_('PATTERN'),
                  dest="preserve", help=_("Specifies pathname(s) which will be ignored during final cleanup"))
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
parser.add_option("", "--webalbum-pic-type",
                  action="store", type="choice",
                  choices=list(lazygal.eyecandy.WEBALBUMPIC_TYPES.keys()),
                  dest="webalbumpic_type",
                  help=_("Webalbum picture type. Default is messy."))
parser.add_option("", "--pic-sort-by",
                  action="store", metavar=_('ORDER'),
                  dest="pic_sort_by", help=_("Sort order for images in a folder: filename, numeric, mtime, or exif. Add ':reverse' to reverse the chosen order."))
parser.add_option("", "--subgal-sort-by",
                  action="store", metavar=_('ORDER'),
                  dest="subgal_sort_by", help=_("Sort order for sub galleries in a folder: dirname, numeric, exif or mtime. Add ':reverse' to reverse the chosen order."))
parser.add_option("", "--filter-by-tag", type="string",
                  action="append", metavar=_('TAG'),
                  dest="filter_by_tag", help=_("Only include in the gallery pics whose IPTC keywords match the supplied filter(s)."))
parser.add_option("", "--exclude", type="string",
                  action="append", metavar=_('PATTERN'),
                  dest="exclude", help=_("Regular expression pattern(s) describing directories or filenames to exclude from consideration."))
parser.add_option("", "--keep-gps-data",
                  action="store_true",
                  dest="keep_gps",
                  help=_("Do not remove GPS location tags from EXIF metadata. Mostly useful with holiday photos."))
parser.add_option("", "--no-video",
                  action="store_true",
                  dest="novideo",
                  help=_("Do not process videos nor include them in indexes."))
(options, args) = parser.parse_args()

if options.show_version:
    print(_('lazygal version %s') % lazygal.__version__)
    sys.exit(0)

if len(args) != 1:
    parser.print_help()
    sys.exit(_("Bad command line: wrong number of arguments."))

source_dir = args[0]
if not os.path.isdir(source_dir):
    print(_("Directory %s does not exist.") % source_dir)
    sys.exit(1)


cmdline_config = lazygal.config.LazygalConfig()
for section in cmdline_config.valid_sections:
    cmdline_config.add_section(section)


if options.quiet: cmdline_config.set('runtime', 'quiet', True)
if options.debug: cmdline_config.set('runtime', 'debug', True)
if options.check_all_dirs:
    cmdline_config.set('runtime', 'check-all-dirs', True)

if options.dest_dir is not None:
    cmdline_config.set('global', 'output-directory', options.dest_dir)
if options.force_gen_pages:
    cmdline_config.set('global', 'force-gen-pages', True)
if options.clean_destination:
    cmdline_config.set('global', 'clean-destination', True)
if options.preserve is not None:
    cmdline_config.set('global', 'preserve_args', options.preserve)
if options.dir_flattening_depth is not None:
    cmdline_config.set('global', 'dir-flattening-depth',
                       options.dir_flattening_depth)
if options.puburl is not None:
    cmdline_config.set('global', 'puburl', options.puburl)
if options.theme is not None:
    cmdline_config.set('global', 'theme', options.theme)
if options.exclude is not None:
    cmdline_config.set('global', 'exclude_args', options.exclude)

if options.default_style is not None:
    cmdline_config.set('webgal', 'default-style', options.default_style)
if options.webalbumpic_bg is not None:
    cmdline_config.set('webgal', 'webalbumpic-bg', options.webalbumpic_bg)
if options.webalbumpic_type is not None:
    cmdline_config.set('webgal', 'webalbumpic-type', options.webalbumpic_type)
if options.image_size is not None:
    cmdline_config.set('webgal', 'image-size', options.image_size)
if options.thumbnail_size is not None:
    cmdline_config.set('webgal', 'thumbnail-size', options.thumbnail_size)
if options.thumbs_per_page is not None:
    cmdline_config.set('webgal', 'thumbs-per-page', options.thumbs_per_page)
if options.pic_sort_by is not None:
    cmdline_config.set('webgal', 'sort-medias', options.pic_sort_by)
if options.subgal_sort_by is not None:
    cmdline_config.set('webgal', 'sort-subgals', options.subgal_sort_by)
if options.filter_by_tag is not None:
    cmdline_config.set('webgal', 'filter-by-tag', options.filter_by_tag)
if options.original:
    cmdline_config.set('webgal', 'original', 'Yes')
if options.orig_base is not None:
    cmdline_config.set('webgal', 'original-baseurl', options.orig_base)
if options.orig_symlink:
    try:
        os.symlink
    except AttributeError:
        print(_("Option --orig-symlink is not available on this platform."))
        sys.exit(1)
    else:
        cmdline_config.set('webgal', 'original-symlink', True)
if options.dirzip:
    cmdline_config.set('webgal', 'dirzip', True)
if options.quality is not None:
    cmdline_config.set('webgal', 'jpeg-quality', options.quality)
if options.keep_gps:
    cmdline_config.set('webgal', 'keep-gps', True)
if options.novideo:
    cmdline_config.set('webgal', 'novideo', True)

if options.tpl_vars is not None:
    cmdline_config.add_section('template-vars')
    tpl_vars_defs = options.tpl_vars.split(',')
    for single_def in tpl_vars_defs:
        name, value = single_def.split('=')
        cmdline_config.set('template-vars', name, value)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if sys.stdout.isatty():
    logging_handler = lazygal.log.ProgressConsoleHandler
else:
    logging_handler = logging.StreamHandler
output_log = logging_handler(sys.stdout)
output_log.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(output_log)

try:
    album = Album(source_dir, cmdline_config)
except ValueError as e:
    print(e)
    sys.exit(1)
else:
    if sys.stdout.isatty():
        progress = lazygal.generators.AlbumGenProgress(\
            len(album.stats()['bydir'].keys()), album.stats()['total'])

        def update_progress():
            output_log.update_progress(str(progress))
        progress.updated = update_progress
        progress.updated()
    else:
        progress = None


if options.metadata:
    album.generate_default_metadata()
else:
    try:
        album.generate(progress=progress)
    except KeyboardInterrupt:
        print(_("Interrupted."), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        sys.stdout.write("\r")
        print(e)
        sys.exit(1)


# vim: ts=4 sw=4 expandtab
