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

import os, sys


def path2unicode(path):
    if type(path) is unicode:
        return path
    else:
        return path.decode(sys.getfilesystemencoding())


def is_subdir_of(dir_path, path):
    '''
    Returns whether path is a subdirectory of dir_path.
    '''
    test_path = path
    while test_path != dir_path and test_path != '/':
        test_path, tail = os.path.split(test_path)

    if test_path == dir_path:
        return True
    else:
        return False


def relative_path(from_dir, to_path):
    '''
    Returns the relative path of to_path as if currently working in from_dir.
    '''
    if not os.path.isdir(to_path):
        to_path, fn = os.path.split(to_path)
    else:
        fn = None

    rel_path = ''
    common_path = from_dir
    while not is_subdir_of(common_path, to_path):
        common_path, tail = os.path.split(common_path)
        rel_path = os.path.join('..', rel_path)

    if is_subdir_of(common_path, to_path):
        rel_path = os.path.join(rel_path, to_path[len(common_path)+1:])

    if fn:
        rel_path = os.path.join(rel_path, fn)

    return rel_path


# vim: ts=4 sw=4 expandtab
