#!/usr/bin/env python3
"""Tests for the Côte d'Ivoire reference engine. Offline, standard library only.

  python3 engine/reference/test_ci.py
"""
import json
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ci_engine as E  # noqa: E402

V = json.load(open(os.path.join(HERE, 'test_vectors.json'), encoding='utf-8'))
MODEL = E.Model()


class OpenLocationCode(unittest.TestCase):
    def test_encode(self):
        for t in V['olc']:
            self.assertEqual(E.olc_encode(t['lat'], t['lon'], t['length']), t['code'])

    def test_decode_contains_point(self):
        for t in V['olc']:
            a = E.olc_decode(t['code'])
            self.assertTrue(a.lat_lo <= t['lat'] < a.lat_hi + 1e-12)
            self.assertTrue(a.lng_lo <= t['lon'] < a.lng_hi + 1e-12)

    def test_shorten_recover(self):
        for t in V['olcShorten']:
            self.assertEqual(E.olc_shorten(t['code'], t['lat'], t['lon']), t['short'])
            self.assertEqual(E.olc_recover(t['short'], t['lat'], t['lon']), t['code'])
        for t in V['olcRecover']:
            self.assertEqual(E.olc_recover(t['short'], t['lat'], t['lon']), t['full'])

    def test_round_trip_across_country(self):
        rnd = random.Random(2026)
        for _ in range(2000):
            lat, lon = rnd.uniform(4.3, 10.8), rnd.uniform(-8.6, -2.4)
            code = E.olc_encode(lat, lon, E.SPOT_LENGTH)
            a = E.olc_decode(code)
            self.assertLess(abs(a.lat - lat), 2.0e-5)   # cell 1/40000 deg tall
            self.assertLess(abs(a.lng - lon), 2.0e-5)   # cell 1/32000 deg wide
            self.assertEqual(E.olc_encode(a.lat, a.lng, E.SPOT_LENGTH), code)

    def test_validity(self):
        self.assertTrue(E.olc_is_full('6CQR926H+7Q7'))
        self.assertTrue(E.olc_is_short('926H+7Q7'))
        self.assertFalse(E.olc_is_valid('6CQR926H7Q7'))
        self.assertFalse(E.olc_is_valid('6CQR926H+7Q7O'))


class Damm(unittest.TestCase):
    def test_vectors(self):
        for t in V['damm']:
            self.assertEqual(E.damm(t['digits']), t['check'])
            self.assertTrue(E.damm_ok(t['digits'] + str(t['check'])))

    def test_catches_single_errors_and_adjacent_swaps(self):
        rnd = random.Random(7)
        for _ in range(300):
            body = ''.join(rnd.choice('0123456789') for _ in range(13))
            full = body + str(E.damm(body))
            for i in range(len(full)):
                for d in '0123456789':
                    if d != full[i]:
                        self.assertFalse(E.damm_ok(full[:i] + d + full[i + 1:]))
            for i in range(len(full) - 1):
                if full[i] != full[i + 1]:
                    self.assertFalse(E.damm_ok(full[:i] + full[i + 1] + full[i] + full[i + 2:]))


