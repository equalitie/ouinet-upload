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

  - ``seed`` uploads all files in the content directory to the local Ouinet
    client (assumed by default to be listening on ``localhost:8080``) so that
    it seeds their data to the distributed cache.

    Use this if you want your Ouinet client to cooperate in seeding the
    content data to the distributed cache.

  - ``inject`` requests all files and directories in the content directory via
    the local Ouinet client (assumed by default to be listening on
    ``localhost:8080``) so that it requests their injection.

    Please note that content must be made available to the relevant injectors
    (e.g. via HTTP) to allow this action.

Usage example (with the Ouinet client listening at ``localhost:8087``):

    $ alias upload="python3 -m ouinet.upload --client-proxy localhost:8087"
    $ cd /path/to/content
    $ ls
    root/
    $ upload root index  # if there were no index files
    $ upload root seed  # to start seeding content data to the cache

At this point you may want to tell a Web server to publish the `root`
directory.  Let us assume that the content is published at
``https://example.com/``.

    $ upload --uri-prefix https://example.com root inject

After that, clients should be able to both look up content URIs and retrieve
content data from the distributed cache, so the content should be fully
browseable using only the distributed cache.

--------

TODO Make this doc more useful.`:)`