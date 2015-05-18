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


def get_hg_rev():
    hgdir = os.path.join(os.path.dirname(__file__), '..', '.hg')
    if os.path.isdir(hgdir):
        import subprocess
        last_revision_cache = os.path.join(hgdir, 'cache', 'last_revision')
        if os.path.isfile(last_revision_cache)\
        and (os.path.getmtime(last_revision_cache) >\
             os.path.getmtime(os.path.join(hgdir, 'store', '00changelog.i'))):
            with open(last_revision_cache, 'r') as fp:
                return fp.read()
        else:
            try:
                o = subprocess.check_output(('hg', 'head',
                        '--repository', os.path.join(hgdir, '..'),
                        '-T', '{node|short},{tag}'))
            except subprocess.CalledProcessError:
                os.unlink(last_revision_cache)
                return ''
            else:
                rev, tag = o.decode(sys.getdefaultencoding()).split(',')
                if tag:
                    # This is a tagged revision, thus a release
                    return ''
                else:
                    with open(last_revision_cache, 'w') as fp:
                        fp.write(rev)
                    return rev
    else:
        return ''


__version__ = '0.8.8'

hg_rev = get_hg_rev()
if hg_rev: __version__ += '+hg' + hg_rev

# vim: ts=4 sw=4 expandtab
