#!/usr/bin/env python3
"""Decode every issued code of the published registry, in every form people hold.

  python3 tools/check-decoding.py [registry/]      # a few minutes, one process per core

For every row of registry/<unit>.csv.gz, with the reference engine and nothing else:
  remembered   "Bonoumin · 61 36" must parse to the row's machine form;
  written      "Bonoumin 61 36 (Cocody)" must parse to the row's machine form;
  plus code    the short Plus Code and its town ("926H+7Q7 Cocody") must recover the
               11-character cell that holds the row's entrance.
Prints the counts and every failure (at most 20 per form) and exits 1 if any form fails.
"""
import collections, csv, gzip, json, multiprocessing, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402

MODEL = None


def check_unit(args):
    path, unit = args
    global MODEL
    if MODEL is None:
        MODEL = E.Model()
    ok, bad = collections.Counter(), collections.defaultdict(list)
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            for form in ('remembered', 'written'):
                try:
                    got = E.parse(MODEL, r[form])['machine']
                except ValueError as e:
                    got = 'error: %s' % e
                if got == r['machine']:
                    ok[form] += 1
                else:
                    bad[form].append((r[form], r['machine'], got))
            cell = E.olc_encode(float(r['entrance_lat']), float(r['entrance_lng']), E.SPOT_LENGTH)
            try:
                got = E.decode_spot(MODEL, r['plus_code'])['plusCode']
            except ValueError as e:
                got = 'error: %s' % e
            if got == cell:
                ok['plus code'] += 1
            else:
                bad['plus code'].append((r['plus_code'], cell, got))
    return unit, ok, {k: (len(v), v[:20]) for k, v in bad.items()}


def main(argv):
    reg = argv[0] if argv else os.path.join(REPO, 'registry')
    with open(os.path.join(reg, 'MANIFEST.json'), encoding='utf-8') as fh:
        units = sorted(json.load(fh)['byUnit'])
    jobs = [(os.path.join(reg, u + '.csv.gz'), u) for u in units]
    ok, failed, examples = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    with multiprocessing.Pool() as pool:
        for unit, o, b in pool.imap_unordered(check_unit, jobs):
            ok.update(o)
            for k, (n, ex) in b.items():
                failed[k] += n
                examples[k].extend(ex)
    for form in ('remembered', 'written', 'plus code'):
        print('%-10s %9d decoded to their own code, %d failed' % (form, ok[form], failed[form]))
        for text, want, got in sorted(examples[form])[:20]:
            print('    %s: want %s, got %s' % (text, want, got))
    return 1 if sum(failed.values()) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
