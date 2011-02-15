# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2010 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import random, time
import unittest
from lazygal import newsize


class TestSizeParser(unittest.TestCase):

    def setUp(self):
        random.seed(time.time())

    def get_random_dimint(self):
        return random.randint(300, 2000)

    def get_random_size(self):
        return (self.get_random_dimint(), self.get_random_dimint())

    def get_random_percentage(self):
        return random.randint(10, 200)

    def assert_ratio_matches(self, orig_size, new_size):
        forig_size = map(float, orig_size)
        fnew_size = map(float, new_size)
        orig_ratio = forig_size[1] / forig_size[0]
        new_ratio = fnew_size[1] / fnew_size[0]
        self.assertAlmostEqual(orig_ratio, new_ratio, 2)

    def check(self, orig_size, size_string, expected_new_size, ratiocheck=True):
        newsizer = newsize.get_newsizer(size_string)
        dest_size = newsizer.dest_size(orig_size)
        self.assertEqual(expected_new_size, dest_size)
        if ratiocheck:
            self.assert_ratio_matches(orig_size, dest_size)

    def test_scale(self):
        orig_size = self.get_random_size()
        scale = self.get_random_percentage()
        size_string = '%d%%' % scale
        real_dest_size = tuple(map(lambda x: x*scale/100, orig_size))

        self.check(orig_size, size_string, real_dest_size)

        orig_size = (1600, 1200)
        size_string = '50%'
        real_dest_size = (800, 600)

        self.check(orig_size, size_string, real_dest_size)

    def test_xyscale(self):
        orig_size = self.get_random_size()
        xscale = self.get_random_percentage()
        yscale = self.get_random_percentage()
        size_string = '%d%%%d%%' % (xscale, yscale)
        x = orig_size[0]
        y = orig_size[1]
        real_dest_size = (x*xscale/100, y*yscale/100)

        self.check(orig_size, size_string, real_dest_size, ratiocheck=False)

        orig_size = (1600, 1200)
        size_string = '50%75%'
        real_dest_size = (800, 900)

        self.check(orig_size, size_string, real_dest_size, ratiocheck=False)

    def test_width(self):
        orig_size = (1024, 768)
        size_string = '640'
        real_dest_size = (640, 480)

        self.check(orig_size, size_string, real_dest_size)

    def test_height(self):
        orig_size = (1024, 768)
        size_string = 'x1200'
        real_dest_size = (1600, 1200)

        self.check(orig_size, size_string, real_dest_size)

    def test_maxwidthheight(self):
        self.check((1024, 768), '800x600', (800, 600))
        self.check((768, 1024), '800x600', (450, 600))

    def test_minwidthheight(self):
        self.check((1024, 768), '800x600^', (800, 600))
        self.check((768, 1024), '800x600^', (800, 1066))

    def test_mandatorywidthheight(self):
        self.check((1024, 768), '800x600!', (800, 600), ratiocheck=False)
        self.check((768, 1024), '800x600!', (800, 600), ratiocheck=False)

    def test_widthheightiflarger(self):
        self.check((1024, 768), '800x600>', (800, 600))
        self.check((768, 1024), '800x600>', (450, 600))
        self.check((420, 200), '800x600>', (420, 200))

    def test_widthheightifsmaller(self):
        self.check((1024, 768), '800x600<', (1024, 768))
        self.check((768, 1024), '800x600<', (768, 1024))
        self.check((420, 200), '800x600<', (1260, 600))
        self.check((420, 700), '800x600<', (420, 700))

    def test_area(self):
        self.check((1024, 768), '480000@', (800, 600))
        self.check((768, 1024), '480000@', (600, 800))

if __name__ == '__main__':
    unittest.main()


# vim: ts=4 sw=4 expandtab
