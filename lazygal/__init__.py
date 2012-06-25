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


__all__ = [
        'generators',
        ]


# Compute installation prefix
if os.path.isfile(os.path.join(os.path.dirname(__file__), '..', 'setup.py')):
    INSTALL_MODE = 'source'
    INSTALL_PREFIX = ''
else:
    # Lazygal is installed, assume we are in
    # $prefix/lib/python2.X/dist-packages/lazygal
    INSTALL_MODE = 'installed'
    INSTALL_PREFIX = os.path.join(os.path.dirname(__file__),
                                  '..', '..', '..', '..')
    INSTALL_PREFIX = os.path.normpath(INSTALL_PREFIX)


def get_hg_rev():
    try:
        lazygal_dir = os.path.join(os.path.dirname(__file__), '..')
        if not os.path.isdir(os.path.join(lazygal_dir, '.hg')):
            raise IOError

        import mercurial.hg, mercurial.ui, mercurial.node
        repo = mercurial.hg.repository(mercurial.ui.ui(), lazygal_dir)

        last_revs = repo.changelog.parents(repo.dirstate.parents()[0])
        known_tags = repo.tags().items()
        for tag, rev in known_tags:
            if tag != 'tip':
                for last_rev in last_revs:
                    if rev == last_rev:
                        # This is a tagged revision, assume this is a release.
                        return ''
        return mercurial.node.short(last_revs[0])
    except (IOError, OSError, ImportError):
        return ''


__version__ = '0.7.2'

hg_rev = get_hg_rev()
if hg_rev: __version__ += '+hg' + hg_rev

# vim: ts=4 sw=4 expandtab
