#!/usr/bin/env python
#
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

import sys, os, locale, gettext
from optparse import OptionParser
import genshi.core
import ConfigParser

import lazygal
from lazygal.generators import Album, SOURCEDIR_CONFIGFILE
from lazygal.genmedia import THUMB_SIZE_NAME
from lazygal.newsize import is_known_newsizer


CONFIGFILE = '~/.lazygal/config'
CONFIGDEFAULTS = {
    'quiet': 'No',
    'theme': 'default',
    'default-style': 'default',
    'clean-destination': 'No',
    'check-all-dirs': 'No',
    'dir-flattening-depth': 'No',
    'original': 'No',
    'orig-base': 'No',
    'orig-symlink': 'No',
    'image-size': 'small=800x600,medium=1024x768',
    'thumbnail-size': '150x113',
    'make-dir-zip': 'No',
    'thumbs-per-page': '0',
    'pic-sort-by': 'exif',
    'subgal-sort-by': 'filename',
    'quality': '85',
    'optimize': 'Yes',
    'progressive': 'Yes',
    'webalbumpic-bg': 'transparent',
    'template-vars': '',
}

# i18n
LOCALES_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                             'build', 'mo'))
if not os.path.exists(LOCALES_PATH):
    LOCALES_PATH = '/usr/share/locale'
gettext.install('lazygal', LOCALES_PATH, unicode=1)

locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())


# Read configuration file
config = ConfigParser.ConfigParser(defaults = CONFIGDEFAULTS)
# The following will hold until the config file has more than one section.
# See http://mail.python.org/pipermail/python-list/2006-March/370021.html
config.add_section('lazygal')
config.read(os.path.expanduser(CONFIGFILE))

usage = _("usage: %prog [options] albumdir")
parser = OptionParser(usage=usage)

# The help option must be changed to comply with i18n.
parser.get_option('-h').help = _("Show this help message and exit.")

parser.add_option("", "--quiet",
                  action="store_true",
                  dest="quiet", default=config.getboolean('lazygal', 'quiet'),
                  help=_("Don't output anything except for errors."))
parser.add_option("", "--debug",
                  action="store_true",
                  dest="debug", default=False,
                  help=_("Output everything that lazygal is doing."))
parser.add_option("-o", "--output-directory",
                  action="store", type="string",
                  dest="dest_dir", default=".",
                  help=_("Directory where web pages, slides and thumbs will be written (default is current directory)."))
parser.add_option("-t", "--theme",
                  action="store", type="string",
                  dest="theme",
                  default=config.get('lazygal', 'theme'),
                  help=_("Theme name (looked up in theme directory) or theme full path."))
parser.add_option("", "--default-style",
                  action="store", type="string",
                  dest="default_style",
                  default=config.get('lazygal', 'default-style'),
                  help=_("Default style to apply to the theme."))
parser.add_option("", "--template-vars",
                  action="store", type="string",
                  dest="tpl_vars",
                  default=config.get('lazygal', 'template-vars'),
                  help=_("Common variables to load all templates with."))
parser.add_option("", "--clean-destination",
                  action="store_true",
                  dest="clean_dest",
                  default=config.getboolean('lazygal', 'clean-destination'),
                  help=_("Clean destination directory of files that should not be there."))
parser.add_option("-v", "--version",
                  action="store_true",
                  dest="show_version", default=False,
                  help=_("Display program version."))
parser.add_option("", "--check-all-dirs",
                  action="store_true",
                  dest="check_all_dirs", default=config.getboolean('lazygal', 'check-all-dirs'),
                  help=_("Exhaustively go through all directories regardless of source modification time."))
parser.add_option("", "--dir-flattening-depth",
                  action="store", type="int",
                  dest="dir_flattening_depth",
                  default=config.getboolean('lazygal', 'dir-flattening-depth'),
                  help=_("Level below witch the directory tree is flattened. Default is 0 which is unlimited."))
