#!/usr/bin/env python3
"""Côte d'Ivoire's national border, and the rule that the border decides.

A code is only ever issued for a building whose entrance lies inside the
national border (OpenStreetMap's admin_level 2 boundary of Côte d'Ivoire) or
within BORDER_M = 300 m of it (engine/SPEC.md, "The border decides"). Zone
outlines from other sources (the sous-préfectures, the communes) may spill
over the border; they never decide.

    Border(path)               the border from a GeoJSON Polygon or MultiPolygon
                               (a geometry, a Feature or a FeatureCollection)
    Border.outside_m(lat, lon) 0 inside, else the distance in metres to the
                               border line (math.inf beyond REACH_M = 390 m)
    Border.allows(lat, lon)    the rule: inside, or at most BORDER_M - margin_m
                               outside, where margin_m is the simplification
                               error recorded in the file (0 for the full border)

    python3 engine/reference/border.py simplify <country.geojson> <out.geojson> [tolerance_m]
        Douglas-Peucker in metres (default 50 m), every ring; writes the
        simplified border with its largest measured deviation (maxDeviationM)
    python3 engine/reference/border.py check <border.geojson> <registry folder>
        counts the published codes whose entrance lies more than BORDER_M
        outside the border; exits 1 if there is any

Distances are on a local plane at the point's latitude (110,574 m per degree of
latitude, 111,320 m x cos(latitude) per degree of longitude). Standard library
only.
"""
import csv
import gzip
import json
import math
import os
import sys

BORDER_M = 300.0
M_LAT = 110574.0
M_LON_EQ = 111320.0
CELL = 0.02      # grid cell, degrees
PAD = 0.0036     # an edge is listed in every cell within PAD degrees of it (at least 390 m)
REACH_M = 390.0  # how far outside_m measures; farther is math.inf


def polygons(obj):
    """Every polygon (outer ring, holes...) of a GeoJSON object, as [lon, lat] lists."""
    t = obj.get('type')
    if t == 'FeatureCollection':
        return [p for f in obj['features'] for p in polygons(f)]
    if t == 'Feature':
        return polygons(obj['geometry'])
    if t == 'Polygon':
        return [obj['coordinates']]
    if t == 'MultiPolygon':
        return list(obj['coordinates'])
    return []


def _seg_m(px, py, ax, ay, bx, by, k):
    """Distance in metres from (px, py) to the segment a-b (lon, lat), at scale k = cos(lat)."""
    ax, bx, px_ = (ax - px) * M_LON_EQ * k, (bx - px) * M_LON_EQ * k, 0.0
    ay, by, py_ = (ay - py) * M_LAT, (by - py) * M_LAT, 0.0
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px_ - ax) * dx + (py_ - ay) * dy) / l2))
    return math.hypot(ax + t * dx, ay + t * dy)


def _cross(ox, oy, px, py, ax, ay, bx, by):
    """Whether the segment o-p crosses the edge a-b. An edge end exactly on the
    line o-p counts as below it, as in the ray test, so a crossing through a
    vertex is counted once."""
    def above(x, y):
        return (px - ox) * (y - oy) - (py - oy) * (x - ox) > 0
    if above(ax, ay) == above(bx, by):
        return False
    t1 = (bx - ax) * (oy - ay) - (by - ay) * (ox - ax)
    t2 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    return t1 * t2 < 0


class Border:
    def __init__(self, path_or_obj):
        if isinstance(path_or_obj, dict):
            obj = path_or_obj
        else:
            with open(path_or_obj, encoding='utf-8') as fh:
                obj = json.load(fh)
        props = obj.get('properties') or {}
        if obj.get('type') == 'FeatureCollection' and obj['features']:
            props = obj['features'][0].get('properties') or {}
        self.margin_m = float(props.get('maxDeviationM') or 0.0)
        self.edges = []
        for poly in polygons(obj):
            for ring in poly:
                for i in range(1, len(ring)):
                    (ax, ay), (bx, by) = ring[i - 1][:2], ring[i][:2]
                    if (ax, ay) != (bx, by):
                        self.edges.append((ax, ay, bx, by))
                if ring and ring[0][:2] != ring[-1][:2]:
                    self.edges.append((ring[-1][0], ring[-1][1], ring[0][0], ring[0][1]))
        self.rows, self.cells, self._centre = {}, {}, {}
        for e in self.edges:
            ax, ay, bx, by = e
            for r in range(int(math.floor(min(ay, by) / CELL)), int(math.floor(max(ay, by) / CELL)) + 1):
                self.rows.setdefault(r, []).append(e)
            for cy in range(int(math.floor((min(ay, by) - PAD) / CELL)), int(math.floor((max(ay, by) + PAD) / CELL)) + 1):
                for cx in range(int(math.floor((min(ax, bx) - PAD) / CELL)), int(math.floor((max(ax, bx) + PAD) / CELL)) + 1):
                    self.cells.setdefault((cx, cy), []).append(e)

    def _ray(self, lon, lat):
        """Even-odd test against every edge of the point's row."""
        inside = False
        for ax, ay, bx, by in self.rows.get(int(math.floor(lat / CELL)), ()):
            if (ay > lat) != (by > lat) and lon < (bx - ax) * (lat - ay) / (by - ay) + ax:
                inside = not inside
        return inside

    def _centre_in(self, c):
        v = self._centre.get(c)
        if v is None:
            v = self._centre[c] = self._ray((c[0] + 0.5) * CELL, (c[1] + 0.5) * CELL)
        return v

    def inside(self, lat, lon):
        c = (int(math.floor(lon / CELL)), int(math.floor(lat / CELL)))
        es = self.cells.get(c)
        if not es:
            return self._centre_in(c)
        # the cell's centre is classified once; the edges between it and the point flip it
        ox, oy = (c[0] + 0.5) * CELL, (c[1] + 0.5) * CELL
        inside = self._centre_in(c)
        for ax, ay, bx, by in es:
            if _cross(ox, oy, lon, lat, ax, ay, bx, by):
                inside = not inside
        return inside

    def outside_m(self, lat, lon):
        if self.inside(lat, lon):
            return 0.0
        k = math.cos(math.radians(lat))
        es = self.cells.get((int(math.floor(lon / CELL)), int(math.floor(lat / CELL))), ())
        d = min((_seg_m(lon, lat, *e, k) for e in es), default=math.inf)
        return d if d <= REACH_M else math.inf

    def allows(self, lat, lon):
        return self.outside_m(lat, lon) <= BORDER_M - self.margin_m


