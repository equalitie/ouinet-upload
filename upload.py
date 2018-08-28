#!/usr/bin/env python3
"""Prepare a content directory and publish it to Ouinet.
"""

import argparse
import html
import os
import sys


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

def gen_index(iname, dname, dirnames, filenames):
    q = html.escape
    rh = INDEX_HEAD % (q(dname),)
    rup = INDEX_UP_ITEM % (q(iname),)
    rdl = ''.join(INDEX_DIR_ITEM % (q('%s/%s' % (dn, iname)), q(dn)) for dn in dirnames)
    rfl = ''.join(INDEX_FILE_ITEM % (q(fn), q(fn)) for fn in filenames if fn != iname)
    rt = INDEX_TAIL
    return ''.join([rh, rup, rdl, rfl, rt])

def generate_indexes(path, idxname, force=False):
    for (dirpath, dirnames, filenames) in os.walk(path):
        index_fn = os.path.join(dirpath, idxname)
        if not force and os.path.exists(index_fn):
            raise RuntimeError("refusing to overwrite existing index file: %s"
                               % index_fn)
        index = gen_index(idxname,
                          os.path.basename(dirpath), dirnames, filenames)
        with open(index_fn, 'w') as index_f:
            index_f.write(index)

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
        'directory', metavar="DIR",
        help="the content directory to prepare and publish")
    args = parser.parse_args()

    print("Creating index files...", file=sys.stderr)
    generate_indexes(args.directory, args.index_name, args.force_index)

    # TODO: Try to inject content using the Ouinet client.
    # TODO: Optionally seed content through the Ouinet client or an IPFS node.

if __name__ == '__main__':
    main()
