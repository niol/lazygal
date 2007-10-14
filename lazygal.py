#!/usr/bin/env python
#
# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import sys, os
from optparse import OptionParser
import ConfigParser

import lazygal
from lazygal.generators import Album

CONFIGFILE = '~/.lazygal/config'
CONFIGDEFAULTS = {
    'theme': 'default',
    'clean-destination': 'No',
    'image-size': 'small=800x600,medium=1024x768',
    'thumbnail-size': '150x113',
    'quality': '85',
}

# Read configuration file
config = ConfigParser.ConfigParser(defaults = CONFIGDEFAULTS)
# The following will hold until the config file has more than one section.
# See http://mail.python.org/pipermail/python-list/2006-March/370021.html
config.add_section('lazygal')
config.read(os.path.expanduser(CONFIGFILE))

usage = "usage: %prog [options] albumdir"
parser = OptionParser(usage=usage)
parser.add_option("", "--quiet",
                  action="store_true",
                  dest="quiet", default=False,
                  help="Don't output anything except for errors.")
parser.add_option("", "--debug",
                  action="store_true",
                  dest="debug", default=False,
                  help="Output everything that lazygal is doing.")
parser.add_option("-o", "--output-directory",
                  action="store", type="string",
                  dest="dest_dir", default=".",
                  help="Directory where web pages, slides and thumbs will be written (default is current directory).")
parser.add_option("-t", "--theme",
                  action="store", type="string",
                  dest="theme",
                  default=config.get('lazygal', 'theme'),
                  help="Theme name (looked up in theme directory) or theme full path.")
parser.add_option("", "--template-vars",
                  action="store", type="string",
                  dest="tpl_vars", default=None,
                  help="Common variables to load all templates with.")
parser.add_option("", "--clean-destination",
                  action="store_true",
                  dest="clean_dest",
                  default=config.getboolean('lazygal', 'clean-destination'),
                  help="Clean destination directory of files that should not be there.")
parser.add_option("-v", "--version",
                  action="store_true",
                  dest="show_version", default=False,
                  help="Display program version.")
parser.add_option("", "--check-all-dirs",
                  action="store_true",
                  dest="check_all_dirs", default=False,
                  help="Exhaustively go through all directories regardless of source modification time.")
parser.add_option("-s", "--image-size",
                  action="store", type="string",
                  dest="image_size",
                  default=config.get('lazygal', 'image-size'),
                  help="Size of images, define as <name>=<x>x<y>,..., eg. small=800x600,medium=1024x768.")
parser.add_option("-T", "--thumbnail-size",
                  action="store", type="string",
                  dest="thumbnail_size",
                  default=config.get('lazygal', 'thumbnail-size'),
                  help="Size of thumbnails, define as <x>x<y>, eg. 150x113.")
parser.add_option("-q", "--quality",
                  action="store", type="int",
                  dest="quality",
                  default=config.get('lazygal', 'quality'),
                  help="Quality of generated JPEG images (default is 85).")
(options, args) = parser.parse_args()

if options.show_version:
    print 'lazygal version %s' % lazygal.__version__
    sys.exit(0)

if len(args) != 1:
    parser.print_help()
    sys.exit("Bad command line.")

source_dir = args[0]
if not os.path.isdir(source_dir):
    sys.exit("Directory %s does not exist.", source_dir)

sizes = []
size_defs = options.image_size.split(',')
for single_def in size_defs:
    name, string_size = single_def.split('=')
    x, y = string_size.split('x')
    sizes.append((name, (int(x), int(y))))

x, y = options.thumbnail_size.split('x')
thumbnail = (int(x), int(y))

album = Album(source_dir, thumbnail, sizes, quality=options.quality)

if options.tpl_vars:
    tpl_vars = {}
    tpl_vars_defs = options.tpl_vars.split(',')
    for single_def in tpl_vars_defs:
        name, value = single_def.split('=')
        tpl_vars[name] = value
    album.set_tpl_vars(tpl_vars)

album.set_theme(options.theme)

log_level = None
if options.quiet:
    log_level = 'error'
if options.debug:
    log_level = 'debug'
if log_level != None:
    album.set_logging(log_level)

album.generate(options.dest_dir, options.check_all_dirs, options.clean_dest)


# vim: ts=4 sw=4 expandtab