parser.add_option("-s", "--image-size",
                  action="store", type="string",
                  dest="image_size",
                  default=config.get('lazygal', 'image-size'),
                  help=_("Size of images, define as <name>=SIZE,..., eg. small=800x600,medium=1024x768. The special dimensions 0x0 use original size. See manual page for SIZE syntax."))
parser.add_option("-T", "--thumbnail-size",
                  action="store", type="string",
                  dest="thumbnail_size",
                  default=config.get('lazygal', 'thumbnail-size'),
                  help=_("Size of thumbnails, define as SIZE, eg. 150x113. See manual page for SIZE syntax."))
parser.add_option("-q", "--quality",
                  action="store", type="int",
                  dest="quality",
                  default=config.get('lazygal', 'quality'),
                  help=_("Quality of generated JPEG images (default is 85)."))
parser.add_option("-O", "--original",
                  action="store_true",
                  dest="original", default=False,
                  help=_("Include original photos in output."))
parser.add_option("", "--orig-base",
                  action="store", type="string",
                  dest="orig_base",
                  default=config.get('lazygal', 'orig-base'),
                  help=_("Do not copy original photos in output directory, instead link them using submitted relative path as base."))
parser.add_option("", "--orig-symlink",
                  action="store_true",
                  dest="orig_symlink",
                  default=config.get('lazygal', 'orig-symlink'),
                  help=_("Do not copy original photos in output directory, instead link them using submitted relative path as base."))
parser.add_option("", "--puburl",
                  action="store", type="string",
                  dest="pub_url",
                  help=_("Publication URL (only usefull for feed generation)."))
parser.add_option("-m", "--generate-metadata",
                  action="store_true",
                  dest="metadata", default=False,
                  help=_("Generate metadata description files where they don't exist instead of generating the web gallery."))
parser.add_option("-n", "--thumbs-per-page",
                  action="store", type="int",
                  dest="thumbs_per_page",
                  default=config.getint('lazygal', 'thumbs-per-page'),
                  help=_("Maximum number of thumbs per index page. This enables index pagination (0 is unlimited)."))
parser.add_option("-z", "--make-dir-zip",
                  action="store_true",
                  dest="dirzip", default=config.getboolean('lazygal', 'make-dir-zip'),
                  help=_("Make a zip archive of original pictures for each directory."))
parser.add_option("", "--webalbum-pic-bg",
                  action="store", type="string",
                  dest="webalbumpic_bg",
                  default=config.get('lazygal', 'webalbumpic-bg'),
                  help=_("Webalbum picture background color. Default is transparent, and implies the PNG format. Any other value, e.g. red, white, blue, uses JPEG."))
parser.add_option("", "--optimize",
                  action="store_true",
                  dest="optimize", default=config.getboolean('lazygal', 'optimize'),
                  help=_("Run an extra optimization pass an each image."))
parser.add_option("", "--progressive",
                  action="store_true",
                  dest="progressive", default=config.getboolean('lazygal', 'progressive'),
                  help=_("Generate Progressive JPEG images."))
parser.add_option("", "--pic-sort-by",
                  action="store", default=config.get('lazygal', 'pic-sort-by'), metavar=_('ORDER'),
                  dest="pic_sort_by", help=_("Sort order for images in a folder: filename, mtime, or exif. Add ':reverse' to reverse the chosen order."))
parser.add_option("", "--subgal-sort-by",
                  action="store", default=config.get('lazygal', 'subgal-sort-by'), metavar=_('ORDER'),
                  dest="subgal_sort_by", help=_("Sort order for sub galleries in a folder: filename or mtime. Add ':reverse' to reverse the chosen order."))
(options, args) = parser.parse_args()

if options.show_version:
    print _('lazygal version %s') % lazygal.__version__
    sys.exit(0)

if len(args) != 1:
    parser.print_help()
    sys.exit(_("Bad command line."))

source_dir = args[0]
if not os.path.isdir(source_dir):
    print _("Directory %s does not exist.") % source_dir
    sys.exit(1)

