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
import urllib.error
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
DESC_FILE_EXT = '.desc'
LINK_FILE_EXT = '.link'

API_UPLOAD_EP = 'http://localhost/api/upload'
API_INSERT_EP_PFX = 'http://localhost/api/insert/'
API_DESC_EP = 'http://localhost/api/descriptor'


def _logline(*args):
    print(*args, file=sys.stderr)

def _logpart(*args):
    print(*args, file=sys.stderr, end='', flush=True)

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

    Return whether non-fatal errors happened.
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
    return True

_insdata_ext_rx = re.compile(r'\.ins-(?P<db>[0-9a-z]+)$');
_ctype_from_db = {
    'bep44': 'application/x-bittorrent'
}

def seed_files(path, proxy):
    """Upload files under `path` to a Ouinet client for it to seed them.

    The client's HTTP proxy endpoint is given in `proxy` as a ``HOST:PORT``
    string.

    Files in Ouinet data directories are handled specially depending on their
    purpose (e.g. descriptors are uploaded, insertion data is used to reinsert
    mappings).

    Return whether non-fatal errors happened (e.g. there was a problem when
    seeding a file).
    """
    proxy_handler = urllib.request.ProxyHandler({'http': 'http://' + proxy})
    url_opener = urllib.request.build_opener(proxy_handler)

    ok = True
    for (dirpath, dirnames, filenames) in os.walk(path):
        for fn in filenames:
            api_ep, ctype, insdb = API_UPLOAD_EP, 'application/octet-stream', None
            # Identify Ouinet data files.
            if os.path.basename(dirpath) == DATA_DIR_NAME:
                ins = _insdata_ext_rx.search(fn)
                if ins:  # insertion data
                    insdb = ins.group('db')
                    api_ep = API_INSERT_EP_PFX + insdb  # insert, not upload
                    ctype = _ctype_from_db.get(insdb)  # db-specific type
                    if not ctype:  # unknown db
                        continue
                elif not fn.endswith(DESC_FILE_EXT):  # descriptor
                    continue  # unknown Ouinet data file
            fpath = os.path.join(dirpath, fn)
            fstat = os.stat(fpath)
            with open(fpath, 'rb') as f:  # binary matters!
                req = urllib.request.Request(api_ep, data=f )
                req.add_header('Content-Type', ctype)
                req.add_header('Content-Length', fstat.st_size)
                _logpart('<' if insdb else '^', fpath)
                try:
                    with url_opener.open(req) as res:
                        msg = json.loads(res.read())
                        logtail = ( insdb.upper() + '=' + msg['key'] if insdb
                                    else ' '.join(msg['data_links']) )
                except urllib.error.HTTPError as he:
                    ok = False
                    try:  # attempt to extract API error string
                        logtail = 'ERROR="%s"' % json.loads(he.read())['error']
                    except Exception:
                        logtail = 'ERROR="%s"' % he
                except Exception as e:
                    ok = False
                    logtail = 'ERROR="%s"' % e
                _logline('', logtail)
    return ok

_uri_rx = re.compile(r'^[a-z][\+\-\.-0-9a-z]+:')
_ins_hdr_rx = re.compile(r'^X-Ouinet-Insert-(?P<db>.*)', re.IGNORECASE)

def inject_uris(path, uri_prefix, proxy):
    """Request content under `path` via a Ouinet client to inject it.

    URIs for the different items are built by prepending `uri_prefix` to their
    path relative to the given `path`.

    The client's HTTP proxy endpoint is given in `proxy` as a ``HOST:PORT``
    string.

    The descriptor (and its storage link) resulting from injecting a given
    file is saved in a Ouinet data directory in the file's directory, along
    with any data base-dependent insertion data.

    Ouinet data directories are excluded from injection.

    Return whether non-fatal errors happened (e.g. a URI failed to be
    injected, or a descriptor or insertion data failed to be retrieved).
    """
    if not _uri_rx.match(uri_prefix):
        raise ValueError("invalid URI prefix: " + uri_prefix)

    path_prefix_len = len(path) + len(os.sep)  # to help remove path prefix
    uri_prefix = uri_prefix.rstrip('/')  # remove trailing slashes
    proxy_handler = urllib.request.ProxyHandler({'http': 'http://' + proxy})
    url_opener = urllib.request.build_opener(proxy_handler)
    buf = bytearray(4096)

    ok = True
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
            inj = dict(desc=None, dlnk=None, insdata={})
            _logpart('v', uri)
            try:
                with url_opener.open(req) as res:
                    # Capture injection headers from the response.
                    for (h, v) in res.headers.items():
                        if h == 'X-Ouinet-Descriptor':
                            inj['desc'] = v
                        elif h == 'X-Ouinet-Descriptor-Link':
                            inj['dlnk'] = v
                        elif _ins_hdr_rx.match(h):
                            db = _ins_hdr_rx.match(h).group('db')
                            inj['insdata'][db] = v
                    while res.readinto(buf):  # consume body data
                        pass
            except Exception as e:
                err = str(e)
            else:
                err = '' if inj['desc'] else "URI was not injected"
            _logline(' ERROR="%s"' % err if err else '')
            if err:
                ok = False
                continue

            def save_descf(data, transf, ext, log):
                nonlocal ok
                try:
                    data = transf(data)
                except Exception:
                    ok = False
                    _logpart(' -' + log)
                    return
                path = os.path.join(descdir, fn + ext)
                with open(path, 'wb') as f:
                    f.write(data)
                _logpart(' +' + log)

            _logpart('>', uri)
            # Save the descriptor resulting from the injection.
            save_descf( inj.get('desc'),
                        (lambda x: zlib.decompress(base64.b64decode(x))),
                        DESC_FILE_EXT, 'DESC' )
            # Save the descriptor storage link.
            save_descf( inj.get('dlnk'),
                        (lambda x: x.encode('utf-8')),  # though probably ASCII
                        LINK_FILE_EXT, 'LINK' )
            # Save any db-dependent insertion data.
            for (db, insd) in inj['insdata'].items():
                save_descf( insd, base64.b64decode,
                            '.ins-' + db.lower(), db.upper() )
            _logline('')
    return ok

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

    ok = True

    if 'index' in args.action:
        _logline("Creating index files...")
        ok = ok and generate_indexes(args.directory, args.index_name, args.force_index)

    if 'inject' in args.action:
        _logline("Requesting content via the Ouinet client...")
        ok = ok and inject_uris(args.directory, args.uri_prefix, args.client_proxy)

    if 'seed' in args.action:
        _logline("Uploading files to the Ouinet client...")
        ok = ok and seed_files(args.directory, args.client_proxy)

    return 0 if ok else 2

if __name__ == '__main__':
    sys.exit(main())
