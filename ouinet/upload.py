#!/usr/bin/env python3
"""Prepare a content directory and publish it to Ouinet.
"""

import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import zlib


# Defaults for command line options.
CLIENT_PROXY_DEF='localhost:8080'
INDEX_NAME_DEF='index.html'

# TODO: Use proper templating for this.
INDEX_HEAD="""\
<!DOCTYPE html>
<body>
<h1>Index for <code>%s</code>:</h1>
<ul>
"""
INDEX_UP_ITEM="""\
<li class="up"><a href="../%s">Go up</a></li>
"""
INDEX_DIR_ITEM="""\
<li class="dir"><a href="%s">%s/</a></li>
"""
INDEX_FILE_ITEM="""\
<li class="file"><a href="%s">%s</a></li>
"""
INDEX_TAIL="""\
</ul>
</body>
"""

DATA_DIR_NAME = '.ouinet'

API_UPLOAD_EP = 'http://localhost/api/upload'
API_DESC_EP = 'http://localhost/api/descriptor'


def gen_index(iname, dname, dirnames, filenames):
    """Generate content of index file for a directory.

    The directroy is called `dname` and it has a list of subdirectories
    (`dirnames`) and files (`filenames`).

    Links to parent and children point straight to the index file called
    `iname` in them.

    The Ouinet data directory is excluded from the listing.
    """
    q = html.escape
    rh = INDEX_HEAD % (q(dname),)
    rup = INDEX_UP_ITEM % (q(iname),)
    rdl = ''.join(INDEX_DIR_ITEM % (q('%s/%s' % (dn, iname)), q(dn))
                  for dn in dirnames if dn != DATA_DIR_NAME)
    rfl = ''.join(INDEX_FILE_ITEM % (q(fn), q(fn))
                  for fn in filenames if fn != iname)
    rt = INDEX_TAIL
    return ''.join([rh, rup, rdl, rfl, rt])

def generate_indexes(path, idxname, force=False):
    """Create per-directory index files under the given `path`.

    The index files are called as indicated in `idxname`.  `RuntimeError` is
    raised if an index file is found to exist.  This can be avoided by setting
    `force`, in which case it is overwritten.

    Ouinet data directories are excluded from listings.
    """
    for (dirpath, dirnames, filenames) in os.walk(path):
        if os.path.basename(dirpath) == DATA_DIR_NAME:
            continue
        index_fn = os.path.join(dirpath, idxname)
        if not force and os.path.exists(index_fn):
            raise RuntimeError("refusing to overwrite existing index file: %s"
                               % index_fn)
        index = gen_index(idxname,
                          os.path.basename(dirpath), dirnames, filenames)
        with open(index_fn, 'w') as index_f:
            index_f.write(index)

def seed_files(path, proxy):
    """Upload files under `path` to a Ouinet client for it to seed them.

    The client's HTTP proxy endpoint is given in `proxy` as a ``HOST:PORT``
    string.

    Files in Ouinet data directories are also seeded.
    """
    proxy_handler = urllib.request.ProxyHandler({'http': 'http://' + proxy})
    url_opener = urllib.request.build_opener(proxy_handler)

    for (dirpath, dirnames, filenames) in os.walk(path):
        for fn in filenames:
            fpath = os.path.join(dirpath, fn)
            fstat = os.stat(fpath)
            with open(fpath, 'rb') as f:  # binary matters!
                req = urllib.request.Request(API_UPLOAD_EP, data=f)
                req.add_header('Content-Type', 'application/octet-stream')
                req.add_header('Content-Length', fstat.st_size)
                with url_opener.open(req) as res:
                    msg = json.loads(res.read())
                    print('^', fpath, ':', ' '.join(msg['data_links']), file=sys.stderr)

_uri_rx = re.compile(r'^[a-z][\+\-\.-0-9a-z]+:')

