% LAZYGAL(1)
% Alexandre Rossi

# NAME

lazygal - static web gallery generator

# SYNOPSIS

**lazygal** **-h** | **-v** | options albumdir

# DESCRIPTION

This manual page explains the `lazygal` program. This program is a static web
gallery generator written in Python.

`lazygal` works so: you should have an original store of files - possibly
containing subdirectories (their names serving as headings if not using
the album metadata feature). This is the source file hierarchy. It will
never be modified by `lazygal`. Then, when launching:

`$ lazygal -o /var/www/MyAlbum /home/user/SourceDir`

`lazygal` will analyze the contents of the source hierarchy and will (re)create
the target hierarchy, with all the bells and whistles defined by the
templates. Only missing parts or parts that are not up to date will be
generated. There is a limitation to this mechanism though: although
updates in the source directory, in the metadata or in the themes are
detected, changes in command line options and configuration files since
last generation are not and the user should manually delete files that
need to be generated again.

`lazygal` source directory crawling will follow symbolic links on directories
so that you can arrange what you want to publish in any way that suits you
without copying data around.

# OPTIONS

These programs follow the usual GNU command line syntax, with long
options starting with two dashes (\`-\'). A summary of options is
included below. For a complete description, see the `-h` switch.

`-v` `--version`

:   Show program\'s version number and exit.

`-h` `--help`

:   Show summary of options.

`--quiet`

:   Don\'t output anything except for errors.

`--debug`

:   Output everything that lazygal is doing.

`-o DEST_DIR` `--output-directory=DEST_DIR`

:   Directory where web pages, slides and thumbs will be written
    (default is current directory).

`-t THEME` `--theme=THEME`

:   Theme name (looked up in theme directory) or theme full path.

`--default-style=DEFAULT_STYLE`

:   Default style to apply to the theme. This is actually the filename
    (no extension) of the CSS stylesheet of the theme that is not marked
    as `alternate`, thus should get used as default or preferred by the
    web browser.

`--template-vars=TPL_VARS`

:   Common variables to load all templates with, e.g.
    `--template-vars='footer=foo bar,color=baz'`. For longer variable
    contents, it is easier to use a configuration file (see
    LAZYGAL-CONF).

`-f` `--force-gen-pages`

:   Force rebuild of web pages, regardless of the modification times of
    their dependencies. This is handy when changing a configuration
    option affecting these (theme, directory flattening, etc.).

`--clean-destination`

:   Clean destination directory of files that should not be there.

`--preserve=PATTERN`

:   Specify a file pattern (or name) which should be ignored during
    cleanup of the destination. May be specified more than once. Values
    given here will be in addition to those specified in configuration
    files.

`--exclude=PATTERN`

:   Specify a file pattern (or name) which should be ignored during
    processing. May be specified more than once. Values given here will
    be in addition to those specified in configuration files.

`--check-all-dirs`

:   Exhaustively go through all directories regardless of source
    modification time.

`-s IMAGE_SIZE` `--image-size=IMAGE_SIZE`

:   Size of images, define as name=xxy, \..., eg.
    small=800x600,medium=1024x768. The special dimensions 0x0 use
    original size. Refer to the IMAGE RESIZE DESCRIPTION section for
    more information on the available syntax. The number of sizes provided
    will define the number of sizes that will be generated:
    `--image-size="medium=800x600"` will only generate all images for a medium
    size (no small size)
    `--image-size="small=640x480,medium=800x600,large=1024x768"` will
    generate 3 sizes for all images (small, medium, large)

`-T THUMBNAIL_SIZE` `--thumbnail-size=THUMBNAIL_SIZE`

:   Size of thumbnails, eg. 150x113. Refer to the IMAGE RESIZE
    DESCRIPTION section for more information on the available syntax.

`-q QUALITY` `--quality=QUALITY`

:   Quality of generated JPEG images (default is 85).

`-O` `--original`

:   Include original photos in output.

`--orig-base=RELATIVE_PATH`

:   Do not copy original photos in output directory, instead link them
    using RELATIVE\_PATH as base for those links (discarded without
    `-O`).

`--orig-symlink`

:   Do not copy original photos in output directory, instead create
    symlinks to their original locations. This is useful when you plan
    transferring the whole directory which `` generated to some other
    location, perhaps with `rsync`, and you wish to avoid creating an
    extra copy of each photo.

    > **Caution**
    >
    > This option is not available on Windows; if you try to use it on
    > that operating system, `lazygal` will immediately exit with an exit
    > status of 1.

`--puburl=PUB_URL`

:   Publication URL (only useful for feed generation).

`-m` `--generate-metadata`

:   Generate metadata description files where they don\'t exist in the
    source tree instead of generating the web gallery. This disables all
    other options.

`-n THUMBS_PER_PAGE` `--thumbs-per-page=THUMBS_PER_PAGE`

:   Maximum number of thumbs per index page. This enables index
    pagination (0 is unlimited).

`--filter-by-tag=TAG`

:   If set, lazygal will only export the pictures that have one of their
    (IPTC) tags matching TAG. It is also possible to use an equivalent
    of AND and OR boolean tests to filter tags. For more details, read
    below the section TAG FILTERING.

`--pic-sort-by=ORDER`

:   Sort order for images in a subgallery, among \'mtime\',
    \'filename\', \'numeric\', or \'exif\'. (default is \'exif\' which
    is by EXIF date if EXIF data is available, filename otherwise,
    sorting EXIF-less images before). \'numeric\' does a numeric sort on
    the numeric part of the filename. Add \':reverse\' to reverse the
    sort order (e.g. `--pic-sort-by=mtime:reverse`).

`--subgal-sort-by=ORDER`

:   Sort order for subgalleries, among \'exif\' (EXIF date of the latest
    picture in sub-gallery), \'mtime\', \'dirname\', or \'numeric\'
    (default is \'dirname\'). \'numeric\' does a numeric sort on the
    numeric part of the dirname. Add \':reverse\' to reverse the sort
    order (e.g. `--subgal-sort-by=dirname:reverse`).

`--dir-flattening-depth=LEVEL`

:   Level below which the directory tree is flattened. Default is no
    flattening (\'No\').

    This option makes the program include the web gallery index of child
    galleries in their parent\'s gallery index, if their level is
    greater than the supplied LEVEL. The level of the album root is 0.

    Index pages with multiple galleries (which happens when this section
    is used) show the pictures links in gallery sections.

    The following examples show the produced indexes for a sample album
    (2 sub-galleries, 1 sub-sub-gallery, 1 picture in each one of
    those).

    **Example 1. --dir-flattening-depth=No** (default)
    ```
    index.html <- sub-gallery links
    subgal1/index.html <- index with img1
    subgal1/img1.html
    subgal1/subsubgal1/index.html <- index with img2
    subgal1/subsubgal1/img2.html
    subgal2/index.html <- index with img3
    subgal2/img3.html
    ```

    **Example 2. --dir-flattening-depth=0**
    ```
    index.html <- contains index for all pics
    subgal1/img1.html
    subgal1/subsubgal1/img2.html
    subgal2/img3.html
    ```

    **Example 3. --dir-flattening-depth=1**
    ```
    index.html <- contains index for all pics
    subgal1/index.html <- index with img1 and img2
    subgal1/img1.html
    subgal1/subsubgal1/img2.html
    subgal2/index.html <- index with img3
    subgal2/img3.html
    ```

`-z` `--make-dir-zip`

:   Make a zip archive of original pictures for each directory.

`--webalbum-pic-bg=WEBALBUMPIC_BG`

:   Webalbum picture background color. Default is transparent, and
    implies the PNG format. Any other value, e.g. red, white, blue, uses
    JPEG.

`--webalbum-pic-type=WEBALBUMPIC_TYPE`

:   What type of web album thumbnails to generate. By default, lazygal
    generates the well-loved \"messy\" thumbnails with randomly selected
    pictures from the album each rotated by a random amount and pasted
    together. This default can also be forced by specifying \'messy\' as
    WEBALBUMPIC\_TYPE.

    On the other hand, specifying \'tidy\' as the value of this option
    forces lazygal to skip the rotations, resulting in more regularly
    shaped thumbnails which can also be more densely packed. This can be
    an advantage if not all users of your albums have huge screens :-)

`--keep-gps-data`

:   Do not remove GPS data from EXIF tags. By default the location tags
    are removed for privacy reasons. However, there are situations when
    having the location data makes sense and is desired. This is mostly
    meant to be used with holiday photos.

`--no-video`

:   Do not process videos nor include them in indexes.

# THEMES

A theme maps to a directory that contains the following items:

`theme/SHARED_*`

:   Files to put in the web gallery directory `shared`, e.g. CSS,
    Javascript, images or other resources common to all galleries.

`theme/browse.thtml`

:   The XHTML template for the theme browse page (displaying one
    picture).

`theme/dirindex.thtml` or `theme/dynindex.thtml`

:   The XHTML template for the directory index page (pictures and
    sub-galleries links).

Depending on which index file is present, the theme will be:

`dirindex.thtml`: fully static

:   one HTML page per picture, per size and one index per size, or

`dynindex.thtml`: dynamic

:   only one index per directory is to be generated.

`theme/*.thtml` must be valid XML. See
`http://genshi.edgewall.org/wiki/Documentation/xml-templates.html` for
syntax. Dependencies for statically included templates (i.e. with
filenames not computed from variables) are automatically computed: when
an included template is modified, the software will automatically figure
out which pages to re-generate. Missing template files will be searched
for in the `default` theme.

`theme/SHARED_*` files (common resources for the directory `shared`) are
renamed to strip the `SHARED_` prefix and:

- Processed using the Genshi text template engine (see
  `http://genshi.edgewall.org/wiki/Documentation/text-templates.html`
  for syntax.) if their file extension starts with `t`,

- Copied to the web album destination otherwise.

Using the theme manifest `theme/manifest.json` file, it is possible to
include files from other directories to be copied into the web album
shared files.

    {
        "shared": [
            # copy as shared/lib.js
            { "path": "../lib-2.1.js", "dest": "lib.js" },

            # copy as shared/js/lib-2.1.js
            { "path": "../lib-2.1.js", "dest": "js/" }

            # copy first found as shared/lib.js
            # instruct ./setup.py dl_assets to download it from url otherwise
            { "path": [ "/usr/share/javascript/lib-2.1.js", "lib.js"],
              "dest": "lib.js",
              "url": "https://lib.com/lib-latest.js"
            },

            # copy prefixed files in shared/
            { "path": "SHARED_*" },
        ]
    }
            

Please refer to the examples supplied in `/usr/share/lazygal/themes`.

# ALBUM METADATA

If a directory from the source album contains a file named
`album_description`, it is processed as a source of album metadata. The
format is borrowed from another album generating tool - Matew. Each line
is treated as one possible tag, unknown lines are simply ignored.
Example content of this file follows:

    Album name "My album"
    Album description "Description, which can be very long."
    Album image identifier relative/path/to/image.jpg

Otherwise, the user can provide metadata in the following files.

`SOURCE_DIR/album-name`

:   The title to use for this album directory.

`SOURCE_DIR/album-description`

:   The description for this album directory. HTML tags are used
    verbatim from this file.

`SOURCE_DIR/album-picture`

:   The relative path to the image to use at the top of the album
    picture stack.

`SOURCE_DIR/PICTURE_FILENAME.comment`

:   The description to use for this particular image. Please note that
    HTML tags are taken as provided in this file for output in the
    templates.

Lazygal also extracts information from many metadata tags in image
files. Regarding image description, Lazygal searches for comments in
this order:

1. `pic.jpeg.comment` file

2. `Exif.Photo.UserComment`

3. `Exif.Image.ImageDescription`

4. `Iptc.Application2.ObjectName`

5. JPEG comment

# FILES

`~/.lazygal`

:   User configuration directory.

`~/.lazygal/themes`

:   User themes directory.

# CONFIGURATION FILES

Multiple configuration files are processed by DHPACKAGE. The
configuration is initially set up with the defaults. The defaults can be
found in the DHPACKAGE source distribution in `lazygal/defaults.json`.

Then, the configuration files are processed in the following order, each
newly defined value overloading formerly defined values.

Finally, any command-line-provided parameter takes precedence on any
configuration file value.

`~/.lazygal/config`

:   User configuration file. See LAZYGAL-CONF for format.

`SOURCE_DIR/.lazygal`

:   Album root configuration file. See LAZYGAL-CONF for format.

`SOURCE_DIR/gal/.lazygal`

:   Web gallery configuration file. Only the `webgal` and
    `template-vars` sections are red in these files. The configuration
    applies to the gallery representing the directory of the
    configuration file, and all of its sub-directories, unless another
    configuration file in a sub-directory overloads some of the defined
    configuration values. See LAZYGAL-CONF for format.

# SIZE DESCRIPTION

The size string follows the same syntax as ImageMagick\'s.

`scale`%

:   Height and width both scaled by specified percentage.

`xscale`%`yscale`%

:   Height and width individually scaled by specified percentages.

width

:   Width given, height automatically selected to preserve aspect ratio.

x`height`

:   Height given, width automatically selected to preserve aspect ratio.

`width`x`height`

:   Maximum values of height and width given, aspect ratio preserved.

`width`x`height`^

:   Minimum values of width and height given, aspect ratio preserved.

`width`x`height`!

:   Width and height emphatically given, original aspect ratio ignored.

`width`x`height`>

:   Change as per the supplied dimensions but only if an image dimension
    exceeds a specified dimension.

`width`x`height`<

:   Change dimensions only if both image dimensions exceed specified
    dimensions.

`pixels`@

:   Resize image to have specified area in pixels. Aspect ratio is
    preserved.

# TAG FILTERING

Tag filtering supports regular expression matching thanks to the \'re\'
module of Python. All the filter matchings can be indicated to lazygal
by successive uses of the \'filter-by-tag\' option, or by giving a
coma-separated list of keywords.

We illustrate here how more elaorated tag filtering can be done.

We want to export only the images that have the tags \'lazygal\' AND
\'hiking\'.

`$ lazygal --filter-by-tag=lazygal --filter-by-tag=hiking`
        
or:

`$ lazygal --filter-by-tag=lazygal,hiking`
        
We want to export the images that have the tags \'lazygal\' OR
\'hiking\'.

`$ lazygal --filter-by-tag="(lazygal|hiking)"`
        
We want to export the images that have one of the tags \'hiking\_2012\',
\'hiking\_2013\', \'hiking\_France\', etc.

`$ lazygal --filter-by-tag="hiking_.*"`
        
We want to export the images that have the tag \'lazygal\', AND one of
the tags \'hiking\_2012\', \'hiking\_2013\', \'hiking\_France\', etc.

`$ lazygal --filter-by-tag="lazygal,hiking_.*"`
        
# SEE ALSO

**lazygal.conf**(5)

More information is available on the program website:
`https://sml.zincube.net/~niol/repositories.git/lazygal/about/`.

# AUTHOR

This manual page was written for the DEBIAN system (but may be used by
others). Permission is granted to copy, distribute and/or modify this
document under the terms of the GNU General Public License, Version 2
any later version published by the Free Software Foundation.

On Debian systems, the complete text of the GNU General Public License
can be found in /usr/share/common-licenses/GPL.