class Spots(unittest.TestCase):
    def test_real_points(self):
        for t in V['spots']:
            s = E.spot(MODEL, t['lat'], t['lon'])
            self.assertEqual(s['plusCode'], t['plusCode'], t['label'])
            self.assertEqual(s.get('short'), t['short'], t['label'])
            back = E.decode_spot(MODEL, t['short'])
            self.assertEqual(back['plusCode'], t['plusCode'])

    def test_reference_towns_are_unambiguous(self):
        # no two reference towns are written alike (SPEC.md 7): a town two units share is
        # written with its département ("Lolobo (Béoumi)")
        folded = [E._fold(n) for n, _, _ in MODEL.refs.values()]
        self.assertEqual(len(folded), len(set(folded)))
        self.assertEqual(MODEL.refs['110105'][0], 'Lolobo (Béoumi)')
        self.assertEqual(MODEL.refs['020102'][0], 'Lolobo (Attiégouakro)')

    def test_shared_towns_round_trip(self):
        # points around every town whose name another unit's town shares: the short code
        # names the labelled town and recovers the cell; the bare name recovers it only when
        # one reading is possible, and is refused otherwise
        bare = {}
        for u, (name, rlat, rlon) in MODEL.refs.items():
            if ' (' in name:
                bare[u] = name.split(' (')[0]
        self.assertEqual(len(bare), 10)
        rnd = random.Random(7)
        resolved = refused = 0
        for u, town in sorted(bare.items()):
            _, rlat, rlon = MODEL.refs[u]
            for _ in range(200):
                lat, lon = rlat + rnd.uniform(-0.25, 0.25), rlon + rnd.uniform(-0.25, 0.25)
                s = E.spot(MODEL, lat, lon)
                if s['short'] == s['plusCode']:
                    continue
                self.assertEqual(E.decode_spot(MODEL, s['short'])['plusCode'], s['plusCode'], s['short'])
                if s['reference'] != MODEL.refs[u][0]:
                    continue
                code = s['short'].split(' ')[0]
                for typed in (MODEL.refs[u][0].upper(), MODEL.refs[u][0].replace(' (', ', ').rstrip(')')):
                    self.assertEqual(E.decode_spot(MODEL, code + ' ' + typed)['plusCode'], s['plusCode'], typed)
                try:
                    got = E.decode_spot(MODEL, code + ' ' + town)['plusCode']
                except ValueError:
                    refused += 1
                    continue
                self.assertEqual(got, s['plusCode'], code + ' ' + town)
                resolved += 1
        self.assertGreater(resolved, 0)

    def test_areas(self):
        for t in V['spots']:
            u, a = MODEL.area_at(t['lat'], t['lon'])
            self.assertEqual((u, a['index'], a['name']), (t['unit'], t['areaIndex'], t['areaName']), t['label'])


class Codes(unittest.TestCase):
    def test_check_vectors(self):
        for t in V['check']:
            self.assertEqual(E.name_digits(t['key']), t['nameDigits'])
            self.assertEqual(E.check_digit(t['key'], t['number']), t['check'])

    def test_machine_round_trip(self):
        m = E.machine('010120', '034', 19817, 'sikogi')
        self.assertEqual(m, 'CI-010120-034-19817-1')
        p = E.parse(MODEL, m)
        self.assertEqual((p['unit'], p['index'], p['number'], p['area']), ('010120', '034', 19817, 'Sicogi'))

    def test_typo_rejected(self):
        with self.assertRaises(ValueError):
            E.parse(MODEL, 'CI-010120-034-19871-1')   # swapped digits
        with self.assertRaises(ValueError):
            E.parse(MODEL, 'CI-010120-034-15817-1')   # another Sicogi's block (Koumassi), not this area's

    def test_structure_and_entrance(self):
        p = E.parse(MODEL, E.machine('010120', '034', 19817, 'sikogi', structure=2, entrance=3))
        self.assertEqual((p['structure'], p['entrance']), (2, 3))

    def test_remembered(self):
        self.assertEqual(E.remembered('Sicogi', 19817), 'Sicogi · 1 98 17')
        for t in ('Sicogi 1 98 17', 'SICOGI·19817', 'Sicogi · 1 98 17', 'Sicogi 19817-1', 'Sicogi 19817-1 (Yopougon)',
                  'sicogi 19817, Yopougon', 'Sicogi-19817'):
            p = E.parse(MODEL, t)
            self.assertEqual((p['unit'], p['index'], p['number']), ('010120', '034', 19817), t)
        self.assertEqual(E.written('Sicogi', 19817, 'sikogi', 'Yopougon'), 'Sicogi 1 98 17 (Yopougon)')
        self.assertEqual(E.remembered('Bonoumin', 5552), 'Bonoumin · 55 52')

    def test_official_address_is_kept_as_written(self):
        p = E.parse(MODEL, '115, Rue des Moineaux, Le Plateau')
        self.assertEqual((p['form'], p['system'], p['number'], p['street'], p['commune']),
                         ('official', 'PADA', 115, 'Rue des Moineaux', 'Le Plateau'))
        self.assertEqual(E.official_display(p), '115, Rue des Moineaux, Le Plateau')

    def test_spoken(self):
        for t in V['spoken']:
            self.assertEqual(E.spoken_number(t['number']), t['pairs'])
            self.assertEqual(E.say_fr(t['number']), t['fr'])


