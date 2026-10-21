#!/usr/bin/env python3
"""National name ranges for Côte d'Ivoire. "Name NNNN" is unique in the whole
country on its own, with no commune or town after it, and the name is a short
PLATE NAME of at most 12 characters and 2 words.

Every code area first gets its plate name (tools/ci_plates.py, rule in
engine/reference/plate_names.py). Every area whose plate name folds to the same
key (engine/SPEC.md §4.1) then draws its numbers from ONE national range for that
key. The range is cut into one frozen
block per area, in a frozen order, with spare room left in every block and at the
top of the range for areas that appear later. Standard library only.

Inputs
  model/areas/areas.csv        the 9,834 interim code areas (this repo)
  model/areas/admin-units.csv  unit names (for qualifiers)
  SAMPLE (optional)            a 10% random sample of building centroids (x,y), the
                               same file national_areas.py read (out/ci/sample.csv,
                               964,816 points); compounds = points x 10 x 0.834.
                               Without it, the compounds already estimated in
                               model/areas/name-blocks.csv (compounds_est) are reused.
Outputs
  model/areas/areas.csv        plate name, rule, council flag and candidates per area
  model/areas/name-blocks.csv  one row per area: key, plate name, digits, block
  model/areas/plate-aliases.csv  official names typed instead of the plate name
  model/stats/name-repeats.json  the counts quoted in docs/model.md

  python3 tools/name_ranges.py [SAMPLE]
  python3 tools/name_ranges.py --counts <work>/area-counts.json   the real compounds, at issue

Compounds per area are estimated by giving each sampled building to the nearest
area point anywhere in the country (as national_areas.py does), not only inside
its own unit: close to the interim rule, good enough to size blocks.
"""
import collections
import csv
import json
import math
import re
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'engine', 'reference'))
from ci_engine import name_key, block_size, range_for, NAME_SPARE_MIN, NAME_SPARE_SHARE  # noqa: E402
sys.path.insert(0, os.path.join(HERE, 'tools'))
import ci_plates  # noqa: E402
import plate_names as P  # noqa: E402

M = os.path.join(HERE, 'model')
RATIO = 0.834
SAMPLE_FACTOR = 10


