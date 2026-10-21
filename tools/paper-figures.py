#!/usr/bin/env python3
"""The data behind the paper's figures, written next to their TikZ sources in docs/figures/.

  python3 tools/paper-figures.py

Reads registry/, engine/data/register.json, model/ and model/stats/; standard library only.

  map.tex              sous-préfectures shaded by compounds per km² (polygons simplified
                       with Douglas-Peucker at 0.004°), with the reference towns of the
                       largest cities; written as a complete TikZ source
  area-sizes.dat       areas by compounds, in logarithmic bins
  bonoumin.dat         the compounds of Bonoumin (010114-083): metres east and north of the
                       frame's south-west corner, number, in number order
  ranges.tex           the national ranges of Bonoumin and Belleville: blocks, tail reserves,
                       skipped stretch and spare; written as a complete TikZ source
  spot.dat             the entrances inside the Plus Code cell 6CQR926H, in metres
  sources.dat          footprints per region: OpenStreetMap and the machine-learned layers
  plate-lengths.dat    characters of the official name and of the plate name, per area
  *-fr.tex             the French figures of docs/paper.fr.md: each source above with its
                       labels in French and decimal commas (sources-fr.dat for the regions)
"""
import collections, csv, gzip, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, 'docs', 'figures')
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as E  # noqa: E402

