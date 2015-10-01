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
try:
    import configparser
except ImportError: # py2compat
    import ConfigParser as configparser
    configparser.RawConfigParser.read_file = configparser.RawConfigParser.readfp
import collections
import functools
import json
import copy


from . import py2compat


USER_CONFIG_PATH = os.path.expanduser('~/.lazygal/config')
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__),
                                   'defaults.json')


class BetterConfigParser(configparser.RawConfigParser):

    def getint(self, section, option):
        try:
            if not self.getboolean(section, option):
                return False
            else:
                raise ValueError
        except (ValueError, AttributeError):
            return configparser.RawConfigParser.getint(self, section, option)

    def getstr(self, section, option):
        try:
            if not self.getboolean(section, option):
                return False
            else:
                raise ValueError
        except (ValueError, AttributeError):
            return configparser.RawConfigParser.get(self, section, option)

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


class LazygalConfigDeprecated(BaseException): pass
class NoSectionError(BaseException): pass
class NoOptionError(BaseException): pass


class LazygalIniConfig(BetterConfigParser):

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
            logging.warning(_("  Ignoring unknown section '%s'."), section)

    def new_option_cb(self, section, option):
        if section != 'template-vars':
            logging.warning(_("  Ignoring unknown option '%s' in section '%s'."),
                            option, section)


def false_or(s, f=None):
    if s.lower() in ('no', 'false'):
        return False
    elif f:
        return f(s)
    else:
        return s


def get_bool(s):
    if s.lower() in ('true', 'yes', 'on', '1') or s == 1:
        return True
    if s.lower() in ('false', 'no', 'off', '0') or s == 0:
        return False
    raise ValueError(_("Unknown boolean value '%s'") % s)


def get_list(s):
    if s:
        return [i.strip() for i in s.split(',')]
    return []


def get_dict(s):
    d = {}
    for i in s.split(','):
        key, value = i.split('=')
        d[key.strip()] = value.strip()
    return d


def get_int(s):
    return int(s)


def get_order(s):
    try:
        order, reverse = s.split(':')
    except ValueError:
        order, reverse = s, False
    return {'order': order, 'reverse': reverse == 'reverse'}


STRING_TO_JSON = collections.OrderedDict({
    'runtime': {
        'quiet'               : get_bool,
        'debug'               : get_bool,
        'check-all-dirs'      : get_bool,
    },
    'global': {
        'force-gen-pages'     : get_bool,
        'clean-destination'   : get_bool,
        'preserve'            : get_list,
        'dir-flattening-depth': functools.partial(false_or, f=get_int),
        'puburl'              : false_or,
        'exclude'             : get_list,
        'preserve_args'       : get_list,
        'exclude_args'        : get_list,
    },
    'webgal': {
        'image-size'          : get_dict,
        'thumbs-per-page'     : get_int,
        'filter-by-tag'       : get_list,
        'sort-medias'         : get_order,
        'sort-subgals'        : get_order,
        'original'            : get_bool,
        'original-baseurl'    : false_or,
        'original-symlink'    : get_bool,
        'dirzip'              : get_bool,
        'jpeg-quality'        : get_int,
        'jpeg-optimize'       : get_bool,
        'jpeg-progressive'    : get_bool,
        'publish-metadata'    : get_bool,
        'keep-gps'            : get_bool,
    },
})


class LazygalConfig(object):
    valid_sections = ('runtime', 'global', 'webgal', 'template-vars', )

    def __init__(self, load_defaults=False):
        self.c = collections.OrderedDict()
        self.valid_options = {s:[] for s in self.valid_sections}

        self.load(self.load_file(DEFAULT_CONFIG_PATH),
                  defaults=True, setvalue=load_defaults)

    def has_section(self, section):
        return section in self.c

    def add_section(self, section):
        if not self.has_section(section):
            if section in self.valid_sections:
                self.c[section] = collections.OrderedDict()
            else:
                raise ValueError("section '%s' is not a valid section name"
                                 % section)

    def options(self, section):
        return self.c[section].keys()

    def get(self, section, option):
        if not self.has_section(section):
            raise NoSectionError(section)
        if option in self.c[section]:
            return self.c[section][option]
        else:
            raise NoOptionError(_('%s in section %s') % (option, section))

    def set(self, section, option, value):
        self.add_section(section)

        if option in self.valid_options[section] or section == 'template-vars':
            if py2compat.isstr(value)\
            and section in STRING_TO_JSON\
            and option in STRING_TO_JSON[section]:
                value = STRING_TO_JSON[section][option](value)
            self.c[section][option] = copy.deepcopy(value)
        else:
            raise ValueError(_("option '%s' is not valid in section '%s'")
                                % (option, section))

    def load(self, newconf, setvalue=True, defaults=False):
        for section, s in newconf.items():
            if defaults and section not in self.valid_sections:
                continue # ignore default section loading

            for k, v in s.items():
                if defaults:
                    self.valid_options[section].append(k)
                if not defaults or (defaults and setvalue):
                    try:
                        self.set(section, k, v)
                    except ValueError as e:
                        logging.warning(_('Ignoring option: %s') % e.args[0])

    def load_file(self, path):
        newconf = None
        with open(path, 'r') as json_fp:
            newconf = json.load(json_fp)
        return newconf

    def load_inifile(self, path):
        iniconf = LazygalIniConfig(defaults=False)
        with open(path) as fp:
            iniconf.read_file(fp)

        for s in iniconf.sections():
            for key, value in iniconf.items(s):
                try:
                    self.set(s, key, value)
                except ValueError as e:
                    logging.warning(_('Ignoring option: %s') % e.args[0])

    def load_any(self, path):
        if not os.path.isfile(path):
            logging.debug(_('Cannot load non-existent config %s.') % path)
            return

        try:
            self.load(self.load_file(path))
        except ValueError:
            try:
                self.load_inifile(path)
            except Exception:
                raise
            else:
                logging.warning(_('INI-style config file format is deprecated.'))

    def __str__(self):
        return json.dumps(self.c)

    def items(self):
        return self.c.items()

    def __getitem__(self, key):
        return self.c[key]


class LazygalWebgalConfig(LazygalConfig):
    valid_sections = ('webgal', 'template-vars', )


# vim: ts=4 sw=4 expandtab
