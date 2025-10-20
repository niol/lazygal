# coding=utf-8
# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2010-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import codecs
import datetime
import locale
import os
import shutil
import time
import unittest


from . import LazygalTest
from lazygal import mediautils
from lazygal import metadata
from lazygal.metadata import GExiv2

metadata.FILE_METADATA_ENCODING = "utf-8"  # force for these tests
from lazygal.generators import Album
from lazygal.sourcetree import Directory


class TestFileMetadata(LazygalTest):

    def setUp(self):
        super().setUp()

        self.source_dir = self.get_working_path()
        album = Album(self.source_dir)
        self.album_root = Directory(self.source_dir, [], [], album)

    def test_album_name(self):
        album_name = "Album de <b>l'école<b>"
        self.create_file(os.path.join(self.source_dir, "album-name"), album_name)

        md = metadata.DirectoryMetadata(self.album_root.path)
        self.assertEqual(md.get()["album_name"], album_name)

    def test_album_desc(self):
        album_desc = "Allons voir la fête de l'école tous ensemble"
        self.create_file(os.path.join(self.source_dir, "album-description"), album_desc)

        md = metadata.DirectoryMetadata(self.album_root.path)
        self.assertEqual(md.get()["album_description"], album_desc)

    def test_img_desc(self):
        img_path = self.add_img(self.source_dir, "captioned_pic.jpg")

        # Set dumy comment which should be ignored.
        im = metadata.GExiv2.Metadata(img_path)
        im["Exif.Photo.UserComment"] = "comment not to show"
        im.save_file()

        # Output real comment which should be chosen over the dummy comment.
        image_caption = "Les élèves forment une ronde dans la <em>cour</em>."
        self.create_file(
            os.path.join(self.source_dir, img_path + ".comment"), image_caption
        )

        imgmd = metadata.ImageInfoTags(img_path)
        self.assertEqual(imgmd.get_comment(), image_caption)

    def test_album_picture(self):
        img_names = (
            "ontop.jpg",
            "second.jpg",
        )
        for img_name in img_names:
            self.add_img(self.source_dir, img_name)
        self.create_file(
            os.path.join(self.source_dir, "album-picture"), "\n".join(img_names)
        )

        # Reload the directory now that the metadata file is present
        self.album_root = Directory(self.source_dir, [], [], self.album_root.album)

        self.assertEqual(img_names[0], self.album_root.album_picture)

    def test_matew_metadata_album_picture(self):
        img_names = ("ontop.jpg", "second.jpg", "realtitle.jpg")
        for img_name in img_names:
            self.add_img(self.source_dir, img_name)

        self.create_file(
            os.path.join(self.source_dir, "album_description"),
            """
Album image identifier "realtitle.jpg"
""",
        )

        # Reload the directory now that the metadata file is created
        self.album_root = Directory(self.source_dir, [], [], self.album_root.album)

        self.assertEqual(img_names[2], self.album_root.album_picture)

    def test_auto_metadata_album_picture(self):
        img_names = (
            "ontop.jpg",
            "second.jpg",
        )
        for img_name in img_names:
            self.add_img(self.source_dir, img_name)

        self.album_root = Directory(
            self.source_dir, [], img_names, self.album_root.album
        )

        self.assertEqual(img_names[0], self.album_root.album_picture)

    def test_gen_metadata(self):
        img_names = (
            "first\xe3.jpg",
            "second.jpg",
        )
        for img_name in img_names:
            self.add_img(self.source_dir, img_name)

        self.album_root.album.generate_default_metadata()

        with codecs.open(
            os.path.join(self.source_dir, "album_description"), "r", "utf-8"
        ) as f:
            fmd = f.read()

        self.assertEqual(
            fmd,
            """# Directory metadata for lazygal, Matew format
Album name "%s"
Album description ""
Album image identifier "first\xe3.jpg"
"""
            % os.path.basename(self.source_dir).replace("_", " "),
        )

    def test_comment_none(self):
        im_md = metadata.ImageInfoTags(self.get_sample_path("sample.jpg"))
        self.assertEqual(im_md.get_comment(), "")

    def test_image_description(self):
        sample = "sample-image-description.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "test ImageDescription")

    def test_jpeg_comment(self):
        sample = "sample-jpeg-comment.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "test jpeg comment")

    def test_jpeg_comment_unicode(self):
        sample = "sample-jpeg-comment-unicode.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "test jpeg comment éù")

    def test_usercomment_ascii(self):
        sample = "sample-usercomment-ascii.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "deja vu")

    def test_usercomment_unicode_le(self):
        sample = "sample-usercomment-unicode-ii.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "unicode test éà")

    def test_usercomment_unicode_be(self):
        sample = "sample-usercomment-unicode-mm.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "unicode test : éàê")

    def test_usercomment_empty_and_encoding(self):
        """
        Exif.Photo.UserComment: charset="Ascii"

        Exif.Image.ImageDescription: unset
        Iptc.Application2.ObjectName: Jasper the Bear

        In this example, the IPTC tag should be chosen because the
        EXIF photo user comment should be considered empty.
        """
        sample = "sample-usercomment-empty-and-encoding.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))

        self.assertEqual(im_md.get_comment(), "Jasper the Bear")

    def test_exif_date(self):
        sample = "sample.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        d = im_md.get_date()
        self.assertEqual(d, datetime.datetime(2010, 2, 5, 23, 56, 24))

        sample = "sample-model-nikon1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        d = im_md.get_date()
        self.assertEqual(d, datetime.datetime(2011, 5, 21, 22, 19, 30))

    def test_model(self):
        sample = "sample-model-nikon1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_camera_name(), "NIKON D5000")

    def test_lens(self):
        sample = "sample-model-nikon1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_lens_name(), "35mm F1.8 D G")

        sample = "sample-model-nikon2.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_lens_name(), "70-200mm F2.8 D G")

        sample = "sample-model-pentax1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_lens_name(), "smc PENTAX-DA 18-55mm F3.5-5.6 AL WR")

        sample = "sample-bad-lens.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_lens_name(), "")

    def test_flash(self):
        sample = "sample-model-pentax1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_flash(), "Yes, auto")

    def test_focal_length(self):
        sample = "sample-model-pentax1.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_focal_length(), "18 mm (35 mm equivalent: 27 mm)")

    def test_authorship(self):
        sample = "sample-author-badencoding.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(
            im_md.get_authorship(),
            "\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd",
        )

    def test_keywords(self):
        sample = "sample-image-keywords.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(
            im_md.get_keywords(),
            set(
                [
                    "lazygal",
                    "Iptc.Application2.Keywords.lazygal",
                    "Xmp.MicrosoftPhoto.LastKeywordXMP.lazygal",
                    "Xmp.dc.subject.lazygal",
                    "Xmp.digiKam.TagsList.lazygal",
                    #'Xmp.lr.hierarchicalSubject.lazygal'
                ]
            ),
        )

    def test_invalid_iptc_keyword(self):
        sample = "sample-bad-iptc-keywords.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(
            im_md._metadata.get_raw("Iptc.Application2.Keywords"),
            b"Anton\x1c\x1c\x1c\x1cBj\xf6rn",
        )
        self.assertEqual(
            im_md.get_keywords(),
            {"Personen/Kollegen/Björn", "Anton", "Personen/Familie/Anton", "Björn"},
        )

    def test_location(self):
        sample = "sample.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(im_md.get_location(), None)

        sample = "sample-with-gps.jpg"
        im_md = metadata.ImageInfoTags(self.get_sample_path(sample))
        self.assertEqual(
            im_md.get_location(),
            {
                "latitude": 47.0636,
                "latitudeRef": "N",
                "longitude": 8.6893,
                "longitudeRef": "E",
                "altitude": 1527,
            },
        )

        gps_sample_path = os.path.join(self.get_working_path(), "sample.jpg")
        shutil.copy(self.get_sample_path("sample-with-gps.jpg"), gps_sample_path)
        gps_sample_path_md = GExiv2.Metadata(gps_sample_path)
        del gps_sample_path_md["Exif.GPSInfo.GPSAltitude"]
        gps_sample_path_md.save_file()
        gps_sample_path_md = metadata.ImageInfoTags(gps_sample_path)
        self.assertEqual(gps_sample_path_md.get_location(), None)

    @unittest.skipIf(not mediautils.HAVE_VIDEO, "video support not available")
    def test_video(self):
        sample = "vid.mov"
        vid_md = metadata.VideoInfoTags(self.get_sample_path(sample))
        self.assertEqual(
            vid_md.get_date(),
            datetime.datetime(2007, 2, 10, 17, 51, 8, tzinfo=datetime.timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()


# vim: ts=4 sw=4 expandtab
