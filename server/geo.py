"""Distances, outlines and the national boundary.

The constants and formulas are the issuer's, so a deployment measures a
distance or an outline exactly as N-Ways does when it decides whether a point
already has a code or whether an outline is a plausible home.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'engine', 'reference'))
import border  # noqa: E402

# Metres per degree on a local plane (enough at the scale of a compound).
M_LAT = 110574.0
M_LON_EQ = 111320.0


def dist_m(lat1, lng1, lat2, lng2):
    """Distance used for doors and entrances (80 m rule): one metre-per-degree
    figure on both axes, longitude scaled at the mean latitude."""
    dy = (lat2 - lat1) * 111320.0
    dx = (lng2 - lng1) * 111320.0 * math.cos((lat1 + lat2) / 2 * math.pi / 180)
    return math.hypot(dx, dy)


def ground_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres (mean Earth radius); used to find the
    code at a point and the codes near a point."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(min(1.0, math.sqrt(a)))


def ring_area(ring):
    """Area in m2 of an outline [[lng, lat], ...] (shoelace on a local plane,
    longitude scaled at the first vertex)."""
    if len(ring) < 3:
        return 0.0
    k = math.cos(ring[0][1] * math.pi / 180)
    a = 0.0
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = ring[i][0] * M_LON_EQ * k, ring[i][1] * M_LAT
        xj, yj = ring[j][0] * M_LON_EQ * k, ring[j][1] * M_LAT
        a += xi * yj - xj * yi
    return abs(a) / 2


def ring_perimeter(ring):
    n = len(ring)
    return sum(dist_m(ring[i][1], ring[i][0], ring[(i + 1) % n][1], ring[(i + 1) % n][0]) for i in range(n))


def in_ring(x, y, ring):
    """Even-odd test of the point (x = lng, y = lat) against one ring."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def overlap_share(a, b, step_m=0.5):
    """Share of the smaller of two outlines covered by the other, estimated on
    a grid of step_m metres over the smaller one's box. An outline that covers
    more than half of an existing one (or is more than half inside it) is the
    same building."""
    small, big = (a, b) if ring_area(a) <= ring_area(b) else (b, a)
    xs, ys = [p[0] for p in small], [p[1] for p in small]
    k = math.cos(math.radians(sum(ys) / len(ys)))
    dx, dy = step_m / (M_LON_EQ * k), step_m / M_LAT
    total = hit = 0
    y = min(ys) + dy / 2
    while y < max(ys):
        x = min(xs) + dx / 2
        while x < max(xs):
            if in_ring(x, y, small):
                total += 1
                if in_ring(x, y, big):
                    hit += 1
            x += dx
        y += dy
    return hit / total if total else 0.0


class Outline:
    """Côte d'Ivoire's national border (engine/data/outline.geojson: the
    OpenStreetMap admin_level 2 boundary, simplified to about 50 m). A point
    belongs to the country when its entrance is inside the border or within
    300 m of it (border.BORDER_M), measured against the simplified line less
    its recorded deviation (maxDeviationM), so a point more than 300 m outside
    the true border is always refused. Zone outlines never decide."""

    def __init__(self, path):
        self.border = border.Border(path)

    def outside_m(self, lat, lng):
        return self.border.outside_m(lat, lng)

    def contains(self, lat, lng):
        return self.border.allows(lat, lng)


def default_outline(repo):
    return Outline(os.path.join(repo, 'engine', 'data', 'outline.geojson'))
