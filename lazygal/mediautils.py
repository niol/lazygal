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
import signal

try:
    import gobject
    import pygst
    pygst.require('0.10')

    # http://29a.ch/tags/pygst
    argv = sys.argv
    sys.argv = []
    import gst
    sys.argv = argv

    import gst.extend.discoverer
except ImportError:
    HAVE_GST = False
else:
    HAVE_GST = True
    gobjects_threads_init = False


interrupted = False
def signal_handler(signum, frame):
    global interrupted
    interrupted = True


def gobject_init():
    gobject.threads_init()
    gobjects_threads_init = True
    signal.signal(signal.SIGINT, signal_handler)


import Image as PILImage


class TranscodeError(Exception): pass


class GstVideoOpener(object):

    def __init__(self, input_file):
        self.input_file = input_file

        self.pipeline = gst.Pipeline()
        self.running = False

        self.pipeline.set_auto_flush_bus(True)

        # Input
        self.filesrc = gst.element_factory_make("filesrc", "source")
        self.pipeline.add(self.filesrc)

        # Decoding
        self.decode = gst.element_factory_make("decodebin", "decode")
        self.decode.connect("new-decoded-pad", self.on_dynamic_pad)
        self.pipeline.add(self.decode)
        self.filesrc.link(self.decode)

        self.aqueue = None
        self.vqueue = None

    def on_dynamic_pad(self, dbin, pad, islast):
        pad_type = pad.get_caps().to_string()[0:5]

        if pad_type == 'audio':
            if self.aqueue is not None: pad.link(self.aqueue.get_pad("sink"))
        elif pad_type == 'video':
            if self.vqueue is not None: pad.link(self.vqueue.get_pad("sink"))
        else:
            print "E: Unknown PAD detected: %s" % pad_type

    def open(self):
        # Init gobjects threads only if a conversion is initiated
        if not gobjects_threads_init:
            gobject_init()

        self.filesrc.set_property("location",
                            self.input_file.encode(sys.getfilesystemencoding()))

    def check_interrupt(self):
        if interrupted:
            msg = gst.message_new_application(self.pipeline,
                                              gst.Structure('interrupted'))
            self.pipeline.get_bus().post(msg)
        if interrupted or not self.running:
            return False # Remove timeout handler
        return True

    def __stop_pipeline(self):
        self.running = False
        self.pipeline.set_state(gst.STATE_NULL)

    def run_pipeline(self):
        self.pipeline.set_state(gst.STATE_PLAYING)
        self.running = True

        gobject.timeout_add(250, self.check_interrupt)

        while self.running:
            message = self.pipeline.get_bus().poll(gst.MESSAGE_ANY, -1)
            if message.type == gst.MESSAGE_EOS:
                self.__stop_pipeline()
            elif message.type == gst.MESSAGE_ERROR:
                self.__stop_pipeline()
                raise TranscodeError(message.parse_error())
            elif message.type == gst.MESSAGE_APPLICATION:
                if message.src == self.pipeline:
                    struct_name = message.structure.get_name()
                    if struct_name == 'aborded_playback':
                        self.__stop_pipeline()
                    elif struct_name == 'interrupted':
                        self.__stop_pipeline()
                        raise KeyboardInterrupt

    def stop_pipeline(self):
        msg = gst.message_new_application(self.pipeline,
                                          gst.Structure('aborded_playback'))
        self.pipeline.get_bus().post(msg)


class GstVideoInfo(object):

    def __init__(self, path):
        self.path = path
        self.loop = gobject.MainLoop()

    def __stream_discovered(self, obj, success):
        self.loop.quit()

    def inspect(self):
        # Init gobjects threads only if an inspection is initiated
        if not gobjects_threads_init:
            gobject_init()

        discoverer = gst.extend.discoverer.Discoverer(self.path.encode('utf-8'))
        discoverer.connect('discovered', self.__stream_discovered)
        discoverer.discover()
        self.loop.run()

        self.videowidth = discoverer.videowidth
        self.videoheight = discoverer.videoheight
        self.videorate = discoverer.videorate
        self.audiorate = discoverer.audiorate
        self.audiodepth = discoverer.audiodepth
        self.audiowidth = discoverer.audiowidth
        self.audiochannels = discoverer.audiochannels

        self.audiolength = discoverer.audiolength
        self.videolength = discoverer.videolength

        self.is_video = discoverer.is_video
        self.is_audio = discoverer.is_audio


