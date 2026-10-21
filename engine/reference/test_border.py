"""Tests of the national border (border.py): the inside test, distances
outside, the simplification's bound and the registry check.

    python3 -m unittest discover -s engine/reference -p 'test_*.py'
"""
import csv
import gzip
import io
import json
import math
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout

import border as B

HERE = os.path.dirname(os.path.abspath(__file__))
OUTLINE = os.path.join(os.path.dirname(HERE), 'data', 'outline.geojson')


def even_odd(lon, lat, rings):
    inside = False
    for ring in rings:
        j = len(ring) - 1
        for i in range(len(ring)):
            (xi, yi), (xj, yj) = ring[i][:2], ring[j][:2]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


def wiggly(n=4000, seed=3):
    """A closed ring around (7.5, -5.5) with a jagged edge, as a border has."""
    rnd = random.Random(seed)
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 0.5 + 0.0003 * rnd.uniform(-1, 1) + 0.01 * math.sin(40 * a)
        ring.append([-5.5 + r * math.cos(a), 7.5 + r * math.sin(a)])
    ring.append(ring[0])
    return {'type': 'Polygon', 'coordinates': [ring]}


class TestBorder(unittest.TestCase):
    def test_outline_is_small_and_records_its_deviation(self):
        self.assertLess(os.path.getsize(OUTLINE), 1_000_000)
        props = json.load(open(OUTLINE, encoding='utf-8'))['features'][0]['properties']
        self.assertGreaterEqual(props['maxDeviationM'], props['toleranceM'])
        self.assertEqual(props['borderM'], B.BORDER_M)
        self.assertIn('admin_level 2', props['source'])

    def test_inside_matches_even_odd(self):
        b = B.Border(OUTLINE)
        rings = [r for p in B.polygons(json.load(open(OUTLINE, encoding='utf-8'))) for r in p]
        rnd = random.Random(1)
        pts = [(rnd.uniform(4, 11), rnd.uniform(-9, -2.2)) for _ in range(2000)]
        # and points close to the line, where the grid matters
        for ring in rings:
            for lon, lat in ring[::25]:
                pts.append((lat + rnd.uniform(-0.003, 0.003), lon + rnd.uniform(-0.003, 0.003)))
        for lat, lon in pts:
            self.assertEqual(b.inside(lat, lon), even_odd(lon, lat, rings), (lat, lon))

    def test_distance_outside(self):
        b = B.Border({'type': 'Polygon', 'coordinates': [[[-6, 7], [-5, 7], [-5, 8], [-6, 8], [-6, 7]]]})
        self.assertEqual(b.outside_m(7.5, -5.5), 0.0)
        k = math.cos(math.radians(7.5))
        self.assertAlmostEqual(b.outside_m(7.5, -5 + 200 / (B.M_LON_EQ * k)), 200, delta=0.5)
        self.assertAlmostEqual(b.outside_m(8 + 250 / B.M_LAT, -5.5), 250, delta=0.5)
        self.assertTrue(b.allows(7.5, -5 + 299 / (B.M_LON_EQ * k)))
        self.assertFalse(b.allows(7.5, -5 + 301 / (B.M_LON_EQ * k)))
        self.assertEqual(b.outside_m(7.5, -4.9), math.inf)
        self.assertFalse(b.allows(7.5, -4.9))
        self.assertFalse(b.allows(20, 20))

    def test_simplification_keeps_the_rule(self):
        """No point more than 300 m outside the full border passes the
        simplified one, and no point inside the full border fails it."""
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, 'full.geojson'), os.path.join(tmp, 'simple.geojson')
            json.dump(wiggly(), open(src, 'w'))
            with redirect_stdout(io.StringIO()):
                B.simplify(src, dst, 50)
            full, simple = B.Border(src), B.Border(dst)
            self.assertLess(len(simple.edges), len(full.edges) / 2)
            self.assertGreater(simple.margin_m, 0)
            rnd = random.Random(2)
            for i in range(4000):
                a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.47, 0.53)
                lat, lon = 7.5 + r * math.sin(a), -5.5 + r * math.cos(a)
                d = full.outside_m(lat, lon)
                if d > B.BORDER_M:
                    self.assertFalse(simple.allows(lat, lon), (lat, lon, d))
                if d == 0:
                    self.assertTrue(simple.allows(lat, lon), (lat, lon))

    def test_check_counts_codes_across(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'b.geojson')
            json.dump({'type': 'Polygon', 'coordinates': [[[-6, 7], [-5, 7], [-5, 8], [-6, 8], [-6, 7]]]}, open(src, 'w'))
            reg = os.path.join(tmp, 'registry')
            os.mkdir(reg)
            k = math.cos(math.radians(7.5))
            with gzip.open(os.path.join(reg, '010101.csv.gz'), 'wt', newline='') as fh:
                w = csv.writer(fh)
                w.writerow(['machine', 'entrance_lat', 'entrance_lng'])
                w.writerow(['IN', 7.5, -5.5])
                w.writerow(['NEAR', 7.5, -5 + 100 / (B.M_LON_EQ * k)])
                w.writerow(['FAR', 7.5, -4.9])
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(B.check(src, reg), 1)
            self.assertIn('1 outside the border within 300 m; 1 more than 300 m outside', out.getvalue())


if __name__ == '__main__':
    unittest.main()
