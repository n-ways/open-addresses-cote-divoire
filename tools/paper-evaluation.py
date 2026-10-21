#!/usr/bin/env python3
"""The measured properties of the paper's evaluation chapter: model/stats/evaluation.json.

  python3 tools/paper-evaluation.py            # reads registry/ and engine/data/register.json

Reads every published code once (standard library only, one zone file at a time) and checks:

  conformance   every row against the reference engine: the number lies in its area's
                blocks, the check digit is Damm's over the name key and the number, the
                remembered and written forms and the Plus Code are what the engine writes
  uniqueness    machine forms, and the remembered form (name key, number) nationally
  lengths       digits of the numbers, characters of the remembered form
  decoding      a fixed random sample (seed 2026): remembered, written and machine forms
                parsed back to the same code; short Plus Codes recovered to the entrance
                (the codes written against a town that carries its département, because
                another unit's reference town has the same name, are counted; every
                issued code in every form is decoded by tools/check-decoding.py)
  slips         for the same sample, every single-digit substitution and every swap of two
                neighbouring digits of the number: how many would land on another issued
                home of the same name, how many fall outside every block, and how many the
                check digit of the machine form catches
  orders        the distance on the ground between consecutive numbers of each area, for the
                issued Hilbert order and for two alternatives on the same compounds: the
                Z-order (Morton) curve on the same grid and serpentine rows 100 m high
  ranges        the counterfactual of numbering each area on its own from 1000: how many
                remembered forms would then name more than one home
"""
import collections, csv, gzip, json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402

SAMPLE = 100000
SEED = 2026


def metres(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 110574.0, (lon2 - lon1) * 111320.0 * k)


def morton(x, y, order=16):
    z = 0
    for i in range(order):
        z |= ((x >> i) & 1) << (2 * i) | ((y >> i) & 1) << (2 * i + 1)
    return z


