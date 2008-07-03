# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2007-2008 Alexandre Rossi <alexandre.rossi@gmail.com>
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
from genshi.template import TemplateLoader, MarkupTemplate, TextTemplate
import __init__


class LazygalTemplate(object):

    def __complement_values(self, values):
        values.update(self.common_values)
        values['gen_date'] = time.strftime("%c")
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
        return self.generate(t=values, _=_)


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


class XmlTemplate(LazygalTemplate, MarkupTemplate):

    serialization_method = 'xhtml'


class PlainTemplate(LazygalTemplate, TextTemplate):

    serialization_method = 'text'


class TplFactory(TemplateLoader):

    known_exts = {
        '.thtml': XmlTemplate,
        '.tcss'  : PlainTemplate
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
            tpl = TemplateLoader.load(self, tpl_file, cls=self.known_exts[ext])
            if self.common_values:
                tpl.common_values = self.common_values
            else:
                tpl.common_values = {}
            return tpl
        else:
            raise ValueError(_('Unknown template type'))


# vim: ts=4 sw=4 expandtab
