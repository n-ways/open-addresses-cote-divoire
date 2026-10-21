#!/usr/bin/env python3
"""Conformance vectors for every port of the engine: engine/reference/vectors.json.

Computed by the reference engine (engine/reference/ci_engine.py) on the committed model
(model/areas, frozen at first issue); a port (the N-Ways backend's internal/addressing/ci)
must reproduce them value for value.

  python3 tools/vectors.py
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402


def decode(m, text):
    try:
        r = E.parse(m, text)
        if r['form'] == 'official':
            return {'text': text, 'error': 'official'}
        mach = r.get('machine') or E.machine(r['unit'], r['index'], r['number'], r['key'])
        return {'text': text, 'machine': mach}
    except ValueError as e:
        return {'text': text, 'error': str(e)}


def main():
    rnd = random.Random(245)
    m = E.Model()
    areas = [a for u in sorted(m.areas) for a in m.areas[u]]
    words = sorted({a['plate'] for a in areas} | {a['name'].split(';')[0] for a in areas})
    tricky = ['Koffikro', 'Kofikro', 'Adjouffou', 'Adjoufou', 'Riviéra II', 'Riviera 2', 'RIVIERA-2', 'Les Lauriers', 'Lauriers',
              'Kouassikro', 'Kwassikro', 'Cocody', 'Kokody', 'PK 18', 'Kilomètre 18', "N'Guessankro", 'N’Guéssankro', 'Saint-Michel',
              'St Michel', 'Cœur de Ville', 'Quartier Résidentiel', 'Yopougon Sicogi', 'Abobo-Baoulé', 'II Plateaux', 'Deux Plateaux']
    keys = [[w, E.name_key(w)] for w in tricky + rnd.sample(words, 600)]
    forms, found = [], []
    for a in rnd.sample(areas, 500):
        key = m.key_of(a['unit'], a['index'])
        lo, hi = m.block(a['unit'], a['index'])
        n = rnd.randint(lo, hi)
        unit = m.units[a['unit']]['name']
        chk = E.check_digit(key, n)
        forms.append({'zone': '%s-%s' % (a['unit'], a['index']), 'number': n, 'check': chk, 'home': '%s %d' % (a['plate'], n),
                      'remembered': E.remembered(a['plate'], n), 'written': E.written(a['plate'], n, key, unit),
                      'machine': E.machine(a['unit'], a['index'], n, key)})
        for text in ('%s %d' % (a['plate'], n), E.remembered(a['plate'], n), E.written(a['plate'], n, key, unit),
                     '%s %d, %s' % (a['plate'], n, unit), E.machine(a['unit'], a['index'], n, key)):
            found.append(decode(m, text))
    off = [a for a in areas if E.name_key(a['name']) != m.key_of(a['unit'], a['index'])]
    for a in rnd.sample(off, min(120, len(off))):
        n = m.block(a['unit'], a['index'])[0] + 1
        found.append(decode(m, '%s %d' % (a['name'].split(';')[0], n)))
    for a in rnd.sample(areas, 60):
        key = m.key_of(a['unit'], a['index'])
        n = m.block(a['unit'], a['index'])[0] + 3
        found.append(decode(m, '%s %d-%d' % (a['plate'], n, (E.check_digit(key, n) + 1) % 10)))
        found.append(decode(m, '%s %d, Nulle Part' % (a['plate'], n)))
        found.append(decode(m, 'CI-%s-%s-%d-%d' % (a['unit'], a['index'], n, (E.check_digit(key, n) + 1) % 10)))
    found.append(decode(m, 'Nulle Part 1234'))
    # Two readings of one text (SPEC.md 9): the plate name wins over an official name typed
    # instead of it, a commune decides, the "·" fixes the split.
    for text in ('Air France 1 10 00 (Korhogo)', 'Air France 1 10 00', 'Air France 1 · 10 00', 'Air France · 1 10 00',
                 'Air France I 10 00 (Bouaké)', 'Air France 1 10 00, Bouaké', 'Air France 1 10 00 (Man)',
                 'Air France 2 21 00', 'Air France 2 21 00 (Man)', 'Ahougnansou 1 23 45', 'Ahougnansou 1 23 45 (Bouaké)'):
        found.append(decode(m, text))
    spots = []
    for _ in range(400):
        lat, lng = rnd.uniform(4.4, 10.7), rnd.uniform(-8.5, -2.6)
        sp = E.spot(m, lat, lng)
        rec = None
        if sp['short'] != sp['plusCode']:
            rec = E.decode_spot(m, sp['short'])['plusCode']
        d = E.olc_decode(sp['plusCode'])
        spots.append({'lat': lat, 'lng': lng, 'full': sp['plusCode'], 'short': sp['short'], 'recovered': rec, 'decoded': [d.lat, d.lng]})
    # Reference towns two units share are written with their département (SPEC.md 7);
    # the bare town decodes only when one reading is possible.
    towns = []
    trnd = random.Random(7)
    for u in sorted(c for c, (name, _, _) in m.refs.items() if ' (' in name):
        name, rlat, rlon = m.refs[u]
        for _ in range(6):
            sp = E.spot(m, rlat + trnd.uniform(-0.2, 0.2), rlon + trnd.uniform(-0.2, 0.2))
            code = sp['short'].split(' ')[0]
            for text in (sp['short'], code + ' ' + name.split(' (')[0]):
                try:
                    towns.append({'text': text, 'full': E.decode_spot(m, text)['plusCode']})
                except ValueError as e:
                    towns.append({'text': text, 'error': str(e)})
    frame = (-3.99, 5.34, -3.98, 5.35)
    comps = [{'key': 'c%02d' % k, 'cx': frame[0] + rnd.uniform(0, 0.01), 'cy': frame[1] + rnd.uniform(0, 0.01)} for k in range(37)]
    E.number_compounds(comps, frame, (4400, 4499))
    reg = {'compounds': [{'h': c['h'], 'number': c['number']} for c in comps], 'range': [4400, 4499], 'tailReserve': [4466, 4499]}
    inserts = []
    for _ in range(60):
        lon, lat = frame[0] + rnd.uniform(-0.001, 0.011), frame[1] + rnd.uniform(-0.001, 0.011)
        try:
            n = E.provisional_number(reg, frame, lon, lat)
        except ValueError:
            n = None
        inserts.append({'lat': lat, 'lon': lon, 'number': n})
        if n is not None:
            reg['compounds'].append({'h': E.frame_hilbert(frame, lon, lat), 'number': n})
    blocks = []
    for a in rnd.sample(areas, 80):
        key = m.key_of(a['unit'], a['index'])
        c = rnd.choice([1, 40, 120, 900, 4000])
        b = E.next_block(m, key, c)
        blocks.append({'zone': '%s-%s' % (a['unit'], a['index']), 'compounds': c, 'block': list(b) if b else None})
    hil = [[x, y, E.hilbert_index(x, y)] for x, y in ((0, 0), (1, 0), (65535, 65535), (12345, 54321), (40000, 2))]
    out = {'note': 'Computed by engine/reference/ci_engine.py on the frozen register; every port must match.',
           'nameKeys': keys, 'forms': forms, 'found': found, 'spots': spots, 'spotTowns': towns,
           'numbering': {'frame': frame, 'lo': 4400, 'hi': 4499,
                         'compounds': [{'id': c['key'], 'lat': c['cy'], 'lon': c['cx']} for c in comps],
                         'numbers': {c['key']: c['number'] for c in comps}, 'inserts': inserts},
           'nextBlocks': blocks, 'hilbert': hil,
           'blockSizes': [[n, E.block_size(n)] for n in (0, 1, 49, 50, 51, 99, 100, 4500, 22000)],
           'pairs': [[n, E.spoken_number(n)] for n in (1000, 4817, 48217, 10000, 99999)]}
    json.dump(out, open(os.path.join(REPO, 'engine', 'reference', 'vectors.json'), 'w'), ensure_ascii=False, indent=0)
    print(len(keys), 'name keys,', len(forms), 'forms,', len(found), 'decodings,', len(spots), 'spots,', len(inserts), 'inserts,', len(blocks), 'blocks')


if __name__ == '__main__':
    main()
