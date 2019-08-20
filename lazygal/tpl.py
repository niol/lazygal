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

from genshi.core import START
from genshi.template import TemplateLoader, MarkupTemplate, NewTextTemplate
from genshi.template import TemplateNotFound
from genshi.template.eval import UndefinedError
from genshi.input import XMLParser

import lazygal
from . import py2compat


class LazygalTemplate(object):

    def __init__(self, loader, genshi_tpl):
        self.loader = loader
        self.path = genshi_tpl.filepath
        self.genshi_tpl = genshi_tpl

    def __complement_values(self, values):
        values['gen_datetime'] = py2compat.datetime.now()

        # using time.strftime() here instead of datetime.strftime() because
        # the latter does not carry the current timezone info, and '%c' in some
        # locales needs to display tzname.
        values['gen_date'] = py2compat.u(time.strftime('%c'))

        values['lazygal_version'] = lazygal.__version__

        return values

    def __generate(self, values):
        # The cryptic values['_'] = _ is the way to pass the gettext
        # translation function to the templates : the _() callable is assigned
        # to the '_' keyword arg.
        values['_'] = _
        return self.genshi_tpl.generate(**values)

    def instanciate(self, values):
        self.__complement_values(values)
        # encoding=None gives us a unicode string instead of an utf-8 encoded
        # string. This is because we are not out of lazygal yet.
        return self.__generate(values).render(self.serialization_method,
                                              encoding=None)

    def dump(self, values, dest):
        self.__complement_values(values)

        page = open(dest, 'wb')
        try:
            self.__generate(values).render(method=self.serialization_method,
                                           out=page, encoding='utf-8')
        except UndefinedError as e:
            print('W: %s' % e)
            raise
        finally:
            page.close()


class XmlTemplate(LazygalTemplate):

    serialization_method = 'xhtml'
    genshi_tpl_class = MarkupTemplate

    def subtemplates(self, tpl=None):
        if tpl is None:
            tpl = self

        subtemplates = []
        f = open(tpl.path, 'r')
        try:
            for kind, data, pos in XMLParser(f, filename=tpl.path):
                if kind is START:
                    tag, attrib = data
                    if tag.namespace == 'http://www.w3.org/2001/XInclude'\
                            and tag.localname == 'include':
                        subtpl_ident = attrib.get('href')
                        try:
                            subtpl = self.loader.load(subtpl_ident)
                        except TemplateNotFound:
                            # This will fail later, here we just need to ignore
                            # template idents that are dynamically computed.
                            pass
                        else:
                            subtemplates.append(subtpl)
        finally:
            f.close()

        for subtemplate in subtemplates:
            for new_subtpl in self.subtemplates(subtemplate):
                if new_subtpl not in subtemplates:
                    subtemplates.append(new_subtpl)

        return subtemplates


class PlainTemplate(LazygalTemplate):

    serialization_method = 'text'
    genshi_tpl_class = NewTextTemplate


class TplFactory(object):

    known_exts = {
        '.thtml': XmlTemplate,
        '.tcss' : PlainTemplate,
        '.tjs'  : PlainTemplate,
    }

    def __init__(self, default_tpl_dir, tpl_dir):
        # We use lenient mode here because we want an easy way to check whether
        # a template variable is defined, or the empty string, thus defined()
        # will only work for the 'whether it is defined' part of the test.
        self.loader = TemplateLoader([tpl_dir, default_tpl_dir],
                                     variable_lookup='lenient')

    def is_known_template_type(self, file):
        filename, ext = os.path.splitext(os.path.basename(file))
        return ext in self.known_exts.keys()

    def load(self, tpl_ident):
        if self.is_known_template_type(tpl_ident):
            filename, ext = os.path.splitext(os.path.basename(tpl_ident))
            tpl_class = self.known_exts[ext]
            tpl = self.loader.load(tpl_ident, cls=tpl_class.genshi_tpl_class)
            return tpl_class(self, tpl)
        else:
            raise ValueError(_('Unknown template type for %s' % tpl_ident))


# vim: ts=4 sw=4 expandtab
