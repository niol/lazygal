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


import sys
import os


__all__ = ['generators', ]


# Compute installation prefix
if os.path.isfile(os.path.join(os.path.dirname(__file__), '..', 'setup.py')):
    INSTALL_MODE = 'source'
    INSTALL_PREFIX = ''
else:
    # Lazygal is installed, assume we are in
    # $prefix/lib/pythonX/dist-packages/lazygal
    INSTALL_MODE = 'installed'
    INSTALL_PREFIX = os.path.join(os.path.dirname(__file__),
                                  '..', '..', '..', '..')
    INSTALL_PREFIX = os.path.normpath(INSTALL_PREFIX)


def query_git_for_tag(gitdir):
    import subprocess
    o = subprocess.check_output(('git','-C', os.path.dirname(__file__),
                                 'describe', '--tags', )) \
        .decode(sys.stdout.encoding).strip()
    tokens = o.split('-')
    h = tokens[-1]
    if len(h) != 8:
        # this is not a hash
        h = None
    return '+'.join(tokens), h


def git_repo_mtime(gitdir):
    return max([
        os.path.getmtime(os.path.join(gitdir, 'index')),
        os.path.getmtime(os.path.join(gitdir, 'HEAD')),
        os.path.getmtime(os.path.join(gitdir, 'refs', 'tags')),
    ])


def get_git_rev():
    gitdir = os.path.join(os.path.dirname(__file__), '..', '.git')
    if os.path.isdir(gitdir):
        last_revision_cache = os.path.join(gitdir, 'last_revision')

        if os.path.isfile(last_revision_cache)\
        and os.path.getmtime(last_revision_cache) > git_repo_mtime(gitdir):
            with open(last_revision_cache, 'r') as fp:
                return fp.read()
        else:
            import subprocess
            try:
                lastrev = query_git_for_tag(gitdir)
            except subprocess.CalledProcessError:
                if os.path.isfile(last_revision_cache):
                    os.unlink(last_revision_cache)
                return ''
            else:
                v, h = lastrev
                if h:
                    with open(last_revision_cache, 'w') as fp:
                        fp.write(v)
                    return v
                else:
                    return ''
    else:
        return ''


__version__ = '0.10.1'

rev = get_git_rev()
if rev: __version__ = rev

# vim: ts=4 sw=4 expandtab
