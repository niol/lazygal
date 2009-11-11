import sys

import pyexiv2

fn = sys.argv[1]
comment = sys.argv[2]

im = pyexiv2.Image(fn)
im.readMetadata()

# Assume comment is in utf-8, more encoding processing example using
# sys.stdin.encoding and example processing in lazygal/metadata.py
im['Exif.Photo.UserComment'] = comment
im.writeMetadata()