def _dp(ring, tol_m):
    """Douglas-Peucker of one closed ring (first point repeated last); returns the ring and its largest deviation."""
    pts = ring[:-1] if ring[0] == ring[-1] else ring[:]
    n = len(pts)
    if n < 4:
        return ring, 0.0
    # split at the vertex farthest from the first, so both halves are open chains
    k0 = math.cos(math.radians(pts[0][1]))
    far = max(range(n), key=lambda i: math.hypot((pts[i][0] - pts[0][0]) * k0, pts[i][1] - pts[0][1]))
    chain = pts + [pts[0]]
    keep = {0, far, n}
    worst = 0.0
    stack = [(0, far), (far, n)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        ax, ay = chain[i][:2]
        bx, by = chain[j][:2]
        best, bi = -1.0, None
        for m in range(i + 1, j):
            d = _seg_m(chain[m][0], chain[m][1], ax, ay, bx, by, math.cos(math.radians(chain[m][1])))
            if d > best:
                best, bi = d, m
        if best > tol_m:
            keep.add(bi)
            stack += [(i, bi), (bi, j)]
        else:
            worst = max(worst, best)
    out = [chain[i] for i in sorted(keep)]
    return out, worst


def simplify(src, dst, tol_m=50.0):
    with open(src, encoding='utf-8') as fh:
        obj = json.load(fh)
    polys, worst, before = [], 0.0, 0
    for poly in polygons(obj):
        rings = []
        for r, ring in enumerate(poly):
            before += len(ring)
            s, w = _dp(ring, tol_m)
            if len(s) >= 4:
                rings.append([[round(x, 6), round(y, 6)] for x, y in (p[:2] for p in s)])
                worst = max(worst, w)
            elif r == 0:
                break
        if rings:
            polys.append(rings)
    # rounding to 1e-6 degrees moves a vertex at most 0.1 m; one metre covers it and the scale differences
    dev = math.ceil(worst) + 1
    out = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {
        'name': "Côte d'Ivoire", 'source': 'OpenStreetMap, admin_level 2 (ODbL)',
        'toleranceM': tol_m, 'maxDeviationM': dev, 'borderM': BORDER_M},
        'geometry': {'type': 'MultiPolygon', 'coordinates': polys}}]}
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    after = sum(len(r) for p in polys for r in p)
    print('%d points -> %d, largest deviation %.1f m (recorded %d m), %d bytes' % (before, after, worst, dev, os.path.getsize(dst)))


def check(border_path, registry):
    b = Border(border_path)
    n = near = far = 0
    worst = []
    for name in sorted(os.listdir(registry)):
        if not name.endswith('.csv.gz') or name == 'areas.csv.gz':
            continue
        with gzip.open(os.path.join(registry, name), 'rt', encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                n += 1
                d = b.outside_m(float(r['entrance_lat']), float(r['entrance_lng']))
                if d == 0:
                    continue
                if d <= BORDER_M:
                    near += 1
                else:
                    far += 1
                    worst.append((d, r['machine']))
    print('%d codes; %d outside the border within %.0f m; %d more than %.0f m outside' % (n, near, BORDER_M, far, BORDER_M))
    for d, m in sorted(worst, reverse=True)[:20]:
        print('  %s %s' % (m, 'more than 390 m' if math.isinf(d) else '%.0f m' % d))
    return far


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'simplify':
        simplify(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 50.0)
    elif len(sys.argv) == 4 and sys.argv[1] == 'check':
        sys.exit(1 if check(sys.argv[2], sys.argv[3]) else 0)
    else:
        sys.exit(__doc__)