def order_gaps(zone_pts, areas, gaps):
    """Distances between consecutive compounds of each area under three orders."""
    for zone, pts in zone_pts.items():
        if len(pts) < 2:
            continue
        x0, y0, x1, y1 = areas[zone]['frame']
        n = (1 << 16) - 1

        def cell(p):
            return (int(max(0, min(n, (p[2] - x0) / (x1 - x0) * n))), int(max(0, min(n, (p[1] - y0) / (y1 - y0) * n))))
        k = math.cos(math.radians((y0 + y1) / 2))

        def rows(p):
            band = int((y1 - p[1]) * 110574.0 // 100)
            x = (p[2] - x0) * 111320.0 * k
            return (band, x if band % 2 == 0 else -x)
        orders = {
            'hilbert': sorted(pts),
            'morton': sorted(pts, key=lambda p: morton(*cell(p))),
            'rows': sorted(pts, key=rows),
        }
        for name, seq in orders.items():
            for a, b in zip(seq, seq[1:]):
                gaps[name].append(metres(a[1], a[2], b[1], b[2]))


def main():
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    areas = {a['aid']: a for a in reg['areas']}
    manifest = json.load(open(os.path.join(REPO, 'registry', 'MANIFEST.json'), encoding='utf-8'))
    model = E.Model()
    units = {u['code']: u for u in reg['units']}

    labelled = {E._fold(n) for n, _, _ in model.refs.values() if ' (' in n}
    shared_ref = 0
    total = 0
    bad = collections.Counter()
    issued = set()          # (name id, number): the remembered form, nationally
    machines = 0
    seen_zone_number = set()
    digits = collections.Counter()
    rem_len = collections.Counter()
    plus_len = collections.Counter()
    rng = random.Random(SEED)
    sample = []
    gaps = {'hilbert': [], 'morton': [], 'rows': []}
    for unit in sorted(manifest['byUnit']):
        zone_pts = collections.defaultdict(list)
        with gzip.open(os.path.join(REPO, 'registry', unit + '.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                total += 1
                a = areas[r['zone']]
                n = int(r['number'])
                if not any(lo <= n <= hi for lo, hi in a['blocks']):
                    bad['number outside its blocks'] += 1
                if str(E.check_digit(a['key'], n)) != r['check']:
                    bad['check digit'] += 1
                if r['machine'] != 'CI-%s-%s-%d-%s' % (a['unit'], a['index'], n, r['check']):
                    bad['machine form'] += 1
                if r['remembered'] != E.remembered(a['plate'], n):
                    bad['remembered form'] += 1
                if r['written'] != E.written(a['plate'], n, unit_name=units[a['unit']]['name']):
                    bad['written form'] += 1
                lat, lon = float(r['entrance_lat']), float(r['entrance_lng'])
                zone_pts[r['zone']].append((n, lat, lon))
                full = E.olc_encode(lat, lon, E.SPOT_LENGTH)
                if not (r['plus_code'] == full or r['plus_code'].split(' ')[0] == E.olc_shorten(full, *E.nearest_reference(model, lat, lon)[3:5])):
                    bad['plus code'] += 1
                k = a['family'] * 100000 + n
                if k in issued:
                    bad['remembered form repeated'] += 1
                issued.add(k)
                zn = (r['zone'], n)
                if zn in seen_zone_number:
                    bad['machine form repeated'] += 1
                seen_zone_number.add(zn)
                machines += 1
                digits[len(r['number'])] += 1
                rem_len[len(r['remembered'])] += 1
                plus_len[len(r['plus_code'].split(' ')[0])] += 1
                if ' ' in r['plus_code'] and E._fold(r['plus_code'].split(' ', 1)[1]) in labelled:
                    shared_ref += 1
                if len(sample) < SAMPLE:
                    sample.append(r)
                else:
                    j = rng.randrange(total)
                    if j < SAMPLE:
                        sample[j] = r
        order_gaps(zone_pts, areas, gaps)
        print(unit, total, file=sys.stderr)

    # Decoding round trips and Plus Code recovery, on the sample.
    dec = collections.Counter()
    spot_err = []
    for r in sample:
        for form in ('remembered', 'written', 'machine'):
            try:
                p = E.parse(model, r[form])
                ok = p.get('machine', r['machine']) == r['machine'] if form != 'machine' else (
                    p['unit'] + p['index'] + str(p['number'])) == r['machine'][3:9] + r['machine'][10:13] + r['number']
            except ValueError:
                ok = False
            dec[form + (' ok' if ok else ' failed')] += 1
        sp = r['plus_code']
        try:
            d = E.decode_spot(model, sp)
            spot_err.append(metres(d['lat'], d['lon'], float(r['entrance_lat']), float(r['entrance_lng'])))
        except ValueError:
            dec['plus code failed'] += 1
    spot_err.sort()

    # Slips in the number, on the sample.
    slips = collections.Counter()
    for r in sample:
        a = areas[r['zone']]
        n = r['number']
        wrongs = []
        for i, ch in enumerate(n):
            for d in '0123456789':
                if d != ch and not (i == 0 and d == '0'):
                    wrongs.append(('substitution', n[:i] + d + n[i + 1:]))
        for i in range(len(n) - 1):
            if n[i] != n[i + 1] and not (i == 0 and n[i + 1] == '0'):
                wrongs.append(('transposition', n[:i] + n[i + 1] + n[i] + n[i + 2:]))
        for kind, w in wrongs:
            m = int(w)
            slips[kind] += 1
            if a['family'] * 100000 + m in issued:
                slips[kind + ' lands on another home'] += 1
                if E.damm_ok(E.name_digits(a['key']) + w + r['check']):
                    slips[kind + ' passes the check'] += 1
            elif model.resolve(a['plate'], m) is None:
                slips[kind + ' not issued'] += 1
            else:
                slips[kind + ' in a block, unissued'] += 1

    # The counterfactual: each area numbered on its own from 1000 with the same block and step rule.
    by_key = collections.defaultdict(list)
    for a in reg['areas']:
        if a['compounds']:
            by_key[a['key']].append(a['compounds'])
    ambiguous = 0
    for key, cs in by_key.items():
        if len(cs) < 2:
            continue
        sets = []
        for c in cs:
            cap = E.block_size(c)
            step = max(1, int(cap // (c * 1.5)))
            sets.append(set(1000 + i * step for i in range(c)))
        count = collections.Counter()
        for s in sets:
            count.update(s)
        ambiguous += sum(v for v in count.values() if v > 1)

    def q(v, p):
        return round(v[min(len(v) - 1, int(p * (len(v) - 1)))], 2)

    out = {
        'about': 'Measured on the published registry by tools/paper-evaluation.py.',
        'codes': total,
        'conformanceFailures': dict(bad),
        'distinctMachineForms': len(seen_zone_number),
        'distinctRememberedForms': len(issued),
        'numberDigits': dict(sorted(digits.items())),
        'rememberedFormLength': {'min': min(rem_len), 'max': max(rem_len),
                                 'mean': round(sum(k * v for k, v in rem_len.items()) / total, 2),
                                 'histogram': dict(sorted(rem_len.items()))},
        'plusCodeShortLength': dict(sorted(plus_len.items())),
        'sample': {'size': len(sample), 'seed': SEED},
        'decoding': dict(sorted(dec.items())),
        'plusCodeRecoveryMetres': {'p50': q(spot_err, 0.5), 'p99': q(spot_err, 0.99),
                                   'within3m': sum(1 for e in spot_err if e <= 3), 'over1km': sum(1 for e in spot_err if e > 1000)},
        'referenceNamesShared': sorted(m for v in model.by_ref_name.values() if len(v) > 1 for m in {model.refs[c][0] for c in v}),
        'referenceTownsWithDepartement': sorted(n for n, _, _ in model.refs.values() if ' (' in n),
        'plusCodesNamingTownWithDepartement': shared_ref,
        'slips': dict(sorted(slips.items())),
        'perAreaNumberingAmbiguousCodes': ambiguous,
        'consecutiveNumbersMetres': {k: {'median': q(sorted(v), 0.5), 'mean': round(sum(v) / len(v), 1),
                                         'p90': q(sorted(v), 0.9), 'shareOver200m': round(sum(1 for e in v if e > 200) / len(v), 4)}
                                     for k, v in gaps.items()},
    }
    path = os.path.join(REPO, 'model', 'stats', 'evaluation.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