def inject_uris(path, uri_prefix, proxy):
    """Request content under `path` via a Ouinet client to inject it.

    URIs for the different items are built by prepending `uri_prefix` to their
    path relative to the given `path`.

    The client's HTTP proxy endpoint is given in `proxy` as a ``HOST:PORT``
    string.

    The descriptor resulting from injecting a given file is saved in a Ouinet
    data directory in the file's directory.

    Ouinet data directories are excluded from injection.
    """
    if not _uri_rx.match(uri_prefix):
        raise ValueError("invalid URI prefix: " + uri_prefix)

    path_prefix_len = len(path) + len(os.sep)  # to help remove path prefix
    uri_prefix = uri_prefix.rstrip('/')  # remove trailing slashes
    proxy_handler = urllib.request.ProxyHandler({'http': 'http://' + proxy})
    url_opener = urllib.request.build_opener(proxy_handler)
    buf = bytearray(4096)

    for (dirpath, dirnames, filenames) in os.walk(path):
        # Avoid Ouinet data directory.
        if os.path.basename(dirpath) == DATA_DIR_NAME:
            continue
        # Create a Ouinet data directory to hold descriptors.
        descdir = os.path.join(dirpath, DATA_DIR_NAME)
        try:
            os.mkdir(descdir)
        except FileExistsError:
            pass

        filenames.insert(0, '')  # also inject URI of directory itself
        for fn in filenames:
            # Build target URI and request.
            path_tail = os.path.join(dirpath, fn)[path_prefix_len:]
            uri_tail = path_tail.replace(os.sep, '/')
            uri = uri_prefix + '/' + uri_tail
            req = urllib.request.Request(
                # Perform synchronous injection to get the descriptor.
                uri, headers={'X-Ouinet-Sync': 'true'})
            # Send the request to perform the injection.
            with url_opener.open(req) as res:
                print('v', uri, file=sys.stderr)
                desc = res.headers['X-Ouinet-Descriptor']
                while res.readinto(buf):  # consume body data
                    pass
            if not desc:
                raise RuntimeError("URI was not injected: %s" % uri)
            # Save the descriptor resulting from the injection.
            desc = zlib.decompress(base64.b64decode(desc))
            descpath = os.path.join(descdir, fn + '.json')
            with open(descpath, 'wb') as descf:
                print('>', uri, file=sys.stderr)
                descf.write(desc)

def main():
    parser = argparse.ArgumentParser(
        description="Prepare a content directory and publish it to Ouinet.")
    parser.add_argument(
        '--client-proxy', metavar="HOST:PORT", default=CLIENT_PROXY_DEF,
        help=("the HOST and PORT of the Ouinet client's HTTP proxy"
              " (default: %s)" % CLIENT_PROXY_DEF))
    parser.add_argument(
        '--index-name', metavar="NAME", default=INDEX_NAME_DEF,
        help=("the NAME of the index file to be created in each subdirectory "
              " (default: %s)" % INDEX_NAME_DEF))
    parser.add_argument(
        '--force-index', default=False, action='store_true',
        help=("overwrite existing index files"))
    parser.add_argument(
        '--uri-prefix', metavar="URI", default='',
        help=("URI to prepend to content paths when injecting"
              " (no default)"))
    parser.add_argument(
        # Normalize to avoid confusing ``os.path.{base,dir}name()``.
        'directory', metavar="DIR", type=os.path.normpath,
        help="the content directory to prepare and publish")
    parser.add_argument(
        'action', metavar='ACTION', nargs='+', choices='index inject seed'.split(),
        help=("actions to perform:"
              " 'index' creates per-directory index files,"
              " 'inject' requests content via the Ouinet client to inject it and stores descriptors beside content,"
              " 'seed' uploads files to the Ouinet client for it to seed their data"))
    args = parser.parse_args()

    if 'index' in args.action:
        print("Creating index files...", file=sys.stderr)
        generate_indexes(args.directory, args.index_name, args.force_index)

    if 'inject' in args.action:
        print("Requesting content via the Ouinet client...", file=sys.stderr)
        inject_uris(args.directory, args.uri_prefix, args.client_proxy)

    if 'seed' in args.action:
        print("Uploading files to the Ouinet client...", file=sys.stderr)
        seed_files(args.directory, args.client_proxy)

if __name__ == '__main__':
    main()
