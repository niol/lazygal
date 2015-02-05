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
try:
    import configparser
except ImportError: # py2compat
    import ConfigParser as configparser

from . import LazygalTestGen
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
        config = configparser.RawConfigParser()
        config.add_section('template-vars')
        config.set('template-vars', 'foo', 'root')
        config.set('template-vars', 'root', 'root')
        with open(os.path.join(self.source_dir, '.lazygal'), 'a') as f:
            config.write(f)

        # src_dir/gal/.lazygal
        config = configparser.RawConfigParser()
        config.add_section('template-vars')
        config.set('template-vars', 'foo', 'gal')
        config.set('template-vars', 'gal', 'gal')
        with open(os.path.join(self.source_dir, 'gal', '.lazygal'), 'a') as f:
            config.write(f)

        # src_dir/gal/subgal/.lazygal
        config = configparser.RawConfigParser()
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
        self.assertRaises(lazygal.config.NoOptionError,
                          dest_gal.config.get, 'template-vars', 'subgal')
        self.assertEqual(dest_gal.config.get('template-vars', 'foo'), 'gal')

        dest_root = WebalbumDir(source_root, [dest_gal], self.album, dest_path)
        self.assertEqual(dest_root.config.get('global', 'puburl'),
                         'http://example.com/album/')
        self.assertEqual(dest_root.config.get('template-vars', 'root'), 'root')
        self.assertRaises(lazygal.config.NoOptionError,
                          dest_root.config.get, 'template-vars', 'gal')
        self.assertRaises(lazygal.config.NoOptionError,
                          dest_root.config.get, 'template-vars', 'subgal')
        self.assertEqual(dest_root.config.get('template-vars', 'foo'), 'root')

    def test_types(self):
        config = lazygal.config.LazygalConfig()

        # bool
        for true in ('1', 'yes', 'true', 'on'):
            config.set('runtime', 'quiet', true)
            self.assertTrue(config.get('runtime', 'quiet') is True, true)
        for false in ('0', 'no', 'false', 'off'):
            config.set('runtime', 'quiet', false)
            self.assertTrue(config.get('runtime', 'quiet') is False, false)

        # int
        config.set('webgal', 'thumbs-per-page', '2')
        self.assertEqual(config.get('webgal', 'thumbs-per-page'), 2)

        # int or false
        config.set('global', 'dir-flattening-depth', 'False')
        self.assertTrue(config.get('global', 'dir-flattening-depth') is False)
        config.set('global', 'dir-flattening-depth', '2')
        self.assertEqual(config.get('global', 'dir-flattening-depth'), 2)

        # list
        config.set('webgal', 'filter-by-tag', 'foo, bar')
        self.assertEqual(config.get('webgal', 'filter-by-tag'), ['foo', 'bar'])

        # dict
        config.set('webgal', 'image-size', 'medium=foo, normal=bar')
        self.assertEqual(config.get('webgal', 'image-size'),
                         {'medium': 'foo', 'normal': 'bar'})

        # order
        config.set('webgal', 'sort-medias', 'dirname:reverse')
        self.assertEqual(config.get('webgal', 'sort-medias'),
                         {'order': 'dirname', 'reverse': True})

        # false or string
        config.set('webgal', 'original-baseurl', 'False')
        self.assertTrue(config.get('webgal', 'original-baseurl') is False)
        config.set('webgal', 'original-baseurl', './foo')
        self.assertEqual(config.get('webgal', 'original-baseurl'), './foo')

    def test_syntax(self):
        config = lazygal.config.LazygalConfig()
        configw = lazygal.config.LazygalWebgalConfig()

        # not a valid section
        self.assertRaises(ValueError, config.set, 'foo', 'bar', 'baz')
        self.assertRaises(ValueError, configw.set, 'runtime', 'quiet', 'false')

        # not a valid option
        self.assertRaises(ValueError, config.set, 'webgal', 'foo', 'bar')

        # basic option content parsing error
        self.assertRaises(ValueError, config.set,
                                      'webgal', 'dir-flattening-depth', 'foo')
        self.assertRaises(ValueError, config.set,
                                      'webgal', 'image-size', 'crappy')
        self.assertRaises(ValueError, config.set, 'runtime', 'quiet', 'foo')


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
