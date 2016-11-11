# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2010-2012 Alexandre Rossi <alexandre.rossi@gmail.com>
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
import logging
import multiprocessing


from . import py2compat


class VideoError(Exception): pass


try:
    import gi
    try:
        gi.require_version('Gst', '1.0')
    except ValueError:
        raise ImportError
    from gi.repository import GObject, GLib, Gst
    if '__getitem__' not in dir(Gst.Caps):
        logging.warning('Missing `python-gst-1.0` overrides')
        raise ImportError
except ImportError:
    HAVE_GST = False
else:
    HAVE_GST = True
    gst_init = False
    GstPbutils = False
    gi.require_version('GstPbutils', '1.0')


class InterruptHandler(object):

    def __enter__(self):
        self.interrupted = False
        self.released = False

        self.original_handler = signal.getsignal(signal.SIGINT)

        def handler(signum, frame):
            self.release()
            self.interrupted = True
        signal.signal(signal.SIGINT, handler)

        return self

    def __exit__(self, type, value, tb):
        self.release()

    def release(self):
        if self.released:
            return False
        signal.signal(signal.SIGINT, self.original_handler)
        self.released = True
        return True


def GST_init():
    global gst_init
    Gst.init(None)

    global GstPbutils
    from gi.repository import GstPbutils

    gst_init = True


from PIL import Image as PILImage


