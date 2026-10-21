#!/usr/bin/env python3
"""The small inputs of Côte d'Ivoire's registry build, in a work folder.

Reads, read-only, the osmium exports of N-Ways' Côte d'Ivoire extract (tools/README.md:
admin, bar and place .geojsonseq in the work folder), N-Ways' routing compounds and
gates (data/valhalla), N-Ways places (the database) and this repo's units
(model/units), and writes:

  enclosures.geojson  closed walls, fences, hedges and retaining walls (40-6,000 m2): every
                      structure inside one is one compound (engine/SPEC.md 5, rule 2)
  estates.geojson     closed enclosures over 6,000 m2 and N-Ways' estate, government,
                      military and police compounds: parents, whose compounds keep their
                      own codes
  gates.csv           OpenStreetMap barrier=gate/entrance points, N-Ways gates
  places.csv          N-Ways places (POIs) in Côte d'Ivoire
  units.geojson       the 520 units (the 10 Abidjan communes first, then the 510
                      sous-préfectures), with their 6-digit codes (model/areas/admin-units.csv)
  country.geojson     the national boundary (admin_level 2): a footprint outside it is
                      in a neighbouring country and gets no code

Every id is stable: osm:<type>/<id>, nways:<id>.

  python3 tools/prepare-inputs.py <work folder>
"""
import csv, json, math, os, subprocess, sys, unicodedata

ROOT = os.environ.get('NWAYS_ROOT', '.')   # the N-Ways data folder (data/osm, data/valhalla)
DB = os.environ.get('NWAYS_DB', '')        # the N-Ways database (places), a libpq connection string
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
M = lambda f: os.path.join(REPO, 'model', f)
BOX = (-8.70, 4.10, -2.40, 10.80)
ENCL_MAX = 6000


def seq(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


def oid(p):
    return f"osm:{p.get('@type', 'way')}/{p.get('@id')}"


def ring_area(ring):
    """Area of a lon/lat ring in m2 (local equirectangular)."""
    k = math.cos(math.radians(ring[0][1])) * 111320.0
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * k, ring[i][1] * 110574.0
        x2, y2 = ring[i + 1][0] * k, ring[i + 1][1] * 110574.0
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    if g['type'] == 'MultiPolygon':
        return g['coordinates']
    if g['type'] == 'LineString' and len(g['coordinates']) >= 4 and g['coordinates'][0] == g['coordinates'][-1]:
        return [[g['coordinates']]]
    return []


def poly_area(ps):
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in ps)


def in_box(x, y):
    return BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().replace('-', ' ').strip()


# ---------------------------------------------------------------- enclosures and estates
feats, est, seen = [], [], set()
for o in seq(W('bar.geojsonseq')):
    p, g = o['properties'], o['geometry']
    kind = p.get('barrier') if p.get('barrier') in ('wall', 'fence', 'hedge', 'retaining_wall') else None
    ps = polys(g)
    if not kind or not ps:
        continue
    i = oid(p)
    if i in seen:          # osmium writes a closed way twice (line and area)
        continue
    seen.add(i)
    a = poly_area(ps)
    if 40 <= a <= ENCL_MAX:
        feats.append({'type': 'Feature', 'properties': {'eid': i, 'kind': 'osm-' + kind, 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
    elif ENCL_MAX < a <= 2_000_000:
        est.append({'type': 'Feature', 'properties': {'estate': i, 'kind': 'walled', 'name': ''},
                    'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(W('enclosures.geojson'), 'w'))
for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'compounds.geojsonseq')):
    p, g = o['properties'], o['geometry']
    ps = polys(g)
    if not ps or not in_box(*ps[0][0][0]) or p['kind'] not in ('estate', 'government', 'military', 'police'):
        continue
    est.append({'type': 'Feature', 'properties': {'estate': 'nways:' + str(p['id']), 'kind': p['kind'], 'name': p.get('name') or ''},
                'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': est}, open(W('estates.geojson'), 'w'))

# ---------------------------------------------------------------- gates
with open(W('gates.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['gid', 'src', 'barrier', 'lon', 'lat'])
    for o in seq(W('bar.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and (p.get('barrier') in ('gate', 'lift_gate', 'sliding_gate', 'swing_gate', 'entrance') or p.get('entrance')):
            w.writerow([oid(p), 'osm', p.get('barrier') or 'entrance', *g['coordinates']])
    for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'gates.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and in_box(*g['coordinates']):
            w.writerow(['nways:' + str(p.get('id')), 'nways', p.get('barrier') or p.get('kind') or 'gate', *g['coordinates']])

# ---------------------------------------------------------------- N-Ways places (POIs)
with open(W('places.csv'), 'w') as f:
    subprocess.run(['psql', DB, '-Atc', """COPY (SELECT p.id, p.name, p.category, p.source, ST_X(p.location::geometry) lon, ST_Y(p.location::geometry) lat
        FROM places p JOIN regions r ON ST_Intersects(r.geom, p.location::geometry) WHERE r.country='CI' ORDER BY p.id) TO STDOUT WITH CSV HEADER"""],
                   stdout=f, check=True)

# ---------------------------------------------------------------- units
codes = {}
for r in csv.DictReader(open(M('areas/admin-units.csv'), encoding='utf-8')):
    codes[(r['kind'] == 'commune-abidjan', fold(r['name']))] = r['code']
units = []
for fe in json.load(open(M('units/abidjan-communes.geojson'), encoding='utf-8'))['features']:
    units.append({'type': 'Feature', 'properties': {'unit': codes[(True, fold(fe['properties']['name']))], 'name': fe['properties']['name'], 'rank': 0},
                  'geometry': fe['geometry']})
for fe in json.load(open(M('units/sous-prefectures.geojson'), encoding='utf-8'))['features']:
    u = fe['properties']['pcode'][2:]
    units.append({'type': 'Feature', 'properties': {'unit': u, 'name': fe['properties']['name'], 'rank': 1}, 'geometry': fe['geometry']})
json.dump({'type': 'FeatureCollection', 'features': units}, open(W('units.geojson'), 'w'), ensure_ascii=False)
known = {r['code'] for r in csv.DictReader(open(M('areas/admin-units.csv'), encoding='utf-8'))}
missing = [f['properties']['unit'] for f in units if f['properties']['unit'] not in known]
assert not missing, missing

for o in seq(W('admin.geojsonseq')):
    if o['properties'].get('admin_level') == '2' and o['properties'].get('ISO3166-1') in ('CI', None) and 'Ivoire' in (o['properties'].get('name:fr') or o['properties'].get('name') or ''):
        json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': "Côte d'Ivoire"}, 'geometry': o['geometry']}]},
                  open(W('country.geojson'), 'w'))
        break
else:
    sys.exit('no admin_level 2 boundary for Côte d\'Ivoire in admin.geojsonseq')
print(len(feats), 'enclosures,', len(est), 'estates,', len(units), 'units')
