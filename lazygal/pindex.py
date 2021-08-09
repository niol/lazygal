# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2015-2020 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import logging
import os
import json
import collections
import datetime

from . import make
from . import tplvars


def json_serializer(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError('Type %s is not JSON serializable', type(obj))


def datetime_hook(json_dict):
    for (key, value) in json_dict.items():
        if type(value) is str:
            try:
                json_dict[key] = datetime.datetime.fromisoformat(value)
            except ValueError:
                pass # not a datetime in ISO8601 format
    return json_dict


class JSONWebFile(make.FileMakeObject):

    def __init__(self, webgal):
        super().__init__(os.path.join(webgal.path, self.json_filename))
        self.webgal = webgal

        self.data = None
        try:
            with open(self._path, 'r') as json_fp:
                self.data = json.load(json_fp, object_hook=datetime_hook)

            if 'version' not in self.data \
            or self.data['version'] != self.version:
                raise ValueError('persistent json data version mismatch')
        except FileNotFoundError:
            self._init_data()
        except ValueError as ve:
            logging.debug(ve)
            os.unlink(self._path)
            self.stamp_delete()
            self._init_data()

    def _init_data(self):
        self.data = collections.OrderedDict()
        self.data['version'] = self.version

    def dump(self):
        with open(self._path, 'w') as json_fp:
            if self.webgal.config.get('runtime', 'debug'):
                indent = 4
            else:
                indent = None
            json.dump(self.data, json_fp,
                      indent=indent, default=json_serializer)


class PersistentIndex(JSONWebFile):

    json_filename = 'index.json'
    version = 1

    def __init__(self, webgal):
        super().__init__(webgal)

        for f in self.webgal.config.files:
            self.add_file_dependency(f)
        self.add_dependency(self.webgal.source_dir)
        for src_media in self.webgal.source_dir.medias:
            self.add_dependency(src_media)
        for subgal in self.webgal.subgals:
            self.add_dependency(subgal.pindex)

    def _init_data(self):
        super()._init_data()

        self.data['config'] = {
            'webgal': dict(self.webgal.config['webgal']),
        }

        self.data['count'] = {
            'media' : 0,
            'image'  : 0,
            'video'  : 0,
            'subgal': len(self.webgal.source_dir.subdirs),
        }


        self.data['all_count'] = {
            'media' : 0,
            'image' : 0,
            'video' : 0,
        }

        self.data['medias'] = {}

    def __populate_data(self):
        for media in self.webgal.source_dir.medias:
            for t in ('media', media.type):
                self.data['count'][t] = self.data['count'][t] + 1

        to_delete = []
        for media_filename, media_info in self.data['medias'].items():
            if media_filename not in self.webgal.source_dir.medias_names:
                to_delete.append(media_filename)

        for media_filename in to_delete:
            del(self.data['medias'][media_filename])

        if 'subgals' not in self.data:
            self.data['subgals'] = []

        self.data['all_count'] = {
            'media' : self.data['count']['media'],
            'image' : self.data['count']['image'],
            'video' : self.data['count']['video'],
        }

        for subgal in self.webgal.subgals:
            for count_type in self.data['all_count']:
                self.data['all_count'][count_type] =\
                    self.data['all_count'][count_type] +\
                    subgal.pindex.data['all_count'][count_type]

            self.data['subgals'].append(subgal.source_dir.name)

    def load_media(self, src_media):
        if self.webgal.skip_media(src_media):
            return

        self.data['medias'][src_media.filename] = {}

        for key, value in src_media.md.items():
            if not self.webgal.config.get('webgal', 'publish-metadata') \
            and key == 'metadata':
                v = {}
            else:
                v = value
            self.data['medias'][src_media.filename][key] = v

        i = self.data['medias'][src_media.filename]
        if 'location' in i['metadata'] \
        and not self.webgal.config.get('webgal', 'keep-gps'):
            i['metadata']['location'] = None

    def unpublish_media(self, src_media):
        del self.data['medias'][src_media.filename]
        for t in ('media', src_media.type):
            self.data['count'][t] = self.data['count'][t] - 1

    def webgal_info(self):
        dir_info = {}
        if self.webgal.source_dir.metadata:
            dir_info.update(self.webgal.source_dir.metadata.get())

        if 'album_name' not in dir_info:
            dir_info['album_name'] = self.webgal.source_dir.human_name

        return dir_info

    def build(self):
        if not self.webgal.has_media_below():
            return

        logging.info("  DUMPJSON %s", self.json_filename)
        self.__populate_data()

        # Create the webgal directory if it does not exist
        if not os.path.isdir(self.webgal.path) \
        and self.webgal.has_media_below():
            logging.info(_("  MKDIR %%WEBALBUMROOT%%/%s"),
                         self.webgal.source_dir.strip_root())
            logging.debug("(%s)", self.webgal.path)
            os.makedirs(self.webgal.path)

        self.dump()

    def get_media_count(self, media_type='media'):
        return self.data['count'][media_type]


class WebAssets(JSONWebFile):

    json_filename = 'webassets.json'
    version = 1

    def _init_data(self):
        super()._init_data()
        self.data['dirzip'] = None
        self.dirzip = None

    def build(self):
        if self.webgal.has_media():
            logging.info("  JSONWEBASSETS %s", self.json_filename)

            if self.webgal.dirzip:
                dirzip_size = self.webgal.dirzip.size()
                self.data['dirzip'] = {
                    'filename': self.webgal.dirzip.filename,
                    'size'    : dirzip_size,
                    'sizestr' : tplvars.format_filesize(dirzip_size),
                }

            self.dump()


# vim: ts=4 sw=4 expandtab