class GstVideoOpener(object):

    def __init__(self, input_file):
        if not gst_init:
            GST_init()

        self.input_file = py2compat.u(input_file,
                                      sys.getfilesystemencoding())

        self.progress = None

        self.pipeline = Gst.Pipeline()
        self.running = False

        self.pipeline.set_auto_flush_bus(True)

        # Input
        self.filesrc = Gst.ElementFactory.make('filesrc', None)
        self.pipeline.add(self.filesrc)

        # Decoding
        self.decode = Gst.ElementFactory.make('decodebin', None)
        self.decode.connect('pad-added', self.on_dynamic_pad)
        self.pipeline.add(self.decode)
        self.filesrc.link(self.decode)

        self.aqueue = None
        self.vqueue = None

    def on_dynamic_pad(self, dbin, pad):
        pad_type = pad.query_caps(None).to_string()[0:5]

        if pad_type == 'audio':
            if self.aqueue is not None:
                pad.link(self.aqueue.get_static_pad('sink'))
        elif pad_type == 'video':
            if self.vqueue is not None:
                pad.link(self.vqueue.get_static_pad('sink'))
        else:
            logging.warning("E: Unknown PAD detected: %s", pad_type)

    def open(self):
        self.filesrc.set_property('location', self.input_file)

    def __post_msg(self, msg_txt):
        msg = Gst.Message.new_application(self.pipeline,
                                          Gst.Structure.new_empty(msg_txt))
        self.pipeline.get_bus().post(msg)

    def set_progress(self, progress):
        self.progress = progress

    def monitor_progress(self):
        cp_success, current_position =\
            self.pipeline.query_position(Gst.Format.TIME)
        if self.media_duration is None:
            md_success, media_duration =\
                self.pipeline.query_duration(Gst.Format.TIME)
            if md_success:
                self.media_duration = media_duration

        if self.progress and self.media_duration is not None\
        and self.media_duration > 0:
            self.progress.set_task_progress(100 * current_position
                                            // self.media_duration)

        # check if stalled
        stalled = False
        if current_position <= self.last_position:
            self.stalled_counter = self.stalled_counter + 1
            if self.stalled_counter >= 20:
                stalled = True
                self.__post_msg('stalled')
        else:
            self.last_position = current_position
            self.stalled_counter = 0

    def __stop_pipeline(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

    def run_pipeline(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True
        self.media_duration = None
        self.last_position = 0
        self.stalled_counter = 0

        with InterruptHandler() as ih:
            bus = self.pipeline.get_bus()
            while self.running:
                if ih.interrupted:
                    self.__stop_pipeline()
                    raise KeyboardInterrupt

                self.monitor_progress()

                message = bus.timed_pop_filtered(1000000000,
                                                 Gst.MessageType.EOS
                                               | Gst.MessageType.ERROR
                                               | Gst.MessageType.APPLICATION)
                if message is None:
                    continue

                if message.type == Gst.MessageType.EOS:
                    self.__stop_pipeline()
                elif message.type == Gst.MessageType.ERROR:
                    self.__stop_pipeline()
                    raise VideoError(message.parse_error())
                elif message.type == Gst.MessageType.APPLICATION:
                    if message.src == self.pipeline:
                        struct_name = message.get_structure().get_name()
                        if struct_name == 'aborded_playback':
                            self.__stop_pipeline()
                        elif struct_name == 'stalled':
                            self.__stop_pipeline()
                            raise VideoError('Pipeline is stalled, this is a problem either in gst or in lazygal\'s use of gst')

        if self.progress:
            self.progress.set_task_done()

    def stop_pipeline(self):
        msg = Gst.Message.new_application(self.pipeline,
            Gst.Structure.new_empty('aborded_playback'))
        self.pipeline.get_bus().post(msg)

        if self.progress is not None:
            self.progress.set_task_done()


class GstVideoInfo(object):

    def __init__(self, path):
        self.path = py2compat.u(path, sys.getfilesystemencoding())

    def inspect(self):
        # Init gobjects threads only if an inspection is initiated
        if not gst_init:
            GST_init()

        discoverer = GstPbutils.Discoverer()
        try:
            info = discoverer.discover_uri(Gst.filename_to_uri(self.path))
        except GLib.GError as e:
            raise VideoError(e)

        vinfo_caps = info.get_video_streams()[0].get_caps()[0]
        self.videowidth = vinfo_caps['width']
        self.videoheight = vinfo_caps['height']
        return info


class GstVideoReader(GstVideoOpener):

    def __init__(self, mediapath):
        super(GstVideoReader, self).__init__(mediapath)

        # Output
        self.oqueue = Gst.ElementFactory.make('queue', 'Output')
        self.pipeline.add(self.oqueue)

    def decode_audio(self):
        # Audio
        self.aqueue = Gst.ElementFactory.make('queue', 'Audio input')
        self.pipeline.add(self.aqueue)

        convert = Gst.ElementFactory.make('audioconvert', 'convert')
        self.pipeline.add(convert)
        self.aqueue.link(convert)

        self.resample = Gst.ElementFactory.make('audioresample', 'resample')
        self.pipeline.add(self.resample)
        convert.link(self.resample)

    def decode_video(self):
        # Video
        self.vqueue = Gst.ElementFactory.make('queue', 'Video input')
        self.pipeline.add(self.vqueue)

        self.colorspace = Gst.ElementFactory.make('videoconvert')
        self.pipeline.add(self.colorspace)
        self.vqueue.link(self.colorspace)


class GstVideoTranscoder(GstVideoReader):

    def __init__(self, mediapath, audiocodec, videocodec, muxer,
                 width=None, height=None):
        super(GstVideoTranscoder, self).__init__(mediapath)

        # Audio
        self.decode_audio()

        self.audioenc = Gst.ElementFactory.make(audiocodec, 'audioenc')
        self.pipeline.add(self.audioenc)
        self.resample.link(self.audioenc)

        aoqueue = Gst.ElementFactory.make("queue", "Audio output")
        self.pipeline.add(aoqueue)
        self.audioenc.link(aoqueue)

        # Video
        self.decode_video()

        self.videoenc = Gst.ElementFactory.make(videocodec, 'videoenc')
        self.pipeline.add(self.videoenc)

        if width is not None and height is not None:
            self.videoscale = Gst.ElementFactory.make('videoscale',
                                                      'videoscale')
            self.videoscale.set_property('method', 'bilinear')
            self.pipeline.add(self.videoscale)
            self.colorspace.link(self.videoscale)
            caps_str = 'video/x-raw,format=YUY2'
            caps_str += ", width=%d, height=%d" % (width, height)
            caps = Gst.Caps.from_string(caps_str)
            self.caps_filter = Gst.ElementFactory.make('capsfilter', 'filter')
            self.caps_filter.set_property("caps", caps)
            self.pipeline.add(self.caps_filter)
            self.videoscale.link(self.caps_filter)
            self.caps_filter.link(self.videoenc)
        else:
            self.colorspace.link(self.videoenc)

        voqueue = Gst.ElementFactory.make('queue', 'Video output')
        self.pipeline.add(voqueue)
        self.videoenc.link(voqueue)

        self.muxer = Gst.ElementFactory.make(muxer, 'muxer')
        self.pipeline.add(self.muxer)
        aoqueue.link(self.muxer)
        voqueue.link(self.muxer)

        # Output
        self.muxer.link(self.oqueue)

        # Add output file
        self.sink = Gst.ElementFactory.make('filesink', 'sink')
        self.sink.set_property("sync", False)
        self.pipeline.add(self.sink)
        self.oqueue.link(self.sink)

    def convert(self, output_file):
        self.open()

        output_file = output_file
        self.sink.set_property("location", output_file)

        self.run_pipeline()


class OggTheoraTranscoder(GstVideoTranscoder):

    def __init__(self, mediapath):
        # Working pipeline
        # gst-launch-1.0 filesrc location=surf_luge.mov ! decodebin name=decode
        # decode. ! queue ! videoconvert ! theoraenc ! queue ! oggmux name=muxer
        # decode. ! queue ! audioconvert ! vorbisenc ! queue ! muxer.
        # muxer. ! queue ! filesink location=surf_luge.ogg sync=false

        super(OggTheoraTranscoder, self).__init__(mediapath,
                                                  'vorbisenc', 'theoraenc',
                                                  'oggmux')


class WebMTranscoder(GstVideoTranscoder):

    def __init__(self, mediapath, width=None, height=None):
        # Working pipeline
        # gst-launch-1.0 filesrc location=oldfile.ext ! decodebin name=demux !
        # queue ! videoconvert ! vp8enc ! webmmux name=mux ! filesink
        # location=newfile.webm demux. ! queue ! progressreport ! audioconvert
        # ! audioresample ! vorbisenc ! mux.
        # (Thanks
        # http://stackoverflow.com/questions/4649925/convert-video-to-webm-using-gstreamer/4649990#4649990
        # ! )

        super(WebMTranscoder, self).__init__(mediapath,
                                             'vorbisenc', 'vp8enc', 'webmmux',
                                             width, height)

        self.videoenc.set_property('threads', multiprocessing.cpu_count())


class MP4Transcoder(GstVideoTranscoder):

    def __init__(self, mediapath):
        # Working pipeline
        # gst-launch-0.10 filesrc location=oldfile.ext ! decodebin name=demux !
        # demux. ! queue ! audioconvert ! faac profile=2 ! queue !
        # avmux_mp4 name=muxer
        # demux. ! queue ! avcolorspace ! x264enc pass=4 quantizer=30
        # subme=4 threads=0 ! queue !
        # muxer. muxer. ! queue ! filesink location=newfile.mp4

        super(MP4Transcoder, self).__init__(mediapath,
                                            'faac', 'x264enc', 'avmux_mp4')

        self.audioenc.set_property('profile', 2)

        self.videoenc.set_property('pass', 4)
        self.videoenc.set_property('quantizer', 30)
        self.videoenc.set_property('subme', 4)
        self.videoenc.set_property('threads', 0)


class VideoFrameExtractor(GstVideoReader):

    def __init__(self, path, fps):
        super(VideoFrameExtractor, self).__init__(path)

        self.fps = fps

        self.decode_video()

        # Grab video size when possible
        self.video_size = None
        input_pad = self.colorspace.get_static_pad('sink')
        input_pad.connect('notify::caps', self.cb_new_caps)

        videorate = Gst.ElementFactory.make('videorate')
        self.pipeline.add(videorate)
        self.colorspace.link(videorate)

        # RGB is what is assumed in order to load the frame into a PIL Image.
        self.capsfilter = Gst.ElementFactory.make('capsfilter')
        self.capsfilter.set_property(
            'caps',
            Gst.Caps.from_string('video/x-raw,format=RGB,framerate=%s/1'
                                 % fps))
        self.pipeline.add(self.capsfilter)
        videorate.link(self.capsfilter)

        self.app_sink = Gst.ElementFactory.make('appsink')
        self.app_sink.set_property('emit-signals', True)
        self.app_sink.set_property('max-buffers', 10)
        self.app_sink.set_property('sync', False)
        self.app_sink.connect('new-sample', self.on_new_buffer)
        self.pipeline.add(self.app_sink)
        self.capsfilter.link(self.app_sink)

    def cb_new_caps(self, pad, args):
        caps = pad.get_current_caps()
        if not caps: return
        if 'video' in caps.to_string():
            (success, width) = caps.get_structure(0).get_int('width')
            (success, height) = caps.get_structure(0).get_int('height')
            self.video_size = (width, height)

    def open_frame(self, buf):
        im = PILImage.frombuffer('RGB', self.video_size, buf,
                                 'raw', 'RGB', 0, 1)
        return im

    def on_new_buffer(self, appsink):
        sample = appsink.emit('pull-sample')
        gstbuf = sample.get_buffer()
        buf = gstbuf.extract_dup(0, gstbuf.get_size())
        self.cb_grabbed_frame_buf(buf)
        return False

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
            self.frame = self.open_frame(buf).copy()
            # Abord playback as frame has been found.
            self.stop_pipeline()

    def get_frame(self):
        self.open()
        self.run_pipeline()
        return self.frame


class VideoBestFrameFinder(VideoFrameExtractor):

    def __init__(self, path, fps, intro_seconds):
        super(VideoBestFrameFinder, self).__init__(path, fps)

        self.max_frames = self.fps * intro_seconds  # Frames to go through
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
                average = average + (float(histogram[value_index]) / n_samples)
            average_hist.append(average)

        # Find histogram closest to average histogram
        min_mse = None
        best_frame_no = None
        for hist_index in range(len(self.histograms)):
            hist = self.histograms[hist_index]
            mse = 0.0
            for value_index in range(n_values):
                gap = average_hist[value_index] - hist[value_index]
                mse = mse + gap * gap

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
    import sys
    import os

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    converter_types = sys.argv[1].split(',')
    converters = {}
    for converter_type in converter_types:
        if converter_type == 'ogg':
            converter = OggTheoraTranscoder
        elif converter_type == 'webm':
            converter = WebMTranscoder
        elif converter_type == 'mp4':
            converter = MP4Transcoder
        elif converter_type == 'jpeg':
            converter = VideoThumbnailer
        else:
            raise ValueError('unknwon converter type %s' % converter_type)
        converters[converter_type] = converter

    for file_path in sys.argv[2:]:
        file_path = py2compat.u(file_path, sys.getfilesystemencoding())

        videoinfo = GstVideoInfo(file_path)
        videoinfo.inspect()
        print('Video is %dx%d' % (videoinfo.videowidth, videoinfo.videoheight))

        fn, ext = os.path.splitext(os.path.basename(file_path))
        for converter_type, converter in converters.items():

            counter_str = ''
            counter = 0
            filename_free = False
            while not filename_free:
                target_path = fn + counter_str + '.' + converter_type
                if os.path.isfile(target_path):
                    counter = counter + 1
                    counter_str = '_%d' % counter
                else:
                    filename_free = True

            converter(file_path).convert(target_path)


# vim: ts=4 sw=4 expandtab
