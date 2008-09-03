#!/usr/bin/env python
#
# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2008 Alexandre Rossi <alexandre.rossi@gmail.com>
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
from lazygal.generators import Album, SOURCEDIR_CONFIGFILE, THUMB_SIZE_NAME

CONFIGFILE = '~/.lazygal/config'
CONFIGDEFAULTS = {
    'quiet': 'No',
    'theme': 'default',
    'default-style': 'default',
    'clean-destination': 'No',
    'check-all-dirs': 'No',
    'original': 'No',
    'image-size': 'small=800x600,medium=1024x768',
    'thumbnail-size': '150x113',
    'make-dir-zip': 'No',
    'thumbs-per-page': '0',
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
parser.add_option("-s", "--image-size",
                  action="store", type="string",
                  dest="image_size",
                  default=config.get('lazygal', 'image-size'),
                  help=_("Size of images, define as <name>=<x>x<y>,..., eg. small=800x600,medium=1024x768. The special dimensions 0x0 use original size."))
parser.add_option("-T", "--thumbnail-size",
                  action="store", type="string",
                  dest="thumbnail_size",
                  default=config.get('lazygal', 'thumbnail-size'),
                  help=_("Size of thumbnails, define as <x>x<y>, eg. 150x113."))
parser.add_option("-q", "--quality",
                  action="store", type="int",
                  dest="quality",
                  default=config.get('lazygal', 'quality'),
                  help=_("Quality of generated JPEG images (default is 85)."))
parser.add_option("-O", "--original",
                  action="store_true",
                  dest="original", default=False,
                  help=_("Include original photos in output."))
parser.add_option("", "--puburl",
                  action="store", type="string",
                  dest="pub_url",
                  help=_("Publication URL (only usefull for feed generation)."))
parser.add_option("-m", "--generate-metadata",
                  action="store_true",
                  dest="metadata", default=False,
                  help=_("Generate metadata description files where they don't exist."))
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

# Load a config file in the source_dir root
sourcedir_configfile = os.path.join(source_dir, SOURCEDIR_CONFIGFILE)
if os.path.isfile(sourcedir_configfile):
    config.read(sourcedir_configfile)

sizes = []
size_defs = options.image_size.split(',')
for single_def in size_defs:
    name, string_size = single_def.split('=')
    if name == THUMB_SIZE_NAME:
        print _("Size name '%s' is reserved for internal processing.")\
                % THUMB_SIZE_NAME
        sys.exit(1)
    x, y = string_size.split('x')
    sizes.append((name, (int(x), int(y))))

x, y = options.thumbnail_size.split('x')
thumbnail = (int(x), int(y))

album = Album(source_dir, thumbnail, sizes, quality=options.quality,
              optimize=options.optimize, progressive=options.progressive,
              thumbs_per_page=options.thumbs_per_page,
              dirzip=options.dirzip)

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
album.set_original(options.original)
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
