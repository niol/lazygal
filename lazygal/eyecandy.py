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
import Image, ImageDraw


class Color:
    TRANSPARENT = (0, 0, 0, 0)


class PictureMess:

    RESULT_SIZE = (200, 150)
    THUMB_HOW_MANY = 5
    THUMB_MAX_ROTATE_ANGLE = 40
    THUMB_SIZE = [3*max(RESULT_SIZE)/5 for i in range(2)]

    def __init__(self, images_paths, top_image_path=None, bg='transparent'):
        if len(images_paths) > self.THUMB_HOW_MANY:
            self.images_paths = random.sample(images_paths, self.THUMB_HOW_MANY)
        else:
            self.images_paths = images_paths

        if top_image_path:
            if top_image_path in self.images_paths:
                self.images_paths.remove(top_image_path)
            else:
                self.images_paths.pop()
            self.images_paths.append(top_image_path)

        self.bg = bg != 'transparent' and bg or Color.TRANSPARENT

        self.picture_mess = None

    def __frame(self, img, color='black', width=2):
        d = ImageDraw.Draw(img)
        w = width/2
        d.line(((w, w), (w, img.size[1]-w),
                (img.size[0]-w, img.size[1]-w), (img.size[0]-w, w), (w, w), ),
                fill=color, width=width)
        del d

    def __build_mess_thumb(self, image_path):
        mt = Image.open(image_path)

        # Make the picture smaller to avoid rotating a big picture and at the
        # same time have some good quality in rotated image.
        acceptable_working_size = map(lambda x: x*2, self.THUMB_SIZE)
        if mt.size[0] > acceptable_working_size[0]\
        or mt.size[1] > acceptable_working_size[1]:
            mt.thumbnail(map(lambda x: x*2, self.THUMB_SIZE), Image.ANTIALIAS)

        self.__frame(mt, 'white', 5)
        self.__frame(mt, 'black', 1)

        # Add an alpha channel to the pic
        if mt.mode != 'RGBA':
            mt = mt.convert('RGBA')
        mt.putalpha(mt.split()[3])

        rotation = random.randint(-self.THUMB_MAX_ROTATE_ANGLE,
                                  self.THUMB_MAX_ROTATE_ANGLE)
        rotated = mt.rotate(rotation, expand=True)
        rotated.thumbnail(self.THUMB_SIZE, Image.ANTIALIAS)
        return rotated

    def __rand_coord_with_step(self, coord, holding_coord):
        return random.randint(0, holding_coord - coord)

    def __place_thumb_box(self, thumb):
        x_to_fit = self.__rand_coord_with_step(thumb.size[0],
                                               self.picture_mess.size[0])
        y_to_fit = self.__rand_coord_with_step(thumb.size[1],
                                               self.picture_mess.size[1])
        return (x_to_fit, y_to_fit)

    def __add_img_to_mess_top(self, img):
        self.picture_mess.paste(img, self.__place_thumb_box(img), mask=img)

    def __build_picture_mess(self):
        self.picture_mess = Image.new("RGBA", self.RESULT_SIZE, self.bg)
        added_one_thumb = False
        for image_path in self.images_paths:
            try:
                mess_thumb = self.__build_mess_thumb(image_path)
            except IOError:
                # Do not add this thumb to the picture mess
                pass
            else:
                self.__add_img_to_mess_top(mess_thumb)
                added_one_thumb = True
        if not added_one_thumb:
            raise ValueError("No readable image found in submitted list.")

    def write(self, output_file):
        self.__build_picture_mess()
        self.picture_mess.save(output_file)


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser();
    parser.add_option("-s", "--seed", type="int", dest="seed")
    parser.add_option("-b", "--background", type="string",
                      dest="color", default="transparent")
    (options, args) = parser.parse_args()

    if options.seed:
        random.seed(options.seed)

    PictureMess(args[0:], bg=options.color).write('test.png')


# vim: ts=4 sw=4 expandtab
