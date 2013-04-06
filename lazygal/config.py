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
import logging
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

    def getlist(self, section, option):
        str_vlist = self.get(section, option)

        if str_vlist == '':
            return []

        if type(str_vlist) is not list:
            str_vlist = str_vlist.split(',')

        # handle the case several vals were given at once (separated by comas)
        vlist = []
        for v in str_vlist:
            multiple_v = v.split(',')
            for mv in multiple_v:
                vlist.append(mv)

        return vlist

    def load(self, other_config, init=False, sections=None):
        """
        Take another configuration object and overload values in this config
        object.
        """
        all_sections = False
        if sections is None:
            sections = other_config.sections()
            all_sections = True

        for section in sections:
            if all_sections or other_config.has_section(section):
                if not self.has_section(section):
                    if not init:
                        self.new_section_cb(section)
                    self.add_section(section)
                for option in other_config.options(section):
                    if not init and not self.has_option(section, option):
                        self.new_option_cb(section, option)
                    self.set(section, option, other_config.get(section, option))

    def new_section_cb(self, section):
        pass

    def new_option_cb(self, section, option):
        pass


USER_CONFIG_PATH = os.path.expanduser('~/.lazygal/config')


DEFAULT_CONFIG = BetterConfigParser()
DEFAULT_CONFIG.readfp(open(os.path.join(os.path.dirname(__file__),
                                        'defaults.conf')))


class LazygalConfigDeprecated(BaseException): pass


class LazygalConfig(BetterConfigParser):

    def __init__(self):
        BetterConfigParser.__init__(self)
        self.load(DEFAULT_CONFIG, init=True)

    def check_deprecation(self, config=None):
        if config is None: config = self

        if config.has_section('lazygal'):
            raise LazygalConfigDeprecated("'lazygal' section is deprecated")

    def read(self, filenames):
        conf = BetterConfigParser()
        conf.read(filenames)
        self.load(conf)
        self.check_deprecation()

    def load(self, other_config, init=False, sections=None):
        self.check_deprecation(other_config)
        BetterConfigParser.load(self, other_config, init, sections)

    def new_section_cb(self, section):
        if section != 'template-vars':
            logging.warning(_("  Ignoring unknown section '%s'.") % section)

    def new_option_cb(self, section, option):
        if section != 'template-vars':
            logging.warning(_("  Ignoring unknown option '%s' in section '%s'.")
                            % (option, section, ))


class LazygalWebgalConfig(LazygalConfig):

    def __init__(self, global_config):
        LazygalConfig.__init__(self)
        LazygalConfig.load(self, global_config, init=True)

    def load(self, other_config, init=False):
        LazygalConfig.load(self, other_config, init,
                           sections=('webgal', 'template-vars', ))


# vim: ts=4 sw=4 expandtab
