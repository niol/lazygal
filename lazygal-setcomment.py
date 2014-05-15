#!/usr/bin/env python

import sys

from lazygal.pygexiv2 import GExiv2
from lazygal import py2compat

fn = sys.argv[1]
comment = sys.argv[2]

im = GExiv2.Metadata(py2compat.u(fn))

# Assume comment is in utf-8, more encoding processing example using
# sys.stdin.encoding and example processing in lazygal/metadata.py
im['Exif.Photo.UserComment'] = comment
im.save_file()
