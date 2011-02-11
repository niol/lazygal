# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import Image, ImageDraw, ImageChops, ImageFilter


class Color:
    TRANSPARENT = (0, 0, 0, 0)


class PictureMess:

    RESULT_SIZE = (200, 150)
    STEP = 5
    THUMB_HOW_MANY = 5
    THUMB_MAX_ROTATE_ANGLE = 40
    THUMB_SIZE = [3*max(RESULT_SIZE)/5 for i in range(2)]
    THUMB_WHITE_WIDTH = 5

    def __init__(self, images_paths, top_image_path=None, bg='transparent'):
        if len(images_paths) > self.THUMB_HOW_MANY:
            self.images_paths = random.sample(images_paths, self.THUMB_HOW_MANY)
        else:
            self.images_paths = images_paths

        if top_image_path:
            # Put the top image as the last in the list (the top of the image
            # stack).
            if top_image_path in self.images_paths:
                self.images_paths.remove(top_image_path)
            elif len(self.images_paths) >= self.THUMB_HOW_MANY:
                self.images_paths.pop()
            self.images_paths.append(top_image_path)

        self.bg = bg != 'transparent' and bg or Color.TRANSPARENT

        self.picture_mess = None

    def __build_mess_thumb(self, image_path):
        img = Image.open(image_path)
        img.thumbnail(self.THUMB_SIZE, Image.ANTIALIAS)

        white_size = [ x + 2*self.THUMB_WHITE_WIDTH for x in img.size ]

        white = Image.new('RGB', white_size, 'white')
        white.paste(img, (self.THUMB_WHITE_WIDTH, self.THUMB_WHITE_WIDTH))

        maxi = 2*max(white_size)

        thumb = Image.new('RGBA', (maxi, maxi))

        thumb.paste(white, ((maxi - white_size[0])/ 2,
                            (maxi - white_size[1])/ 2))

        rotation = random.randint(-self.THUMB_MAX_ROTATE_ANGLE,
                                  self.THUMB_MAX_ROTATE_ANGLE)
        thumb = thumb.rotate(rotation, resample=Image.BILINEAR)

        thumb = thumb.crop(thumb.getbbox())
        thumb.thumbnail(self.THUMB_SIZE, Image.ANTIALIAS)
        return thumb

    def __rand_coord_with_step(self, coord, holding_coord):
        return random.randint(0 + self.STEP, holding_coord - coord - self.STEP)

    def __place_thumb_box(self, thumb):
        x_to_fit = self.__rand_coord_with_step(thumb.size[0],
                                               self.picture_mess.size[0])
        y_to_fit = self.__rand_coord_with_step(thumb.size[1],
                                               self.picture_mess.size[1])
        return (x_to_fit, y_to_fit)

    def __paste_img_to_mess_top(self, img, pos):
        # http://www.mail-archive.com/image-sig@python.org/msg03387.html
        img_without_alpha = img.convert('RGB')

        if self.picture_mess.mode == 'RGBA':
            invert_alpha = ImageChops.invert(
                Image.merge('L', self.picture_mess.split()[3:]))
            if invert_alpha.size != img.size:
                w, h = img.size
                box = pos + (pos[0] + w, pos[1] + h)
                invert_alpha = invert_alpha.crop(box)
        else:
            invert_alpha = None

        self.picture_mess.paste(img_without_alpha, pos, img)

        if invert_alpha:
            dest_alpha = Image.merge('L', self.picture_mess.split()[3:])
            self.picture_mess.paste(img_without_alpha, pos, invert_alpha)
            self.picture_mess.putalpha(dest_alpha)

    def __add_img_to_mess_top(self, img):
        self.__paste_img_to_mess_top(img, self.__place_thumb_box(img))

    def __build_picture_mess(self):
        self.picture_mess = Image.new("RGBA", self.RESULT_SIZE)
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

        shadow = Image.new('RGBA', self.picture_mess.size, self.bg)

        shadow.paste('black', None, self.picture_mess)
        shadow = shadow.filter(ImageFilter.BLUR)

        tmp = self.picture_mess
        self.picture_mess = shadow

        self.__paste_img_to_mess_top(tmp, (0,0))
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
