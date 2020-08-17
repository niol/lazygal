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
import json

from PIL import Image

from . import LazygalTestGen, has_symlinks
import lazygal.config
from lazygal.generators import WebalbumDir
from lazygal.sourcetree import Directory
from lazygal.metadata import GEXIV2_DATE_FORMAT
from lazygal.pygexiv2 import GExiv2
from lazygal.mediautils import VideoProcessor


class TestGenerators(LazygalTestGen):

    def test_albumstats(self):
        pics = ['img%d.jpg' % i for i in range(0, 8)]
        self.setup_subgal('subgal', pics)
        self.setup_subgal('vidgal', ['vid.webm'])

        expected_stats = {
            self.source_dir: 0,
            os.path.join(self.source_dir, 'subgal') : 8,
            os.path.join(self.source_dir, 'vidgal') : 1,
        }

        self.assertEqual(self.album.stats()['total'], 9)
        self.assertEqual(self.album.stats()['bydir'], expected_stats)

    def test_genfile_filelayout(self):
        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        error = '%s has not been generate though it should have'

        # Check root dir contents
        self.assertTrue(os.path.isdir(dest_path))
        for fn in ('index.json', 'index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(dest_path, fn)),
                            error % fn)

        # Check subgal dir contents
        dest_subgal_path = os.path.join(dest_path, 'subgal')
        self.assertTrue(os.path.isdir(dest_subgal_path))
        for fn in ('index.json', 'index.html', 'index_medium.html',
                   'subgal_img.html', 'subgal_img_medium.html',
                   'subgal_img_thumb.jpg', 'subgal_img_small.jpg',
                   'subgal_img_medium.jpg'):
            self.assertTrue(os.path.isfile(os.path.join(dest_subgal_path, fn)),
                            error % fn)

        # Check JSON root index
        with open(os.path.join(dest_path, 'index.json')) as json_fp:
            pindex = json.load(json_fp)
            self.assertEqual(pindex['medias'], {})
            self.assertEqual(pindex['count'],
                             {'media': 0, 'video': 0, 'image': 0, 'subgal': 1})
            self.assertEqual(pindex['all_count'],
                             {'media': 1, 'video': 0, 'image': 1})
            self.assertEqual(pindex['subgals'], ['subgal'])

        # Check JSON subgal index
        with open(os.path.join(dest_path, 'subgal', 'index.json')) as json_fp:
            pindex = json.load(json_fp)
            self.assertEqual(pindex['medias'], {'subgal_img.jpg': {
                'comment': None,
                'date': '2010-02-05T23:56:24',
                'width': 640,
                'height': 427,
                'metadata': {
                    'date'        : '2010-02-05T23:56:24',
                    'comment'     : None,
                    'rotation'    : 0,
                    'camera_name' : 'HTC Dream',
                    'lens_name'   : '',
                    'flash'       : '',
                    'exposure'    : 'None',
                    'iso'         : '',
                    'fnumber'     : '',
                    'focal_length': '',
                    'authorship'  : '',
                    'keywords'    : [],
                    'location'    : None,
                },
                'type': 'image',
            }})
            self.assertEqual(pindex['count'],
                             {'media': 1, 'video': 0, 'image': 1, 'subgal': 0})
            self.assertEqual(pindex['all_count'],
                             {'media': 1, 'video': 0, 'image': 1})
            self.assertEqual(pindex['subgals'], [])


    def test_genfile_umask(self):
        """
        The software should honor the umask setting.
        """
        oldmask = os.umask(0o027)

        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        target_dperms = oct(0o040750)
        target_fperms = oct(0o0100640)

        error = 'wrong perms %s instead of %s for %s'

        for root, dir, files in os.walk(dest_path):
            for f in files:
                fpath = os.path.join(root, f)
                fperms = oct(os.stat(fpath).st_mode)
                self.assertEqual(fperms, target_fperms,
                                 error % (fperms, target_fperms, fpath))

        for d in ('subgal', 'shared'):
            dpath = os.path.join(dest_path, d)
            dperms = oct(os.stat(dpath).st_mode)
            self.assertEqual(dperms, target_dperms,
                             error % (dperms, target_dperms, dpath))

        os.umask(oldmask)

    def test_spot_foreign_files(self):
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
        os.mkdir(os.path.join(dest_path, 'extra_dir'))

        # remove a pic in source_dir
        os.unlink(os.path.join(self.source_dir, 'subgal', 'img6.jpg'))

        # new objects to probe filesystem
        pics.remove('img6.jpg')
        source_subgal = Directory(os.path.join(self.source_dir, 'subgal'),
                                  [], pics, self.album)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)
        expected = map(lambda fn: os.path.join(dest_path, 'subgal', fn),
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
        expected =  map(lambda fn: os.path.join(dest_path, fn),
                        ['extra_thumb.jpg', 'extra_dir']
                       )
        self.assertEqual(sorted(dest_gal.list_foreign_files()),
                         sorted(expected))

    def test_cleanup(self):
        """
        Check that the foreign files are deleted.
        """
        config = lazygal.config.LazygalConfig()
        config.set('global', 'clean-destination', "true")
        self.setup_album(config)

        pics = ['img%02d.jpg' % i for i in range(4, 8)]
        source_subgal = self.setup_subgal('subgal', pics)

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        # add thumbs and directories that should not be there
        self.add_img(dest_path, 'extra_thumb.jpg')
        self.add_img(os.path.join(dest_path, 'subgal'), 'extra_thumb2.jpg')
        os.mkdir(os.path.join(dest_path, 'extra_dir'))
        self.add_img(os.path.join(dest_path, 'extra_dir'), 'extra_thumb3.jpg')

        # remove a pic in source_dir
        os.unlink(os.path.join(self.source_dir, 'subgal', 'img06.jpg'))

        self.album.generate(dest_path)

        try:
            for f in ['extra_thumb2.jpg',
                    'img06_thumb.jpg', 'img06_small.jpg', 'img06_medium.jpg',
                    'img06.html', 'img06_medium.html',
                    ]:
                self.assertFalse(os.path.isfile(os.path.join(dest_path, 'subgal', f)))

            for f in ['extra_thumb.jpg']:
                self.assertFalse(os.path.isfile(os.path.join(dest_path, f)))
            for f in ['extra_dir']:
                self.assertFalse(os.path.isdir(os.path.join(dest_path, f)))
        except AssertionError:
            print("\n contents of dest_path : ")
            print(sorted(os.listdir(dest_path)))
            print(sorted(os.listdir(os.path.join(dest_path, 'subgal'))))
            raise

    def test_clean_empty_dirs(self):
        """
        Check that empty dirs at destination are removed
        .
        This case might happen when (1) the destination dir is created according
        to the contents of source_dir.
        (2) Then source_dir becomes empty, either because all the images have
        been removed, or because tag filtering is applied with different
        settings. The next lazygal generation should remove the destination dir.
        """
        config = lazygal.config.LazygalConfig()
        config.set('global', 'clean-destination', "true")
        self.setup_album(config)

        pics = ['img.jpg']
        source_subgal = self.setup_subgal('subgal', pics)

        dest_path = self.get_working_path()
        self.album.generate(dest_path)

        # all the files in subgal should be here after the first generation
        try:
            for f in ['img_thumb.jpg', 'img_small.jpg', 'img_medium.jpg',
                     'img.html', 'img_medium.html',
                     ]:
                self.assertTrue(os.path.isfile(os.path.join(dest_path, 'subgal', f)))

            for f in ['subgal']:
                self.assertTrue(os.path.isdir(os.path.join(dest_path, f)))
        except AssertionError:
            print("\n contents of dest_path after first generation: ")
            print(sorted(os.listdir(dest_path)))
            print(sorted(os.listdir(os.path.join(dest_path, 'subgal'))))
            raise

        # remove the pic in subgal, and force a new generation
        os.unlink(os.path.join(self.source_dir, 'subgal', 'img.jpg'))
        self.album.generate(dest_path)

        # now the subdirectory subgal and its contents should no longer be there
        try:
            for f in ['img.jpg',
                     'img_thumb.jpg', 'img_small.jpg', 'img_medium.jpg',
                     'img.html', 'img_medium.html',
                     ]:
                self.assertFalse(os.path.isfile(os.path.join(dest_path, 'subgal', f)))

            for f in ['subgal']:
                self.assertFalse(os.path.isdir(os.path.join(dest_path, f)))
        except AssertionError:
            print("\n contents of dest_path after the second generation: ")
            print(sorted(os.listdir(dest_path)))
            print(sorted(os.listdir(os.path.join(dest_path, 'subgal'))))
            raise

    @unittest.skipIf(not has_symlinks(), 'symlinks not supported on platform')
    def test_clean_dirsymlinks(self):
        """
        Check that symlinks in directory source, that should make albums
        in dest, are not cleaned up in dest.
        """
        config = lazygal.config.LazygalConfig()
        config.set('global', 'clean-destination', "true")
        self.setup_album(config)

        pics = ['img.jpg']
        source_subgal = self.setup_subgal('subgal', pics)

        # add a symlink on source that should be duplicated in dest
        out_of_tree_subgal = os.path.join(self.get_working_path(),
                                          'oot_subgal')
        os.mkdir(out_of_tree_subgal)
        self.add_img(out_of_tree_subgal, 'oot_img.jpg')
        os.symlink(out_of_tree_subgal,
                   os.path.join(self.source_dir, 'oot_subgal_symlink'))

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        # all the files in subgal should be here after the first generation
        try:
            self.assertTrue(os.path.isdir(os.path.join(dest_path,
                                                        'subgal')))
            for f in ['img_thumb.jpg', 'img_small.jpg',
                        'img_medium.jpg', 'img.html', 'img_medium.html',
                        ]:
                self.assertTrue(os.path.isfile(os.path.join(dest_path,
                                                            'subgal', f)))
            self.assertTrue(os.path.isdir(os.path.join(dest_path,
                                                    'oot_subgal_symlink')))
            for f in ['oot_img_thumb.jpg', 'oot_img_small.jpg',
                        'oot_img_medium.jpg', 'oot_img.html',
                        'oot_img_medium.html',
                        ]:
                self.assertTrue(os.path.isfile(os.path.join(dest_path,
                                                    'oot_subgal_symlink', f)))
        except AssertionError:
            print("\n contents of dest_path after first generation: ")
            print(sorted(os.listdir(dest_path)))
            print(sorted(os.listdir(os.path.join(dest_path, 'subgal'))))
            raise

        # remove the pic in subgal, and force a new generation
        os.unlink(os.path.join(self.source_dir, 'subgal', 'img.jpg'))
        os.rmdir(os.path.join(self.source_dir, 'subgal'))
        self.album.generate(dest_path)

        # only file in symlinkd gal should be there
        try:
            self.assertFalse(os.path.exists(os.path.join(dest_path,
                                                         'subgal')))
            for f in ['img_thumb.jpg', 'img_small.jpg',
                        'img_medium.jpg', 'img.html', 'img_medium.html',
                        ]:
                self.assertFalse(os.path.exists(os.path.join(dest_path,
                                                             'subgal', f)))
            self.assertTrue(os.path.isdir(os.path.join(dest_path,
                                                    'oot_subgal_symlink')))
            for f in ['oot_img_thumb.jpg', 'oot_img_small.jpg',
                        'oot_img_medium.jpg', 'oot_img.html',
                        'oot_img_medium.html',
                        ]:
                self.assertTrue(os.path.isfile(os.path.join(dest_path,
                                                    'oot_subgal_symlink', f)))
        except AssertionError:
            print("\n contents of dest_path after first generation: ")
            print(sorted(os.listdir(dest_path)))
            print(sorted(os.listdir(os.path.join(dest_path, 'subgal'))))
            raise

    @unittest.skipIf(not has_symlinks(), 'symlinks not supported on platform')
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
        self.assertTrue(os.path.islink(symlink))
        # Test if that symlink point to the image in the source_dir
        self.assertEqual(os.path.realpath(symlink), img_path)

    def test_metadata_osize_copy(self):
        img_path = self.add_img(self.source_dir, 'md_filled.jpg')

        # Add some metadata
        gps_data = GExiv2.Metadata(self.get_sample_path('sample-with-gps.jpg'))
        source_image = GExiv2.Metadata(img_path)
        for tag in gps_data.get_exif_tags():
            source_image[tag] = gps_data[tag]
        dummy_comment = 'nice photo'
        source_image['Exif.Photo.UserComment'] = dummy_comment
        dummy_date = datetime.datetime(2011, 2, 3, 12, 51, 43)
        source_image['Exif.Photo.DateTimeDigitized'] = dummy_date.strftime(GEXIV2_DATE_FORMAT)
        assert 'Exif.GPSInfo.GPSLongitude' in source_image
        assert 'Exif.GPSInfo.GPSLatitude' in source_image
        source_image.save_file()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_img_path = os.path.join(dest_dir, 'md_filled_small.jpg')
        dest_image = GExiv2.Metadata(dest_img_path)

        # Check that metadata is still here for reduced pictures.
        self.assertEqual(dest_image['Exif.Photo.UserComment'], dummy_comment)
        self.assertEqual(dest_image['Exif.Photo.DateTimeDigitized'], dummy_date.strftime('%Y:%m:%d %H:%M:%S'))

        # Check that blacklised tags are not present anymore in the reduced
        # picture.
        def lat(): return dest_image['Exif.GPSInfo.GPSLongitude']
        self.assertRaises(KeyError, lat)

        def long(): return dest_image['Exif.GPSInfo.GPSLatitude']
        self.assertRaises(KeyError, long)

        # Check that metadata is not in the JSON index
        with open(os.path.join(dest_dir, 'index.json')) as json_fp:
            pindex = json.load(json_fp)
            self.assertEqual(pindex['medias']['md_filled.jpg']['metadata']['location'],
                             None)

    def test_metadata_osize_nopublish(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'publish-metadata', 'No')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'md_filled.jpg')

        # Add some metadata
        source_image = GExiv2.Metadata(img_path)
        dummy_comment = 'nice photo'
        source_image['Exif.Photo.UserComment'] = dummy_comment
        source_image.save_file()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_img_path = os.path.join(dest_dir, 'md_filled_small.jpg')
        dest_image = GExiv2.Metadata(dest_img_path)

        # Check that metadata is not here for reduced pictures.
        def com(): return dest_image['Exif.Photo.UserComment']
        self.assertRaises(KeyError, com)

        # Check that metadata is not in the JSON index
        with open(os.path.join(dest_dir, 'index.json')) as json_fp:
            pindex = json.load(json_fp)
            self.assertFalse('metadata' in pindex['medias']['md_filled.jpg'])

    def test_resize_rotate_size(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'image-size', 'std=800x600')
        self.setup_album(config)

        norotate_path = self.add_img(self.source_dir, 'norotate.jpg')
        torotate_path = self.add_img(self.source_dir, 'torotate.jpg')
        torotate = GExiv2.Metadata(torotate_path)
        torotate['Exif.Image.Orientation'] = '8'
        torotate.save_file()

        # Generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        dest_norotate_path = os.path.join(dest_dir, 'norotate_std.jpg')
        im = Image.open(dest_norotate_path)
        self.assertEqual(im.size, (800, 533, ))
        im.close()

        dest_torotate_path = os.path.join(dest_dir, 'torotate_std.jpg')
        im = Image.open(dest_torotate_path)
        self.assertEqual(im.size, (400, 600, ))
        im.close()

    def test_feed(self):
        config = lazygal.config.LazygalConfig()
        config.set('global', 'puburl', 'http://example.com/album/')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'img01.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'index.xml')))

    def test_dirzip(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'dirzip', 'Yes')
        self.setup_album(config)

        img_path = self.add_img(self.source_dir, 'img01.jpg')
        img_path = self.add_img(self.source_dir, 'img02.jpg')
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'src.zip')))

    def test_filter_by_tag(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'filter-by-tag', 'lazygal')
        self.setup_album(config)

        # tagfound pictures will be pushed on the destination, tagnotfound pictures
        # should be filtered out.
        # The sub-directory 'sdir_tagnotfound' should not be created on the destination
        # side, because it should be empty.
        tagfound_path           = self.add_img(self.source_dir, 'tagfound.jpg')
        tagfound2_path          = self.add_img(self.source_dir, 'tagfound2.jpg')
        tagnotfound_path        = self.add_img(self.source_dir, 'tagnotfound.jpg')
        untagged_path           = self.add_img(self.source_dir, 'untagged.jpg')
        sdir_tagfound           = self.setup_subgal('sdir_tagfound', ['sdir_tagfound.jpg', 'sdir_tagnotfound.jpg'])
        sdir_tagnotfound        = self.setup_subgal('sdir_tagnotfound', ['sdir_tagfound.jpg', 'sdir_tagnotfound.jpg'])
        sdir_untagged           = self.setup_subgal('sdir_untagged', ['untagged.jpg'])
        tagfound_subdir_path    = os.path.join(self.source_dir, sdir_tagfound.name, 'sdir_tagfound.jpg')
        tagnotfound_subdir_path = os.path.join(self.source_dir, sdir_tagnotfound.name, 'sdir_tagnotfound.jpg')
        tagfound       = GExiv2.Metadata(tagfound_path)
        tagfound2      = GExiv2.Metadata(tagfound2_path)
        tagnotfound    = GExiv2.Metadata(tagnotfound_path)
        tagfound_sd    = GExiv2.Metadata(tagfound_subdir_path)
        tagnotfound_sd = GExiv2.Metadata(tagnotfound_subdir_path)
        tagfound['Iptc.Application2.Keywords']       = 'lazygal'
        tagfound['Xmp.dc.subject']                   = 'lazygal2'
        tagfound.save_file()
        tagfound2['Iptc.Application2.Keywords']      = 'lazygalagain'
        tagfound2['Xmp.dc.subject']                  = 'lazygal'
        tagfound2.save_file()
        tagnotfound['Iptc.Application2.Keywords']    = 'another_tag'
        tagnotfound.save_file()
        tagfound_sd['Iptc.Application2.Keywords']    = 'lazygal'
        tagfound_sd['Xmp.dc.subject']                = 'lazygal2'
        tagfound_sd.save_file()
        tagnotfound_sd['Iptc.Application2.Keywords'] = 'lazygal_lazygal'
        tagnotfound_sd['Xmp.dc.subject']             = 'lazygal2'
        tagnotfound_sd.save_file()

        # generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        try:
            self.assertTrue(os.path.isdir(os.path.join(dest_dir, 'sdir_tagfound')))
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'tagfound_thumb.jpg')))
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'tagfound2_thumb.jpg')))
            self.assertFalse(os.path.isfile(os.path.join(dest_dir, 'tagnotfound_thumb.jpg')))
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'sdir_tagfound', 'sdir_tagfound_thumb.jpg')))
            self.assertFalse(os.path.isfile(os.path.join(dest_dir, 'sdir_tagnotfound', 'sdir_tagnotfound_thumb.jpg')))
            self.assertFalse(os.path.isdir(os.path.join(dest_dir, 'sdir_tagnotfound')))
            self.assertFalse(os.path.isfile(os.path.join(dest_dir, 'sdir_untagged', 'untagged.jpg')))
            self.assertFalse(os.path.isdir(os.path.join(dest_dir, 'sdir_untagged')))
        except AssertionError:
            print("\n contents of dest_dir : ")
            print(os.listdir(dest_dir))
            raise

    def test_filter_and_dirzip(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'dirzip', 'Yes')
        config.set('webgal', 'filter-by-tag', 'lazygal')
        self.setup_album(config)

        # We need at least two pictures to display, because lazygal generates a
        # zip archive only if there is more than one picture.
        tagfound_path    = self.add_img(self.source_dir, 'tagfound.jpg')
        tagfound_path2   = self.add_img(self.source_dir, 'tagfound2.jpg')
        tagnotfound_path = self.add_img(self.source_dir, 'tagnotfound.jpg')
        tagfound    = GExiv2.Metadata(tagfound_path)
        tagfound2   = GExiv2.Metadata(tagfound_path2)
        tagnotfound = GExiv2.Metadata(tagnotfound_path)
        tagfound['Iptc.Application2.Keywords']    = 'lazygal'
        tagfound['Xmp.dc.subject']                = 'lazygal2'
        tagfound.save_file()
        tagfound2['Iptc.Application2.Keywords']   = 'lazygalagain'
        tagfound2['Xmp.dc.subject']               = 'lazygal'
        tagfound2.save_file()
        tagnotfound['Iptc.Application2.Keywords'] = 'another_tag'
        tagnotfound.save_file()

        # generate album
        dest_dir = self.get_working_path()
        self.album.generate(dest_dir)

        try:
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'src.zip')))
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'tagfound_thumb.jpg')))
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, 'tagfound2_thumb.jpg')))
            self.assertFalse(os.path.isfile(os.path.join(dest_dir, 'false_thumb.jpg')))
        except AssertionError:
            print("\n contents of dest_dir : ")
            print(os.listdir(dest_dir))
            raise

    def test_withvideo(self):
        source_subgal = self.setup_subgal('subgal', [], ['vid.mov',
                                                         'vid-silent.mov'])

        # silence a video to make sure it does not crash
        silencer = VideoProcessor(os.path.join(source_subgal.path, 'vid.mov'))
        silencer.cmd.extend(['-c', 'copy', '-an'])
        # overwrite the existing file
        silencer.convert(os.path.join(source_subgal.path, 'vid-silent.mov'))

        # create empty video file to ensure nothing crashes
        self.create_file(os.path.join(source_subgal.path, 'vid-broken.mov'))

        dest_path = self.get_working_path()

        self.album.generate(dest_path)

        error = '%s has not been generated though it should have'

        # Check root dir contents
        self.assertTrue(os.path.isdir(dest_path))
        for fn in ('index.html', 'index_medium.html'):
            self.assertTrue(os.path.isfile(os.path.join(dest_path, fn)),
                            error % fn)

        # Check subgal dir contents
        dest_subgal_path = os.path.join(dest_path, 'subgal')
        self.assertTrue(os.path.isdir(dest_subgal_path))
        for fn in ('index.html', 'index_medium.html',
                   'vid.html', 'vid_medium.html', 'vid_thumb.jpg',
                   'vid_video.webm',
                   'vid-silent.html', 'vid-silent_medium.html', 'vid-silent_thumb.jpg',
                   'vid-silent_video.webm'):
            self.assertTrue(os.path.isfile(os.path.join(dest_subgal_path, fn)),
                            error % fn)


