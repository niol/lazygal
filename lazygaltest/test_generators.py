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
import shutil

from __init__ import LazygalTestGen
import lazygal.config
from lazygal.generators import WebalbumDir
from lazygal.sourcetree import Directory
from lazygal import pyexiv2api as pyexiv2


class TestGenerators(LazygalTestGen):

    def test_genfile_filelayout(self):
        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        # Check root dir contents
        self.assertTrue(os.path.isdir(dest_path))
        for fn in ('index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(dest_path, fn)))

        # Check subgal dir contents
        dest_subgal_path = os.path.join(dest_path, 'subgal')
        self.assertTrue(os.path.isdir(dest_subgal_path))
        for fn in ('index.html', 'index_medium.html',
                   'subgal_img.html', 'subgal_img_medium.html',
                   'subgal_img_thumb.jpg', 'subgal_img_small.jpg',
                   'subgal_img_medium.jpg'):
            self.assertTrue(os.path.isfile(os.path.join(dest_subgal_path, fn)))

    def test_filecleanup(self):
        '''
        Files that are not part of what was generated or updated shall be
        spotted.
        '''
        pics = [ 'img%d.jpg' % i for i in range(0, 8)]
        source_subgal = self.setup_subgal('subgal', pics)

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        # add a thumbs that should not be there
        self.add_img(dest_path, 'extra_thumb.jpg')
        self.add_img(os.path.join(dest_path, 'subgal'), 'extra_thumb2.jpg')

        # remove a pic in source_dir
        os.unlink(os.path.join(self.source_dir, 'subgal', 'img6.jpg'))

        # new objects to probe filesystem
        pics.remove('img6.jpg')
        source_subgal = Directory(os.path.join(self.source_dir, 'subgal'),
                                  [], pics, self.album)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)
        expected = map(lambda fn:\
                             unicode(os.path.join(dest_path, 'subgal', fn)),
                       ['extra_thumb2.jpg',
                        'img6_thumb.jpg',
                        'img6_small.jpg', 'img6_medium.jpg',
                        'img6.html', 'img6_medium.html',
                       ]
                      )
        self.assertEqual(sorted(dest_subgal.list_foreign_files()),
                         sorted(expected))

        source_gal = Directory(self.source_dir, [source_subgal], [], self.album)
        dest_gal = WebalbumDir(source_gal, [dest_subgal], self.album, dest_path)
        self.assertEqual(sorted(dest_gal.list_foreign_files()),
                         [os.path.join(dest_path, 'extra_thumb.jpg')])

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
        config = lazygal.config.LazygalConfig()
        config.set('global', 'puburl', 'http://example.com/album/')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'img01.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        self.assertEqual(os.path.isfile(os.path.join(dest_dir, 'index.xml')),
                         True)


class TestSpecialGens(LazygalTestGen):

    def setUp(self):
        super(TestSpecialGens, self).setUp(False)
        self.dest_path = os.path.join(self.tmpdir, 'dst')

    def test_paginate(self):
        '''
        It shall be possible to split big galleries on mutiple index pages.
        '''
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'thumbs-per-page', 4)
        self.setup_album(config)

        pics = [ 'img%d.jpg' % i for i in range(0, 9)]
        source_subgal = self.setup_subgal('subgal', pics)

        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    def test_flatten(self):
        config = lazygal.config.LazygalConfig()
        config.set('global', 'dir-flattening-depth', 1)
        self.setup_album(config)

        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])
        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    def test_flattenpaginate(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'thumbs-per-page', 4)
        config.set('global', 'dir-flattening-depth', 1)
        self.setup_album(config)

        pics = [ 'img%d.jpg' % i for i in range(0, 9)]
        source_subgal = self.setup_subgal('subgal', pics)

        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    def test_dir_symlink(self):
        '''
        The generator should follow symlinks on directories, but should not get
        stuck in infinite recursion if two distinct directory trees have
        symbolic links to each other.
        '''
        self.setup_album()

        pics = [ 'img%d.jpg' % i for i in range(0, 2)]
        source_subgal = self.setup_subgal('subgal', pics)

        # cp -ar to create an out-of-tree source dir with pics
        src2_path = os.path.join(self.get_working_path(), 'symlink_target')
        shutil.copytree(self.source_dir, src2_path)

        # symlink src2 so it show in album
        os.symlink(src2_path, os.path.join(self.source_dir, 'symlinked'))
        # symlink src in src2 to check if the generator goes in an infinite
        # loop.
        os.symlink(self.source_dir, os.path.join(src2_path, 'do_not_follow'))

        self.album.generate(self.dest_path)

        # Check root dir contents
        self.assertTrue(os.path.isdir(self.dest_path))
        for fn in ('index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(self.dest_path, fn)))
        for dn in ('subgal', 'symlinked'):
            self.assertTrue(os.path.isdir(os.path.join(self.dest_path, dn)))

        # Check symlinked root contents
        dest_path = os.path.join(self.dest_path, 'symlinked')
        for fn in ('index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(dest_path, fn)))

        # Check symlinked subgal contents
        dest_path = os.path.join(self.dest_path, 'symlinked', 'subgal')
        for fn in ('index.html', 'index_medium.html',
                   'img0.html', 'img0_medium.html',
                   'img0_thumb.jpg', 'img0_small.jpg',
                   'img0_medium.jpg',
                   'img1.html', 'img1_medium.html',
                   'img1_thumb.jpg', 'img1_small.jpg',
                   'img1_medium.jpg'):
            fp = os.path.join(dest_path, fn)
            self.assertTrue(os.path.isfile(fp), "%s is missing" % fp)

        # Check that symlinked initial root has not been processed
        self.assertFalse(os.path.isdir(os.path.join(self.dest_path, 'symlinked', 'subgal', 'do_not_follow')))


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
