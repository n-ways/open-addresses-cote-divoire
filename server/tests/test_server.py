"""Tests of the registry server on the fixture registry (server/testdata):
the full area table and every code of one zone, 080104 (Parc National de
Bona, 787 codes in 7 areas), exactly as published.

    python3 -m unittest discover -s server/tests -t .
"""
import csv
import gzip
import io
import json
import math
import os
import re
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from server import api, geo, register, service, store

HERE = os.path.dirname(os.path.abspath(__file__))
TESTDATA = os.path.join(os.path.dirname(HERE), 'testdata')
FIXTURE = os.path.join(TESTDATA, 'registry')
KEY = 'test-issuing-key'


def quiet(*a, **k):
    pass


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def rows_of(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


class Server:
    """A running server on a fresh copy of the fixture database."""

    def __init__(self, db, keys=(KEY,), per_day=1000):
        self.store = store.Store(db)
        self.svc = service.Service(self.store, geo.default_outline(register.REPO), keys, per_day)
        self.httpd = api.serve(self.svc, '127.0.0.1', 0, ['*'], log_requests=False)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None, key=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path), data=data, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if key:
            req.add_header('Authorization', 'Bearer ' + key)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.store.release()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='nways-ci-')
        cls.db = os.path.join(cls.tmp, 'addresses.sqlite')
        store.import_registry(FIXTURE, cls.db, log=quiet)
        cls.rows = rows_of(os.path.join(FIXTURE, '080104.csv.gz'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def fresh(self, name, **kw):
        db = os.path.join(self.tmp, name + '.sqlite')
        shutil.copy(self.db, db)
        s = Server(db, **kw)
        self.addCleanup(s.close)
        return s, db

    def assertError(self, got, status, code):
        st, body = got
        self.assertEqual(st, status, body)
        self.assertEqual(set(body), {'error'}, body)
        self.assertLessEqual({'code', 'message'}, set(body['error']))
        self.assertEqual(body['error']['code'], code, body)
        self.assertTrue(body['error']['message'])


class TestImportExport(Base):
    def test_round_trip_is_byte_identical(self):
        out = os.path.join(self.tmp, 'export')
        conn = store.connect(self.db)
        store.export_registry(conn, out, log=quiet)
        conn.close()
        for name in ('areas.csv.gz', '080104.csv.gz'):
            with gzip.open(os.path.join(FIXTURE, name)) as a, gzip.open(os.path.join(out, name)) as b:
                self.assertEqual(a.read(), b.read(), name)
            with open(os.path.join(out, name), 'rb') as fh:
                head = fh.read(10)
            self.assertEqual(head[4:8], b'\0\0\0\0', 'no time stamp in the gzip header')
            self.assertEqual(head[3] & 0x08, 0, 'no file name in the gzip header')
        with open(os.path.join(FIXTURE, 'MANIFEST.json'), 'rb') as a, open(os.path.join(out, 'MANIFEST.json'), 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_import_refuses_a_changed_file(self):
        bad = os.path.join(self.tmp, 'bad-registry')
        shutil.copytree(FIXTURE, bad)
        rows = rows_of(os.path.join(bad, '080104.csv.gz'))
        rows[5]['entrance_lat'] = '9.0000000'
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=store.CODE_COLUMNS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
        with gzip.open(os.path.join(bad, '080104.csv.gz'), 'wt', encoding='utf-8') as fh:
            fh.write(buf.getvalue())
        target = os.path.join(self.tmp, 'refused.sqlite')
        with self.assertRaisesRegex(store.ImportError_, 'SHA-256'):
            store.import_registry(bad, target, log=quiet)
        self.assertFalse(os.path.exists(target))
        self.assertFalse(os.path.exists(target + '.importing'))

    def test_import_refuses_a_wrong_count(self):
        bad = os.path.join(self.tmp, 'bad-count')
        shutil.copytree(FIXTURE, bad)
        m = read_json(os.path.join(bad, 'MANIFEST.json'))
        m['byUnit']['080104'] += 1
        m['codes'] += 1
        with open(os.path.join(bad, 'MANIFEST.json'), 'w', encoding='utf-8') as fh:
            json.dump(m, fh)
        with self.assertRaisesRegex(store.ImportError_, 'rows'):
            store.import_registry(bad, os.path.join(self.tmp, 'refused2.sqlite'), log=quiet)

    def test_reimport_is_safe_and_keeps_local_codes_unless_forced(self):
        db = os.path.join(self.tmp, 'again.sqlite')
        self.assertEqual(store.import_registry(FIXTURE, db, log=quiet), 787)
        self.assertEqual(store.import_registry(FIXTURE, db, log=quiet), 787)
        s = Server(db)
        r0 = self.rows[0]
        st, _ = s.call('PATCH', '/v1/codes/' + r0['machine'], {'status': 'confirmed'}, key=KEY)
        s.close()
        self.assertEqual(st, 200)
        with self.assertRaisesRegex(store.ImportError_, 'export them first'):
            store.import_registry(FIXTURE, db, log=quiet)
        self.assertEqual(store.import_registry(FIXTURE, db, force=True, log=quiet), 787)

    def test_grid_index_when_sqlite_has_no_rtree(self):
        db = os.path.join(self.tmp, 'grid.sqlite')
        real = store.has_rtree
        store.has_rtree = lambda conn: False
        try:
            store.import_registry(FIXTURE, db, log=quiet)
        finally:
            store.has_rtree = real
        s = Server(db)
        self.addCleanup(s.close)
        self.assertFalse(s.store.rtree)
        r = self.rows[10]
        st, a = s.call('GET', '/v1/at?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual((st, a['status'], a['code']['machine']), (200, 'found', r['machine']))
        st, n = s.call('GET', '/v1/near?lat=%s&lng=%s&radius=300' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual(n['results'][0]['machine'], r['machine'])
        st, c = s.call('POST', '/v1/codes', {'lat': float(r['entrance_lat']) + 0.0002, 'lng': float(r['entrance_lng']), 'of': r['machine']}, key=KEY)
        self.assertEqual(st, 201, c)
        st, a = s.call('GET', '/v1/at?lat=%f&lng=%s' % (float(r['entrance_lat']) + 0.0002, r['entrance_lng']))
        self.assertEqual(a['code']['machine'], c['machine'])

    def test_spatial_index(self):
        conn = store.connect(self.db)
        n = conn.execute('SELECT count(*) FROM codes_rtree').fetchone()[0]
        conn.close()
        self.assertEqual(n, 787)


class TestRead(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = Server(cls.db, keys=())

    @classmethod
    def tearDownClass(cls):
        cls.s.close()
        super().tearDownClass()

    def get(self, path):
        return self.s.call('GET', path)

    def test_health_and_info(self):
        st, h = self.get('/v1/health')
        self.assertEqual((st, h['status'], h['country'], h['codes'], h['issuing']), (200, 'ok', 'CI', 787, False))
        self.assertEqual(h['registryExported'], '2026-10-20T14:50:41Z')
        st, i = self.get('/v1/info')
        self.assertEqual(st, 200)
        self.assertEqual((i['zones'], i['areas'], i['codes']['total']), (520, 9834, 787))
        self.assertIn('N-WAYS LIMITED', i['credit'])

    def test_card_has_every_registry_column(self):
        r = self.rows[0]
        st, c = self.get('/v1/codes/' + r['machine'])
        self.assertEqual(st, 200)
        self.assertEqual(c['registry'], r)
        self.assertEqual((c['machine'], c['remembered'], c['written'], c['number']), (r['machine'], r['remembered'], r['written'], int(r['number'])))
        self.assertEqual(c['area']['id'], r['zone'])
        self.assertEqual(c['zone']['key'], '080104')
        self.assertEqual(c['spot']['short'], r['plus_code'])
        self.assertEqual(len(c['spot']['plusCode']), 12)

    def test_card_errors(self):
        r = self.rows[0]
        wrong = r['machine'][:-1] + str((int(r['machine'][-1]) + 1) % 10)
        self.assertError(self.get('/v1/codes/' + wrong), 422, 'bad_check_digit')
        self.assertError(self.get('/v1/codes/CI-080104'), 400, 'bad_machine_form')
        self.assertError(self.get('/v1/codes/CI-999999-001-1000-0'), 404, 'unknown_area')
        st, v = self.get('/v1/verify?code=CI-080104-001-1499')
        self.assertFalse(v['valid'])
        # a valid code no compound has yet
        a = self.s.svc.reg.by_zone['080104-001']
        free = self.s.svc.reg.forms(a, 1499)['machine']
        self.assertError(self.get('/v1/codes/' + free), 404, 'not_issued')

    def test_find_remembered_in_every_spelling(self):
        r = next(x for x in self.rows if x['zone'] == '080104-001')
        n = r['number']
        for q in ('Tiobel · %s %s' % (n[:2], n[2:]), 'tiobel %s' % n, 'TIOBEL %s %s' % (n[:2], n[2:]), 'Tiobel%s' % n,
                  '  tiobel   %s ' % n, 'Tiobel %s %s (Parc National de Bona)' % (n[:2], n[2:]), 'Tiobel %s, Bouna' % n,
                  'Tiobel-%s' % n):
            st, f = self.get('/v1/find?q=' + urllib.request.quote(q))
            self.assertEqual(st, 200, (q, f))
            self.assertEqual(f['results'][0]['machine'], r['machine'], q)

    def test_find_accents_and_official_names(self):
        r = next(x for x in self.rows if x['zone'] == '080104-006')
        n = r['number']
        for q in ('Gadie Pere %s' % n, 'GADIÉ PÉRÉ %s' % n, 'Mare de Gadié Péré %s' % n):
            st, f = self.get('/v1/find?q=' + urllib.request.quote(q))
            self.assertEqual(st, 200, (q, f))
            self.assertEqual(f['results'][0]['machine'], r['machine'])

    def test_find_machine_and_spot(self):
        r = self.rows[3]
        st, f = self.get('/v1/find?q=' + urllib.request.quote(r['machine'].lower().replace('-', ' - ', 1)))
        self.assertEqual((st, f['form'], f['results'][0]['machine']), (200, 'machine', r['machine']))
        st, f = self.get('/v1/find?q=' + urllib.request.quote(r['plus_code']))
        self.assertEqual(st, 200, f)
        self.assertEqual(f['form'], 'spot')
        self.assertEqual(f['results'][0]['machine'], r['machine'])

    def test_find_errors(self):
        r = self.rows[0]
        wrong = r['machine'][:-1] + str((int(r['machine'][-1]) + 1) % 10)
        self.assertError(self.get('/v1/find?q=' + wrong), 422, 'bad_check_digit')
        self.assertError(self.get('/v1/find?q='), 400, 'missing_query')
        self.assertError(self.get('/v1/find?q=Nowhereville%201234'), 404, 'not_found')
        self.assertError(self.get('/v1/find?q=Tiobel%201002%20(Cocody)'), 404, 'not_found')
        self.assertError(self.get('/v1/find?q=Tiobel%201499'), 404, 'not_issued')
        self.assertError(self.get('/v1/find?q=Tiobel%209999'), 404, 'not_found')
        # two readings: the plate name wins (this fixture holds no Korhogo code, so it is
        # decoded and then not found among the issued codes, never refused as ambiguous)
        st, e = self.get('/v1/find?q=' + urllib.request.quote('Air France 1 10 00 (Korhogo)'))
        self.assertEqual((st, e['error']['code']), (404, 'not_issued'), e)
        self.assertIn('Korhogo', e['error']['message'])
        self.assertError(self.get('/v1/find?q=' + urllib.request.quote('115, Rue des Moineaux, Le Plateau')), 404, 'unknown_official_address')

    def test_at(self):
        r = self.rows[10]
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        st, a = self.get('/v1/at?lat=%f&lng=%f' % (lat + 0.00003, lng))
        self.assertEqual((st, a['status'], a['code']['machine']), (200, 'found', r['machine']))
        self.assertLessEqual(a['distanceM'], 12)
        st, a = self.get('/v1/at?lat=%f&lng=%f' % (lat + 0.01, lng))
        self.assertEqual((st, a['status'], a['canIssue']), (200, 'none', False))
        self.assertIn('id', a['area'])
        self.assertError(self.get('/v1/at?lat=4.8&lng=-4.0'), 422, 'outside_country')
        self.assertError(self.get('/v1/at?lat=abc&lng=1'), 400, 'bad_number')
        self.assertError(self.get('/v1/at?lat=5.3'), 400, 'bad_point')

    def test_near(self):
        r = self.rows[10]
        st, n = self.get('/v1/near?lat=%s&lng=%s&radius=500&limit=5' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual(st, 200)
        self.assertEqual(n['results'][0]['machine'], r['machine'])
        self.assertLessEqual(n['count'], 5)
        ds = [x['distanceM'] for x in n['results']]
        self.assertEqual(ds, sorted(ds))
        self.assertError(self.get('/v1/near?lat=9.3&lng=-4.1&radius=501'), 400, 'bad_radius')
        self.assertError(self.get('/v1/near?lat=9.3&lng=-4.1&limit=101'), 400, 'bad_limit')

    def test_verify(self):
        r = self.rows[0]
        st, v = self.get('/v1/verify?code=' + r['machine'])
        self.assertEqual((st, v['valid'], v['issued'], v['status']), (200, True, True, 'provisional'))
        wrong = r['machine'][:-1] + str((int(r['machine'][-1]) + 1) % 10)
        st, v = self.get('/v1/verify?code=' + wrong)
        self.assertEqual((v['syntax'], v['area'], v['inBlock'], v['check'], v['valid']), (True, True, True, False, False))
        st, v = self.get('/v1/verify?code=CI-080104-001-9999-0')
        self.assertEqual((v['area'], v['inBlock']), (True, False))
        st, v = self.get('/v1/verify?code=hello')
        self.assertFalse(v['syntax'])
        self.assertError(self.get('/v1/verify'), 400, 'missing_code')

    def test_spot(self):
        r = self.rows[1]
        st, s = self.get('/v1/spot?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual(st, 200)
        self.assertEqual(s['short'], r['plus_code'])
        st, d = self.get('/v1/spot/decode?code=' + urllib.request.quote(s['short']))
        self.assertEqual(st, 200, d)
        self.assertEqual(d['plusCode'], s['plusCode'])
        self.assertAlmostEqual(d['lat'], float(r['entrance_lat']), places=4)
        self.assertEqual(d['code']['machine'], r['machine'])
        # a reference town two units share is written with its département; the bare town
        # decodes only when one reading is possible, and is refused otherwise
        st, s = self.get('/v1/spot?lat=7.777&lng=-5.376')
        self.assertEqual((st, s['short'], s['reference']), (200, 'QJGF+RJ2 Lolobo (Béoumi)', 'Lolobo (Béoumi)'))
        for text in ('QJGF+RJ2 Lolobo (Béoumi)', 'QJGF+RJ2 lolobo, beoumi', 'QJGF+RJ2 Lolobo'):
            st, d = self.get('/v1/spot/decode?code=' + urllib.request.quote(text))
            self.assertEqual((st, d['plusCode'], d['reference']), (200, s['plusCode'], 'Lolobo (Béoumi)'), text)
        self.assertError(self.get('/v1/spot/decode?code=' + urllib.request.quote('VMV4+VJP Lolobo')), 422, 'bad_spot')
        self.assertError(self.get('/v1/spot/decode?code=XXXX'), 422, 'bad_spot')
        self.assertError(self.get('/v1/spot/decode?code=926H%2B7Q7%20Atlantis'), 422, 'bad_spot')

    def test_zones_and_areas(self):
        st, z = self.get('/v1/zones')
        self.assertEqual((st, z['count']), (200, 520))
        bona = next(x for x in z['zones'] if x['key'] == '080104')
        self.assertEqual((bona['codes'], bona['areas']), (787, 7))
        st, z = self.get('/v1/zones/080104')
        self.assertEqual((st, len(z['areas']), z['codes']), (200, 7, 787))
        self.assertError(self.get('/v1/zones/999999'), 404, 'unknown_zone')
        st, a = self.get('/v1/areas/080104-004')
        self.assertEqual((st, a['plateName'], a['digits'], a['blocks'][0]['lo']), (200, 'Sokoura', 5, 40200))
        self.assertEqual(a['codes']['total'], 27)
        self.assertTrue(any(x['id'] == '110301-090' for x in a['sameName']))
        self.assertError(self.get('/v1/areas/080104-999'), 404, 'unknown_area')
        st, f = self.get('/v1/areas?name=sokoura')
        self.assertEqual(st, 200)
        self.assertGreaterEqual(f['count'], 3)
        st, f = self.get('/v1/areas?name=' + urllib.request.quote('Mare de Gadié Péré'))
        self.assertEqual((st, [x['id'] for x in f['areas']]), (200, ['080104-006']))
        self.assertError(self.get('/v1/areas?name=Atlantis'), 404, 'unknown_name')
        self.assertError(self.get('/v1/areas'), 400, 'missing_name')

    def test_zone_codes_paging(self):
        seen, after = [], ''
        while True:
            st, p = self.get('/v1/zones/080104/codes?limit=300&after=' + after)
            self.assertEqual(st, 200)
            seen += [c['machine'] for c in p['results']]
            if not p['next']:
                break
            after = p['next']
        self.assertEqual(seen, sorted(r['machine'] for r in self.rows))
        self.assertError(self.get('/v1/zones/080104/codes?limit=0'), 400, 'bad_limit')

    def test_read_only_and_routing(self):
        self.assertError(self.s.call('POST', '/v1/codes', {'lat': 9.3, 'lng': -4.1}, key=KEY), 403, 'read_only')
        self.assertError(self.s.call('PATCH', '/v1/codes/' + self.rows[0]['machine'], {'status': 'confirmed'}), 403, 'read_only')
        self.assertError(self.get('/v1/nothing'), 404, 'no_such_endpoint')
        self.assertError(self.s.call('DELETE', '/v1/codes/' + self.rows[0]['machine']), 405, 'method_not_allowed')


class TestOfficialAddress(Base):
    def test_official_address_is_found_and_exported_quoted(self):
        db = os.path.join(self.tmp, 'official.sqlite')
        shutil.copy(self.db, db)
        r = self.rows[50]
        official = '115, Rue des Moineaux, Le Plateau'
        conn = store.connect(db)
        conn.execute('UPDATE codes SET official_address = ?, official_fold = ? WHERE machine = ?', (official, store.fold(official), r['machine']))
        conn.commit()
        s = Server(db)
        self.addCleanup(s.close)
        st, f = s.call('GET', '/v1/find?q=' + urllib.request.quote('115 rue des moineaux, le plateau'))
        self.assertEqual((st, f['form'], f['results'][0]['machine']), (200, 'official', r['machine']))
        self.assertEqual(f['results'][0]['officialAddress'], official)
        out = os.path.join(self.tmp, 'export-official')
        store.export_registry(conn, out, log=quiet)
        conn.close()
        with gzip.open(os.path.join(out, '080104.csv.gz'), 'rt', encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn(',"115, Rue des Moineaux, Le Plateau",', text)
        row = next(x for x in rows_of(os.path.join(out, '080104.csv.gz')) if x['machine'] == r['machine'])
        self.assertEqual(row['official_address'], official)


class TestContract(unittest.TestCase):
    def test_openapi_lists_every_endpoint(self):
        with open(os.path.join(os.path.dirname(HERE), 'openapi.yaml'), encoding='utf-8') as fh:
            text = fh.read()
        documented = set(re.findall(r'^  "(/v1/[^"]*)":', text, re.M))
        served = set()
        for _, pattern, _ in api.routes(None):
            served.add(re.sub(r'\(\[\^/\]\+\)', '{x}', pattern))
        norm = {re.sub(r'\{[^}]+\}', '{x}', p) for p in documented}
        self.assertEqual(norm, served)


class TestIssue(Base):
    def test_parity_with_the_issuer_and_extension_blocks(self):
        s, db = self.fresh('parity')
        with open(os.path.join(TESTDATA, 'parity.json'), encoding='utf-8') as fh:
            parity = json.load(fh)
        new_blocks = {}
        for area in parity['areas']:
            for exp in area['results']:
                st, c = s.call('POST', '/v1/codes', {'lat': exp['lat'], 'lng': exp['lng'], 'of': area['of']}, key=KEY)
                self.assertEqual(st, 201, c)
                got = {k: c[k] for k in ('number', 'machine', 'home', 'remembered', 'written')}
                self.assertEqual(got, {k: exp[k] for k in got}, (area['zone'], exp))
                self.assertEqual((c['status'], c['issued'], c['entrance']['kind'], c['profile']['kind']),
                                 ('provisional', 'on-demand', 'door', 'door'))
                if 'newBlock' in exp:
                    new_blocks.setdefault(area['zone'], []).append(exp['newBlock'])
        self.assertIn('080104-003', new_blocks)
        self.assertIn('080104-004', new_blocks)
        st, a = s.call('GET', '/v1/areas/080104-004')
        self.assertEqual([[b['lo'], b['hi']] for b in a['blocks']][1:], new_blocks['080104-004'])
        # the new blocks and codes survive a restart and appear in the export
        s.close()
        conn = store.connect(db)
        out = os.path.join(self.tmp, 'export-after-issue')
        store.export_registry(conn, out, log=quiet)
        conn.close()
        areas = {r['zone']: r for r in rows_of(os.path.join(out, 'areas.csv.gz'))}
        self.assertEqual(areas['080104-003']['blocks'], '1000-1099|%d-%d' % tuple(new_blocks['080104-003'][0]))
        codes = rows_of(os.path.join(out, '080104.csv.gz'))
        self.assertEqual(len(codes), 787 + sum(len(a['results']) for a in parity['areas']))
        m = read_json(os.path.join(out, 'MANIFEST.json'))
        self.assertNotEqual(m['exported'], '2026-10-20T14:50:41Z')
        # re-import of the export gives the same state
        again = os.path.join(self.tmp, 'reimported.sqlite')
        self.assertEqual(store.import_registry(out, again, log=quiet), len(codes))
        s2 = Server(again)
        self.addCleanup(s2.close)
        st, a = s2.call('GET', '/v1/areas/080104-003')
        self.assertEqual(len(a['blocks']), 2)

    def test_new_compound_takes_the_neighbours_area(self):
        s, _ = self.fresh('neighbour')
        r = next(x for x in self.rows if x['zone'] == '080104-001')
        lat, lng = float(r['entrance_lat']) + 0.0005, float(r['entrance_lng'])  # about 55 m away
        st, c = s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng}, key=KEY)
        self.assertEqual(st, 201, c)
        self.assertEqual(c['area']['id'], s.svc.place_for(lat, lng)['zone'])
        self.assertEqual((c['entrance']['kind'], c['profile']['kind'], c['profile']['structures']), ('centre', 'building', 0))
        a = s.svc.reg.by_zone[c['area']['id']]
        issued = [(int(x['number']), float(x['entrance_lat']), float(x['entrance_lng'])) for x in self.rows if x['zone'] == a['zone']]
        self.assertEqual(c['number'], s.svc.reg.insert(a, issued, lat, lng)[0])
        # the same spot again: it has its code now
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat + 0.00001, 'lng': lng}, key=KEY), 409, 'already_has_code')
        st, again = s.call('GET', '/v1/at?lat=%f&lng=%f' % (lat, lng))
        self.assertEqual((again['status'], again['code']['machine']), ('found', c['machine']))

    def test_far_from_every_code_takes_the_nearest_place(self):
        s, _ = self.fresh('far')
        lat, lng = 9.45, -3.75  # inside the park, more than 250 m from any code of the fixture
        self.assertIsNone(s.svc.code_at(lat, lng, 250.0))
        st, c = s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng}, key=KEY)
        self.assertEqual(st, 201, c)
        self.assertEqual(c['area']['id'], s.svc.reg.nearest_area(lat, lng)['zone'])

    def test_duplicates_and_outlines(self):
        s, _ = self.fresh('dups')
        r = self.rows[20]
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        st, e = s.call('POST', '/v1/codes', {'lat': lat + 0.00001, 'lng': lng}, key=KEY)
        self.assertError((st, e), 409, 'already_has_code')
        self.assertEqual(e['error']['existing']['machine'], r['machine'])
        d = 0.0001  # about 11 m
        around = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d]]
        st, e = s.call('POST', '/v1/codes', {'lat': lat + 0.0002, 'lng': lng + 0.0002, 'outline': around}, key=KEY)
        self.assertError((st, e), 409, 'already_has_code')  # the outline holds a published entrance
        tiny = [[lng, lat + 0.001], [lng + 0.00001, lat + 0.001], [lng, lat + 0.00101]]
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat + 0.001, 'lng': lng, 'outline': tiny}, key=KEY), 422, 'bad_outline')
        big = [[lng, lat + 0.01], [lng + 0.003, lat + 0.01], [lng + 0.003, lat + 0.013], [lng, lat + 0.013]]
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat + 0.01, 'lng': lng, 'outline': big}, key=KEY), 422, 'bad_outline')
        house = [[lng + 0.0010, lat + 0.0010], [lng + 0.0011, lat + 0.0010], [lng + 0.0011, lat + 0.0011], [lng + 0.0010, lat + 0.0011]]
        st, c = s.call('POST', '/v1/codes', {'lat': lat + 0.00105, 'lng': lng + 0.00105, 'outline': house}, key=KEY)
        self.assertEqual(st, 201, c)
        self.assertEqual((c['profile']['structures'], c['profile']['class']), (1, 'residential'))
        self.assertAlmostEqual(c['profile']['floorAreaM2'], round(geo.ring_area(house), 1), places=1)
        shifted = [[x + 0.00002, y] for x, y in house]
        st, e = s.call('POST', '/v1/codes', {'lat': lat + 0.00105, 'lng': lng + 0.00125, 'outline': shifted}, key=KEY)
        self.assertError((st, e), 409, 'already_has_code')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng, 'of': 'CI-080104-001-1499-0'}, key=KEY), 404, 'unknown_code')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat + 0.001, 'lng': lng, 'of': r['machine']}, key=KEY), 422, 'too_far')
        self.assertError(s.call('POST', '/v1/codes', {'lat': 4.8, 'lng': -4.0}, key=KEY), 422, 'outside_country')
        self.assertError(s.call('POST', '/v1/codes', {'lat': 'x'}, key=KEY), 400, 'bad_point')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng, 'outline': 'square'}, key=KEY), 400, 'bad_outline')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng, 'outline': [[lng, lat], [lng, lat + 0.0001]]}, key=KEY),
                         400, 'bad_outline')
        self.assertError(s.call('POST', '/v1/codes', raw=b'{"lat": %r, "lng": %r, "outline": [[NaN, 1], [2, 3], [4, 5]]}' % (lat, lng),
                                key=KEY), 400, 'bad_outline')
        self.assertError(s.call('POST', '/v1/codes', raw=b'{not json', key=KEY), 400, 'bad_json')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng}), 401, 'unauthorized')
        self.assertError(s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng}, key='wrong'), 401, 'unauthorized')

    def test_border_decides(self):
        """The border decides: a point well across the national border is
        refused even though the nearest-area rule would give it an area; a
        point inside is issued; the 300 m tolerance holds against the
        simplified outline."""
        s, _ = self.fresh('border')
        o = s.svc.outline
        across, inside = (9.06, -2.70), (9.06, -2.80)   # the eastern border runs near -2.78 here
        self.assertIsNotNone(s.svc.reg.nearest_area(*across))
        self.assertGreater(o.outside_m(*across), 300)
        self.assertError(s.call('POST', '/v1/codes', {'lat': across[0], 'lng': across[1]}, key=KEY), 422, 'outside_country')
        self.assertError(s.call('GET', '/v1/at?lat=%f&lng=%f' % across), 422, 'outside_country')
        st, c = s.call('POST', '/v1/codes', {'lat': inside[0], 'lng': inside[1]}, key=KEY)
        self.assertEqual(st, 201, c)
        # walk east from inside to the simplified line, then measure along the parallel
        lng = inside[1]
        while o.outside_m(9.06, lng) == 0:
            lng += 0.00001
        out = lambda m: lng + m / (geo.M_LON_EQ * math.cos(math.radians(9.06)))
        self.assertLessEqual(o.outside_m(9.06, out(150)), 150.5)
        self.assertTrue(o.contains(9.06, out(150)))
        self.assertGreater(o.outside_m(9.06, out(400)), 300)
        self.assertError(s.call('POST', '/v1/codes', {'lat': 9.06, 'lng': out(400)}, key=KEY), 422, 'outside_country')
        # the simplification's deviation is taken off the 300 m, never added to it
        margin = o.border.margin_m
        self.assertGreaterEqual(margin, 50)
        for i in range(0, 600, 5):
            d = o.outside_m(9.06, out(i))
            self.assertEqual(o.contains(9.06, out(i)), d <= 300 - margin, (i, d))
        # an entrance cannot be moved across either: issued just within the
        # tolerance, then moved less than 80 m further out
        walk = lambda m: next(x for x in (out(i) for i in range(0, 2000)) if o.outside_m(9.06, x) >= m)
        at, to = walk(300 - margin - 10), walk(300 - margin + 5)
        self.assertLess(geo.dist_m(9.06, at, 9.06, to), 80)
        st, c = s.call('POST', '/v1/codes', {'lat': 9.06, 'lng': at}, key=KEY)
        self.assertEqual(st, 201, c)
        self.assertError(s.call('PATCH', '/v1/codes/' + c['machine'], {'entrance': {'lat': 9.06, 'lng': to}}, key=KEY),
                         422, 'outside_country')

    def test_daily_limit(self):
        s, _ = self.fresh('limit', per_day=2)
        base = self.rows[30]
        for i in range(2):
            st, c = s.call('POST', '/v1/codes', {'lat': float(base['entrance_lat']) + 0.0001 * (i + 1),
                                                 'lng': float(base['entrance_lng']), 'of': base['machine']}, key=KEY)
            self.assertEqual(st, 201, c)
        self.assertError(s.call('POST', '/v1/codes', {'lat': float(base['entrance_lat']) + 0.0004, 'lng': float(base['entrance_lng']),
                                                      'of': base['machine']}, key=KEY), 429, 'daily_limit')

    def test_change_status_and_entrance(self):
        s, _ = self.fresh('change')
        r = self.rows[40]
        m = r['machine']
        st, c = s.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'}, key=KEY)
        self.assertEqual((st, c['status']), (200, 'confirmed'))
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        st, c = s.call('PATCH', '/v1/codes/' + m, {'entrance': {'lat': lat + 0.0003, 'lng': lng}}, key=KEY)
        self.assertEqual((st, c['entrance']['kind']), (200, 'gate'))
        self.assertAlmostEqual(c['entrance']['lat'], lat + 0.0003, places=7)
        self.assertEqual(c['spot']['short'], s.svc.reg.spot_short(lat + 0.0003, lng))
        self.assertError(s.call('PATCH', '/v1/codes/' + m, {'entrance': {'lat': lat + 0.001, 'lng': lng}}, key=KEY), 422, 'too_far')
        self.assertError(s.call('PATCH', '/v1/codes/' + m, {'status': 'lost'}, key=KEY), 400, 'bad_status')
        self.assertError(s.call('PATCH', '/v1/codes/' + m, {}, key=KEY), 400, 'bad_body')
        st, c = s.call('PATCH', '/v1/codes/' + m, {'status': 'retired'}, key=KEY)
        self.assertEqual((st, c['status']), (200, 'retired'))
        self.assertError(s.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'}, key=KEY), 409, 'retired')
        self.assertError(s.call('GET', '/v1/find?q=' + urllib.request.quote(r['home'])), 410, 'retired')
        st, v = s.call('GET', '/v1/verify?code=' + m)
        self.assertEqual((v['issued'], v['valid'], v['status']), (True, False, 'retired'))
        self.assertError(s.call('PATCH', '/v1/codes/CI-080104-001-1499-0', {'status': 'confirmed'}, key=KEY), 404, 'unknown_code')
        self.assertError(s.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'}), 401, 'unauthorized')


if __name__ == '__main__':
    unittest.main()
