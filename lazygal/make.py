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

import os
import time
import shutil


class CircularDependency(Exception):
    pass


class MakeTask(object):
    """
    A simple task that remembers the last time it was built.
    """

    def __init__(self):
        self.deps = []
        self.output_items = []
        self.__last_build_time = -1 # older than oldest epoch
        self.__built_once = False
        self.__dep_only = False

    def add_dependency(self, dependency):
        if self in dependency.deps:
            raise CircularDependency("%s <-> %s" % (self, dependency))
        self.deps.append(dependency)
        for output_item in dependency.output_items:
            self.register_output(output_item)

    def add_file_dependency(self, file_path):
        self.add_dependency(FileSimpleDependency(file_path))

    def get_mtime(self):
        return self.__last_build_time

    def set_dep_only(self):
        """
        Set this task to being only used as an intermediate work, its output
        is not required in the end. It won't be taken into account when
        computing whether a depending task should be built, even if it is
        older. But make() will be called if the depending task is built.
        """
        self.__dep_only = True

    def is_dep_only(self):
        return self.__dep_only

    def stamp_build(self, build_time=None):
        if not build_time:
            build_time = time.time()
        self.__last_build_time = build_time
        self.__built_once = True

    def needs_build(self):
        if not self.__built_once:
            return True

        for dependency in self.deps:
            if dependency.get_mtime() > self.get_mtime()\
            or dependency.needs_build():
                if not dependency.is_dep_only():
                    return True
        return False

    def make(self, force=False):
        if self.needs_build() or force:
            for d in self.deps:
                d.make() # dependency building not forced
            self.call_build()

    def call_build(self):
        """
        This method is really simple in this implementation, but it can be
        overridden with more complicated things in subclasses. The purpose is
        to setup some state before and/or after build.
        """
        self.build()
        self.stamp_build()

    def build(self):
        """
        This method should be implemented in subclasses to define what the
        task should do.
        """
        raise NotImplementedError

    def register_output(self, output):
        """
        This provides a facility to register within the makefile machinery what
        items are built from the task.
        """
        if not output in self.output_items:
            self.output_items.append(output)


class GroupTask(MakeTask):
    """
    A class that builds nothing but groups subtasks.
    """

    def build(self):
        pass

    def add_dependency(self, dependency):
        super(GroupTask, self).add_dependency(dependency)
        if dependency.get_mtime() > self.get_mtime():
            self.stamp_build(dependency.get_mtime())


class FileSimpleDependency(MakeTask):
    """
    Simple file dependency that needn't build. It just should be there.
    """

    def __init__(self, path):
        MakeTask.__init__(self)
        self._path = path
        try:
            mtime = self.get_mtime()
        except OSError:
            pass
        else:
            self.stamp_build(mtime)

    def get_mtime(self):
        return os.path.getmtime(self._path)

    def build(self):
        pass


class FileMakeObject(FileSimpleDependency):

    def __init__(self, path):
        FileSimpleDependency.__init__(self, path)
        self.register_output(self._path)

    def needs_build(self):
        return FileSimpleDependency.needs_build(self)\
               or not os.path.exists(self._path)

    def get_mtime(self):
        try:
            mtime = super(FileMakeObject, self).get_mtime()
        except OSError:
            # Return last built time
            mtime = super(FileSimpleDependency, self).get_mtime()
        return mtime

    def build(self):
        MakeTask.build(self)


class FileCopy(FileMakeObject):
    """
    Simple file copy make target.
    """

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst
        FileMakeObject.__init__(self, dst)
        self.add_file_dependency(self.src)

    def build(self):
        shutil.copy(self.src, self.dst)


# vim: ts=4 sw=4 expandtab
