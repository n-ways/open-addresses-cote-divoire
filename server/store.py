"""The SQLite database of a deployment: import of the published registry,
export in the same format, and the lookups the API needs.

Import verifies every file against MANIFEST.json (SHA-256 of the uncompressed
CSV, rows per unit, the total) and refuses any mismatch. It builds a new
database next to the target and swaps it in only when everything matched, so
an interrupted or refused import leaves the previous database untouched.

Export writes the registry back in the published format: the same columns in
the same order, the same row order (name, then number, per unit), the same
CSV quoting, gzip with no name or time stamp (as `gzip -n`), and a
MANIFEST.json. After importing a published registry, an export is identical
to it byte for byte once uncompressed.
"""
import csv
import datetime
import gzip
import hashlib
import io
import json
import math
import os
import sqlite3
import threading

from . import register as regmod

CODE_COLUMNS = ['machine', 'home', 'remembered', 'written', 'zone', 'official_name', 'number', 'check', 'status', 'issued',
                'issued_at', 'entrance_lat', 'entrance_lng', 'entrance_kind', 'plus_code', 'official_address', 'class', 'use',
                'kind', 'structures', 'floor_area_m2', 'rule', 'estate']
AREA_COLUMNS = ['zone', 'unit', 'unit_name', 'index', 'plate_name', 'official_name', 'name_key', 'name_id', 'blocks',
                'needs_council_choice', 'place_lat', 'place_lon', 'frame']

SCHEMA = '''
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE units (code TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT, departement TEXT, region TEXT,
    ref TEXT, ref_lat REAL, ref_lon REAL);
CREATE TABLE names (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, plate TEXT NOT NULL, digits INTEGER NOT NULL);
CREATE TABLE aliases (key TEXT PRIMARY KEY, official TEXT NOT NULL, plate_key TEXT NOT NULL, areas TEXT NOT NULL);
CREATE TABLE areas (zone TEXT PRIMARY KEY, ord INTEGER NOT NULL, area_id INTEGER NOT NULL UNIQUE, unit TEXT NOT NULL,
    unit_name TEXT NOT NULL, idx TEXT NOT NULL, plate_name TEXT NOT NULL, official_name TEXT NOT NULL,
    name_key TEXT NOT NULL, name_id INTEGER NOT NULL, blocks TEXT NOT NULL, needs_council_choice INTEGER NOT NULL,
    place_lat REAL NOT NULL, place_lon REAL NOT NULL, frame TEXT NOT NULL,
    plate_fold TEXT NOT NULL, official_fold TEXT NOT NULL);
CREATE INDEX areas_unit ON areas (unit, idx);
CREATE INDEX areas_name ON areas (name_key);
CREATE INDEX areas_plate_fold ON areas (plate_fold);
CREATE INDEX areas_official_fold ON areas (official_fold);
CREATE TABLE codes (
    id INTEGER PRIMARY KEY,
    machine TEXT NOT NULL UNIQUE,
    home TEXT NOT NULL, remembered TEXT NOT NULL, written TEXT NOT NULL,
    zone TEXT NOT NULL, official_name TEXT NOT NULL,
    number INTEGER NOT NULL, check_digit INTEGER NOT NULL,
    status TEXT NOT NULL, issued TEXT NOT NULL, issued_at TEXT NOT NULL,
    entrance_lat REAL NOT NULL, entrance_lng REAL NOT NULL, entrance_kind TEXT NOT NULL,
    plus_code TEXT NOT NULL, official_address TEXT NOT NULL,
    class TEXT NOT NULL, use TEXT NOT NULL, kind TEXT NOT NULL, structures INTEGER NOT NULL,
    floor_area_m2 TEXT NOT NULL, rule TEXT NOT NULL, estate TEXT NOT NULL,
    unit TEXT NOT NULL, name_id INTEGER NOT NULL,
    anchor_lat REAL NOT NULL, anchor_lng REAL NOT NULL,
    official_fold TEXT NOT NULL DEFAULT '',
    outline TEXT,
    local INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX codes_name_number ON codes (name_id, number);
CREATE INDEX codes_remembered ON codes (remembered);
CREATE INDEX codes_home ON codes (home);
CREATE INDEX codes_zone_number ON codes (zone, number);
CREATE INDEX codes_unit_order ON codes (unit, name_id, number);
CREATE INDEX codes_official ON codes (official_fold) WHERE official_fold <> '';
CREATE TABLE issue_log (key_id TEXT NOT NULL, at TEXT NOT NULL, machine TEXT NOT NULL);
CREATE INDEX issue_log_key ON issue_log (key_id, at);
'''

