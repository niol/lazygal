# Lazygal, a lazy static web gallery generator.
# Copyright (C) 2010-2020 Alexandre Rossi <alexandre.rossi@gmail.com>
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


import json
import logging
import math
import os
import shutil
import subprocess
import tempfile


from PIL import Image as PILImage


class VideoError(Exception): pass


FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')
HAVE_VIDEO = FFMPEG and FFPROBE


class VideoProcessor(object):

    def __init__(self, input_file):
        self.progress = None

        self.global_opts = ['-nostdin', '-progress', '-',
                            '-y', # force overwrite existing file
                           ]
        self.input_file_opts = ['-hwaccel', 'auto']
        self.input_file = input_file
        self.output_file_opts = []

        self.cmd = [FFMPEG, '-nostdin', '-progress', '-',
                    '-y', # force overwrite existing file
                    '-i', input_file]
        self.videofilters = []
        self.duration = None

    def set_progress(self, progress):
        self.progress = progress

    def scale(self, newsize):
        self.videofilters.append('scale=%d:%d' % (newsize[0], newsize[1]))

    def parse_time(self, time_str):
        h, m, s = time_str.split(':')
        return 3600 * int(h) + 60 * int(m) + float(s)

    def parse_output(self, line):
        if line.startswith('Duration:'):
            self.duration = self.parse_time(line.split(' ')[1].strip(','))
        elif self.duration and line.startswith('out_time='):
            try:
                position = self.parse_time(line.split('=')[1])
            except ValueError:
                position = 0
            percent = math.floor(100 * position / self.duration)
            if self.progress:
                self.progress.set_task_progress(percent)
            else:
                logging.info('progress: %d%%' % percent)

    def convert(self, outfile):
        runcmd = [FFMPEG]
        runcmd.extend(self.global_opts)
        runcmd.extend(self.input_file_opts)
        runcmd.extend(['-i', self.input_file])
        if self.videofilters:
            runcmd.extend(['-vf', ','.join(self.videofilters)])
        runcmd.extend(self.output_file_opts)
        runcmd.append(outfile)
        logging.debug('RUNNING %s' % ' '.join(runcmd))
        with subprocess.Popen(runcmd, text=True, errors='replace',
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as p:
            for line in p.stdout:
                line = line.strip()
                logging.debug(line)
                self.parse_output(line)


class VideoInfo(object):

    def __init__(self, path):
        self.path = path

    def inspect(self):
        try:
            info = subprocess.check_output([FFPROBE, '-v', 'error',
                                            '-print_format', 'json',
                                            '-show_format', '-show_streams',
                                            self.path],
                                            stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            raise ValueError('cannot load metadata')
        return json.loads(info)


class VideoTranscoder(VideoProcessor):

    def __init__(self, mediapath, videocodec, audiocodec):
        super().__init__(mediapath)
        self.output_file_opts.extend(['-c:v', videocodec,
                                      '-c:a', audiocodec])
        self.videofilters.extend('format=yuv420p')


class WebMTranscoder(VideoTranscoder):

    def __init__(self, mediapath):
        super().__init__(mediapath, 'libvpx-vp9', 'libopus')
        self.output_file_opts.extend(['-crf', '22', '-b:v', '2000k',
                                     ])


class MP4Transcoder(VideoTranscoder):

    def __init__(self, mediapath):
        super().__init__(mediapath, 'libx264', 'aac')
        self.output_file_opts.extend(['-movflags', 'faststart',
                                      '-preset', 'slow',
                                      '-crf', '22'
                                     ])


class VideoFramesExtractor(VideoProcessor):

    def __init__(self, input_file, resize=None, scene=True, frames=10):
        super().__init__(input_file)

        if scene:
            self.videofilters.append('select=gt(scene\,0.4)')
            self.videofilters.append('fps=1/60')
        else: # in case of very short video with one scene
            self.videofilters.append('fps=1')

        if resize is not None:
            self.scale(resize)

        self.output_file_opts.extend(['-frames:v', str(frames),
                                      '-vsync', 'vfr'])


class VideoThumbnailer(object):

    def __init__(self, video):
        self.video = video

    def find_most_representative(self, images):
        images = list(images)
        if not images: return None
        if len(images) == 1: return images[0]

        histograms = []
        for path in images:
            with open(path, 'rb') as im_fp:
                im = PILImage.open(im_fp)
                histograms.append((path, im.histogram()))

        n_samples = len(histograms)
        n_values = len(histograms[0][1])

        # Average each histogram value
        average_hist = []
        for value_index in range(n_values):
            average = 0.0
            for path, histogram in histograms:
                average = average + (float(histogram[value_index]) / n_samples)
            average_hist.append(average)

        # Find histogram closest to average histogram
        min_mse = None
        best_frame_no = None
        for hist_index in range(len(histograms)):
            hist = histograms[hist_index][1]
            mse = 0.0
            for value_index in range(n_values):
                gap = average_hist[value_index] - hist[value_index]
                mse = mse + gap * gap

            if min_mse is None or mse < min_mse:
                min_mse = mse
                best_frame_no = hist_index

        return histograms[hist_index][0]

    def convert(self, outfile, resize=None):
        tmpdir = tempfile.mkdtemp(prefix='lazygal-')

        try:
            tmpimg_name = os.path.join(tmpdir,
                '%s_%%s_%%%%d.jpg' % os.path.basename(self.video))
            VideoFramesExtractor(self.video, resize) \
                .convert(tmpimg_name % 'scene')
            VideoFramesExtractor(self.video, resize, scene=False).convert(tmpimg_name % 'noscene')
            best = self.find_most_representative(map(lambda fn:
                                                     os.path.join(tmpdir, fn),
                                                 os.listdir(tmpdir)))
            if not best:
                raise VideoError('no best frame found')
            shutil.copyfile(best, outfile)
        except VideoError:
            raise
        finally:
            shutil.rmtree(tmpdir)


if __name__ == '__main__':
    import sys
    import os

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    converter_types = sys.argv[1].split(',')
    converters = {}
    for converter_type in converter_types:
        if converter_type == 'webm':
            converter = WebMTranscoder
        elif converter_type == 'mp4':
            converter = MP4Transcoder
        elif converter_type == 'jpeg':
            converter = VideoThumbnailer
        else:
            raise ValueError('unknwon converter type %s' % converter_type)
        converters[converter_type] = converter

    for file_path in sys.argv[2:]:
        videoinfo = VideoInfo(file_path)
        i = videoinfo.inspect()
        for s in i['streams']:
            if s['codec_type'] == 'video':
                print('Video is %dx%d, %ds' % (s['width'], s['height'],
                                               round(float(s['duration']))))
                break # search only first video stream

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
