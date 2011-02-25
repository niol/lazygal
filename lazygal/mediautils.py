# Lazygal, a lazy satic web gallery generator.
# Copyright (C) 2010-2011 Alexandre Rossi <alexandre.rossi@gmail.com>
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
try:
    import gobject
    import pygst
    pygst.require('0.10')
    # http://29a.ch/tags/pygst
    argv = sys.argv
    sys.argv = []
    import gst
    sys.argv = argv
except ImportError:
    HAVE_GST = False
else:
    HAVE_GST = True
    gobjects_threads_init = False


def gobject_init():
    gobject.threads_init()
    gobjects_threads_init = True


class TranscodeError(Exception): pass


class GstVideoOpener(object):

    def __init__(self):
        self.pipeline = gst.Pipeline()

        # Input
        self.filesrc = gst.element_factory_make("filesrc", "source")
        self.pipeline.add(self.filesrc)

        # Decoding
        self.decode = gst.element_factory_make("decodebin", "decode")
        self.decode.connect("new-decoded-pad", self.on_dynamic_pad)
        self.pipeline.add(self.decode)
        self.filesrc.link(self.decode)

    def on_dynamic_pad(self, dbin, pad, islast):
        pad_type = pad.get_caps().to_string()[0:5]
        if pad_type == 'audio':
            pad.link(self.aqueue.get_pad("sink"))
        elif pad_type == 'video':
            pad.link(self.vqueue.get_pad("sink"))
        else:
            print "E: Unknown PAD detected: %s" % pad_type

    def open(self, input_file):
        # Init gobjects threads only if a conversion is initiated
        if not gobjects_threads_init:
            gobject_init()

        input_file = input_file.encode(sys.getfilesystemencoding())
        self.filesrc.set_property("location", input_file)

    def run_pipeline(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

        finished = False
        while not finished:
            message = self.bus.poll(gst.MESSAGE_ANY, -1)
            if message.type == gst.MESSAGE_EOS:
                self.pipeline.set_state(gst.STATE_NULL)
                finished = True
            elif message.type == gst.MESSAGE_ERROR:
                self.pipeline.set_state(gst.STATE_NULL)
                raise TranscodeError(message.parse_error())


class GstVideoConverter(GstVideoOpener):

    def __init__(self):
        super(GstVideoConverter, self).__init__()

        # Output
        self.oqueue = gst.element_factory_make("queue")
        self.pipeline.add(self.oqueue)

        self.sink = gst.element_factory_make("filesink", "sink")
        self.sink.set_property("sync", False)
        self.pipeline.add(self.sink)
        self.oqueue.link(self.sink)

        self.pipeline.set_auto_flush_bus(True)
        self.bus = self.pipeline.get_bus()

    def decode_audio(self):
        # Audio
        self.aqueue = gst.element_factory_make("queue")
        self.pipeline.add(self.aqueue)

        convert = gst.element_factory_make("audioconvert", "convert")
        self.pipeline.add(convert)
        self.aqueue.link(convert)

        self.resample = gst.element_factory_make("audioresample", "resample")
        self.pipeline.add(self.resample)
        convert.link(self.resample)

    def decode_video(self):
        # Video
        self.vqueue = gst.element_factory_make("queue")
        self.pipeline.add(self.vqueue)

        self.ff = gst.element_factory_make("ffmpegcolorspace")
        self.pipeline.add(self.ff)
        self.vqueue.link(self.ff)

    def convert(self, input_file, output_file):
        self.open(input_file)

        output_file = output_file.encode(sys.getfilesystemencoding())
        self.sink.set_property("location", output_file)

        self.run_pipeline()


class OggTheoraTranscoder(GstVideoConverter):

    def __init__(self):
        super(OggTheoraTranscoder, self).__init__()

        # Working pipeline
        # gst-launch-0.10 filesrc location=surf_luge.mov ! decodebin name=decode
        # decode. ! queue ! ffmpegcolorspace ! theoraenc ! queue ! oggmux name=muxer
        # decode. ! queue ! audioconvert ! vorbisenc ! queue ! muxer.
        # muxer. ! queue ! filesink location=surf_luge.ogg sync=false

        # Audio
        self.decode_audio()

        self.vorbisenc = gst.element_factory_make("vorbisenc", "vorbisenc")
        self.pipeline.add(self.vorbisenc)
        self.resample.link(self.vorbisenc)

        aoqueue = gst.element_factory_make("queue")
        self.pipeline.add(aoqueue)
        self.vorbisenc.link(aoqueue)

        # Video
        self.decode_video()

        self.theoraenc = gst.element_factory_make("theoraenc")
        self.pipeline.add(self.theoraenc)
        self.ff.link(self.theoraenc)

        voqueue = gst.element_factory_make("queue")
        self.pipeline.add(voqueue)
        self.theoraenc.link(voqueue)

        # Muxer
        self.oggmux = gst.element_factory_make("oggmux", "oggmux")
        self.pipeline.add(self.oggmux)
        aoqueue.link(self.oggmux)
        voqueue.link(self.oggmux)

        # Output
        self.oggmux.link(self.oqueue)


if __name__ == '__main__':
    import sys, os
    converter = OggTheoraTranscoder()
    for file_path in sys.argv[1:]:
        fn, ext = os.path.splitext(file_path)
        ogg_path = fn + '.ogg'
        converter.convert(file_path, ogg_path)


# vim: ts=4 sw=4 expandtab