RTREE = 'CREATE VIRTUAL TABLE codes_rtree USING rtree(id, min_lat, max_lat, min_lng, max_lng)'
GRID = '''CREATE TABLE codes_grid (cell INTEGER NOT NULL, id INTEGER NOT NULL);
CREATE INDEX codes_grid_cell ON codes_grid (cell)'''
GRID_DEG = 0.001  # about 110 m: the integer grid used when SQLite has no R*Tree


class ImportError_(Exception):
    """The registry does not match its manifest; nothing was changed."""


def fold(s):
    """Case, accents, spacing and punctuation folded away (for official names
    and addresses)."""
    return regmod.ref._fold(s or '')


def connect(path, readonly=False):
    if readonly:
        conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True, check_same_thread=False, timeout=30)
    else:
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn


def has_rtree(conn):
    try:
        conn.execute('CREATE VIRTUAL TABLE temp.rtree_probe USING rtree(id, a, b)')
        conn.execute('DROP TABLE temp.rtree_probe')
        return True
    except sqlite3.OperationalError:
        return False


def grid_cell(lat, lng):
    return int((lat + 90) / GRID_DEG) * 1000000 + int((lng + 180) / GRID_DEG)


# ---------------------------------------------------------------- import

def _read_gz(path):
    with open(path, 'rb') as fh:
        return gzip.decompress(fh.read())


