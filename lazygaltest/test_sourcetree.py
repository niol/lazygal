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

    def get_dir(self, drpath):
        """
        Returns a directory object inside the test album root.
        """
        dpath = os.path.join(self.source_dir, drpath)
        return Directory(dpath, [], [], self.album)

    def test_skipped(self):
        d = self.get_dir('joe/young')
        self.assertEqual(d.should_be_skipped(), False, d.path)

        d = self.get_dir('.svn/young')
        self.assertEqual(d.should_be_skipped(), True, d.path)

        d = self.get_dir('joe/young/.git')
        self.assertEqual(d.should_be_skipped(), True, d.path)


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
