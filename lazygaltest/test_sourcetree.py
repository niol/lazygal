# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2011-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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


from gi.repository import GExiv2


from . import LazygalTest
from lazygal import py2compat
from lazygal.generators import Album
from lazygal.sourcetree import Directory


class TestSourceTree(LazygalTest):

    def setUp(self):
        super(TestSourceTree, self).setUp()

        self.source_dir = self.get_working_path()
        self.album = Album(self.source_dir)

    def get_dir(self, drpath):
        """
        Returns a directory object inside the test album root.
        """
        dpath = os.path.join(self.source_dir, drpath)
        os.makedirs(dpath)
        return Directory(dpath, [], [], self.album)

    def test_skipped(self):
        d = self.get_dir('joe/young')
        self.assertEqual(d.should_be_skipped(), False, d.path)

        d = self.get_dir('.svn/young')
        self.assertEqual(d.should_be_skipped(), True, d.path)

        d = self.get_dir('joe/young/.git')
        self.assertEqual(d.should_be_skipped(), True, d.path)

    def test_dir_parent_paths(self):
        d = self.get_dir('joe/young/early_years')

        expected = [
            os.path.join(self.source_dir, 'joe/young/early_years'),
            os.path.join(self.source_dir, 'joe/young'),
            os.path.join(self.source_dir, 'joe'),
            self.source_dir,
        ]
        self.assertEqual(d.parent_paths(), list(map(py2compat.u, expected)))

    def test_latest_media_stamp(self):
        dpath = os.path.join(self.source_dir, 'srcdir')
        os.makedirs(dpath)

        pics = ['pic1.jpg', 'pic2.jpg', 'pic3.jpg']

        for fn in pics:
            self.add_img(dpath, fn)

        # no exif test
        imgpath = os.path.join(dpath, 'pic1.jpg')
        img = GExiv2.Metadata(imgpath)
        del img['Exif.Photo.DateTimeDigitized']
        del img['Exif.Photo.DateTimeOriginal']
        img.save_file()
        os.utime(imgpath, (0, py2compat.datetime(2011, 7, 3).timestamp()))
        imgpath = os.path.join(dpath, 'pic2.jpg')
        img = GExiv2.Metadata(imgpath)
        del img['Exif.Photo.DateTimeDigitized']
        del img['Exif.Photo.DateTimeOriginal']
        img.save_file()
        os.utime(imgpath, (0, py2compat.datetime(2011, 7, 4).timestamp()))
        imgpath = os.path.join(dpath, 'pic3.jpg')
        img = GExiv2.Metadata(imgpath)
        del img['Exif.Photo.DateTimeDigitized']
        del img['Exif.Photo.DateTimeOriginal']
        img.save_file()
        os.utime(imgpath, (0, py2compat.datetime(2011, 7, 2).timestamp()))
        d = Directory(dpath, [], pics, self.album)
        self.assertEqual(d.latest_media_stamp(),
                         py2compat.datetime(2011, 7, 4).timestamp())

        # mixed exif and no exif test
        imgpath = os.path.join(dpath, 'pic2.jpg')
        img = GExiv2.Metadata(imgpath)
        img['Exif.Photo.DateTimeOriginal'] =\
            py2compat.datetime(2015, 7, 4).strftime('%Y:%m:%d %H:%M:%S')
        img.save_file()
        d = Directory(dpath, [], pics, self.album)
        self.assertEqual(d.latest_media_stamp(),
                         py2compat.datetime(2015, 7, 4).timestamp())

        # full exif
        imgpath = os.path.join(dpath, 'pic1.jpg')
        img = GExiv2.Metadata(imgpath)
        img['Exif.Photo.DateTimeOriginal'] =\
            py2compat.datetime(2015, 8, 1).strftime('%Y:%m:%d %H:%M:%S')
        img.save_file()
        imgpath = os.path.join(dpath, 'pic3.jpg')
        img = GExiv2.Metadata(imgpath)
        img['Exif.Photo.DateTimeOriginal'] =\
            py2compat.datetime(2015, 8, 20).strftime('%Y:%m:%d %H:%M:%S')
        img.save_file()
        d = Directory(dpath, [], pics, self.album)
        self.assertEqual(d.latest_media_stamp(),
                         py2compat.datetime(2015, 8, 20).timestamp())


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
