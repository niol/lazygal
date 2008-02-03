# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2008 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, shutil


class CircularDependency(Exception):
    pass


class MakeObject:

    def __init__(self):
        self.deps = []
        self.output_items = []
        self.builder = None
        self.__prepared = False

    def add_dependency(self, dependency):
        if self in dependency.deps:
            raise CircularDependency("%s <-> %s" % (self, dependency))
        self.deps.append(dependency)
        self.output_items.extend(dependency.output_items)

    def add_file_dependency(self, file_path):
        self.add_dependency(FileSimpleDependency(file_path))

    def get_mtime(self):
        raise NotImplementedError

    def needs_build(self):
        for dependency in self.deps:
            if dependency.get_mtime() > self.get_mtime():
                return True
        return False

    def make(self, force=False):
        if not self.__prepared:
            self.prepare()
            self.__prepared = True

        for d in self.deps:
            d.make() # dependency building is not forced, regardless of current
                     # target.
        if self.needs_build() or force:
            self.build()

    def prepare(self):
        """Method called before make, this is usefull if you want to build in your target internals stuff needed by dependencies."""
        pass

    def build(self):
        if self.builder:
            self.builder()
        else:
            raise NotImplementedError

    def register_builder(self, builder_func):
        self.builder = builder_func

    def register_output(self, output):
        """This provides a facility to register within the makefile machinery what items are built from the task."""
        self.output_items.append(output)


class FileSimpleDependency(MakeObject):
    """Simple file dependency that needn't build. It just should be there."""

    def __init__(self, path):
        MakeObject.__init__(self)
        self._path = path

    def get_mtime(self):
        return os.path.getmtime(self._path)

    def build(self):
        pass


class FileMakeObject(FileSimpleDependency):

    def __init__(self, path):
        FileSimpleDependency.__init__(self, path)
        # The built file is a forced output of this target
        self.register_output(path)

    def needs_build(self):
        return FileSimpleDependency.needs_build(self)\
               or not os.path.exists(self._path)

    def get_mtime(self):
        try:
            mtime = FileSimpleDependency.get_mtime(self)
        except OSError:
            # Let's tell that the file is very old, older than 1.1.1970 if it
            # does not exist.
            return -1
        return mtime

    def build(self):
        MakeObject.build(self)


class FileCopy(FileMakeObject):
    """Simple file copy make target."""

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst
        FileMakeObject.__init__(self, dst)
        self.add_file_dependency(self.src)

    def build(self):
        shutil.copy(self.src, self.dst)


# vim: ts=4 sw=4 expandtab
