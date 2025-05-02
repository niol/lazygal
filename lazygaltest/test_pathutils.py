# coding=utf-8
#
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
import posixpath
import ntpath
from . import LazygalTest
from lazygal.pathutils import *
from lazygal.sourcetree import Directory


class TestPathutils(LazygalTest):

    def setUp(self):
        super().setUp()
        self.test_root = self.get_working_path()

    def d(self, dpath):
        """
        Create a working directory in a test location if it does not exist.
        """
        if dpath[0] == "/":
            dpath = dpath[1:]

        dpath = os.path.join(self.test_root, dpath)
        if not os.path.exists(dpath):
            os.makedirs(dpath)
        assert os.path.isdir(dpath)
        return dpath

    def f(self, fpath):
        """
        Create a working file in a test location if it does not exist.
        """
        dpath = self.d(os.path.dirname(fpath))
        fpath = os.path.join(dpath, os.path.basename(fpath))
        if not os.path.exists(fpath):
            with open(fpath, "a"):
                os.utime(fpath, None)
        assert os.path.isfile(fpath)
        return fpath

    def test_is_subdir_of_dirs(self):
        self.assertTrue(is_subdir_of(self.d("/tmp"), self.d("/tmp/foo")))
        self.assertFalse(is_subdir_of(self.d("/tmp"), self.d("/tmpx/foo")))
        self.assertTrue(is_subdir_of(self.d("/tmp/bar"), self.f("/tmp/bar/baz/jay")))
        self.assertFalse(is_subdir_of(self.d("/tmp/john/mail"), self.d("/tmpz")))

    def test_is_subdir_of_files(self):
        self.assertTrue(is_subdir_of(self.d("/tmp"), self.f("/tmp/foo")))
        self.assertFalse(is_subdir_of(self.d("/tmp"), self.f("/tmpx/foo")))
        self.assertTrue(is_subdir_of(self.d("/tmp/bar"), self.f("/tmp/bar/baz/jay")))
        self.assertFalse(is_subdir_of(self.d("/tmp/john/mail"), self.f("/tmpz")))

    def test_url_path(self):
        self.assertEqual(url_path("/usr/bin/lazygal", posixpath), "/usr/bin/lazygal")
        self.assertEqual(url_path("../bin/lazygal", posixpath), "../bin/lazygal")
        self.assertEqual(
            url_path("C:\\Program Files\\Lazygal\\Lazygal.exe", ntpath),
            "Program Files/Lazygal/Lazygal.exe",
        )
        self.assertEqual(
            url_path("..\\Lazygal\\Lazygal.exe", ntpath), "../Lazygal/Lazygal.exe"
        )

    def test_url_quote(self):
        self.assertEqual(
            url_quote("http://host:8080/~user/album/"), "http://host:8080/~user/album/"
        )
        self.assertEqual(
            url_quote("https://host/~user/album/"), "https://host/~user/album/"
        )
        self.assertEqual(url_quote("/albumé/"), "/album%C3%A9/")
        self.assertEqual(url_quote("filter: user/"), "filter%3A%20user/")
        self.assertEqual(url_quote("index.html", "id"), "index.html#id")


if __name__ == "__main__":
    unittest.main()


# vim: ts=4 sw=4 expandtab
