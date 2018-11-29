# Ouinet uploader

This is a simple script to help content providers prepare a content directory
and publish it using [Ouinet](https://github.com/equalitie/ouinet), circulate
the content offline, and enable users to reinsert (parts of) that content when
injectors are not reachable.

The basic syntax is:

    python3 -m ouinet.upload [OPTION...] CONTENT_DIR ACTION...

Where ``CONTENT_DIR`` is the path to the directory holding content.
``ACTION`` is one or more of the following ones:

  - ``index`` recursively scans the content directory and creates in each
    directory a simple index file (``index.html`` by default).

    The generated index file for each directory under the content directory
    (including itself) contains the name of the directory, a link to its
    parent, and links to files and index files in directories under it.

    This action is intended as a helper tool for content publishers to make
    the whole content directory amenable for navigation using a web browser.
    This may not be needed if the content directory already includes such
    index files.

  - ``inject`` requests all files and directories in the content directory via
    the local Ouinet client (assumed by default to be listening on
    ``localhost:8080``) so that it requests their injection.

    The URI descriptors resulting from injection are stored beside content (in
    separate ``.ouinet`` data directories).  Circulating these additional
    files (e.g. by seeding them, see below) may help other Ouinet users look
    up content URIs on the distributed cache.

    This action is intended for content publishers to make the content
    available via Ouinet.  Please note that the content must also be made
    available to the relevant injectors (e.g. via HTTP) to allow this action.

  - ``seed`` uploads all files in the content directory to the local Ouinet
    client (assumed by default to be listening on ``localhost:8080``) so that
    it seeds their data to the distributed cache.  Files in `.ouinet` data
    directories are handled specially.

    This action is intended for users who want their Ouinet client to
    cooperate in seeding the content data to the distributed cache when
    injectors are not reachable.

## Usage examples

These examples assume a Ouinet client listening at ``localhost:8087``:

    $ alias upload="python3 -m ouinet.upload --client-proxy localhost:8087"

### Content provider

First, make sure that your client only requests content using the Injector
mechanism.  You may either disable the Origin, Proxy and Cache request
mechanisms at the client's front end page, or you may add the options
``--disable-origin-access`` and ``--disable-proxy-access`` to the client's
command line.

Enter the directory holding the content directory, and create index files if
they are missing:

    $ cd /path/to/content
    $ ls
    root/
    $ upload root index

At this point you may want to tell a Web server to publish the contents of the
``root`` directory or a replica of it.  You can find a sample configuration
file for the NginX web server [here](./docs/nginx-vhost.conf).  Let us assume
that the content is published at ``https://example.com/``:

    $ upload --uri-prefix https://example.com root inject

After that, clients should be able to both look up content URIs and retrieve
content data from the distributed cache to browse it, even if the web server
is no longer reachable.

### Users

To have your client itself seed the content, descriptors and URL-to-descriptor
mappings, you can upload the files to your Ouinet client:

    $ upload root seed

Please note that the Cache request mechanism should be enabled at the client.

--------

TODO Make this doc more useful.`:)`
