#!/usr/bin/env python3
"""The compounds of Côte d'Ivoire for issuing their codes (engine/SPEC.md 5, 6).

Reads <work>/buildings.csv (tools/sort-buildings.py, sorted by code area) one area at a time.

  python3 tools/issue_registry.py group <work>     compounds and profiles: <work>/compounds.jsonl.gz,
                                                    <work>/area-counts.json, <work>/group-stats.json
  python3 tools/build-register.py <work> --freeze  plate names, national ranges, blocks, frames
  python3 tools/issue_registry.py number <work> <lotes.jsonl.gz>
                                                    numbers every area's compounds inside its block
                                                    and writes the issue batches (lotes), unit by unit, for the
                                                    N-Ways issuer (the backend's
                                                    `homecodes issue -country CI`), which numbers them
                                                    again and refuses any difference

The border decides (engine/SPEC.md 5, step 1): `number` drops every compound whose reference point
lies more than 300 m outside the national border (<work>/country.geojson, OpenStreetMap
admin_level 2, unsimplified) before numbering, so no lote ever codes a building in a neighbouring
country; the zones (sous-préfectures, communes) never decide. The count dropped is printed
(acrossBorder) and is 0 for the published registry, since step 3 keeps only footprints whose centre
is inside.

Grouping: ci_engine.group_footprints (SPEC 5: enclosure, annex, single). Numbering:
ci_engine.number_compounds over the area's frozen frame and block (SPEC 5, steps 8 and 9).

Each lote line: {"key": the main structure's stable id, "muni": unit ("010114"), "zone": area
("010114-083"), "areaId", "nameId", "number", "lat", "lon" (the compound's reference point,
SPEC 5 step 7), "anchor", "anchorKind", "gate", "coverage": "nways", "official": null, "estate",
"rule", "dens", "label": the unit, "structures": [...]} (largest first). Structure ids:
OpenStreetMap "osm:way/<id>"; a Google/Microsoft footprint "nw:" + the first 12 hex characters
of the SHA-1 of its centre to 1e-6 degrees and its area to 1 m2.
"""
import collections, csv, gzip, hashlib, json, os, re, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402
import border  # noqa: E402

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made', 'government', 'craft',
        'building:levels', 'height', 'name', 'roof:material', 'building:material']
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def structure_id(r):
    if r['src'] == 'osm':
        return 'osm:' + r['oid']
    return 'nw:' + hashlib.sha1(f"{float(r['lat']):.6f},{float(r['lon']):.6f},{round(float(r['area']))}".encode()).hexdigest()[:12]


def ring_of(wkt):
    """The outer ring of a footprint's first polygon, as (lon, lat) pairs, closing point dropped."""
    s = wkt[wkt.index('('):]
    first = s.lstrip('(').split(')')[0]
    nums = [float(x) for x in NUM.findall(first)]
    pts = list(zip(nums[0::2], nums[1::2]))
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def areas_of(path):
    cur, rows = None, []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['aid'] != cur:
                if rows:
                    yield cur, rows
                cur, rows = r['aid'], []
            rows.append(r)
    if rows:
        yield cur, rows


def height(r):
    try:
        return float(r['height'].replace('m', '').strip()) if r['height'] else None
    except ValueError:
        return None


def profile(r):
    """The reference profile (ci_engine.profile, SPEC 6) of one footprint row."""
    p = E.profile({'btag': r['building'] or None, 'cats': r['poi'] or None, 'landuse': None, 'area': float(r['area']),
                   'perim': float(r['perim']) if r['perim'] else None, 'levels': r['building:levels'] or None,
                   'h': height(r), 'src': r['src']})
    if r['amenity'] or r['shop'] or r['office'] or r['government'] or r['tourism'] or r['healthcare']:
        tag = ('health' if r['amenity'] in ('hospital', 'clinic', 'doctors', 'pharmacy') or r['healthcare'] else
               'education' if r['amenity'] in ('school', 'kindergarten', 'college', 'university') else
               'religious' if r['amenity'] == 'place_of_worship' else
               'government' if r['government'] or r['amenity'] in ('townhall', 'courthouse', 'police', 'post_office') else
               'hospitality' if r['tourism'] in ('hotel', 'guest_house', 'hostel', 'motel') else
               'office' if r['office'] else 'commercial')
        if p['useConfidence'] < 0.75 or p['useClass'] == 'residential':
            p.update(useClass='mixed' if p['useClass'] == 'residential' and p['useSource'] == 'osm:building' else tag,
                     useConfidence=0.75, useSource='osm:tag')
    return p


