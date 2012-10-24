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
import shutil

import Image

from __init__ import LazygalTestGen, skip, has_symlinks
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
        """
        Files that are not part of what was generated or updated shall be
        spotted.
        """
        pics = ['img%d.jpg' % i for i in range(0, 8)]
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
        expected = map(lambda fn:
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

    @skip(not has_symlinks(), 'symlinks not supported on platform')
    def test_originals_symlinks(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'original', 'Yes')
        config.set('webgal', 'original-symlink', 'Yes')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'symlink_target.jpg')

        dest_dir = self.get_working_path()
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

    def test_metadata_osize_nopublish(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'publish-metadata', 'No')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'md_filled.jpg')

        # Add some metadata
        source_image = pyexiv2.ImageMetadata(img_path)
        source_image.read()
        dummy_comment = 'nice photo'
        source_image['Exif.Photo.UserComment'] = dummy_comment
        source_image.write()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_img_path = os.path.join(dest_dir, 'md_filled_small.jpg')
        dest_image = pyexiv2.ImageMetadata(dest_img_path)
        dest_image.read()

        # Check that metadata is not here for reduced pictures.
        def com(): return dest_image['Exif.Photo.UserComment'].value
        self.assertRaises(KeyError, com)

    def test_resize_rotate_size(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'image-size', 'std=800x600')
        self.setup_album(config)

        norotate_path = self.add_img(self.source_dir, 'norotate.jpg')
        torotate_path = self.add_img(self.source_dir, 'torotate.jpg')
        torotate = pyexiv2.ImageMetadata(torotate_path)
        torotate.read()
        torotate['Exif.Image.Orientation'] = 8
        torotate.write()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_norotate_path = os.path.join(dest_dir, 'norotate_std.jpg')
        self.assertEqual(Image.open(dest_norotate_path).size, (800, 533, ))
        dest_torotate_path = os.path.join(dest_dir, 'torotate_std.jpg')
        self.assertEqual(Image.open(dest_torotate_path).size, (400, 600, ))

    def test_feed(self):
        config = lazygal.config.LazygalConfig()
        config.set('global', 'puburl', 'http://example.com/album/')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'img01.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        self.assertEqual(os.path.isfile(os.path.join(dest_dir, 'index.xml')),
                         True)

    def test_dirzip(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'dirzip', 'Yes')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'img01.jpg')
        img_path = self.add_img(self.source_dir, 'img02.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        self.assertEqual(os.path.isfile(os.path.join(dest_dir, 'src.zip')),
                         True)