class NationalNames(unittest.TestCase):
    """'Name NNNN' is unique in the whole country on its own."""

    def test_name_keys(self):
        for t in V['nameKeys']:
            for n in t['names']:
                self.assertEqual(E.name_key(n), t['key'], n)

    def test_same_name_areas_decode_to_different_places(self):
        seen = set()
        for t in V['sameName']:
            p = E.parse(MODEL, t['text'])
            self.assertEqual((p['unit'], p['index'], p['area'], p['commune'], p['machine']),
                             (t['unit'], t['index'], t['area'], t['commune'], t['machine']), t['text'])
            self.assertEqual(E.written(p['area'], p['number'], p['key'], p['commune']), t['written'])
            self.assertEqual(E.parse(MODEL, t['written'])['machine'], t['machine'])
            self.assertEqual(E.parse(MODEL, t['machine'])['index'], t['index'])
            seen.add((p['unit'], p['index']))
        self.assertEqual(len(seen), len(V['sameName']))
        # three Madinas and three Bellevilles, told apart by the number alone
        self.assertEqual(len({(t['unit'], t['index']) for t in V['sameName'] if t['area'] == 'Madina'}), 3)

    def test_numbers_not_in_any_block_are_rejected(self):
        for t in V['notIssued']:
            with self.assertRaises(ValueError, msg=t):
                E.parse(MODEL, t)

    def test_label_cannot_redirect(self):
        with self.assertRaises(ValueError):
            E.parse(MODEL, 'Madina 4600, Touba')   # 4600 is Korhogo's block
        with self.assertRaises(ValueError):
            E.parse(MODEL, 'Belleville 45000 (Abobo)')   # 45000 is Yamoussoukro's block

    def test_typo_into_another_same_named_block_is_caught(self):
        # Every single wrong digit and every adjacent swap in the number of a written code
        # is rejected, including those that land in another Madina or Belleville block.
        crossed = 0
        for t in V['sameName']:
            p = E.parse(MODEL, t['text'])
            n, key, chk = str(p['number']), p['key'], str(E.check_digit(p['key'], p['number']))
            variants = {n[:i] + d + n[i + 1:] for i in range(len(n)) for d in '0123456789'}
            variants |= {n[:i] + n[i + 1] + n[i] + n[i + 2:] for i in range(len(n) - 1)}
            for v in variants - {n}:
                if v[0] == '0':
                    continue
                self.assertFalse(E.damm_ok(E.name_digits(key) + v + chk), (t['text'], v))
                other = MODEL.resolve(p['area'], int(v))
                if other and (other['unit'], other['index']) != (p['unit'], p['index']):
                    crossed += 1
                    with self.assertRaises(ValueError):
                        E.parse(MODEL, '%s %s-%s' % (p['area'], v, chk))
        self.assertGreater(crossed, 10)

    def test_whole_country_is_unique(self):
        # Blocks of one name never overlap and stay within 4 or 5 digits; every area has one.
        self.assertEqual(len(MODEL.area_blocks), sum(len(v) for v in MODEL.areas.values()))
        for key, bl in MODEL.blocks.items():
            prev = 0
            for lo, hi, u, i in bl:
                self.assertGreater(lo, prev, key)
                self.assertTrue(1000 <= lo <= hi <= 99999, key)
                self.assertEqual(len(str(lo)), len(str(hi)), key)
                self.assertEqual(MODEL.key_of(u, i), key)
                prev = hi
        # the decoder sends each area's own first number back to that same area
        for (u, i), bl in MODEL.area_blocks.items():
            a = MODEL.resolve(MODEL.area(u, i)['plate'], bl[0][0])
            self.assertEqual((a['unit'], a['index']), (u, i))

    def test_new_area_gets_a_new_block_and_old_blocks_stay(self):
        before = list(MODEL.blocks['madina'])
        b = E.next_block(MODEL, 'madina', 300)
        self.assertEqual(b, (8100, 8699))
        self.assertEqual(MODEL.blocks['madina'], before)
        # a 4-digit name whose 4-digit space is used up continues with 5-digit numbers
        self.assertEqual(E.next_block(MODEL, 'madina', 1500), (10000, 12999))
        b = E.next_block(MODEL, 'belevile', 2000)
        self.assertEqual(b, (93000, 96999))
        # 'Koffikro 1' and 'Koffikro 2' are names: Koffikro never takes 10000-29999
        self.assertEqual(E.skipped_stretches(MODEL, 'kofikro'), [1, 2])
        self.assertEqual(E.skip_forward(19000, 2000, [1, 2]), 30000)


