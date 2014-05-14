# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2014 Alexandre Rossi <alexandre.rossi@gmail.com>
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
from . import LazygalTest
import lazygal.tpl as tpl


class TestTheme(LazygalTest):

    def setUp(self):
        super(TestTheme, self).setUp()

        self.themes_dir = self.get_working_path()
        self.theme_name = 'test_theme'
        self.theme_dir = os.path.join(self.themes_dir, self.theme_name)
        self.theme_manifest = os.path.join(self.theme_dir, 'manifest.json')
        os.makedirs(self.theme_dir)

    def test_sharedfiles_prefixed(self):
        """
        File prefixed with SHARED_ in theme dir are copied in shared files
        directory.
        """
        prefixed = os.path.join(self.theme_dir, 'SHARED_prefixed.txt')
        self.create_file(prefixed)
        theme = tpl.Theme(self.themes_dir, self.theme_name)

        self.assertEqual(theme.shared_files, [(prefixed, 'prefixed.txt')])

    def test_shared_file_manifest(self):
        """
        The manifest makes it possible to include files from other directories
        in shared files.
        """
        prefixed = os.path.join(self.theme_dir, 'SHARED_prefixed.txt')
        self.create_file(prefixed)
        jslib = os.path.join(self.themes_dir, 'lib-2.1.js')
        self.create_file(jslib)
        self.create_file(self.theme_manifest, """
{
    "shared": [
        {
            "path": "../lib-2.1.js",
            "dest": "lib.js"
        },
        {
            "path": "../lib-2.1.js",
            "dest": "js/"
        }
    ]
}
""", bom=False)

        theme = tpl.Theme(self.themes_dir, self.theme_name)

        self.assertEqual(theme.shared_files,
                         [(jslib, 'lib.js'),
                          (jslib, 'js/lib-2.1.js'),
                          (prefixed, 'prefixed.txt')])


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