class TestSpecialGens(LazygalTestGen):

    def setUp(self):
        super().setUp(False)
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
        config.set('global', 'dir-flattening-depth', 0)
        self.setup_album(config)

        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])
        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    def test_flattenpaginate(self):
        config = lazygal.config.LazygalConfig()
        config.set('webgal', 'thumbs-per-page', 4)
        config.set('global', 'dir-flattening-depth', 0)
        self.setup_album(config)

        pics = ['img%d.jpg' % i for i in range(0, 9)]
        source_subgal = self.setup_subgal('subgal', pics)

        self.album.generate(self.dest_path)
        # FIXME: Check dest dir contents, test only catches uncaught exceptions
        # for now...

    @unittest.skipIf(not has_symlinks(), 'symlinks not supported on platform')
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
        super().setUp(False)
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
            img_exif = GExiv2.Metadata(img_path)
            for tag in ('Exif.Photo.DateTimeDigitized',
                        'Exif.Photo.DateTimeOriginal',
                        'Exif.Image.DateTime',
                        ):
                img_exif[tag] = datetime.datetime(
                    2011, months[index], 1).strftime('%Y:%m:%d %H:%M:%S')
            img_exif.save_file()

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

        dest_subgal.call_populate_deps()
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

        dest_subgal.call_populate_deps()
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

        dest_subgal.call_populate_deps()
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

        dest_subgal.call_populate_deps()
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

        dest_subgal.call_populate_deps()
        dest_subgal.sort_task.make()

        self.assertEqual(
            [subgal.source_dir.name for subgal in dest_subgal.subgals],
            [u'john', u'joe', u'albert', u'2012_Trip', u'1999_Christmas']
        )



if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