class GstVideoReader(GstVideoOpener):

    def __init__(self, mediapath):
        super(GstVideoReader, self).__init__(mediapath)

        # Output
        self.oqueue = gst.element_factory_make("queue")
        self.pipeline.add(self.oqueue)

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


class GstVideoTranscoder(GstVideoReader):

    def __init__(self, mediapath, audiocodec, videocodec, muxer):
        super(GstVideoTranscoder, self).__init__(mediapath)

        # Audio
        self.decode_audio()

        self.audioenc = gst.element_factory_make(audiocodec, 'audioenc')
        self.pipeline.add(self.audioenc)
        self.resample.link(self.audioenc)

        aoqueue = gst.element_factory_make("queue")
        self.pipeline.add(aoqueue)
        self.audioenc.link(aoqueue)

        # Video
        self.decode_video()

        self.videoenc = gst.element_factory_make(videocodec, 'videoenc')
        self.pipeline.add(self.videoenc)
        self.ff.link(self.videoenc)

        voqueue = gst.element_factory_make("queue")
        self.pipeline.add(voqueue)
        self.videoenc.link(voqueue)

        self.muxer = gst.element_factory_make(muxer, 'muxer')
        self.pipeline.add(self.muxer)
        aoqueue.link(self.muxer)
        voqueue.link(self.muxer)

        # Output
        self.muxer.link(self.oqueue)

        # Add output file
        self.sink = gst.element_factory_make("filesink", "sink")
        self.sink.set_property("sync", False)
        self.pipeline.add(self.sink)
        self.oqueue.link(self.sink)

    def convert(self, output_file):
        self.open()

        output_file = output_file.encode(sys.getfilesystemencoding())
        self.sink.set_property("location", output_file)

        self.run_pipeline()


class OggTheoraTranscoder(GstVideoTranscoder):

    def __init__(self, mediapath):
        # Working pipeline
        # gst-launch-0.10 filesrc location=surf_luge.mov ! decodebin name=decode
        # decode. ! queue ! ffmpegcolorspace ! theoraenc ! queue ! oggmux name=muxer
        # decode. ! queue ! audioconvert ! vorbisenc ! queue ! muxer.
        # muxer. ! queue ! filesink location=surf_luge.ogg sync=false

        super(OggTheoraTranscoder, self).__init__(mediapath,
                                                  'vorbisenc', 'theoraenc',
                                                  'oggmux')


class WebMTranscoder(GstVideoTranscoder):

    def __init__(self, mediapath):
        # Working pipeline
        # gst-launch-0.10 filesrc location=oldfile.ext ! decodebin name=demux !
        # queue ! ffmpegcolorspace ! vp8enc ! webmmux name=mux ! filesink
        # location=newfile.webm demux. ! queue ! progressreport ! audioconvert
        # ! audioresample ! vorbisenc ! mux.
        # (Thanks
        # http://stackoverflow.com/questions/4649925/convert-video-to-webm-using-gstreamer/4649990#4649990
        # ! )

        super(WebMTranscoder, self).__init__(mediapath,
                                             'vorbisenc', 'vp8enc', 'webmmux')

        self.videoenc.set_property('quality', 7)


class VideoFrameExtractor(GstVideoReader):

    def __init__(self, path, fps):
        super(VideoFrameExtractor, self).__init__(path)

        self.fps = fps

        self.decode_video()

        # Grab video size when possible
        self.video_size = None
        input_pad = self.ff.get_pad('sink')
        input_pad.connect('notify::caps', self.cb_new_caps)

        videorate = gst.element_factory_make('videorate')
        self.pipeline.add(videorate)
        self.ff.link(videorate)

        # RGB is what is assumed in order to load the frame into a PIL Image.
        self.capsfilter = gst.element_factory_make('capsfilter')
        self.capsfilter.set_property('caps',
                              gst.Caps('video/x-raw-rgb,framerate=%s/1' % fps))
        self.pipeline.add(self.capsfilter)
        videorate.link(self.capsfilter)

        self.app_sink = gst.element_factory_make('appsink')
        self.app_sink.set_property('emit-signals', True)
        self.app_sink.set_property('max-buffers', 10)
        self.app_sink.set_property('sync', False)
        self.app_sink.connect('new-buffer', self.on_new_buffer)
        self.pipeline.add(self.app_sink)
        self.capsfilter.link(self.app_sink)

    def cb_new_caps(self, pad, args):
        caps = pad.get_negotiated_caps()
        if not caps: return
        if 'video' in caps.to_string():
            self.video_size = (caps[0]['width'], caps[0]['height'], )

    def open_frame(self, buf):
        return PILImage.fromstring('RGB', self.video_size, buf)

    def on_new_buffer(self, appsink):
        buf = appsink.emit('pull-buffer')

        self.cb_grabbed_frame_buf(buf)

    def cb_grabbed_frame_buf(self, buf):
        raise NotImplementedError


