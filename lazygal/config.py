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


import os
import sys
import ConfigParser


class BetterConfigParser(ConfigParser.RawConfigParser):

    def getint(self, section, option):
        try:
            if not self.getboolean(section, option):
                return False
            else:
                raise ValueError
        except (ValueError, AttributeError):
            return ConfigParser.RawConfigParser.getint(self, section, option)

    def getstr(self, section, option):
        try:
            if not self.getboolean(section, option):
                return False
            else:
                raise ValueError
        except (ValueError, AttributeError):
            return ConfigParser.RawConfigParser.get(self, section, option)

    def load(self, other_config):
        '''
        Take another configuration object and overload values in this config
        object.
        '''
        for section in other_config.sections():
            if not self.has_section(section):
                self.add_section(section)
            for option in other_config.options(section):
                self.set(section, option, other_config.get(section, option))


USER_CONFIG_PATH = '~/.lazygal/config'


DEFAULT_CONFIG = BetterConfigParser()
DEFAULT_CONFIG.readfp(open(os.path.join(os.path.dirname(__file__),
                                        'defaults.conf')))
DEFAULT_CONFIG.read(os.path.expanduser(USER_CONFIG_PATH))


class LazygalConfigDeprecated(BaseException): pass


class LazygalConfig(BetterConfigParser):

    def __init__(self):
        BetterConfigParser.__init__(self)
        self.load(DEFAULT_CONFIG)

    def check_deprecation(self, config=None):
        if config is None: config = self

        if config.has_section('lazygal'):
            raise LazygalConfigDeprecated("'lazygal' section is deprecated")

    def read(self, filenames):
        BetterConfigParser.read(self, filenames)
        self.check_deprecation()

    def load(self, other_config):
        self.check_deprecation(other_config)
        BetterConfigParser.load(self, other_config)


# vim: ts=4 sw=4 expandtab
