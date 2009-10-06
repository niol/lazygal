# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2009 Alexandre Rossi <alexandre.rossi@gmail.com>
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

import os, time
from genshi.core import START
from genshi.template import TemplateLoader, MarkupTemplate, TextTemplate
from genshi.input import XMLParser
import __init__
import locale


class LazygalTemplate(object):

    def __init__(self, tpl_path, genshi_tpl, common_values=None):
        self.path = tpl_path
        self.common_values = common_values or {}
        self.genshi_tpl = genshi_tpl

    def __complement_values(self, values):
        values.update(self.common_values)
        values['gen_date'] = time.strftime("%c").decode(locale.getpreferredencoding())
        values['lazygal_version'] = __init__.__version__
        return values

    def __generate(self, values):
        # We use here a 't' variable to hold all of the template values, which
        # explains why every single template value is called with the '$t.'
        # prefix.
        #
        # The cryptic _=_ is the way to pass the gettext translation function
        # to the templates : the _() callable is assigned to the '_' keyword
        # arg.
        return self.genshi_tpl.generate(t=values, _=_)

    def instanciate(self, values):
        self.__complement_values(values)
        # encoding=None gives us a unicode string instead of an utf-8 encoded
        # string. This is because we are not out of lazygal yet.
        return self.__generate(values).render(self.serialization_method,
                                              encoding=None)

    def dump(self, values, dest):
        self.__complement_values(values)

        page = open(dest, 'w')
        self.__generate(values).render(method=self.serialization_method,
                                       out=page, encoding='utf-8')
        page.close()


class XmlTemplate(LazygalTemplate):

    serialization_method = 'xhtml'
    genshi_tpl_class = MarkupTemplate

    def subtemplates(self, path=None):
        if path is None:
            path = self.path

        subtemplate_paths = []
        f = open(path, 'r')
        try:
            for kind, data, pos in XMLParser(f, filename=path):
                if kind is START:
                    tag, attrib = data
                    if tag.namespace == 'http://www.w3.org/2001/XInclude'\
                    and tag.localname == 'include':
                        subtemplate_paths.append(attrib.get('href'))
        finally:
            f.close()

        for subtemplate_path in subtemplate_paths:
            subtemplate_paths.extend(self.subtemplates(subtemplate_path))

        return subtemplate_paths


class PlainTemplate(LazygalTemplate, TextTemplate):

    serialization_method = 'text'
    genshi_tpl_class = TextTemplate


class TplFactory(TemplateLoader):

    known_exts = {
        '.thtml' : XmlTemplate,
        '.tcss'  : PlainTemplate,
    }

    common_values = None

    def __init__(self, tpl_dir):
        # We use lenient mode here because we want an easy way to check whether
        # a template variable is defined, or the empty string, thus defined()
        # will only work for the 'whether it is defined' part of the test.
        super(TplFactory, self).__init__([tpl_dir],
                                         variable_lookup='lenient')

    def set_common_values(self, values):
        self.common_values = values

    def is_known_template_type(self, file):
        filename, ext = os.path.splitext(os.path.basename(file))
        return ext in self.known_exts.keys()

    def load(self, tpl_file):
        if self.is_known_template_type(tpl_file):
            filename, ext = os.path.splitext(os.path.basename(tpl_file))
            tpl_class = self.known_exts[ext]
            tpl = TemplateLoader.load(self, tpl_file,
                                      cls=tpl_class.genshi_tpl_class)
            return tpl_class(tpl_file, tpl, self.common_values)
        else:
            raise ValueError(_('Unknown template type'))


# vim: ts=4 sw=4 expandtab