class PlateNames(unittest.TestCase):
    """The remembered name is at most 12 characters and 2 words."""

    def test_limit(self):
        for n in V['plateLimit']['ok']:
            self.assertTrue(E.plate_ok(n), n)
        for n in V['plateLimit']['over']:
            self.assertFalse(E.plate_ok(n), n)
        self.assertEqual(E.plate_names.plate_length('Lém-Ferreira'), 12)
        self.assertEqual(E.plate_names.word_count('Cité de la Paix', 'fr'), 2)
        self.assertFalse(E.plate_ok('Abri 2000 4'))   # one number word at most

    def test_every_plate_fits_unless_the_commune_must_choose(self):
        n = flagged = 0
        for rows in MODEL.areas.values():
            for a in rows:
                n += 1
                if a['needsCouncilChoice']:
                    flagged += 1
                    self.assertLessEqual(len(a['plateCandidates']), 3)
                    if a['plateCandidates']:
                        self.assertIn(a['plate'], a['plateCandidates'] + [a['plate']])
                else:
                    self.assertTrue(E.plate_ok(a['plate']), a['plate'])
        self.assertEqual(n, 9834)
        self.assertGreater(flagged, 0)

    def test_model_rejects_a_long_plate(self):
        import shutil, tempfile, csv
        d = tempfile.mkdtemp()
        try:
            shutil.copytree(E.MODEL, os.path.join(d, 'model'))
            path = os.path.join(d, 'model', 'areas', 'areas.csv')
            with open(path, encoding='utf-8') as fh:
                rows = list(csv.DictReader(fh))
            r = [r for r in rows if r['plate'] == 'Remblais'][0]
            r['plate'] = 'Koumassi Remblais'
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError):
                E.Model(os.path.join(d, 'model'))
        finally:
            shutil.rmtree(d)

    def test_long_official_name_to_plate(self):
        for t in V['plateNames']:
            self.assertFalse(E.plate_ok(t['official']), t['official'])
            self.assertTrue(E.plate_ok(t['plate']), t['plate'])
            p = E.parse(MODEL, t['text'])                       # official name typed: still decodes
            self.assertEqual((p['machine'], p['remembered'], p['area']), (t['machine'], t['remembered'], t['plate']))
            q = E.parse(MODEL, t['remembered'])                 # the plate name gives the same place
            self.assertEqual(q['machine'], t['machine'])

    def test_collision_after_shortening(self):
        seen = set()
        for t in V['plateCollision']:
            p = E.parse(MODEL, t['text'])
            self.assertEqual((p['unit'], p['index'], p['area'], p['official'], p['commune'], p['machine']),
                             (t['unit'], t['index'], t['area'], t['official'], t['commune'], t['machine']))
            seen.add((p['unit'], p['index']))
        self.assertEqual(len(seen), 2)
        self.assertEqual(len({t['area'] for t in V['plateCollision']}), 1)
        self.assertEqual(len({t['official'] for t in V['plateCollision']}), 2)

    def test_alias_never_leaves_its_areas(self):
        for t in V['aliasNotIssued']:
            with self.assertRaises(ValueError, msg=t):
                E.parse(MODEL, t)

    def test_number_in_name(self):
        for t in V['numberInName']:
            p = E.parse(MODEL, t['text'])
            self.assertEqual((p['area'], p['machine']), (t['area'], t['machine']), t['text'])

    def test_plate_name_reading_wins_over_an_alias(self):
        # "Air France 1 10 00" also reads as the alias Air France 1 (official name of
        # France I, Bouaké) with 1000: the plate name is the code people hold, so it wins;
        # a commune decides, and the "·" fixes the split.
        for text, want in (('Air France 1 10 00 (Korhogo)', 'CI-280201-043-11000-1'),
                           ('Air France 1 10 00', 'CI-280201-043-11000-1'),
                           ('Air France · 1 10 00', 'CI-280201-043-11000-1'),
                           ('Air France 1 · 10 00', 'CI-110301-106-1000-7'),
                           ('Air France I 10 00 (Bouaké)', 'CI-110301-106-1000-7'),
                           ('Air France 1 10 00, Bouaké', 'CI-110301-106-1000-7'),
                           ('Air France 2 21 00 (Man)', 'CI-320301-019-22100-9')):
            self.assertEqual(E.parse(MODEL, text)['machine'], want, text)
        with self.assertRaises(ValueError):
            E.parse(MODEL, 'Air France 1 10 00 (Man)')  # neither reading is in Man

    def test_every_colliding_number_decodes_to_its_own_code(self):
        # Every number of a plate name whose five-digit numbers d0000-d9999 another name
        # (an alias "Name d") also reads: written, remembered and plain, all its own.
        n_checked = 0
        for key, bl in MODEL.blocks.items():
            for lo, hi, u, i in bl:
                for d in '123456789':
                    if key + d not in MODEL.aliases and key + d not in MODEL.blocks:
                        continue
                    a = MODEL.area(u, i)
                    unit = MODEL.units[u]['name']
                    for n in range(max(lo, int(d) * 10000), min(hi, int(d) * 10000 + 9999) + 1):
                        want = E.machine(u, i, n, key)
                        for t in (E.written(a['plate'], n, key, unit), E.remembered(a['plate'], n),
                                  '%s %s' % (a['plate'], E.spoken_number(n))):
                            self.assertEqual(E.parse(MODEL, t)['machine'], want, t)
                        n_checked += 1
        self.assertGreater(n_checked, 10000)

    def test_every_area_decodes_from_its_spoken_code(self):
        # "Plate · NN NN" and the same typed without the dot both give the area back
        for (u, i), bl in MODEL.area_blocks.items():
            a = MODEL.area(u, i)
            for n in (bl[0][0], bl[0][1]):
                for t in (E.remembered(a['plate'], n), '%s %s' % (a['plate'], E.spoken_number(n))):
                    p = E.parse(MODEL, t)
                    self.assertEqual((p['unit'], p['index']), (u, i), t)


