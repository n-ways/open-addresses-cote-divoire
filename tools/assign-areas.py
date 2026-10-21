#!/usr/bin/env python3
"""Every Ivorian footprint's code area (engine/SPEC.md 4, "Interim area").

  python3 tools/assign-areas.py <work folder>

Reads <work>/buildings-pts.csv (tools/extract-buildings.py: bid, lon, lat, unit, dens) and
model/areas/areas.csv (the 9,834 code areas, each a named place point of one unit), and
gives every footprint the nearest place point of its own unit (equirectangular distance,
ties to the lower index). A footprint in no unit polygon (the units are simplified to about
40 m, so a few on the coast or the border fall between them) takes the nearest place point
in the country, whatever its unit. One pass, footprints streamed; standard library only.

Writes <work>/area-of.csv (bid, aid = <unit>-<index>, dens) and <work>/area-counts-raw.json
(footprints per area).
"""
import collections, csv, json, math, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
KY = 110.574


class Index:
    """Nearest point on a 0.05 degree grid, searched in growing rings."""

    def __init__(self, pts, cell=0.05):
        self.cell, self.pts, self.g = cell, pts, collections.defaultdict(list)
        for i, p in enumerate(pts):
            self.g[(int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)))].append(i)

    def nearest(self, q):
        cy, cx = int(math.floor(q[0] / self.cell)), int(math.floor(q[1] / self.cell))
        k = math.cos(math.radians(q[0])) * 111.32
        best, r = None, 0
        while True:
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dy), abs(dx)) != r:
                        continue
                    for i in self.g.get((cy + dy, cx + dx), ()):
                        p = self.pts[i]
                        d = math.hypot((q[0] - p[0]) * KY, (q[1] - p[1]) * k)
                        if best is None or (d, i) < best:
                            best = (d, i)
            # a point in ring r is at least (r - 1) cells away: stop once nothing nearer can exist
            if best is not None and best[0] <= (r * self.cell) * min(KY, k):
                return best
            r += 1
            if r > 200:
                return best


areas, by_unit = [], collections.defaultdict(list)
for r in csv.DictReader(open(os.path.join(REPO, 'model', 'areas', 'areas.csv'), encoding='utf-8')):
    areas.append((float(r['lat']), float(r['lon']), r['unit'] + '-' + r['index']))
for a in sorted(areas, key=lambda a: a[2]):
    by_unit[a[2][:6]].append(a)
idx = {u: (Index([(a[0], a[1]) for a in v]), v) for u, v in by_unit.items()}
whole = sorted(areas, key=lambda a: a[2])
widx = Index([(a[0], a[1]) for a in whole])

counts, outside = collections.Counter(), 0
with open(W('buildings-pts.csv'), encoding='utf-8', newline='') as f, open(W('area-of.csv'), 'w', newline='') as o:
    w = csv.writer(o)
    w.writerow(['bid', 'aid', 'dens'])
    for r in csv.DictReader(f):
        q = (float(r['lat']), float(r['lon']))
        u = r['unit']
        if u in idx:
            ix, v = idx[u]
            aid = v[ix.nearest(q)[1]][2]
        else:
            outside += 1
            aid = whole[widx.nearest(q)[1]][2]
        counts[aid] += 1
        w.writerow([r['bid'], aid, r['dens']])
json.dump(dict(sorted(counts.items())), open(W('area-counts-raw.json'), 'w'))
print(sum(counts.values()), 'footprints,', len(counts), 'areas with footprints of', len(areas), ',', outside, 'outside every unit')
