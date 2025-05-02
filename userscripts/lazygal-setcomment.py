#!/usr/bin/env python

import sys

from lazygal.metadata import GExiv2

fn = sys.argv[1]
comment = sys.argv[2]

im = GExiv2.Metadata(fn)

# Assume comment is in utf-8, more encoding processing example using
# sys.stdin.encoding and example processing in lazygal/metadata.py
im["Exif.Photo.UserComment"] = comment
im.save_file()
