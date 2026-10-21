#!/usr/bin/env python3
"""Build the interim code-area tables for Côte d'Ivoire (stdlib only).

Inputs (in this repo):
  model/units/sous-prefectures.geojson   509/510 sous-préfectures (CNTIG/OCHA via HDX, CC BY-IGO)
  model/areas/osm-places.csv             named place points from OpenStreetMap (ODbL)
  model/units/abidjan-communes.geojson   the 10 historical communes of Abidjan (OSM admin_level 8)
Outputs:
  model/areas/admin-units.csv   every unit that can head a machine code: SPs + Abidjan communes, 6-digit code
  model/areas/areas.csv         one code area per named place: unit code, 3-digit index, name, kind, point
  model/areas/references.csv    the reference point (chef-lieu) per unit, used for short Plus Codes

The 6-digit unit code is the OCHA/CNTIG pcode digits (CI010101 -> 010101) for a
sous-préfecture. The 10 communes inside the Abidjan sous-préfecture get interim
codes 010111-010120 (alphabetical), outside the pcode range, until the official
PADA codification (département + commune/sous-préfecture) is published.
Area index: rank of the place inside its unit, north to south then west to east,
frozen when first issued (this file is the frozen list).

  python3 tools/build_areas.py
"""
import collections, csv, json, os, re, sys, unicodedata
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(HERE, 'model')
KINDS = {'city', 'town', 'village', 'hamlet', 'suburb', 'quarter', 'neighbourhood', 'locality'}


def polys(g):
    return [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']


def inside(x, y, ps):
    for P in ps:
        ins = False
        for ring in P:
            j = len(ring) - 1
            for i in range(len(ring)):
                xi, yi = ring[i][0], ring[i][1]
                xj, yj = ring[j][0], ring[j][1]
                if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    ins = not ins
                j = i
        if ins:
            return True
    return False


def box(ps):
    xs = [c[0] for P in ps for c in P[0]]
    ys = [c[1] for P in ps for c in P[0]]
    return min(xs), min(ys), max(xs), max(ys)


def load_units():
    units = []
    for f in json.load(open(os.path.join(M, 'units', 'sous-prefectures.geojson')))['features']:
        p = f['properties']
        ps = polys(f['geometry'])
        units.append({'code': p['pcode'][2:], 'name': p['name'], 'kind': 'sous-prefecture',
                      'departement': p['departement'], 'region': p['region'], 'polys': ps, 'box': box(ps)})
    com = json.load(open(os.path.join(M, 'units', 'abidjan-communes.geojson')))['features']
    com.sort(key=lambda f: f['properties']['name'])
    for n, f in enumerate(com):
        ps = polys(f['geometry'])
        units.append({'code': '0101%02d' % (11 + n), 'name': f['properties']['name'], 'kind': 'commune-abidjan',
                      'departement': 'Abidjan', 'region': 'Abidjan', 'polys': ps, 'box': box(ps)})
    return units


def unit_of(x, y, units):
    # Abidjan communes first (they sit inside the Abidjan sous-préfecture).
    for u in sorted(units, key=lambda u: u['kind'] != 'commune-abidjan'):
        b = u['box']
        if b[0] <= x <= b[2] and b[1] <= y <= b[3] and inside(x, y, u['polys']):
            return u
    return None


def main():
    units = load_units()
    places = [r for r in csv.DictReader(open(os.path.join(M, 'areas', 'osm-places.csv'))) if r['place'] in KINDS]
    per = {}
    for r in places:
        x, y = float(r['lon']), float(r['lat'])
        u = unit_of(x, y, units)
        # The 'Abidjan' city node sits in Le Plateau: a whole-city name is no code-area name.
        if u and u['kind'] == 'commune-abidjan' and r['place'] == 'city':
            continue
        if u:
            per.setdefault(u['code'], []).append((r['name'], r['place'], x, y))
    with open(os.path.join(M, 'areas', 'areas.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['unit', 'index', 'name', 'place', 'lon', 'lat', 'digits'])
        for code in sorted(per):
            ps = sorted(set(per[code]), key=lambda p: (-round(p[3], 5), round(p[2], 5), p[0]))
            if len(ps) > 999:
                sys.exit(f'{code}: {len(ps)} places, more than 999 areas')
            for i, (n, k, x, y) in enumerate(ps, 1):
                w.writerow([code, '%03d' % i, n, k, x, y, 4])
    with open(os.path.join(M, 'areas', 'admin-units.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['code', 'name', 'kind', 'departement', 'region', 'x0', 'y0', 'x1', 'y1', 'areas'])
        for u in sorted(units, key=lambda u: u['code']):
            w.writerow([u['code'], u['name'], u['kind'], u['departement'], u['region'], *[round(v, 5) for v in u['box']], len(set(per.get(u['code'], [])))])
    # Reference point: the place of the unit's own name (city/town/village), else the unit box centre.
    # A short Plus Code is written with the reference town's name, so a name that two units'
    # towns share (accents, case and punctuation aside) is written with the town's département
    # in brackets, as the country tells such places apart: "Lolobo (Béoumi)" (engine/SPEC.md 7).
    refs = []
    for u in sorted(units, key=lambda u: u['code']):
        cands = [p for p in per.get(u['code'], []) if p[0].lower() == u['name'].lower()]
        cands.sort(key=lambda p: ['city', 'town', 'village', 'suburb', 'quarter', 'neighbourhood', 'hamlet', 'locality'].index(p[1]))
        if cands:
            refs.append([u['code'], u['name'], cands[0][2], cands[0][3], 'osm-place:' + cands[0][1]])
        else:
            b = u['box']
            refs.append([u['code'], u['name'], round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6), 'box-centre'])
    fold = lambda s: re.sub(r'[^a-z0-9]', '', ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c)))
    shared = collections.Counter(fold(r[1]) for r in refs)
    dep = {u['code']: u['departement'] for u in units}
    with open(os.path.join(M, 'areas', 'references.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['unit', 'name', 'lon', 'lat', 'how'])
        for r in refs:
            if shared[fold(r[1])] > 1:
                r[1] = '%s (%s)' % (r[1], dep[r[0]])
            w.writerow(r)
    print(len(units), 'units,', sum(len(set(v)) for v in per.values()), 'areas')


if __name__ == '__main__':
    main()
