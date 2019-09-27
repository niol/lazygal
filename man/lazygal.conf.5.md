% LAZYGAL.CONF(5)
% Alexandre Rossi

# NAME

Configuration file for lazygal, a static web gallery generator.

FORMAT DESCRIPTION
==================

lazygal is configured using JSON files. The format looks like this:

    {
        "sectionname": {
            "variable"     : "string value ",
            "boolean"      : false,
            "list"         : ["foo", "bar"],
            "dictionary"  : {
                "key1": "value1",
                "key2": "value2"
            }
        },
        "othersection": {
            "foo"          : "bar"
        }
    }

This format is the preferred way to configure LAZYGAL.

LEGACY FORMAT DESCRIPTION (INI)
===============================

The configuration file can also be an INI like file. The format looks
like this:

    [sectionname]
    variable = string value
    boolean = Yes
    list = foo, bar
    dictionary = key1=value1, key2=value2
    
    [othersection]
    foo = bar

In this INI format, boolean values can be conveniently set in the
following ways:

- For `True`: `1`, `yes`, `true`, and `on`.

- For `False`: `0`, `no`, `false`, and `off`.

Please refer to [the python `ConfigParser`
documentation](http://docs.python.org/library/configparser.html) for
more information on the file format.

runtime section
===============

The `runtime` defines the runtime parameters.

quiet

:   Boolean. Same as `--quiet` in LAZYGAL if `True`. (default is
    `False`).

debug

:   Boolean. Same as `--debug` in LAZYGAL if `True` (default is
    `False`).

check-all-dirs

:   Boolean. Same as `--check-all-dirs` in LAZYGAL if `True`. (default
    is `False`).

global section
==============

The `global` defines the global parameters. Those parameters apply to
all the sub-galleries.

output-directory

:   Same as `--output-directory=DEST_DIR` in LAZYGAL (default is current
    directory).

clean-destination

:   Boolean. Same as `--clean-destination` in LAZYGAL if `True`.

preserve

:   Same as `--preserve=PATTERN` in LAZYGAL. Multiple values may be
    separated by commas.

exclude

:   Same as `--exclude=PATTERN` in LAZYGAL. Multiple values may be
    separated by commas.

dir-flattening-depth

:   Same as `--dir-flattening-depth=LEVEL` in LAZYGAL.

puburl

:   Same as `--puburl=PUB_URL` in LAZYGAL.

theme

:   Same as `--theme=THEME` in LAZYGAL.

webgal section
==============

The `webgal` defines the parameters for a web-gallery.

default-style

:   Same as `--default-style=DEFAULT_STYLE` in LAZYGAL.

webalbumpic-bg

:   Same as `--webalbum-pic-bg=WEBALBUMPIC_BG` in LAZYGAL.

webalbumpic-type

:   Same as `--webalbum-pic-type=WEBALBUMPIC_BG` in LAZYGAL. If you set
    this to \'tidy\' you may also consider setting `webalbumpic-size`
    (see below) to something smaller than the default 200x150.

webalbumpic-size

:   Size of picture mash-up representing galleries, eg. 200x150.

image-size

:   Same as `--image-size=IMAGE_SIZE` in LAZYGAL.

thumbnail-size

:   Same as `--thumbnail-size=THUMBNAIL_SIZE` in LAZYGAL.

video-size

:   Size of videos, eg. 0x0. Refer to the IMAGE RESIZE DESCRIPTION
    section for more information on the available syntax.

    In addition, size can be the name of a previously declared
    image-size.

thumbs-per-page

:   Same as `--thumbs-per-page=THUMBS_PER_PAGE` in LAZYGAL.

sort-medias

:   Same as `--pic-sort-by=ORDER` in LAZYGAL.

sort-subgals

:   Same as `--subgal-sort-by=ORDER` in LAZYGAL.

original

:   Boolean. Same as `--original` in LAZYGAL if `True` (default is
    `False`).

original-baseurl

:   Same as `--orig-base=RELATIVE_PATH` in LAZYGAL.

original-symlink

:   Boolean. Same as `--orig-symlink` in LAZYGAL if `True` (default is
    `False`).

dirzip

:   Same as `--make-dir-zip` in LAZYGAL if `True` (default is `False`).

jpeg-quality

:   Same as `--quality=QUALITY` in LAZYGAL.

jpeg-optimize

:   Boolean. Run an extra optimization pass for each generated thumbnail
    if `True`, the default.

jpeg-progressive

:   Generate progressive JPEG images if `True`, the default.

publish-metadata

:   Publish image metadata if `True`, the default: copy original image
    metadata in reduced picture, and include some information in the
    image page.

filter-by-tag

:   Same as `--filter-by-tag=TAG` in LAZYGAL.

template-vars section
=====================

The `template-vars` defines the custom template variables. The variables
and their value are listed in this section.

For instance, `$footer` is a template variable in the `default`
template. Its value can be defined with this configuration file:

    {
        "template-vars": {
            "footer": "<p>All pics are copyright 2011 me</p>"
        }
    }

SEE ALSO
========

**lazygal**(1)

AUTHOR
======

This manual page was written for the DEBIAN system (but may be used by
others). Permission is granted to copy, distribute and/or modify this
document under the terms of the GNU General Public License, Version 2
any later version published by the Free Software Foundation.

On Debian systems, the complete text of the GNU General Public License
can be found in /usr/share/common-licenses/GPL.
