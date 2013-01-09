# Lazygal

[[!toc levels=2]]

## About

`lazygal` is another static web gallery generator written in [Python][1].

It can be summed up by the following features :

  *   Command line based (thus scriptable).
  *   Handles album updates :
    - Lazy : do not build what's already there.
    - Tells you what should not be in your generated directories (and delete it
      if you want to).
  *   Presents all your pictures and videos and associated data:
    - Recursive : generates subgalleries. Follows symlinks for flexibility.
    - Sort pictures in the same directory by EXIF date if available. More
      sorting options available.
    - Auto rotates pictures if they contain sensor info.
    - Reads and present selected image metadata.
    - Copies image metadata in reduced pictures.
  *   Makes browsing sharing pictures easy :
    - Can generate multiple sizes to browse pictures.
    - Breadcrumbs on every page.
    - RSS feed generation for your album updates.
    - Optional generation of ZIP archives of original pictures.
    - Output internationalization.
    - Optional breaking of big galleries (directories) on multiple pages.
    - HTML5 video pages for videos
  *   Make customization easy :
    - Theming.
    - XHTML and CSS compliance for provided themes.
    - Multiple options for album and picture metadata (picture metadata, flat
      files).
    - Add template variables from the command line or from a configuration
      file.
    - Per-directory configuration.
  *   Does not change your original pictures directories (the source argument).

 [1]: http://python.org

## Example demos

  * [Photos from Japan](http://photos.cihar.com/2007-japan/)
  * [Michal Čihař Photography](http://photos.cihar.com/gallery/)

## Requirements

`lazygal` requires :

  *   [Python][1] >= 2.6.
  *   [Python imaging library (PIL)][4] >= 1.1.6.
  *   [pyexiv2][5], a Python binding to [exiv2][6], a library to access image metadata.
  *   [Genshi][7] >= 0.5, a *Python toolkit for generation of output for the web*.
  *   [Python GStreamer][23] and associated plugins for video transcoding.

Building a `lazygal` installation requires :

  *   `msgfmt` for translations. `intltool-update` and `xgettext` are also needed to update translation files. All are included in the GNU `gettext` package.
  *   `xsltproc` to build manpages from docbook sources. It is included in the [libxslt package][8].

 [4]: http://www.pythonware.com/products/pil/
 [5]: http://tilloy.net/dev/pyexiv2/
 [6]: http://exiv2.org/
 [7]: http://genshi.edgewall.org/
 [23]: http://gstreamer.freedesktop.org/modules/gst-python.html
 [8]: http://xmlsoft.org/XSLT/xsltproc2.html

## Usage

Usage is straightforward :

    $ cd /var/www/album
    $ lazygal ~/pics
    $

More information can be found on the manual pages [lazygal(1)][30] and
[lazygal.conf(5)][31].

If you want to force `lazygal` into checking a directory's contents, simply `touch` the source directory to modify its modification time :

    $ touch album_source/gallery_to_check

 [30]: http://sousmonlit.dyndns.org/~niol/playa/oss/projects/lazygal/lazygal.1.html
 [31]: http://sousmonlit.dyndns.org/~niol/playa/oss/projects/lazygal/lazygal.conf.5.html

## Download & Changelog

A [user friendly changelog for lazygal][32] exists.

 [32]: http://sousmonlit.dyndns.org/~niol/repositories/lazygal/raw-file/tip/ChangeLog

The latest version is [Lazygal 0.7.4][10].

 [10]: http://sousmonlit.dyndns.org/~niol/reposnapshots/lazygal-0.7.4.tar.gz

(full log of changes may be browsed in [Lazygal's repository browser][16])

 [16]: http://sousmonlit.dyndns.org/~niol/repositories/lazygal

Lazygal is part of [Debian][17] (and thus [Ubuntu][18] universe), which should
make it one `aptitude install` away if you use one of those.

 [17]: http://debian.org
 [18]: http://ubuntu.com

## Contributing

### Code

Code may be downloaded using [Mercurial][19] :

    $ hg clone http://sousmonlit.dyndns.org/~niol/repositories/lazygal/

It is browsable online in [Lazygal's repository browser][16], and this page
also provides an up to date snapshot of the development source tree.

`lazygal` may be used directly in the source repository, by calling the
`lazygal.py` script. Building simply prepares the translations and the `man`
pages. Updating a source checkout of the `lazygal` repository is done using
`hg pull -u` in the source directory.

Patches are very welcome.

 [19]: http://www.selenic.com/mercurial/

### Translations

To start a new translation, for example `cs_CZ`, you can proceed as follows. The first script requires `intltool-update` and `xgettext` from the GNU `gettext` package.

    $ devscripts/update-po
    $ cp locale/lazygal.pot locale/cz_CZ.po
    $ $EDITOR locale/cz_CZ.po

(do not bother committing or sending in changes to `lazygal.pot`, they contain a lot of noise because of changes in line numbers)

Another side-note : in templates, translatable strings are declared in a character noisy way (I hope to fix this one day). As an example :

    <p><a href="..">Parent</a></p>

becomes

    <p><a href="..">${_('Parent')}</a></p>

## Bugs & feature requests

This project has too few users/contributors to justify the use of a dedicated bug tracking application.

For now, bug reports and feature requests may go in :

*   by e-mail, directly to <alexandre.rossi@gmail.com> (please put `lazygal` somewhere in the subject),
*   through the [Debian Bug Tracking System][22] to which I think I subscribed,
*   through the [Lazygal's Bitbucket bug tracker][24].

 [22]: http://bugs.debian.org/lazygal
 [24]: https://bitbucket.org/niol/lazygal/issues?status=new&status=open
