# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import unittest
import os
import datetime

from __init__ import LazygalTestGen
from lazygal.generators import WebalbumDir
from lazygal.sourcetree import Directory
from lazygal import pyexiv2api as pyexiv2


class TestSourceTree(LazygalTestGen):

    def test_genfile_filelayout(self):
        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = self.get_working_path()
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.album.generate(dest_path)

        # Check root dir contents
        self.assertTrue(os.path.isdir(dest_path))
        for fn in ('index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(dest_path, fn)))

        # Check subgal dir contents
        self.assertTrue(os.path.isdir(dest_subgal.path))
        for fn in ('index.html', 'index_medium.html',
                   'subgal_img.html', 'subgal_img_medium.html',
                   'subgal_img_thumb.jpg', 'subgal_img_small.jpg',
                   'subgal_img_medium.jpg'):
            self.assertTrue(os.path.isfile(os.path.join(dest_subgal.path, fn)))

    def test_originals_symlinks(self):
        img_path = self.add_img(self.source_dir, 'symlink_target.jpg')

        dest_dir = self.get_working_path()
        self.album.set_original(original=True, orig_symlink=True)
        self.album.generate(dest_dir)

        symlink = os.path.join(dest_dir, os.path.basename(img_path))
        # Test if the original in the webgal is a symlink
        self.assertEqual(os.path.islink(symlink), True)
        # Test if that symlink point to the image in the source_dir
        self.assertEqual(os.path.realpath(symlink), img_path)

    def test_metadata_osize_copy(self):
        img_path = self.add_img(self.source_dir, 'md_filled.jpg')

        # Add some metadata
        gps_data = pyexiv2.ImageMetadata(self.get_sample_path('sample-with-gps.jpg'))
        gps_data.read()
        source_image = pyexiv2.ImageMetadata(img_path)
        source_image.read()
        gps_data.copy(source_image)
        dummy_comment = 'nice photo'
        source_image['Exif.Photo.UserComment'] = dummy_comment
        dummy_date = datetime.datetime(2011, 2, 3, 12, 51, 43)
        source_image['Exif.Photo.DateTimeDigitized'] = dummy_date
        assert 'Exif.GPSInfo.GPSLongitude' in source_image.exif_keys
        assert 'Exif.GPSInfo.GPSLatitude' in source_image.exif_keys
        source_image.write()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_img_path = os.path.join(dest_dir, 'md_filled_small.jpg')
        dest_image = pyexiv2.ImageMetadata(dest_img_path)
        dest_image.read()

        # Check that metadata is still here for reduced pictures.
        self.assertEqual(dest_image['Exif.Photo.UserComment'].value,
                         dummy_comment)
        self.assertEqual(dest_image['Exif.Photo.DateTimeDigitized'].value,
                         dummy_date)

        # Check that blacklised tags are not present anymore in the reduced
        # picture.
        def lat(): return dest_image['Exif.GPSInfo.GPSLongitude'].value
        self.assertRaises(KeyError, lat)

        def long(): return dest_image['Exif.GPSInfo.GPSLatitude'].value
        self.assertRaises(KeyError, long)

    def test_feed(self):
        img_path = self.add_img(self.source_dir, 'img01.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir, 'http://example.com/album/')

        self.assertEqual(os.path.isfile(os.path.join(dest_dir, 'index.xml')),
                         True)


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
