#!/usr/bin/env python3
"""Prepare a content directory and publish it to Ouinet.
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.request


CLIENT_PROXY='localhost:8080'
INDEX_NAME='index.html'

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

API_UPLOAD_EP = 'http://localhost/upload'


def gen_index(iname, dname, dirnames, filenames):
    """Generate content of index file for a directory.

    The directroy is called `dname` and it has a list of subdirectories
    (`dirnames`) and files (`filenames`).

    Links to parent and children point straight to the index file called
    `iname` in them.
    """
    q = html.escape
    rh = INDEX_HEAD % (q(dname),)
    rup = INDEX_UP_ITEM % (q(iname),)
    rdl = ''.join(INDEX_DIR_ITEM % (q('%s/%s' % (dn, iname)), q(dn)) for dn in dirnames)
    rfl = ''.join(INDEX_FILE_ITEM % (q(fn), q(fn)) for fn in filenames if fn != iname)
    rt = INDEX_TAIL
    return ''.join([rh, rup, rdl, rfl, rt])

def generate_indexes(path, idxname, force=False):
    """Create per-directory index files under the given `path`.

    The index files are called as indicated in `idxname`.  `RuntimeError` is
    raised if an index file is found to exist.  This can be avoided by setting
    `force`, in which case it is overwritten.
    """
    for (dirpath, dirnames, filenames) in os.walk(path):
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
                    print(fpath, '->', ', '.join(msg['data_links']), file=sys.stderr)

_uri_rx = re.compile(r'^[a-z][\+\-\.-0-9a-z]+:')

def inject_uris(path, uri_prefix, proxy):
    """Request files under `path` via a Ouinet client to inject them.

    URIs for the files are built by prepending `uri_prefix` to the path of
    files relative to the given `path`.

    The client's HTTP proxy endpoint is given in `proxy` as a ``HOST:PORT``
    string.
    """
    if not _uri_rx.match(uri_prefix):
        raise ValueError("invalid URI prefix: " + uri_prefix)

    path_prefix_len = len(path) + len(os.sep)  # to help remove path prefix
    uri_prefix = uri_prefix.rstrip('/')  # remove trailing slashes
    proxy_handler = urllib.request.ProxyHandler({'http': 'http://' + proxy})
    url_opener = urllib.request.build_opener(proxy_handler)
    buf = bytearray(4096)

    for (dirpath, dirnames, filenames) in os.walk(path):
        for fn in filenames:
            path_tail = os.path.join(dirpath, fn)[path_prefix_len:]
            uri_tail = path_tail.replace(os.sep, '/')
            uri = uri_prefix + '/' + uri_tail
            with url_opener.open(uri) as res:
                print('^', uri, file=sys.stderr)
                while res.readinto(buf):  # consume body data
                    pass

def main():
    parser = argparse.ArgumentParser(
        description="Prepare a content directory and publish it to Ouinet.")
    parser.add_argument(
        '--client-proxy', metavar="HOST:PORT", default=CLIENT_PROXY,
        help=("the HOST and PORT of the Ouinet client's HTTP proxy"
              " (default: %s)" % CLIENT_PROXY))
    parser.add_argument(
        '--index-name', metavar="NAME", default=INDEX_NAME,
        help=("the NAME of the index file to be created in each subdirectory "
              " (default: %s)" % INDEX_NAME))
    parser.add_argument(
        '--force-index', default=False, action='store_true',
        help=("overwrite existing index files"))
    parser.add_argument(
        '--uri-prefix', metavar="URI", default='',
        help=("URI to prepend to content files' paths when injecting"
              " (no default)"))
    parser.add_argument(
        # Normalize to avoid confusing ``os.path.{base,dir}name()``.
        'directory', metavar="DIR", type=os.path.normpath,
        help="the content directory to prepare and publish")
    parser.add_argument(
        'action', metavar='ACTION', nargs='+', choices='index seed inject'.split(),
        help=("actions to perform:"
              " 'index' creates per-directory index files,"
              " 'seed' uploads files to the Ouinet client for it to seed them,"
              " 'inject' requests files via the Ouinet client to inject them"))
    args = parser.parse_args()

    if 'index' in args.action:
        print("Creating index files...", file=sys.stderr)
        generate_indexes(args.directory, args.index_name, args.force_index)

    if 'seed' in args.action:
        print("Uploading files to the Ouinet client...", file=sys.stderr)
        seed_files(args.directory, args.client_proxy)

    if 'inject' in args.action:
        print("Requesting files via the Ouinet client...", file=sys.stderr)
        inject_uris(args.directory, args.uri_prefix, args.client_proxy)

if __name__ == '__main__':
    main()
