# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2007-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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
        self.stamp_delete()
        self.__dep_only = False
        self.update_build_status()

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

    def stamp_delete(self):
        self.__last_build_time = -1  # older than oldest epoch
        self.__built_once = False

    def built_once(self):
        return self.__built_once

    def update_build_status(self):
        """
        Do stuff to update the build status (e.g. probe filesystem, deps).
        """
        pass

    def needs_build(self, return_culprit=False):
        if not self.built_once():
            if return_culprit:
                return 'never built'
            else:
                return True

        for dependency in self.deps:
            if dependency.get_mtime() > self.get_mtime()\
            or dependency.needs_build():
                if not dependency.is_dep_only():
                    if return_culprit:
                        mtime_gap = dependency.get_mtime() - self.get_mtime()
                        if mtime_gap > 0:
                            reason = 'dep newer by %s s' % mtime_gap
                        elif dependency.needs_build():
                            reason = dependency.needs_build(True)
                        else:
                            raise RuntimeError  # should never go here
                        return dependency, reason
                    else:
                        return True
        return False

    def make(self, force=False):
        if force or self.needs_build():
            for d in self.deps:
                d.make()  # dependency building not forced
            self.call_build()

    def call_build(self):
        """
        This method is really simple in this implementation, but it can be
        overridden with more complicated things in subclasses. The purpose is
        to setup some state before and/or after build.
        """
        try:
            self.build()
        except KeyboardInterrupt:
            self.clean_output()
            raise
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
        self.output_items.append(output)

    def clean_output(self):
        """
        Clean-up in case of interruption (KeyboardInterrupt).
        """
        pass

    def print_dep_entry(self, level=0):
        indent = ''
        for index in range(0, level):
            indent = indent + '\t'

        print indent, self, self.get_mtime()

    def print_dep_tree(self, depth=1, parent_level=-1):
        level = parent_level + 1
        if level > depth: return

        self.print_dep_entry(level)

        for d in self.deps:
            d.print_dep_tree(depth, level)


class GroupTask(MakeTask):
    """
    A class that builds nothing but groups subtasks.
    """

    def built_once(self):
        return True  # GroupTask is all about the deps.

    def update_build_status(self):
        super(GroupTask, self).update_build_status()
        # Find youngest dep, which should indicate latest build.
        mtime = None
        for dependency in self.deps:
            if dependency.built_once():
                new_mtime = dependency.get_mtime()
                if mtime is None or new_mtime > mtime:
                    mtime = new_mtime
        if mtime is None:
            self.stamp_delete()
        else:
            self.stamp_build(mtime)

    def add_dependency(self, dependency):
        super(GroupTask, self).add_dependency(dependency)
        dep_mtime = dependency.get_mtime()
        if dep_mtime > self.get_mtime():
            self.stamp_build(dep_mtime)

    def build(self):
        pass


class FileMakeObject(MakeTask):

    def __init__(self, path):
        self._path = path
        super(FileMakeObject, self).__init__()
        self.register_output(self._path)

    def update_build_status(self):
        super(FileMakeObject, self).update_build_status()
        # Update build info according to file existence
        if os.path.exists(self._path):
            self.stamp_build(os.path.getmtime(self._path))
        else:
            self.stamp_delete()

    def clean_output(self):
        if os.path.lexists(self._path):
            os.unlink(self._path)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._path.encode('utf-8'))


class FileSimpleDependency(FileMakeObject):
    """
    Simple file dependency that needn't build. It just should be there.
    """

    def __init__(self, path):
        super(FileSimpleDependency, self).__init__(path)
        assert self.built_once()

    def build(self):
        pass

    def clean_output(self):
        pass


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


class FileSymlink(FileMakeObject):
    """
    Simple file symlink make target.
    """

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst
        FileMakeObject.__init__(self, dst)
        self.add_file_dependency(self.src)

    def build(self):
        if os.path.islink(self.dst):
            os.remove(self.dst)
        os.symlink(self.src, self.dst)


# vim: ts=4 sw=4 expandtab