if options.orig_symlink:
    try:
        _ = os.symlink
    except AttributeError:
        print _("Option --orig-symlink is not available on this platform.")
        sys.exit(1)

# Load a config file in the source_dir root
sourcedir_configfile = os.path.join(source_dir, SOURCEDIR_CONFIGFILE)
if os.path.isfile(sourcedir_configfile):
    config.read(sourcedir_configfile)

    # Load the defaults now that all the config files are red
    default_from_config = {}
    # (section template-vars is handled later in the script)
    for name, value in config.items('lazygal'):
        # FIXME: Not to proud of the following but config options need a big
        # refactoring and their proper module, I'll save this for later.
        if value == 'Yes': value = True
        elif value == 'No': value = False
        else:
            try:
                value = int(value)
            except ValueError: pass
        default_from_config[name.replace('-', '_')] = value
    parser.set_defaults(**default_from_config)

    # Reparse a second time for the new defaults (from the source directory
    # config file) to be taken into account.
    (options, args) = parser.parse_args()

size_strings = []
size_defs = options.image_size.split(',')
for single_def in size_defs:
    try:
        name, string_size = single_def.split('=')
        if name == '': raise ValueError
    except ValueError:
        print _("Sizes is a comma-separated list of size names and specs:\n\t e.g. \"small=640x480,medium=1024x768\".")
        sys.exit(1)
    if name == THUMB_SIZE_NAME:
        print _("Size name '%s' is reserved for internal processing.")\
                % THUMB_SIZE_NAME
        sys.exit(1)
    if not is_known_newsizer(string_size):
        print _("'%s' for size '%s' does not describe a known size syntax.")\
                % (string_size, name, )
        sys.exit(1)
    size_strings.append((name, string_size))

thumb_size_string = options.thumbnail_size
if not is_known_newsizer(thumb_size_string):
    print _("'%s' for thumb size does not describe a known size syntax.")\
            % thumb_string_size
    sys.exit(1)

def parse_sort(sort_string):
    try:
        sort_method, reverse = sort_string.split(':')
    except ValueError:
        sort_method = sort_string
        reverse = False
    if reverse == 'reverse':
        return sort_method, True
    else:
        return sort_method, False

album = Album(source_dir, thumb_size_string, size_strings,
              quality=options.quality,
              dir_flattening_depth=options.dir_flattening_depth,
              optimize=options.optimize, progressive=options.progressive,
              thumbs_per_page=options.thumbs_per_page,
              dirzip=options.dirzip,
              pic_sort_by=parse_sort(options.pic_sort_by),
              subgal_sort_by=parse_sort(options.subgal_sort_by))

if options.tpl_vars or config.has_section('template-vars'):
    tpl_vars = {}
    if config.has_section('template-vars'):
        for option in config.options('template-vars'):
            value = config.get('template-vars', option)
            value = value.decode(locale.getpreferredencoding())
            tpl_vars[option] = genshi.core.Markup(value)
    if options.tpl_vars:
        tpl_vars_defs = options.tpl_vars.split(',')
        for single_def in tpl_vars_defs:
            name, value = single_def.split('=')
            value = value.decode(sys.stdin.encoding)
            tpl_vars[name] = genshi.core.Markup(value)
    album.set_tpl_vars(tpl_vars)

album.set_theme(options.theme, options.default_style)

orig_base = None
if options.original and options.orig_base != 'No':
    orig_base = options.orig_base
album.set_original(options.original, orig_base, options.orig_symlink)

album.set_webalbumpic(bg=options.webalbumpic_bg)

log_level = None
if options.quiet:
    log_level = 'error'
if options.debug:
    log_level = 'debug'
if log_level != None:
    album.set_logging(log_level)

if options.metadata:
    album.generate_default_medatada()
else:
    album.generate(options.dest_dir, options.pub_url,
                   options.check_all_dirs, options.clean_dest)


# vim: ts=4 sw=4 expandtab
