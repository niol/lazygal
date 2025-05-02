# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2013 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import logging


class ProgressConsoleHandler(logging.StreamHandler):

    last_progress_lengh = 0
    progress_msg = ""

    def clear_last_progress(self):
        self.stream.write("\r" + " " * self.last_progress_lengh + "\r")

    def emit(self, record=None):
        try:
            self.clear_last_progress()
            if record is not None:
                self.stream.write(self.format(record) + "\n")
            self.stream.write(self.progress_msg)
            self.last_progress_lengh = len(self.progress_msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def update_progress(self, s):
        self.progress_msg = s
        self.emit()

    def close(self):
        self.clear_last_progress()
        self.flush()
        super().close()


# vim: ts=4 sw=4 expandtab