def estimate(areas, sample):
    C = 0.02
    grid = collections.defaultdict(list)
    for i, a in enumerate(areas):
        grid[(int(a['lon'] // C), int(a['lat'] // C))].append(i)
    cnt = collections.Counter()
    with open(sample, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            x, y = float(r['x']), float(r['y'])
            gx, gy = int(x // C), int(y // C)
            best = None
            for rad in range(0, 60):
                for dx in range(-rad, rad + 1):
                    for dy in (range(-rad, rad + 1) if abs(dx) == rad else (-rad, rad)):
                        for i in grid.get((gx + dx, gy + dy), ()):
                            k = math.cos(math.radians(y))
                            d = ((areas[i]['lon'] - x) * k) ** 2 + (areas[i]['lat'] - y) ** 2
                            if best is None or d < best[0]:
                                best = (d, i)
                if best is not None and rad >= 1:
                    break
            if best is not None:
                cnt[best[1]] += 1
    for i, a in enumerate(areas):
        a['compounds'] = round(cnt[i] * SAMPLE_FACTOR * RATIO)




def skipped_stretches(key, keys):
    """Five-digit stretches a name never uses: d0000-d9999 when the same name
    followed by the digit d is also a name ("Koffikro" and "Koffikro 1")."""
    return sorted(int(d) for d in '123456789' if key + d in keys)


def skip_forward(start, size, skip):
    """First start >= start whose block [start, start+size-1] avoids every skipped stretch."""
    moved = True
    while moved:
        moved = False
        for d in skip:
            if start <= d * 10000 + 9999 and d * 10000 <= start + size - 1:
                start, moved = (d + 1) * 10000, True
    return start


def allocate(areas, units, keyf):
    """Blocks for every area, grouped by keyf(area). Returns (rows, stats, qualified)."""
    for a in areas:
        a['key'] = a['baseKey'] = keyf(a)
        a['qualifier'] = ''
        a['said'] = a['plateName']

    def group(rows):
        g = collections.defaultdict(list)
        for a in rows:
            g[a['key']].append(a)
        return g

    qualified = []
    for key, rows in group(areas).items():
        if range_for(sum(block_size(a['compounds']) for a in rows)) is None:
            # Does not fit 5 digits: the name takes the unit name people already put
            # in front of it ("Yopougon Sicogi"), decided once per name (SPEC.md 4.3).
            qualified.append(key)
            for a in rows:
                a['qualifier'] = units[a['unit']]['name']
                a['said'] = '%s %s' % (a['qualifier'], a['said'])
                a['key'] = name_key(a['said'])
    out, stats = [], []
    keys = set(group(areas))
    for key, rows in sorted(group(areas).items()):
        rows.sort(key=lambda a: (a['unit'], a['index']))  # frozen order: unit code, then area index
        need = sum(block_size(a['compounds']) for a in rows)
        rng = range_for(need)
        if rng is None:
            sys.exit('%s still does not fit after its qualifier' % key)
        digits, lo, hi = rng
        skip = skipped_stretches(key, keys)
        if digits == 5 and skip:
            # "Koffikro 1 18 17" must not also read as Koffikro 11817 (SPEC.md 4.2 step 7)
            if need + max(NAME_SPARE_MIN, math.ceil(need * NAME_SPARE_SHARE)) > 90000 - 10000 * len(skip):
                sys.exit('%s does not fit 5 digits once the stretches %s are skipped' % (key, skip))
        start = lo
        for a in rows:
            size = block_size(a['compounds'])
            if digits == 5:
                start = skip_forward(start, size, skip)
            out.append([key, a['said'], a['unit'], a['index'], a['compounds'], digits, start, start + size - 1, a['qualifier']])
            a['digits'], a['block'] = digits, (start, start + size - 1)
            start += size
        stats.append({'key': key, 'name': rows[0]['said'], 'areas': len(rows), 'compounds': sum(a['compounds'] for a in rows),
                      'allocated': need, 'digits': digits, 'range': [lo, hi], 'spare': hi - start + 1,
                      'officialNames': sorted({a['official'] for a in rows})})
    return out, stats, qualified


def summary(stats, n_areas):
    rep = [s for s in stats if s['areas'] > 1]
    rep.sort(key=lambda s: -s['allocated'])
    area_digits, comp_digits = collections.Counter(), collections.Counter()
    for s in stats:
        area_digits[s['digits']] += s['areas']
        comp_digits[s['digits']] += s['compounds']
    tot = sum(comp_digits.values())
    return rep, {
        'areas': n_areas,
        'nameKeys': len(stats),
        'repeatedNames': len(rep),
        'areasWithRepeatedNames': sum(s['areas'] for s in rep),
        'compoundsInRepeatedNames': sum(s['compounds'] for s in rep),
        'repeatsByAreaCount': {str(k): v for k, v in sorted(collections.Counter(s['areas'] for s in rep).items())},
        'namesByDigits': {str(k): v for k, v in sorted(collections.Counter(s['digits'] for s in stats).items())},
        'areasByDigits': {str(k): v for k, v in sorted(area_digits.items())},
        'compoundShareByDigits': {str(k): round(v / tot, 3) for k, v in sorted(comp_digits.items())},
        'largestSharedRange': {k: rep[0][k] for k in ('name', 'areas', 'compounds', 'allocated', 'digits')} if rep else None,
    }


def ambiguous_number_names(areas):
    """A plate name ending in a number ("Koffikro 1") typed without the "·" could
    also be read as a shorter name and a longer number ("Koffikro" 11817). List
    every such pair whose numbers really overlap (the parser then needs the "·"
    or the check digit; SPEC.md 9)."""
    blocks = collections.defaultdict(list)
    for a in areas:
        blocks[a['key']].append((a['block'][0], a['block'][1], a['unit'], a['index']))
    out = []
    for a in areas:
        m = re.search(r'(\d+)$', a['key'])
        if not m:
            continue
        t, base = m.group(1), a['key'][:m.start()]
        for j in range(1, len(t) + 1):
            alt_key, pre = base + t[:len(t) - j], t[len(t) - j:]
            if not alt_key or pre[0] == '0' or alt_key not in blocks:
                continue
            lo, hi = int(pre + str(a['block'][0])), int(pre + str(a['block'][1]))
            if len(str(lo)) > 5:
                continue
            for blo, bhi, u, i in blocks[alt_key]:
                if blo <= hi and lo <= bhi:
                    out.append({'plate': a['plateName'], 'area': '%s-%s' % (a['unit'], a['index']),
                                'otherKey': alt_key, 'otherArea': '%s-%s' % (u, i)})
    return out


def main():
    units = {r['code']: r for r in csv.DictReader(open(os.path.join(M, 'areas', 'admin-units.csv'), encoding='utf-8'))}
    path = os.path.join(M, 'areas', 'areas.csv')
    with open(path, encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    areas = []
    for r in rows:
        a = dict(r)
        a['lon'], a['lat'] = float(r['lon']), float(r['lat'])
        areas.append(a)
    if len(sys.argv) > 2 and sys.argv[1] == '--counts':
        # the real compounds of every area (tools/issue_registry.py group: area-counts.json)
        real = json.load(open(sys.argv[2]))
        for a in areas:
            a['compounds'] = real.get('%s-%s' % (a['unit'], a['index']), 0)
    elif len(sys.argv) > 1:
        estimate(areas, sys.argv[1])
    else:
        est = {(r['unit'], r['index']): int(r['compounds_est'])
               for r in csv.DictReader(open(os.path.join(M, 'areas', 'name-blocks.csv'), encoding='utf-8'))}
        missing = [a for a in areas if (a['unit'], a['index']) not in est]
        if missing:
            sys.exit('%d areas have no compound estimate in name-blocks.csv: run with the building SAMPLE' % len(missing))
        for a in areas:
            a['compounds'] = est[(a['unit'], a['index'])]
    # Plate names: the short remembered name of each area.
    pl = ci_plates.Plates(areas, units)
    for a in areas:
        d = pl.derive(a['name'], a['unit'])
        a['official'] = d['official']
        a['plateName'] = d['plate']
        a['plateRule'] = d['rule']
        a['needsCouncilChoice'] = d['needsCouncilChoice']
        a['plateCandidates'] = d['candidates'][:3] if d['needsCouncilChoice'] else []
        a['plateReason'] = d.get('reason', '') if d['needsCouncilChoice'] else ''
        a['plateSource'] = d.get('source', '')
        a['fits'] = ci_plates.fits(d['plate'])
    # Before: the same allocation on the full official names (for the comparison only).
    before_rows = [dict(a, plateName=a['official']) for a in areas]
    _, before_stats, _ = allocate(before_rows, units, lambda a: name_key(a['official']))
    before_rep, before = summary(before_stats, len(areas))
    out, stats, qualified = allocate(areas, units, lambda a: name_key(a['plateName']))
    rep, after = summary(stats, len(areas))
    with open(os.path.join(M, 'areas', 'name-blocks.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['key', 'name', 'unit', 'index', 'compounds_est', 'digits', 'block_lo', 'block_hi', 'qualifier'])
        w.writerows(sorted(out, key=lambda r: (r[2], r[3])))
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        cols = ['unit', 'index', 'name', 'plate', 'plateRule', 'needsCouncilChoice', 'plateCandidates', 'plateReason',
                'plateSource', 'place', 'lon', 'lat', 'digits']
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r, a in zip(rows, areas):
            r.update(plate=a['plateName'], plateRule=a['plateRule'], needsCouncilChoice=int(a['needsCouncilChoice']),
                     plateCandidates='|'.join(a['plateCandidates']), plateReason=a['plateReason'],
                     plateSource=a['plateSource'], digits=a['digits'])
            w.writerow(r)
    # Aliases: the official name (and the full OSM spelling) typed instead of the plate
    # name still decodes when it names one plate name only.
    plate_keys = {a['key'] for a in areas}
    claims = collections.defaultdict(lambda: collections.defaultdict(list))
    for a in areas:
        for n in {a['official'], a['name'].split(';')[0].strip()}:
            k = name_key(n)
            if k != a['key']:
                claims[k][a['key']].append(a)
    alias_rows, dropped = [], []
    for k, by in sorted(claims.items()):
        areas_of = list({(x['unit'], x['index']): x for v in by.values() for x in v}.values())
        official = sorted({x['official'] for x in areas_of})[0]
        if k in plate_keys:
            status, note = 'dropped', 'equals the plate name of another area'
        elif len(by) > 1:
            status, note = 'dropped', 'claimed by %d plate names: %s' % (len(by), ', '.join(sorted({x['plateName'] for x in areas_of})))
        else:
            status, note = 'kept', ''
        if status == 'dropped':
            dropped.append({'alias': official, 'key': k, 'why': note})
        alias_rows.append([k, official, '|'.join(sorted(by)), ' '.join('%s-%s' % (x['unit'], x['index']) for x in areas_of),
                           status, note])
    with open(os.path.join(M, 'areas', 'plate-aliases.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['alias_key', 'official', 'plate_key', 'areas', 'status', 'note'])
        w.writerows(alias_rows)
    amb = ambiguous_number_names(areas)
    flagged = [a for a in areas if a['needsCouncilChoice']]
    over_chars = lambda n: P.plate_length(n) > P.MAX_CHARS
    over_words = lambda n: P.word_count(n, ci_plates.LANG) > P.MAX_WORDS
    remembered = lambda a: '%s · %s' % (a['plateName'], ' '.join(re.findall(r'^\d{1,2}?(?=(?:\d\d)*$)|\d\d', str(a['block'][0]))))
    longest = max(areas, key=lambda a: (len(remembered(a)), remembered(a)))
    longest_ok = max([a for a in areas if not a['needsCouncilChoice']], key=lambda a: (len(remembered(a)), remembered(a)))
    plates = {
        'rule': 'plate name: at most %d characters (letters, spaces, hyphens, apostrophes; an accented letter is one) '
                'and %d words (linking words do not count; a hyphen separates words; one number word allowed). '
                'tools/ci_plates.py, engine/reference/plate_names.py' % (P.MAX_CHARS, P.MAX_WORDS),
        'officialOverLimit': {'chars': sum(over_chars(a['official']) for a in areas),
                              'words': sum(over_words(a['official']) for a in areas),
                              'either': sum(over_chars(a['official']) or over_words(a['official']) for a in areas),
                              'numberWords': sum(len(P.number_words(a['official'])) > 1 for a in areas)},
        'byRule': dict(sorted(collections.Counter(a['plateRule'] for a in areas).items())),
        'needsCouncilChoice': len(flagged),
        'councilReasons': dict(collections.Counter(re.sub(r' \(.*', '', a['plateReason']) for a in flagged).most_common()),
        'stillOverLimit': sum(not a['fits'] for a in areas),
        'stillOverLimitNotFlagged': sum(not a['fits'] and not a['needsCouncilChoice'] for a in areas),
        'aliases': {'kept': sum(r[4] == 'kept' for r in alias_rows), 'dropped': len(dropped)},
        'droppedAliases': dropped,
        'ambiguousWithoutSeparator': amb,
        'longestRemembered': {'code': remembered(longest), 'length': len(remembered(longest)), 'official': longest['official'],
                              'flagged': longest['needsCouncilChoice']},
        'longestRememberedNotFlagged': {'code': remembered(longest_ok), 'length': len(remembered(longest_ok)),
                                        'official': longest_ok['official']},
        'known': [{'official': a['official'], 'plate': a['plateName'], 'source': a['plateSource']}
                  for a in areas if a['plateRule'] == 'known'],
    }
    res = {
        'about': 'A remembered code "Name NNNN" is unique nationally on its own, and its name is '
                 'a plate name of at most 12 characters and 2 words. Computed by tools/name_ranges.py from '
                 'model/areas/areas.csv and the compounds of every area (tools/issue_registry.py group).',
        'normalisation': 'engine/SPEC.md 4.1 (ci_engine.name_key), applied to the plate name',
        'blockRule': 'block = max(100, 2 x compounds rounded up to 100); range 1000-9999 (4 digits) if blocks + spare fit, '
                     'else 10000-99999 (5 digits); spare = max(%d, %d%% of the blocks)' % (NAME_SPARE_MIN, round(NAME_SPARE_SHARE * 100)),
        **after,
        'qualifiedNames': [{'key': k, 'areas': [{'unit': a['unit'], 'index': a['index'], 'plate': a['plateName']}
                                                for a in areas if a['baseKey'] == k]} for k in qualified],
        'plateNames': plates,
        'beforePlateNames': {k: v for k, v in before.items()},
        'largestSharedRanges': rep[:15],
        'mostRepeated': sorted(rep, key=lambda s: (-s['areas'], -s['allocated']))[:15],
        'repeatedNamesWith5Digits': [s['name'] for s in rep if s['digits'] == 5],
    }
    json.dump(res, open(os.path.join(M, 'stats', 'name-repeats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ('largestSharedRanges', 'mostRepeated', 'repeatedNamesWith5Digits')},
                     ensure_ascii=False, indent=1)[:6000])
    for s in rep[:12]:
        print(s['name'], s['areas'], s['allocated'], s['digits'], s['officialNames'][:6])


if __name__ == '__main__':
    main()
