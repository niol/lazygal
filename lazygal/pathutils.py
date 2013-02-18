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
import sys
import posixpath
import logging


def is_root_posix(path):
    return path == '/'


def is_root_win32(path):
    return path[1:] == ':\\'  # strip drive letter in comparison


if sys.platform == 'win32':
    is_root = is_root_win32
else:
    is_root = is_root_posix


def path2unicode(path, errors='strict'):
    if type(path) is unicode:
        return path
    else:
        return path.decode(sys.getfilesystemencoding(), errors)


def is_subdir_of(dir_path, path):
    """
    Returns whether path is a subdirectory of dir_path.
    """
    test_path = path
    while test_path != dir_path and not is_root(test_path):
        test_path, tail = os.path.split(test_path)

    if test_path == dir_path:
        return True
    else:
        return False


def url_path(physical_path, input_pathmodule=os.path):
    """
    Convert a physical path to a path suitable for use in a URL link,
    i.e. using forward slashes. This can only be used for relative paths
    because while converting, the root (either '/' or 'C:\\') is irrelevant.
    """
    if input_pathmodule == posixpath: return physical_path

    head = physical_path
    path_list = []
    while head != '' and not is_root_posix(head) and not is_root_win32(head):
        head, tail = input_pathmodule.split(head)
        path_list.append(tail)

    if path_list == []: return ''

    path_list.reverse()
    return posixpath.join(*path_list)


def walk(top, walked=None, topdown=False):
    """
    This is a wrapper around os.walk() from the standard library:
    - following symbolic links on directories
    - whith barriers in place against walking twice the same directory,
      which may happen when two directory trees have symbolic links to
      each other's contents.
    """
    if walked is None: walked = []

    for root, dirs, files in os.walk(top, topdown=topdown):
        walked.append(os.path.realpath(root))

        # Follow symlinks if they have not been walked yet
        for d in dirs:
            d_path = os.path.join(root, d)
            if os.path.islink(d_path):
                if os.path.realpath(d_path) not in walked:
                    for x in walk(d_path, walked):
                        yield x
                else:
                    logging.error("Not following symlink '%s' because directory has already been processed." % d_path)

        yield root, dirs, files


def walk_and_do(top=None, walked=None, dcb=None, fcb=None, topdown=False):
    """
    This walk calls dcb on each found directory and fcb on each found
    file with the following arguments :
        - path
    """
    for root, dirs, files in walk(top, walked, topdown=topdown):
        if dcb is not None:
            dcb(root, dirs, files)
        if fcb is not None:
            map(lambda f: fcb(os.path.join(root, f)), files)


# vim: ts=4 sw=4 expandtab
