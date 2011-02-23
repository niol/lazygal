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


import os, time
import sys, urllib
from xml.etree import cElementTree as ET


class RSS20:

    def __init__(self, link, maxitems=10):
        self.items = []

        self.title = None
        self.description = None
        self.link = link
        self.__maxitems = maxitems

        # Workaround the fact that struct_time does not hold timezone info and
        # that %z in strftime() resets to UTC if an argument is given. This
        # seems to be related to http://bugs.python.org/issue762963 .
        # FIXME : There's got to be a simpler way than this.
        offset = {}
        offset['hour'] = abs(time.timezone / 3600)
        if time.timezone <= 0:
            offset['sign'] = '+'
        else:
            offset['sign'] = '-'
        offset['minute'] = (time.timezone % 3600) / 60
        self.timezone_offset = "%(sign)s%(hour)02d%(minute)02d" % offset

    def __get_root_and_channel(self, feed_filename):
        root = ET.Element('rss', {'version'    : '2.0',
                                  'xmlns:atom' : 'http://www.w3.org/2005/Atom'})

        channel = ET.SubElement(root, 'channel')
        ET.SubElement(channel, 'title' ).text = self.title
        ET.SubElement(channel, 'link' ).text = self.__url_quote(self.link)
        ET.SubElement(channel, 'description' ).text = self.description
        ET.SubElement(channel, 'atom:link', {'href': self.link + feed_filename,
                                             'rel' : 'self',
                                             'type': 'application/rss+xml'})

        return root, channel

    def __url_quote(self, url):
        return urllib.quote(url.encode(sys.getfilesystemencoding()), safe=':/')

    def __rfc822_time(self, timestamp=None):
        if not timestamp:
            timestamp = time.time()
        return time.strftime("%a, %d %b %Y %H:%M:%S " + self.timezone_offset,
                             time.localtime(timestamp))

    def __item_older(self, x, y):
        return int(y['timestamp'] - x['timestamp'])

    def push_item(self, title, link, contents, timestamp):
        item = {}
        item['title'] = title
        item['link'] = link
        item['contents'] =  contents
        item['timestamp'] = timestamp

        i = 0
        while i < len(self.items)\
        and self.__item_older(item, self.items[i]) > 0:
            i = i + 1

        if i < self.__maxitems:
            # We have a candidate
            self.items.insert(i, item)
            if len(self.items) > self.__maxitems:
                # We have one too much, so get rid of it
                self.items.pop()

    def dump(self, path):
        (root, channel) = self.__get_root_and_channel(os.path.basename(path))

        pubdate = ET.SubElement(channel, 'pubDate' )

        self.items.sort(lambda x,y: int(x['timestamp'] - y['timestamp']))
        for item in self.items:
            rssitem = ET.SubElement(channel, 'item')
            ET.SubElement(rssitem, 'title').text = item['title']
            ET.SubElement(rssitem, 'link').text = self.__url_quote(item['link'])
            ET.SubElement(rssitem, 'guid').text = self.__url_quote(item['link'])
            date = self.__rfc822_time(item['timestamp'])
            ET.SubElement(rssitem, 'pubDate').text = date
            ET.SubElement(rssitem, 'description').text = item['contents']

        pubdate.text = self.__rfc822_time()

        feedtree = ET.ElementTree(root)
        feedtree.write(path, 'utf-8')


# vim: ts=4 sw=4 expandtab