class TestSpecialGens(LazygalTestGen):

    def setUp(self):
        super(TestSpecialGens, self).setUp(False)
        self.dest_path = os.path.join(self.tmpdir, 'dst')

    def test_paginate(self):
        """
        It shall be possible to split big galleries on mutiple index pages.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'thumbs-per-page', 4)
        self.setup_album(config)

        pics = ['img%d.jpg' % i for i in range(0, 9)]
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

        pics = ['img%d.jpg' % i for i in range(0, 9)]
        source_subgal = self.setup_subgal('subgal', pics)

        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    @skip(not has_symlinks(), 'symlinks not supported on platform')
    def test_dir_symlink(self):
        """
        The generator should follow symlinks on directories, but should not get
        stuck in infinite recursion if two distinct directory trees have
        symbolic links to each other.
        """
        self.setup_album()

        pics = ['img%d.jpg' % i for i in range(0, 2)]
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


class TestSorting(LazygalTestGen):

    def setUp(self):
        super(TestSorting, self).setUp(False)
        self.dest_path = os.path.join(self.tmpdir, 'dst')

    def __setup_pics(self, subgal_name=None):
        if subgal_name is None:
            subgal_name = 'subgal'
        subgal_path = os.path.join(self.source_dir, subgal_name)
        os.mkdir(subgal_path)

        pics = ['4-december.jpg', '6-january.jpg', '1-february.jpg', '3-june.jpg', '5-august.jpg']
        months = [12, 1, 2, 6, 8]
        for index, pic in enumerate(pics):

            img_path = self.add_img(subgal_path, pic)
            img_exif = pyexiv2.ImageMetadata(img_path)
            img_exif.read()
            for tag in ('Exif.Photo.DateTimeDigitized',
                        'Exif.Photo.DateTimeOriginal',
                        'Exif.Image.DateTime',
                        ):
                img_exif[tag] = datetime.datetime(2011, months[index], 1)
            img_exif.write()

        return subgal_path, pics

    def test_sortbyexif(self):
        """
        It shall be possible to sort images in a gallery according to EXIF
        date.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'sort-medias', 'exif')
        self.setup_album(config)
        subgal_path, pics = self.__setup_pics()

        src_dir = Directory(subgal_path, [], pics, self.album)
        dest_subgal = WebalbumDir(src_dir, [], self.album, self.dest_path)

        dest_subgal.sort_task.make()

        self.assertEqual([media.media.filename for media in dest_subgal.medias],
                         [u'6-january.jpg', u'1-february.jpg', u'3-june.jpg', u'5-august.jpg', u'4-december.jpg'])

    def test_sortbyexif_galsplit(self):
        """
        It shall be possible to sort images in galleries split on multiple
        pages according to EXIF date.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'sort-medias', 'exif')
        config.set('webgal', 'thumbs-per-page', 3)
        self.setup_album(config)
        subgal_path, pics = self.__setup_pics()

        src_dir = Directory(subgal_path, [], pics, self.album)
        dest_subgal = WebalbumDir(src_dir, [], self.album, self.dest_path)

        dest_subgal.sort_task.make()

        self.assertEqual([media.media.filename for media in dest_subgal.medias],
                         [u'6-january.jpg', u'1-february.jpg', u'3-june.jpg', u'5-august.jpg', u'4-december.jpg'])

        # page #1
        page_medias = dest_subgal.index_pages[0][0].galleries[0][1]
        self.assertEqual([media.media.filename for media in page_medias],
                         [u'6-january.jpg', u'1-february.jpg', u'3-june.jpg'])
        # page #2
        page_medias = dest_subgal.index_pages[1][0].galleries[0][1]
        self.assertEqual([media.media.filename for media in page_medias],
                         [u'5-august.jpg', u'4-december.jpg'])

    def test_sortbyfilename(self):
        """
        It shall be possible to sort images in a gallery by filename.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'sort-medias', 'filename')
        self.setup_album(config)
        subgal_path, pics = self.__setup_pics()

        src_dir = Directory(subgal_path, [], pics, self.album)
        dest_subgal = WebalbumDir(src_dir, [], self.album, self.dest_path)

        dest_subgal.sort_task.make()

        self.assertEqual([media.media.filename for media in dest_subgal.medias],
                         [u'1-february.jpg', u'3-june.jpg', u'4-december.jpg', u'5-august.jpg', u'6-january.jpg'])

    def test_sortbyfilename_galsplit(self):
        """
        It shall be possible to sort images in galleries split on multiple
        pages by filename.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'sort-medias', 'filename')
        config.set('webgal', 'thumbs-per-page', 3)
        self.setup_album(config)
        subgal_path, pics = self.__setup_pics()

        src_dir = Directory(subgal_path, [], pics, self.album)
        dest_subgal = WebalbumDir(src_dir, [], self.album, self.dest_path)

        dest_subgal.sort_task.make()

        self.assertEqual([media.media.filename for media in dest_subgal.medias],
                         [u'1-february.jpg', u'3-june.jpg', u'4-december.jpg', u'5-august.jpg', u'6-january.jpg'])

        # page #1
        page_medias = dest_subgal.index_pages[0][0].galleries[0][1]
        self.assertEqual([media.media.filename for media in page_medias],
                         [u'1-february.jpg', u'3-june.jpg', u'4-december.jpg'])
        # page #2
        page_medias = dest_subgal.index_pages[1][0].galleries[0][1]
        self.assertEqual([media.media.filename for media in page_medias],
                         [u'5-august.jpg', u'6-january.jpg'])

    def test_sortsubgals_dirnamereverse(self):
        """
        It shall be possible to sort sub-galleries accoring to the directory
        name.
        """
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'sort-subgals', 'dirname:reverse')
        self.setup_album(config)

        subgal_names = ('john', '2012_Trip', 'albert', '1999_Christmas', 'joe', )
        subgals_src = []
        subgals_dst = []
        for subgal_name in subgal_names:
            path, pics = self.__setup_pics(subgal_name)
            src = Directory(path, [], pics, self.album)
            dst = WebalbumDir(src, [], self.album,
                              os.path.join(self.dest_path, subgal_name))
            subgals_src.append(src)
            subgals_dst.append(dst)

        src_dir = Directory(self.source_dir, subgals_src, [], self.album)
        dest_subgal = WebalbumDir(src_dir, subgals_dst, self.album, self.dest_path)

        dest_subgal.sort_task.make()

        self.assertEqual(
            [subgal.source_dir.name for subgal in dest_subgal.subgals],
            [u'john', u'joe', u'albert', u'2012_Trip', u'1999_Christmas']
        )


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