class VideoFrameNthExtractor(VideoFrameExtractor):

    def __init__(self, path, frame_no, fps):
        super(VideoFrameNthExtractor, self).__init__(path, fps)
        self.frame_index = -1
        self.frame_no = frame_no
        self.frame = None

    def cb_grabbed_frame_buf(self, buf):
        # We're searching for the self.frame_no'th frame.
        self.frame_index = self.frame_index + 1
        if self.frame_index == self.frame_no:
            self.frame = self.open_frame(buf)
            # Abord playback as frame has been found.
            self.stop_pipeline()

    def get_frame(self):
        self.open()
        self.run_pipeline()
        return self.frame


class VideoBestFrameFinder(VideoFrameExtractor):

    def __init__(self, path, fps, intro_seconds):
        super(VideoBestFrameFinder, self).__init__(path, fps)

        self.max_frames = self.fps * intro_seconds # Frames to go through
        self.histograms = []

    def cb_grabbed_frame_buf(self, buf):
        self.frame_number = self.frame_number + 1

        if self.frame_number < self.max_frames:
            # We're searching for the best frame, grab histogram
            self.histograms.append(self.open_frame(buf).histogram())
        else:
            self.stop_pipeline()

    def get_best_frame(self):
        self.open()
        self.frame_number = -1
        self.run_pipeline()

        n_samples = len(self.histograms)
        n_values = len(self.histograms[0])

        # Average each histogram value
        average_hist = []
        for value_index in range(n_values):
            average = 0.0
            for histogram in self.histograms:
                average = average + (float(histogram[value_index])/n_samples)
            average_hist.append(average)

        # Find histogram closest to average histogram
        min_mse = None
        best_frame_no = None
        for hist_index in range(len(self.histograms)):
            hist = self.histograms[hist_index]
            mse = 0.0
            for value_index in range(n_values):
                gap = average_hist[value_index] - hist[value_index]
                mse = mse + gap*gap

            if min_mse is None or mse < min_mse:
                min_mse = mse
                best_frame_no = hist_index

        frame_finder = VideoFrameNthExtractor(self.input_file,
                                              best_frame_no, self.fps)
        return frame_finder.get_frame()


class VideoThumbnailer(object):

    def __init__(self, input_file, thumb_size=None):
        self.input_file = input_file
        self.thumb_size = thumb_size

        # fps images per second should be enough to find a suitable thumbnail
        self.fps = 1
        # search thumb in first intro_seconds seconds
        self.intro_seconds = 300

    def get_thumb(self):
        thumb_finder = VideoBestFrameFinder(self.input_file,
                                            self.fps, self.intro_seconds)
        return thumb_finder.get_best_frame()

    def convert(self, thumbnail_path):
        thumb = self.get_thumb()

        if self.thumb_size is not None:
            thumb.draft(None, self.thumb_size)
            thumb = thumb.resize(self.thumb_size, PILImage.ANTIALIAS)

        thumb.save(thumbnail_path)


if __name__ == '__main__':
    import sys, os

    converter_type = sys.argv[1]
    if converter_type == 'ogg':
        converter = OggTheoraTranscoder
    elif converter_type == 'webm':
        converter = WebMTranscoder
    elif converter_type == 'jpeg':
        converter = VideoThumbnailer
    else:
        raise ValueError

    for file_path in sys.argv[2:]:
        file_path = file_path.decode(sys.getfilesystemencoding())
        fn, ext = os.path.splitext(os.path.basename(file_path))
        target_path = fn + '.' + converter_type
        converter(file_path).convert(target_path)


# vim: ts=4 sw=4 expandtab
