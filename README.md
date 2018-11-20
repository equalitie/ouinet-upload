# Ouinet uploader

This is a simple script to help content providers prepare a content directory
and publish it using [Ouinet](https://github.com/equalitie/ouinet).

The basic syntax is:

    python3 -m ouinet.upload [OPTION...] CONTENT_DIR ACTION...

Where ``CONTENT_DIR`` is the path to the directory holding content.
``ACTION`` is one or more of the following ones:

  - ``index`` recursively scans the content directory and creates in each
    directory a simple index file (``index.html`` by default) to allow
    browsing the whole file hierarchy with a web browser.  This may not be
    needed if the content directory already contains such files.

    The generated index file for each directory under the content directory
    (including itself) contains the name of the directory, a link to its
    parent, and links to files and index files in directories under it.

  - ``inject`` requests all files and directories in the content directory via
    the local Ouinet client (assumed by default to be listening on
    ``localhost:8080``) so that it requests their injection.

    The URI descriptors resulting from injection are stored beside content (in
    separate ``.ouinet`` data directories).  Circulating these additional
    files (e.g. by seeding them, see below) may help other Ouinet users look
    up content URIs on the distributed cache.

    Please note that content must be made available to the relevant injectors
    (e.g. via HTTP) to allow this action.

  - ``seed`` uploads all files in the content directory to the local Ouinet
    client (assumed by default to be listening on ``localhost:8080``) so that
    it seeds their data to the distributed cache.  Files in `.ouinet` data
    directories are handled specially.

    Use this if you want your Ouinet client to cooperate in seeding the
    content data to the distributed cache.

Usage example (with the Ouinet client listening at ``localhost:8087``):

    $ alias upload="python3 -m ouinet.upload --client-proxy localhost:8087"
    $ cd /path/to/content
    $ ls
    root/
    $ upload root index  # if there were no index files

At this point you may want to tell a Web server to publish the contents of the
``root`` directory (you can find a sample configuration file for the NginX web
server [here](./docs/nginx-vhost.conf)).  You may also want to configure your
client to only attempt access to that server using the Injector request
mechanism (e.g. by disabling the Origin, Proxy and Cache mechanisms at the
client's front end page).  Let us assume that the content is published at
``https://example.com/``:

    $ upload --uri-prefix https://example.com root inject

After that, clients should be able to both look up content URIs and retrieve
content data from the distributed cache, so the content should be fully
browseable using only the distributed cache.

To have your client itself seed the content and the descriptors (whether you
run ``inject`` or not), you can upload the files to your Ouinet client:

    $ upload root seed  # to start seeding content data to the cache

You may need to first enable the Cache mechanism at the client (e.g. at its
front end page).  Please note that at the moment this does not seed the
URL-to-descriptor mappings to distributed data bases.

--------

TODO Make this doc more useful.`:)`
