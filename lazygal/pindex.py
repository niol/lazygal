# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2015 Alexandre Rossi <alexandre.rossi@gmail.com>
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


JSON_INDEX_FILENAME = 'index.json'


class PersistentIndex(make.FileMakeObject):

    def __init__(self, webgal):
        super().__init__(os.path.join(webgal.path, JSON_INDEX_FILENAME))
        self.webgal = webgal

        self.add_dependency(self.webgal.source_dir)
        for src_media in self.webgal.source_dir.medias:
            self.add_dependency(src_media)
        for src_subgal in self.webgal.source_dir.subdirs:
            self.add_dependency(src_subgal)

        self.data = None
        try:
            with open(self._path, 'r') as json_fp:
                self.data = json.load(json_fp, object_hook=datetime_hook)
        except FileNotFoundError:
            self.data = collections.OrderedDict()
        except ValueError:
            os.unlink(self._path)
            self.stamp_delete()
            self.data = collections.OrderedDict()

        self.data['config'] = {
            'webgal': dict(self.webgal.config['webgal']),
        }

        self.data['count'] = {
            'media' : 0,
            'image'  : 0,
            'video'  : 0,
            'subgal': len(self.webgal.source_dir.subdirs),
        }

        if 'medias' not in self.data:
            self.data['medias'] = {}

        for media in self.webgal.source_dir.medias:
            if self.__dirty(media.filename):
                self.__load_media(media)
            for t in ('media', media.type):
                self.data['count'][t] = self.data['count'][t] + 1

        to_delete = []
        for media_filename, media_info in self.data['medias'].items():
            try:
                if self.__dirty(media_filename):
                    # should have been loaded in previous loop, do nothing
                    pass
            except ValueError:
                to_delete.append(media_filename)

        for media_filename in to_delete:
            del(self.data['medias'][media_filename])

        if 'subgals' not in self.data:
            self.data['subgals'] = []

        self.data['all_count'] = {
            'media' : self.data['count']['media'],
            'image'  : self.data['count']['image'],
            'video'  : self.data['count']['video'],
        }

        for subgal in self.webgal.subgals:
            for count_type in self.data['all_count']:
                self.data['all_count'][count_type] =\
                    self.data['all_count'][count_type] +\
                    subgal.pindex.data['all_count'][count_type]

            self.data['subgals'].append(subgal.source_dir.name)

        if self.webgal.config.get('webgal', 'dirzip')\
        and self.get_media_count() > 1:
            if not 'dirzip' in self.data:
                self.data['dirzip'] = {'filename': None, }
        elif 'dirzip' in self.data:
            del self.data['dirzip']

    def __find_src_media(self, filename):
        for src_media in self.webgal.source_dir.medias:
            if src_media.filename == filename:
                return src_media
        raise ValueError

    def __dirty(self, hint):
        if self.data is None:
            return True

        if hint == 'srcdir':
            return self.needs_build()
        elif hint not in self.data['medias']:
            return True
        elif hint in self.data['medias']:
            return self.__find_src_media(hint).get_mtime() > self.get_mtime()

        raise ValueError

    def __load_media(self, src_media):
        if self.webgal.skip_media(src_media):
            return

        self.data['medias'][src_media.filename] = {
            'type':   src_media.type,
        }

        for key, value in src_media.md.items():
            if self.webgal.config.get('webgal', 'publish-metadata') \
            or key != 'metadata':
                self.data['medias'][src_media.filename][key] = value

        i = self.data['medias'][src_media.filename]
        if 'metadata' in i and not self.webgal.config.get('webgal', 'keep-gps'):
            i['metadata']['location'] = None

    def webgal_info(self):
        dir_info = {}
        if self.webgal.source_dir.metadata:
            dir_info.update(self.webgal.source_dir.metadata.get())

        if 'album_name' not in dir_info:
            dir_info['album_name'] = self.webgal.source_dir.human_name

        return dir_info

    def __add_built_info(self):
        if 'dirzip' in self.data:
            dirzip_size = self.webgal.dirzip.size()
            self.data['dirzip'] = {
                'filename': self.webgal.dirzip.filename,
                'size'    : dirzip_size,
                'sizestr' : tplvars.format_filesize(dirzip_size),
            }

    def build(self):
        if not self.webgal.has_media_below():
            return

        logging.info("  JSONINDEX %s", JSON_INDEX_FILENAME)
        if self.webgal._deps_populated:
            self.__add_built_info()
        with open(self._path, 'w') as json_fp:
            if self.webgal.config.get('runtime', 'debug'):
                indent = 4
            else:
                indent = None
            json.dump(self.data, json_fp,
                      indent=indent, default=json_serializer)

    def get_media_count(self, media_type='media'):
        return self.data['count'][media_type]

    def dirzip(self):
        if 'dirzip' in self.data:
            return self.data['dirzip']
        else:
            return False


# vim: ts=4 sw=4 expandtab
