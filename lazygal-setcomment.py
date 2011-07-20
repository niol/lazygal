#!/usr/bin/env python

import sys

from lazygal import pyexiv2api as pyexiv2

fn = sys.argv[1]
comment = sys.argv[2]

im = pyexiv2.ImageMetadata(fn)
im.read()

# Assume comment is in utf-8, more encoding processing example using
# sys.stdin.encoding and example processing in lazygal/metadata.py
im['Exif.Photo.UserComment'] = comment
im.write()
