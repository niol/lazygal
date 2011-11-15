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
import ConfigParser

from __init__ import LazygalTestGen
import lazygal.config
from lazygal.generators import WebalbumDir
from lazygal.sourcetree import Directory


class TestConf(LazygalTestGen):

    def test_perdir_conf(self):
        """
        Lazygal shall read configuration files in every source directory,
        the parent directory configuration shall apply to child directories.
        """

        os.makedirs(os.path.join(self.source_dir, 'gal', 'subgal'))

        # src_dir/.lazygal
        config = ConfigParser.RawConfigParser()
        config.add_section('template-vars')
        config.set('template-vars', 'foo', 'root')
        config.set('template-vars', 'root', 'root')
        with open(os.path.join(self.source_dir, '.lazygal'), 'a') as f:
            config.write(f)

        # src_dir/gal/.lazygal
        config = ConfigParser.RawConfigParser()
        config.add_section('template-vars')
        config.set('template-vars', 'foo', 'gal')
        config.set('template-vars', 'gal', 'gal')
        with open(os.path.join(self.source_dir, 'gal', '.lazygal'), 'a') as f:
            config.write(f)

        # src_dir/gal/subgal/.lazygal
        config = ConfigParser.RawConfigParser()
        config.add_section('template-vars')
        config.set('template-vars', 'foo', 'subgal')
        config.set('template-vars', 'subgal', 'subgal')
        with open(os.path.join(self.source_dir, 'gal', 'subgal', '.lazygal'), 'a') as f:
            config.write(f)

        config = lazygal.config.LazygalConfig()
        config.set('global', 'puburl', 'http://example.com/album/')
        self.setup_album(config)

        source_gal = self.setup_subgal('gal', ['gal_img.jpg'])
        source_subgal = self.setup_subgal(os.path.join('gal', 'subgal'),
                                          ['subgal_img.jpg'])
        source_root = Directory(self.source_dir, [source_gal], [], self.album)

        dest_path = self.get_working_path()

        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)
        self.assertEqual(dest_subgal.config.get('global', 'puburl'),
                         'http://example.com/album/')
        self.assertEqual(dest_subgal.config.get('template-vars', 'root'),
                         'root')
        self.assertEqual(dest_subgal.config.get('template-vars', 'gal'),
                         'gal')
        self.assertEqual(dest_subgal.config.get('template-vars', 'subgal'),
                         'subgal')
        self.assertEqual(dest_subgal.config.get('template-vars', 'foo'),
                         'subgal')

        dest_gal = WebalbumDir(source_gal, [dest_subgal], self.album, dest_path)
        self.assertEqual(dest_gal.config.get('global', 'puburl'),
                         'http://example.com/album/')
        self.assertEqual(dest_gal.config.get('template-vars', 'root'), 'root')
        self.assertEqual(dest_gal.config.get('template-vars', 'gal'), 'gal')
        self.assertRaises(ConfigParser.NoOptionError,
                          dest_gal.config.get, 'template-vars', 'subgal')
        self.assertEqual(dest_gal.config.get('template-vars', 'foo'), 'gal')

        dest_root = WebalbumDir(source_root, [dest_gal], self.album, dest_path)
        self.assertEqual(dest_root.config.get('global', 'puburl'),
                         'http://example.com/album/')
        self.assertEqual(dest_root.config.get('template-vars', 'root'), 'root')
        self.assertRaises(ConfigParser.NoOptionError,
                          dest_root.config.get, 'template-vars', 'gal')
        self.assertRaises(ConfigParser.NoOptionError,
                          dest_root.config.get, 'template-vars', 'subgal')
        self.assertEqual(dest_root.config.get('template-vars', 'foo'), 'root')


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