def import_registry(registry, db, register_json=None, force=False, log=print):
    """Load registry/ (MANIFEST.json, areas.csv.gz, <unit>.csv.gz) into a new
    database at db. Returns the number of codes."""
    register_json = register_json or os.path.join(regmod.REPO, 'engine', 'data', 'register.json')
    with open(os.path.join(registry, 'MANIFEST.json'), encoding='utf-8') as fh:
        manifest = json.load(fh)
    if manifest.get('country') != regmod.COUNTRY:
        raise ImportError_('MANIFEST.json is for %r, not %s' % (manifest.get('country'), regmod.COUNTRY))
    if os.path.exists(db) and not force:
        old = connect(db, readonly=True)
        try:
            n = old.execute('SELECT count(*) FROM codes WHERE local = 1').fetchone()[0]
        except sqlite3.DatabaseError:
            n = 0
        old.close()
        if n:
            raise ImportError_('%s holds %d codes issued or changed by this deployment; export them first, '
                               'or pass --force to discard them' % (db, n))
    tmp = db + '.importing'
    for p in (tmp, tmp + '-wal', tmp + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    conn = connect(tmp)
    conn.execute('PRAGMA synchronous=OFF')
    conn.executescript(SCHEMA)
    rtree = has_rtree(conn)
    conn.executescript(RTREE if rtree else GRID)
    try:
        total = _load(conn, registry, manifest, register_json, rtree, log)
        conn.commit()
        conn.execute('ANALYZE')
        conn.commit()
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        conn.close()
    except BaseException:
        conn.close()
        for p in (tmp, tmp + '-wal', tmp + '-shm'):
            if os.path.exists(p):
                os.remove(p)
        raise
    for p in (db + '-wal', db + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    os.replace(tmp, db)
    for p in (tmp + '-wal', tmp + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    return total


def _load(conn, registry, manifest, register_json, rtree, log):
    sha = manifest['sha256']
    by_unit = manifest['byUnit']
    expected = {'areas.csv'} | {u + '.csv' for u in by_unit}
    if set(sha) != expected:
        raise ImportError_('MANIFEST.json lists %s but byUnit implies %s' % (sorted(set(sha) ^ expected), 'the same files'))
    if sum(by_unit.values()) != manifest['codes']:
        raise ImportError_('MANIFEST.json: byUnit adds up to %d, codes says %d' % (sum(by_unit.values()), manifest['codes']))

    with open(register_json, encoding='utf-8') as fh:
        frozen = json.load(fh)
    conn.executemany('INSERT INTO units VALUES (?,?,?,?,?,?,?,?)',
                     [(u['code'], u['name'], u.get('kind'), u.get('departement'), u.get('region'), u.get('ref'),
                       u.get('refLat'), u.get('refLon')) for u in frozen['units']])
    conn.executemany('INSERT INTO names VALUES (?,?,?,?)', [(n['id'], n['key'], n['plate'], n['digits']) for n in frozen['names']])
    conn.executemany('INSERT INTO aliases VALUES (?,?,?,?)',
                     [(a['key'], a['official'], a['plateKey'], json.dumps(a['areas'])) for a in frozen['aliases']])
    area_ids = {a['aid']: a['id'] for a in frozen['areas']}

    # areas.csv: the frozen areas with every block taken since.
    raw = _read_gz(os.path.join(registry, 'areas.csv.gz'))
    if hashlib.sha256(raw).hexdigest() != sha['areas.csv']:
        raise ImportError_('areas.csv: SHA-256 does not match MANIFEST.json')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline='')))
    if rows[0] != AREA_COLUMNS:
        raise ImportError_('areas.csv: unexpected columns %s' % rows[0])
    areas = {}
    out = []
    for i, r in enumerate(rows[1:]):
        d = dict(zip(AREA_COLUMNS, r))
        if d['zone'] not in area_ids:
            raise ImportError_('areas.csv: area %s is not in engine/data/register.json' % d['zone'])
        areas[d['zone']] = d
        out.append((d['zone'], i, area_ids[d['zone']], d['unit'], d['unit_name'], d['index'], d['plate_name'], d['official_name'],
                    d['name_key'], int(d['name_id']), d['blocks'], 1 if d['needs_council_choice'] == 'true' else 0,
                    float(d['place_lat']), float(d['place_lon']), d['frame'], fold(d['plate_name']), fold(d['official_name'])))
    conn.executemany('INSERT INTO areas VALUES (%s)' % ','.join('?' * 17), out)
    log('areas: %d' % len(out))

    total = 0
    for unit in sorted(by_unit):
        name = unit + '.csv'
        raw = _read_gz(os.path.join(registry, name + '.gz'))
        if hashlib.sha256(raw).hexdigest() != sha[name]:
            raise ImportError_('%s: SHA-256 does not match MANIFEST.json' % name)
        reader = csv.reader(io.StringIO(raw.decode('utf-8'), newline=''))
        del raw
        if next(reader) != CODE_COLUMNS:
            raise ImportError_('%s: unexpected columns' % name)
        batch = []
        n = 0
        for r in reader:
            d = dict(zip(CODE_COLUMNS, r))
            a = areas.get(d['zone'])
            if a is None:
                raise ImportError_('%s: %s is in area %s, which areas.csv does not have' % (name, d['machine'], d['zone']))
            if a['unit'] != unit:
                raise ImportError_('%s: %s belongs to unit %s' % (name, d['machine'], a['unit']))
            lat, lng = float(d['entrance_lat']), float(d['entrance_lng'])
            batch.append((d['machine'], d['home'], d['remembered'], d['written'], d['zone'], d['official_name'], int(d['number']),
                          int(d['check']), d['status'], d['issued'], d['issued_at'], lat, lng, d['entrance_kind'], d['plus_code'],
                          d['official_address'], d['class'], d['use'], d['kind'], int(d['structures']), d['floor_area_m2'],
                          d['rule'], d['estate'], unit, int(a['name_id']), lat, lng, fold(d['official_address'])))
            n += 1
        if n != by_unit[unit]:
            raise ImportError_('%s: %d rows, MANIFEST.json says %d' % (name, n, by_unit[unit]))
        first = conn.execute('SELECT coalesce(max(id), 0) FROM codes').fetchone()[0] + 1
        conn.executemany('''INSERT INTO codes (machine, home, remembered, written, zone, official_name, number, check_digit,
            status, issued, issued_at, entrance_lat, entrance_lng, entrance_kind, plus_code, official_address, class, use, kind,
            structures, floor_area_m2, rule, estate, unit, name_id, anchor_lat, anchor_lng, official_fold)
            VALUES (%s)''' % ','.join('?' * 28), batch)
        pts = ((first + i, b[11], b[12]) for i, b in enumerate(batch))
        if rtree:
            conn.executemany('INSERT INTO codes_rtree VALUES (?,?,?,?,?)', ((i, la, la, lo, lo) for i, la, lo in pts))
        else:
            conn.executemany('INSERT INTO codes_grid VALUES (?,?)', ((grid_cell(la, lo), i) for i, la, lo in pts))
        conn.commit()
        total += n
    if total != manifest['codes']:
        raise ImportError_('%d codes imported, MANIFEST.json says %d' % (total, manifest['codes']))
    meta = {'country': regmod.COUNTRY, 'exported': manifest['exported'], 'codes': str(total), 'engine': manifest.get('engine', ''),
            'credit': manifest.get('credit', ''), 'licence': manifest.get('licence', ''), 'spatial': 'rtree' if rtree else 'grid',
            'imported': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'changed': ''}
    conn.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
    log('codes: %d in %d units' % (total, len(by_unit)))
    return total


