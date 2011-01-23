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
from __init__ import LazygalTest
from lazygal.generators import Album
from lazygal.sourcetree import Directory


class TestSourceTree(LazygalTest):

    def setUp(self):
        super(TestSourceTree, self).setUp()

        self.source_dir = self.get_working_path()
        self.album = Album(self.source_dir)
        self.album.set_logging('error')
        self.album.set_theme()

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


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