def cmd_group(work):
    counts, stats, seen = {}, collections.Counter(), set()
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'wt', encoding='utf-8') as out:
        for aid, rows in areas_of(os.path.join(work, 'buildings.csv')):
            fs = []
            for r in rows:
                fs.append({'id': structure_id(r), 'ring': ring_of(r['wkt']), 'area': float(r['area']), 'eid': r['eid'] or None,
                           'lat': float(r['lat']), 'lon': float(r['lon']), 'row': r})
            n = 0
            for ms, rule in E.group_footprints(fs):
                sts = []
                for i in ms:
                    f, r = fs[i], fs[i]['row']
                    p = profile(r)
                    sts.append({'id': f['id'], 'src': r['src'], 'lat': round(f['lat'], 7), 'lon': round(f['lon'], 7),
                                'areaM2': round(f['area'], 1), 'perimeterM': round(float(r['perim'] or 0), 1),
                                'tags': {t: r[t] for t in TAGS if r.get(t)}, 'places': [x for x in (r['poi'] or '').split('|') if x],
                                'class': p['useClass'], 'confidence': p['useConfidence'], 'classSource': p['useSource'],
                                'floors': p['floors'], 'floorsSource': p['floorsSource'], 'wkt': r['wkt']})
                key = sts[0]['id']
                if key in seen:
                    stats['duplicateKey'] += 1
                    continue
                seen.add(key)
                lat, lon = E.reference_point(fs, ms)
                main = fs[ms[0]]['row']
                rec = {'key': key, 'aid': aid, 'lat': round(lat, 7), 'lon': round(lon, 7), 'rule': rule,
                       'enclosed': rule == 'enclosure', 'estate': main['estate'] or None, 'dens': int(main['dens'] or 0),
                       'label': main['unit'] or aid[:6], 'structures': sts}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                n += 1
                stats['rule:' + rule] += 1
                stats['structures'] += len(sts)
                stats[f'size:{min(len(sts), 7)}'] += 1
            counts[aid] = n
            stats['compounds'] += n
    json.dump(counts, open(os.path.join(work, 'area-counts.json'), 'w'))
    json.dump(dict(stats), open(os.path.join(work, 'group-stats.json'), 'w'), indent=1)
    print(json.dumps(dict(stats)))


def cmd_number(work, out_path):
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    area = {a['aid']: a for a in reg['areas']}
    counts = collections.Counter()
    by_area = collections.defaultdict(list)
    cur_unit = None
    national = border.Border(os.path.join(work, 'country.geojson'))

    def flush(out):
        for aid in sorted(by_area):
            a = area[aid]
            cs = [{'key': c['key'], 'cx': c['lon'], 'cy': c['lat'], 'c': c} for c in by_area[aid]]
            E.number_compounds(cs, tuple(a['frame']), tuple(a['blocks'][0]))
            for x in cs:
                c = x['c']
                rec = {'key': c['key'], 'muni': aid[:6], 'zone': aid, 'areaId': a['id'], 'nameId': a['family'],
                       'number': x['number'], 'lat': c['lat'], 'lon': c['lon'], 'anchor': [c['lat'], c['lon']], 'anchorKind': 'centre',
                       'gate': None, 'coverage': 'nways', 'official': None, 'enclosed': c['enclosed'], 'estate': c['estate'],
                       'rule': c['rule'], 'dens': c['dens'], 'label': c['label'], 'structures': c['structures']}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['compounds'] += 1
                counts[f'digits:{len(str(rec["number"]))}'] += 1
        by_area.clear()

    # compounds.jsonl.gz is written area by area in area order, so units arrive one after another
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f, gzip.open(out_path, 'wt', encoding='utf-8') as out:
        for row in f:
            c = json.loads(row)
            if national.outside_m(c['lat'], c['lon']) > border.BORDER_M:
                counts['acrossBorder'] += 1
                continue
            if c['aid'][:6] != cur_unit:
                flush(out)
                cur_unit = c['aid'][:6]
            by_area[c['aid']].append(c)
        flush(out)
    print(json.dumps(counts))


if __name__ == '__main__':
    if sys.argv[1] == 'group':
        cmd_group(os.path.abspath(sys.argv[2]))
    elif sys.argv[1] == 'number':
        cmd_number(os.path.abspath(sys.argv[2]), sys.argv[3])