# ---------------------------------------------------------------- export

def _go_field(s):
    """A CSV field quoted exactly when Go's encoding/csv quotes it (the
    issuer writes the registry with it): when it holds a comma, a quote, a
    carriage return or a newline, when it begins with a space, or when it is
    the two characters \\. ."""
    if s == '':
        return s
    if s == '\\.' or any(c in s for c in ',"\r\n') or s[0].isspace():
        return '"' + s.replace('"', '""') + '"'
    return s


def _line(fields):
    return ','.join(_go_field(f) for f in fields) + '\n'


def code_row(r):
    """A codes row (in CODE_COLUMNS order of the table) as the registry's CSV fields."""
    return [r[0], r[1], r[2], r[3], r[4], r[5], str(r[6]), str(r[7]), r[8], r[9], r[10], '%.7f' % r[11], '%.7f' % r[12], r[13],
            r[14], r[15], r[16], r[17], r[18], str(r[19]), r[20], r[21], r[22]]


CODE_SELECT = '''machine, home, remembered, written, zone, official_name, number, check_digit, status, issued, issued_at,
    entrance_lat, entrance_lng, entrance_kind, plus_code, official_address, class, use, kind, structures, floor_area_m2, rule, estate'''


def _write_gz(path, text_iter):
    h = hashlib.sha256()
    with open(path, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz:
            buf = []
            size = 0
            for s in text_iter:
                b = s.encode('utf-8')
                h.update(b)
                buf.append(b)
                size += len(b)
                if size > 1 << 20:
                    gz.write(b''.join(buf))
                    buf, size = [], 0
            gz.write(b''.join(buf))
    return h.hexdigest()


def export_registry(conn, out, log=print):
    os.makedirs(out, exist_ok=True)
    sha, by_unit = {}, {}

    def areas():
        yield _line(AREA_COLUMNS)
        for r in conn.execute('''SELECT zone, unit, unit_name, idx, plate_name, official_name, name_key, name_id, blocks,
                needs_council_choice, place_lat, place_lon, frame FROM areas ORDER BY ord'''):
            yield _line([r[0], r[1], r[2], r[3], r[4], r[5], r[6], str(r[7]), r[8], 'true' if r[9] else 'false',
                         '%.6f' % r[10], '%.6f' % r[11], r[12]])
    sha['areas.csv'] = _write_gz(os.path.join(out, 'areas.csv.gz'), areas())
    units = [u for (u,) in conn.execute('SELECT DISTINCT unit FROM areas ORDER BY unit')]
    total = 0
    for unit in units:
        n = conn.execute('SELECT count(*) FROM codes WHERE unit = ?', (unit,)).fetchone()[0]
        if not n:
            continue

        def rows(unit=unit):
            yield _line(CODE_COLUMNS)
            for r in conn.execute('SELECT %s FROM codes WHERE unit = ? ORDER BY name_id, number' % CODE_SELECT, (unit,)):
                yield _line(code_row(r))
        sha[unit + '.csv'] = _write_gz(os.path.join(out, unit + '.csv.gz'), rows())
        by_unit[unit] = n
        total += n
    meta = dict(conn.execute('SELECT key, value FROM meta'))
    exported = meta.get('changed') or meta['exported']
    manifest = {'byUnit': by_unit, 'codes': total, 'country': regmod.COUNTRY, 'credit': regmod.CREDIT, 'engine': regmod.ENGINE,
                'exported': exported, 'licence': 'ODbL 1.0 (LICENSE-DATA)', 'sha256': sha}
    with open(os.path.join(out, 'MANIFEST.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    log('exported %d codes in %d units to %s' % (total, len(by_unit), out))
    return total


# ---------------------------------------------------------------- lookups

class Store:
    """Thread-safe access: one connection per thread, writes serialised."""

    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError('no database at %s: run `python3 -m server import` first' % path)
        self.path = path
        self.local = threading.local()
        self.write_lock = threading.Lock()
        c = self.conn()
        self.meta = dict(c.execute('SELECT key, value FROM meta'))
        self.rtree = self.meta.get('spatial') == 'rtree'

    def conn(self):
        c = getattr(self.local, 'c', None)
        if c is None:
            c = connect(self.path)
            self.local.c = c
        return c

    def release(self):
        """Close this thread's connection (the API calls it after each request:
        the server runs one thread per request)."""
        c = getattr(self.local, 'c', None)
        if c is not None:
            c.close()
            self.local.c = None

    def q(self, sql, args=()):
        return self.conn().execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.conn().execute(sql, args).fetchone()

    def ids_in_box(self, lat, lng, metres):
        """Code ids whose entrance lies in the box of `metres` around a point."""
        dlat = metres / 110574.0
        dlng = metres / (111320.0 * max(0.2, math.cos(math.radians(lat))))
        if self.rtree:
            return [i for (i,) in self.q('SELECT id FROM codes_rtree WHERE min_lat <= ? AND max_lat >= ? AND min_lng <= ? AND max_lng >= ?',
                                         (lat + dlat, lat - dlat, lng + dlng, lng - dlng))]
        cells = []
        for a in range(int((lat - dlat + 90) / GRID_DEG), int((lat + dlat + 90) / GRID_DEG) + 1):
            for b in range(int((lng - dlng + 180) / GRID_DEG), int((lng + dlng + 180) / GRID_DEG) + 1):
                cells.append(a * 1000000 + b)
        out = []
        for i in range(0, len(cells), 500):
            part = cells[i:i + 500]
            out += [x for (x,) in self.q('SELECT id FROM codes_grid WHERE cell IN (%s)' % ','.join('?' * len(part)), part)]
        return out

    def add_point(self, conn, code_id, lat, lng):
        if self.rtree:
            conn.execute('INSERT OR REPLACE INTO codes_rtree VALUES (?,?,?,?,?)', (code_id, lat, lat, lng, lng))
        else:
            conn.execute('DELETE FROM codes_grid WHERE id = ?', (code_id,))
            conn.execute('INSERT INTO codes_grid VALUES (?,?)', (grid_cell(lat, lng), code_id))
