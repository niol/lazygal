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


import os
import time
import unittest

from __init__ import LazygalTestGen
from lazygal.generators import WebalbumDir
from lazygal.sourcetree import Directory
from lazygal.genpage import WebalbumIndexPage
from lazygal import pyexiv2api as pyexiv2


class TestDeps(LazygalTestGen):
    """
    Dependencies of built items
    """

    def test_second_build(self):
        """
        Once built, a webgal shall not need build.
        """
        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = os.path.join(self.tmpdir, 'dst')
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.assertTrue(dest_subgal.needs_build(),
               'Webalbum subgal has not been built and does not need build.')

        self.album.generate(dest_path)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.assertFalse(dest_subgal.needs_build(),
            'Webalbum subgal has been built and does need build because of %s.'\
            % str(dest_subgal.needs_build(True)))

    def test_dirmetadata_update(self):
        """
        Updated directory metadata file shall trigger the rebuild of the
        corresponding webgal directory.
        """
        subgal_path = os.path.join(self.source_dir, 'subgal')
        os.mkdir(subgal_path)
        self.add_img(subgal_path, 'subgal_img.jpg')

        # metadata must exist before creating the Directory() object (md files
        # are probed in the constructor.
        self.album.generate_default_metadata()

        source_subgal = Directory(subgal_path, [], ['subgal_img.jpg'],
                                  self.album)

        dest_path = os.path.join(self.tmpdir, 'dst')

        self.album.generate(dest_path)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.assertFalse(dest_subgal.needs_build(),
            'Webalbum subgal has been built and does need build because of %s.'\
            % str(dest_subgal.needs_build(True)))

        # touch the description file
        time.sleep(1) # ensure time diffrence for some systems
        os.utime(os.path.join(source_subgal.path, 'album_description'), None)
        # New objects in order to probe filesystem
        source_subgal = Directory(subgal_path, [], ['subgal_img.jpg'],
                                  self.album)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.assertTrue(dest_subgal.needs_build(),
            'Webalbum subgal should need build because of updated dir md.')

    def test_subgal_update(self):
        """
        Updated subgals shall trigger the webgal rebuild and the parent
        directory index rebuild.
        """
        source_subgal = self.setup_subgal('subgal', ['subgal_img.jpg'])

        dest_path = os.path.join(self.tmpdir, 'dst')

        self.album.generate(dest_path)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        self.assertFalse(dest_subgal.needs_build(),
            'Webalbum subgal has been built and does need build because of %s.'\
            % str(dest_subgal.needs_build(True)))

        self.add_img(source_subgal.path, 'subgal_img2.jpg')
        # New objects to ensure pic is taken into account
        source_subgal = Directory(source_subgal.path, [],
                                  ['subgal_img.jpg', 'subgal_img2.jpg'],
                                  self.album)
        dest_subgal = WebalbumDir(source_subgal, [], self.album, dest_path)

        # Subgal should need build.
        self.assertTrue(dest_subgal.needs_build(),
            'Webalbum subgal should need build because of added pic in subgal.')

        # Parent directory should need build.
        source_gal = Directory(self.source_dir, [source_subgal], [], self.album)
        dest_gal = WebalbumDir(source_gal, [dest_subgal], self.album, dest_path)
        self.assertTrue(dest_gal.needs_build(),
            'Webalbum gal should need build because of added pic in subgal.')

        # Parent directory should need build.
        parent_index = WebalbumIndexPage(dest_gal, 'small', 0,
                                         [dest_subgal],
                                         [(dest_subgal, dest_subgal.medias)])
        self.assertTrue(parent_index.needs_build(),
         'Webalbum gal index should need build because of added pic in subgal.')


if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
