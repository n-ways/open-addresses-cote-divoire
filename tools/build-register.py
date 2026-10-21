#!/usr/bin/env python3
"""The frozen register of Côte d'Ivoire's code areas, at first issue (engine/SPEC.md 4).

  python3 tools/build-register.py <work> [--freeze]

1. tools/name_ranges.py --counts <work>/area-counts.json: plate names, national ranges and
   blocks sized on the real compounds of every area (tools/issue_registry.py group).
2. Every area's frame: the box of its compounds' reference points, widened by 0.0005 degrees
   (ci_engine.area_frame); an area with no compound yet takes the box around its place point.
3. Writes engine/data/register.json (what the engines load: units, names and their blocks,
   areas, aliases, reference towns) and model/stats/register.json (the counts in the papers).
   With --freeze the register is marked frozen: from then on blocks and frames never move
   (SPEC 4.2 step 5), and a new area or a full block takes the next block of its name.
"""
import collections, csv, datetime, gzip, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402

work = os.path.abspath(sys.argv[1])
freeze = '--freeze' in sys.argv
M = lambda *p: os.path.join(REPO, 'model', *p)
rows = lambda p: list(csv.DictReader(open(p, encoding='utf-8')))

subprocess.run([sys.executable, os.path.join(HERE, 'name_ranges.py'), '--counts', os.path.join(work, 'area-counts.json')],
               check=True, stdout=subprocess.DEVNULL)

counts = json.load(open(os.path.join(work, 'area-counts.json')))
box = {}
LINE = re.compile(r'"aid":"([0-9-]+)","lat":(-?[0-9.]+),"lon":(-?[0-9.]+)')
with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        m = LINE.search(line, 0, 200)
        aid, lat, lon = m.group(1), float(m.group(2)), float(m.group(3))
        b = box.get(aid)
        box[aid] = (min(b[0], lat), min(b[1], lon), max(b[2], lat), max(b[3], lon)) if b else (lat, lon, lat, lon)

units = {r['code']: r for r in rows(M('areas', 'admin-units.csv'))}
refs = {r['unit']: r for r in rows(M('areas', 'references.csv'))}
blocks = {(r['unit'], r['index']): r for r in rows(M('areas', 'name-blocks.csv'))}
areas_csv = rows(M('areas', 'areas.csv'))
keys = sorted({r['key'] for r in blocks.values()})
family = {k: i + 1 for i, k in enumerate(keys)}

areas, by_key = [], collections.defaultdict(list)
for i, r in enumerate(sorted(areas_csv, key=lambda r: (r['unit'], r['index']))):
    b = blocks[(r['unit'], r['index'])]
    aid = '%s-%s' % (r['unit'], r['index'])
    lat, lon = float(r['lat']), float(r['lon'])
    bx = box.get(aid)
    frame = E.area_frame([(bx[0], bx[1]), (bx[2], bx[3])] if bx else [(lat, lon)])
    a = {'id': i + 1, 'aid': aid, 'unit': r['unit'], 'index': r['index'], 'plate': b['name'], 'official': r['name'].split(';')[0].strip(),
         'key': b['key'], 'family': family[b['key']], 'digits': int(b['digits']), 'blocks': [[int(b['block_lo']), int(b['block_hi'])]],
         'frame': list(frame), 'lat': lat, 'lon': lon, 'compounds': counts.get(aid, 0), 'qualifier': b['qualifier'] or '',
         'needsCouncilChoice': r['needsCouncilChoice'] == '1',
         'plateCandidates': [c for c in r['plateCandidates'].split('|') if c] if r['needsCouncilChoice'] == '1' else []}
    areas.append(a)
    by_key[b['key']].append(a)

names = []
for k in keys:
    ar = sorted(by_key[k], key=lambda a: a['blocks'][0][0])
    names.append({'id': family[k], 'key': k, 'plate': ar[0]['plate'], 'digits': ar[0]['digits'],
                  'blocks': [[a['blocks'][0][0], a['blocks'][0][1], a['id']] for a in ar]})
aid_id = {a['aid']: a['id'] for a in areas}
aliases = [{'key': r['alias_key'], 'official': r['official'], 'plateKey': r['plate_key'], 'areas': [aid_id[x] for x in r['areas'].split()]}
           for r in rows(M('areas', 'plate-aliases.csv')) if r['status'] == 'kept']
reg = {
    'about': "N-Ways addressing for Côte d'Ivoire: the frozen register of code areas (engine/SPEC.md 4). Built by tools/build-register.py.",
    'frozen': freeze, 'builtAt': datetime.date.today().isoformat(),
    'units': [{'code': u['code'], 'name': u['name'], 'kind': u['kind'], 'departement': u['departement'], 'region': u['region'],
               'ref': refs[u['code']]['name'] if u['code'] in refs else u['name'],
               'refLat': float(refs[u['code']]['lat']) if u['code'] in refs else None,
               'refLon': float(refs[u['code']]['lon']) if u['code'] in refs else None} for u in sorted(units.values(), key=lambda u: u['code'])],
    'names': names, 'areas': areas, 'aliases': aliases,
}
os.makedirs(os.path.join(REPO, 'engine', 'data'), exist_ok=True)
json.dump(reg, open(os.path.join(REPO, 'engine', 'data', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

dig = collections.Counter()
for a in areas:
    dig[a['digits']] += a['compounds']
stats = {
    'areas': len(areas), 'areasWithCompounds': sum(1 for a in areas if a['compounds']), 'compounds': sum(a['compounds'] for a in areas),
    'nameKeys': len(names), 'sharedNames': sum(1 for n in names if len(n['blocks']) > 1),
    'areasInSharedNames': sum(len(n['blocks']) for n in names if len(n['blocks']) > 1),
    'namesByDigits': dict(sorted(collections.Counter(n['digits'] for n in names).items())),
    'compoundsByDigits': dict(sorted(dig.items())),
    'largestArea': max(({'aid': a['aid'], 'plate': a['plate'], 'compounds': a['compounds']} for a in areas), key=lambda x: x['compounds']),
    'needsCouncilChoice': sum(1 for a in areas if a['needsCouncilChoice']),
    'qualified': sorted({a['plate'] for a in areas if a['qualifier']}),
    'aliases': len(aliases),
}
json.dump(stats, open(M('stats', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False))