KLAT = 110574.0
KLON = 111320.0


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def simplify(pts, tol):
    """Douglas-Peucker on a ring of (x, y)."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1e-12
        best, idx = 0.0, None
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if (dx or dy) else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def ring_area_km2(ring):
    lat0 = sum(p[1] for p in ring) / len(ring)
    k = math.cos(math.radians(lat0))
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        s += (x1 * KLON * k) * (y2 * KLAT) - (x2 * KLON * k) * (y1 * KLAT)
    return abs(s) / 2e6


def rings(geom):
    if geom['type'] == 'Polygon':
        return [geom['coordinates']]
    return geom['coordinates']


def write_map(byunit):
    sp = load(os.path.join(REPO, 'model', 'units', 'sous-prefectures.geojson'))['features']
    abidjan = sum(v for k, v in byunit.items() if k.startswith('0101') and k >= '010111') + byunit.get('010101', 0)
    # colour bins: compounds per km²
    bins = [(0, 5), (5, 10), (10, 20), (20, 50), (50, 200), (200, 1e9)]
    colours = ['FDF1E3', 'FBD9B0', 'F8B26A', 'F28A2E', 'C9620A', '7A3A05']
    k = math.cos(math.radians(7.5))
    sc = 1.9  # cm per degree of latitude

    def xy(p):
        return '(%.3f,%.3f)' % ((p[0] + 8.7) * k * sc, (p[1] - 4.3) * sc)

    lines = []
    counts = collections.Counter()
    for f in sp:
        code = f['properties']['pcode'][2:]
        n = abidjan if code == '010101' else byunit.get(code, 0)
        polys = rings(f['geometry'])
        area = sum(ring_area_km2([tuple(p) for p in poly[0]]) - sum(ring_area_km2([tuple(p) for p in h]) for h in poly[1:]) for poly in polys)
        dens = n / area if area else 0
        b = next(i for i, (lo, hi) in enumerate(bins) if lo <= dens < hi)
        counts[b] += 1
        for poly in polys:
            ring = simplify([tuple(p) for p in poly[0]], 0.004)
            if len(ring) < 4:
                continue
            lines.append('\\fill[c%d,draw=white,line width=0.15pt] %s -- cycle;' % (b, ' -- '.join(xy(p) for p in ring[:-1])))
    towns = [('Abidjan', -4.008, 5.32, 'above left'), ('Bouaké', -5.028355, 7.689021, 'right'),
             ('Yamoussoukro', -5.277603, 6.820007, 'left'), ('Daloa', -6.452986, 6.886923, 'left'),
             ('Korhogo', -5.631629, 9.45807, 'right'), ('San-Pédro', -6.646392, 4.758999, 'below'),
             ('Man', -7.550372, 7.410258, 'left'), ('Odienné', -7.561942, 9.504431, 'right')]
    for name, lon, lat, pos in towns:
        lines.append('\\fill[black] %s circle (0.6pt) node[%s,font=\\scriptsize,inner sep=1pt,fill=white,fill opacity=0.75,text opacity=1] {%s};' % (xy((lon, lat)), pos, name))
    labels = ['$<5$', '5--10', '10--20', '20--50', '50--200', '$\\geq 200$']
    legend = []
    for i, lab in enumerate(labels):
        y = 0.4 + i * 0.42
        legend.append('\\fill[c%d,draw=black!30,line width=0.2pt] (12.3,%.2f) rectangle (12.75,%.2f); \\node[right,font=\\scriptsize] at (12.8,%.2f) {%s};' % (i, y, y + 0.32, y + 0.16, lab))
    legend.append('\\node[right,font=\\scriptsize,align=left] at (12.25,3.15) {Compounds\\\\per km\\textsuperscript{2}};')
    with open(os.path.join(OUT, 'map.tex'), 'w', encoding='utf-8') as f:
        f.write('% Compounds per km2 in each of the 510 sous-préfectures (the Abidjan sous-préfecture with its ten communes).\n')
        f.write('% Written by tools/paper-figures.py from registry/MANIFEST.json and model/units/; do not edit by hand.\n')
        f.write('\\documentclass[tikz,border=2mm]{standalone}\n\\usepackage{fontspec}\\setmainfont{LibertinusSans}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold]\n')
        for i, c in enumerate(colours):
            f.write('\\definecolor{c%d}{HTML}{%s}\n' % (i, c))
        f.write('\\begin{document}\n\\begin{tikzpicture}\n')
        f.write('\n'.join(lines + legend))
        f.write('\n\\end{tikzpicture}\n\\end{document}\n')
    return dict(counts)


def write_area_sizes(reg):
    edges = [1, 10, 30, 100, 300, 1000, 3000, 10000, 30000]
    counts = [0] * (len(edges) - 1)
    for a in reg['areas']:
        c = a['compounds']
        if c <= 0:
            continue
        for i in range(len(edges) - 1):
            if edges[i] <= c < edges[i + 1]:
                counts[i] += 1
    with open(os.path.join(OUT, 'area-sizes.dat'), 'w') as f:
        f.write('# compounds per code area (lower edge of the bin), areas in the bin; areas with no compound left out\n')
        f.write('lo hi areas\n')
        for i, n in enumerate(counts):
            f.write('%d %d %d\n' % (edges[i], edges[i + 1], n))
    return counts


def write_bonoumin(reg):
    a = next(x for x in reg['areas'] if x['aid'] == '010114-083')
    x0, y0, x1, y1 = a['frame']
    k = math.cos(math.radians((y0 + y1) / 2))
    rows = []
    with gzip.open(os.path.join(REPO, 'registry', '010114.csv.gz'), 'rt', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['zone'] == '010114-083':
                rows.append(((float(r['entrance_lng']) - x0) * KLON * k, (float(r['entrance_lat']) - y0) * KLAT, int(r['number'])))
    rows.sort(key=lambda t: t[2])
    with open(os.path.join(OUT, 'bonoumin.dat'), 'w') as f:
        f.write('# Bonoumin (Cocody), area 010114-083: every compound, metres east and north of the frame corner (%.6f, %.6f)\n' % (x0, y0))
        f.write('# frame %.0f m x %.0f m\n' % ((x1 - x0) * KLON * k, (y1 - y0) * KLAT))
        f.write('x y n\n')
        for x, y, n in rows:
            f.write('%.1f %.1f %d\n' % (x, y, n))
    return len(rows), ((x1 - x0) * KLON * k, (y1 - y0) * KLAT)


def write_ranges():
    blocks = collections.defaultdict(list)
    with open(os.path.join(REPO, 'model', 'areas', 'name-blocks.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['key'] in ('bonoumin', 'belevile'):
                blocks[r['key']].append((int(r['block_lo']), int(r['block_hi']), r['unit']))
    units = {}
    with open(os.path.join(REPO, 'model', 'areas', 'admin-units.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            units[r['code']] = r['name']
    out = []

    def bar(y, lo_space, hi_space, bl, width, label, skipped=None):
        span = hi_space - lo_space + 1

        def X(v):
            return (v - lo_space) / span * width
        out.append('\\node[left,font=\\small\\bfseries] at (-0.1,%.2f) {%s};' % (y + 0.3, label))
        out.append('\\draw[black!40,line width=0.3pt,fill=black!3] (0,%.2f) rectangle (%.3f,%.2f);' % (y, width, y + 0.6))
        if skipped:
            out.append('\\fill[pattern=north east lines,pattern color=black!35] (%.3f,%.2f) rectangle (%.3f,%.2f);' % (X(skipped[0]), y, X(skipped[1] + 1), y + 0.6))
            out.append('\\node[font=\\scriptsize,fill=white,inner sep=1pt] at (%.3f,%.2f) {set aside};' % ((X(skipped[0]) + X(skipped[1] + 1)) / 2, y + 0.3))
        for i, (lo, hi, unit) in enumerate(sorted(bl)):
            tail = lo + (hi - lo + 1) * 2 // 3
            out.append('\\fill[blk] (%.3f,%.2f) rectangle (%.3f,%.2f);' % (X(lo), y, X(tail), y + 0.6))
            out.append('\\fill[tail] (%.3f,%.2f) rectangle (%.3f,%.2f);' % (X(tail), y, X(hi + 1), y + 0.6))
            out.append('\\draw[white,line width=0.6pt] (%.3f,%.2f) -- (%.3f,%.2f);' % (X(lo), y, X(lo), y + 0.6))
            out.append('\\node[font=\\tiny,rotate=90,anchor=east] at (%.3f,%.2f) {%s};' % ((X(lo) + X(hi + 1)) / 2, y - 0.05, units[unit]))
        top = max(b[1] for b in bl)
        out.append('\\node[font=\\scriptsize] at (%.3f,%.2f) {spare};' % ((X(top + 1) + width) / 2, y + 0.3))
        for v in (lo_space, hi_space + 1):
            out.append('\\node[font=\\scriptsize,above] at (%.3f,%.2f) {%d};' % (X(v), y + 0.6, v if v != hi_space + 1 else hi_space))
        for lo, hi, _ in sorted(bl):
            out.append('\\draw[black!50] (%.3f,%.2f) -- ++(0,0.08);' % (X(lo), y + 0.6))
    bar(3.2, 1000, 9999, blocks['bonoumin'], 13.0, 'Bonoumin')
    bar(0.0, 10000, 99999, blocks['belevile'], 13.0, 'Belleville', skipped=(10000, 29999))
    legend = ('\\fill[blk] (0,-2.2) rectangle (0.4,-1.95); \\node[right,font=\\scriptsize] at (0.45,-2.075) {numbers given at first issue};'
              '\\fill[tail] (4.2,-2.2) rectangle (4.6,-1.95); \\node[right,font=\\scriptsize] at (4.65,-2.075) {tail reserve (top third of a block)};'
              '\\fill[black!3,draw=black!40,line width=0.3pt] (9.2,-2.2) rectangle (9.6,-1.95); \\node[right,font=\\scriptsize] at (9.65,-2.075) {spare of the name};')
    with open(os.path.join(OUT, 'ranges.tex'), 'w', encoding='utf-8') as f:
        f.write('% The national ranges of two names, from model/areas/name-blocks.csv.\n')
        f.write('% Written by tools/paper-figures.py; do not edit by hand.\n')
        f.write('\\documentclass[tikz,border=2mm]{standalone}\n\\usepackage{fontspec}\\setmainfont{LibertinusSans}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold]\n')
        f.write('\\usetikzlibrary{patterns}\n\\definecolor{blk}{HTML}{009E60}\n\\definecolor{tail}{HTML}{8FD3B4}\n')
        f.write('\\begin{document}\n\\begin{tikzpicture}\n' + '\n'.join(out) + '\n' + legend + '\n\\end{tikzpicture}\n\\end{document}\n')
    return {k: sorted(v) for k, v in blocks.items()}


def write_spot_points():
    # The cell 6CQR926H spans 0.0025 degrees in latitude and longitude; its south-west corner
    # follows from the code: 6C -> (-90+4*20, -180+8*20), QR -> +15, +16, 92 -> +7*0.05, +0*0.05,
    # 6H -> +4*0.0025, +11*0.0025.
    lat0 = -90 + 4 * 20 + 15 + 7 * 0.05 + 4 * 0.0025
    lng0 = -180 + 8 * 20 + 16 + 0 * 0.05 + 11 * 0.0025
    k = math.cos(math.radians(lat0))
    pts = []
    for unit in ('010114',):
        with gzip.open(os.path.join(REPO, 'registry', unit + '.csv.gz'), 'rt', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                la, lo = float(r['entrance_lat']), float(r['entrance_lng'])
                if lat0 <= la < lat0 + 0.0025 and lng0 <= lo < lng0 + 0.0025:
                    pts.append(((lo - lng0) * KLON * k, (la - lat0) * KLAT, r['remembered']))
    with open(os.path.join(OUT, 'spot.dat'), 'w', encoding='utf-8') as f:
        f.write('# entrances inside the Plus Code cell 6CQR926H (south-west corner %.4f, %.4f), metres east and north\n' % (lat0, lng0))
        f.write('# cell %.1f m east-west x %.1f m north-south\n' % (0.0025 * KLON * k, 0.0025 * KLAT))
        f.write('x y\n')
        for x, y, _ in pts:
            f.write('%.2f %.2f\n' % (x, y))
    return len(pts), (lat0, lng0)


def write_sources(stats):
    regs = dict(stats['regions'])
    a, b = regs.pop('Abidjan'), regs.pop("District Autonome D'Abidjan")
    merged = {'structures': a['structures'] + b['structures'], 'fromOpenStreetMap': a['fromOpenStreetMap'] + b['fromOpenStreetMap']}
    regs['District of Abidjan'] = merged
    regs['District of Yamoussoukro'] = regs.pop('District Autonome De Yamoussoukro')
    rows = sorted(regs.items(), key=lambda kv: kv[1]['structures'])
    with open(os.path.join(OUT, 'sources.dat'), 'w', encoding='utf-8') as f:
        f.write('# footprints per region, thousands: from OpenStreetMap, from the Google and Microsoft layers\n')
        f.write('region osm ml\n')
        for name, v in rows:
            f.write('{%s} %.1f %.1f\n' % (name, v['fromOpenStreetMap'] / 1000, (v['structures'] - v['fromOpenStreetMap']) / 1000))
    return len(rows)


def write_plate_lengths():
    off, pl = collections.Counter(), collections.Counter()
    with open(os.path.join(REPO, 'model', 'areas', 'areas.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            off[min(len(r['name']), 40)] += 1
            pl[min(len(r['plate']), 40)] += 1
    with open(os.path.join(OUT, 'plate-lengths.dat'), 'w') as f:
        f.write('# areas by characters of the official name and of the plate name (40 = 40 or more)\n')
        f.write('chars official plate\n')
        for n in range(1, 41):
            f.write('%d %d %d\n' % (n, off[n], pl[n]))
    return sum(v for k, v in off.items() if k > 12), sum(v for k, v in pl.items() if k > 12)


FRENCH = {
    'map': [('{Compounds\\\\per km', '{Concessions\\\\par km')],
    'area-sizes': [('xlabel={Compounds in the code area}', 'xlabel={Concessions dans la zone}'),
                   ('ylabel={Code areas}', 'ylabel={Zones}'),
                   ('{4\\,500: largest area\\\\a 4-digit block can hold}', '{4\\,500 : plus grande zone\\\\pour un bloc à 4 chiffres}'),
                   ('xticklabels={1,10,100,1\\,000,10\\,000}', 'xticklabels={1,10,100,1\\,000,10\\,000}')],
    'bonoumin': [('xlabel={metres east}', "xlabel={mètres vers l'est}"), ('ylabel={metres north}', 'ylabel={mètres vers le nord}'),
                 ('ylabel={number}', 'ylabel={numéro}')],
    'spot': [("xlabel={metres east of 6CQR926H's south-west corner}", "xlabel={mètres à l'est du coin sud-ouest de 6CQR926H}"),
             ('ylabel={metres north}', 'ylabel={mètres vers le nord}')],
    'sources': [('xlabel={footprints (thousands)}', 'xlabel={empreintes (milliers)}'),
                ('Google Open Buildings and Microsoft', 'Google Open Buildings et Microsoft'),
                ('sources.dat', 'sources-fr.dat')],
    'plate-lengths': [('xlabel={characters (40 = 40 or more)}', 'xlabel={caractères (40 = 40 ou plus)}'),
                      ('ylabel={code areas}', 'ylabel={zones}'), ('{limit: 12}', '{limite : 12}'),
                      ('\\legend{official name,plate name}', '\\legend{nom officiel,nom de plaque}')],
    'ranges': [('{set aside}', '{écartée}'), ('{spare}', '{réserve}'),
               ('{numbers given at first issue}', '{numéros de la première émission}'),
               ('{tail reserve (top third of a block)}', '{réserve de fin (tiers supérieur)}'),
               ('{spare of the name}', '{réserve du nom}')],
}
NUMBER_FR = '\\pgfplotsset{compat=1.18,/pgf/number format/.cd,use comma,1000 sep={\\,}}'


def write_french():
    """docs/figures/<name>-fr.tex from <name>.tex: the same figure with French labels."""
    with open(os.path.join(OUT, 'sources.dat'), encoding='utf-8') as f:
        rows = f.read()
    rows = rows.replace('{District of Abidjan}', "{District d'Abidjan}").replace('{District of Yamoussoukro}', '{District de Yamoussoukro}')
    rows = rows.replace('footprints per region, thousands: from OpenStreetMap, from the Google and Microsoft layers',
                        'empreintes par région, en milliers : OpenStreetMap, couches Google et Microsoft')
    with open(os.path.join(OUT, 'sources-fr.dat'), 'w', encoding='utf-8') as f:
        f.write(rows)
    for name, pairs in FRENCH.items():
        with open(os.path.join(OUT, name + '.tex'), encoding='utf-8') as f:
            text = f.read()
        for a, b in pairs:
            if a not in text:
                raise ValueError('%s.tex: label %r not found' % (name, a))
            text = text.replace(a, b)
        text = text.replace('\\pgfplotsset{compat=1.18}', NUMBER_FR)
        text = '% French labels; written by tools/paper-figures.py from ' + name + '.tex.\n' + text
        with open(os.path.join(OUT, name + '-fr.tex'), 'w', encoding='utf-8') as f:
            f.write(text)


def main():
    os.makedirs(OUT, exist_ok=True)
    reg = load(os.path.join(REPO, 'engine', 'data', 'register.json'))
    manifest = load(os.path.join(REPO, 'registry', 'MANIFEST.json'))
    stats = load(os.path.join(REPO, 'model', 'stats', 'building-stats.json'))
    print('map bins', write_map(manifest['byUnit']))
    print('area sizes', write_area_sizes(reg))
    print('bonoumin', write_bonoumin(reg))
    print('ranges', write_ranges())
    print('spot', write_spot_points())
    print('regions', write_sources(stats))
    print('plate names over 12 characters (official, plate)', write_plate_lengths())
    write_french()


if __name__ == '__main__':
    main()
