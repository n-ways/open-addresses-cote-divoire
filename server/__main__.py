"""Command line: import, serve, export (see server/README.md)."""
import argparse
import os
import sqlite3
import sys

from . import api, geo, register, service, store


def env_list(name):
    return [x.strip() for x in os.environ.get(name, '').split(',') if x.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(prog='python3 -m server', description="N-Ways Addressing for Côte d'Ivoire: registry server")
    sub = p.add_subparsers(dest='cmd', required=True)
    db_default = os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite')

    pi = sub.add_parser('import', help='load the published registry into a new database (verified against MANIFEST.json)')
    pi.add_argument('--registry', default='registry', help='folder with MANIFEST.json, areas.csv.gz and <zone>.csv.gz')
    pi.add_argument('--db', default=db_default)
    pi.add_argument('--register', default=None, help='engine/data/register.json (default: the one in this repository)')
    pi.add_argument('--force', action='store_true', help='replace a database that holds codes issued or changed here')

    ps = sub.add_parser('serve', help='serve the JSON API')
    ps.add_argument('--db', default=db_default)
    ps.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    ps.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))

    pe = sub.add_parser('export', help='write the registry back in the published format')
    pe.add_argument('--db', default=db_default)
    pe.add_argument('--out', required=True)

    pb = sub.add_parser('backup', help='copy the live database safely (online backup)')
    pb.add_argument('--db', default=db_default)
    pb.add_argument('--out', required=True)

    a = p.parse_args(argv)
    if a.cmd == 'backup':
        src = store.connect(a.db, readonly=True)
        dst = sqlite3.connect(a.out)
        src.backup(dst)
        dst.close()
        src.close()
        print('backed up %s to %s' % (a.db, a.out))
        return 0
    if a.cmd == 'import':
        try:
            n = store.import_registry(a.registry, a.db, a.register, a.force)
        except store.ImportError_ as e:
            print('import refused: %s' % e, file=sys.stderr)
            return 2
        print('imported %d codes into %s' % (n, a.db))
        return 0
    if a.cmd == 'export':
        conn = store.connect(a.db)
        store.export_registry(conn, a.out)
        conn.close()
        return 0
    st = store.Store(a.db)
    keys = env_list('ISSUE_KEYS')
    per_day = int(os.environ.get('ISSUE_PER_DAY', '5'))
    svc = service.Service(st, geo.default_outline(register.REPO), keys, per_day)
    httpd = api.serve(svc, a.host, a.port, env_list('CORS_ORIGINS'))
    print('serving %s codes of %s on http://%s:%d/v1 (%s)' % (st.meta.get('codes'), register.COUNTRY_NAME, a.host, a.port,
                                                             'issuing with %d key(s)' % len(keys) if keys else 'read-only'),
          file=sys.stderr, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