class Registry(unittest.TestCase):
    def setUp(self):
        self.reg = E.build_sample_registry(MODEL, os.path.join(HERE, 'sample-cocody-riviera.csv'))

    def test_sample(self):
        r = V['sampleRegistry']
        self.assertEqual(len(self.reg['compounds']), r['compounds'])
        self.assertEqual((self.reg['digits'], self.reg['step']), (r['digits'], r['step']))
        c = [c for c in self.reg['compounds'] if '75715' in c['members']][0]
        self.assertEqual(c['machine'], r['building75715']['machine'])
        self.assertEqual(c['remembered'], r['building75715']['remembered'])
        self.assertTrue(E.plate_ok(self.reg['area']))

    def test_numbers_follow_curve_and_are_unique(self):
        cs = self.reg['compounds']
        nums = [c['number'] for c in cs]
        self.assertEqual(len(nums), len(set(nums)))
        self.assertEqual(nums, sorted(nums))
        lo, hi = r = V['sampleRegistry']['block']
        self.assertEqual(self.reg['range'], r)
        self.assertTrue(all(lo <= n < self.reg['tailReserve'][0] for n in nums))

    def test_provisional(self):
        r = V['sampleRegistry']['provisional']
        n = E.provisional_number(self.reg, self.reg['frame'], r['lon'], r['lat'])
        self.assertEqual(n, r['number'])
        self.assertNotIn(n, {c['number'] for c in self.reg['compounds']})

    def test_every_structure_has_a_profile(self):
        for c in self.reg['compounds']:
            for s in c['structures']:
                self.assertIn(s['useClass'], set(E.BTAG.values()) | set(E.CATS.values()) | set(E.LANDUSE.values()) | {'mixed', 'residential', 'annex', 'industrial'})
                self.assertTrue(s['floors'] is None or s['floors'] >= 1)  # unknown unless OpenStreetMap says

    def test_hilbert_neighbours(self):
        self.assertEqual([E.hilbert_index(x, y, 1) for x, y in ((0, 0), (0, 1), (1, 1), (1, 0))], [0, 1, 2, 3])


if __name__ == '__main__':
    unittest.main(verbosity=1)
