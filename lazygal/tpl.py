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

class LazygalTemplate:

    def dump(self, values, dest):
        values.update(self.common_values)
        values['gen_date'] = time.strftime("%A, %d %B %Y %H:%M %Z")
        values['lazygal_version'] = __init__.__version__

        page = open(dest, 'w')
        page.write(self.instanciate(values))
        page.close()


class XmlTemplate(LazygalTemplate, MarkupTemplate):

    def instanciate(self, values):
        return self.generate(t=values).render('xhtml')


class PlainTemplate(LazygalTemplate, TextTemplate):

    def instanciate(self, values):
        return self.generate(t=values).render()


class TplFactory(TemplateLoader):

    known_exts = {
        '.thtml': XmlTemplate,
        '.tcss'  : PlainTemplate
    }

    common_values = None

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
