"""The register in force, read from the database, in the shape the reference
engine (engine/reference/ci_engine.py) works on.

The server never re-implements a rule of the engine: name keys, check digits,
the forms of a code, parsing, spot codes, the Hilbert order, block sizes and
the choice of a number all come from ci_engine. This module only loads the
frozen areas and their blocks (including blocks added by this deployment)
into a ci_engine.Model, and adds the one step the engine leaves to the
issuer: trying an area's blocks in turn before taking a new one (`insert`).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import ci_engine as ref  # noqa: E402

from . import geo  # noqa: E402

COUNTRY = 'CI'
COUNTRY_NAME = "Côte d'Ivoire"
CREDIT = "N-Ways Addressing for Côte d'Ivoire, © N-WAYS LIMITED (nways.ng)"
CREDIT_URL = 'https://github.com/n-ways/open-addresses-cote-divoire'
ENGINE = 'internal/addressing/ci (SPEC v1.0)'
LICENCES = {'data': 'ODbL 1.0 (LICENSE-DATA)', 'code': 'Apache-2.0 (LICENSE, NOTICE)', 'documents': 'CC BY 4.0 (LICENSE-DOCS)'}


def parse_blocks(s):
    out = []
    for part in s.split('|'):
        lo, hi = part.split('-')
        out.append((int(lo), int(hi)))
    return out


def format_blocks(blocks):
    return '|'.join('%d-%d' % (lo, hi) for lo, hi in blocks)


class Register(ref.Model):
    """A ci_engine.Model built from the database instead of model/.

    Attributes the engine reads (units, areas, blocks, area_blocks, area_key,
    key_digits, aliases, refs, by_ref_name, shapes) are filled exactly as
    Model.__init__ fills them from the CSV files; on top of them:
      zones      unit code -> unit record (a zone of the API is a unit: a
                 sous-préfecture, or a commune of Abidjan)
      by_zone    area id ("010114-083") -> area record
      by_area_id numeric area id -> area record
      names      name key -> {'id', 'plate', 'digits'}
    """

    def __init__(self, conn, repo=REPO):  # noqa: D401  (Model.__init__ is replaced on purpose)
        self.units, self.refs, self.by_ref_name = {}, {}, {}
        for code, name, kind, dep, region, rname, rlat, rlon in conn.execute(
                'SELECT code, name, kind, departement, region, ref, ref_lat, ref_lon FROM units ORDER BY code'):
            self.units[code] = {'code': code, 'name': name, 'kind': kind, 'departement': dep, 'region': region}
            if rlat is not None and rlon is not None:
                self.refs[code] = (rname, rlat, rlon)
                self.by_ref_name.setdefault(ref._fold(rname), []).append(code)
        self.names = {}
        for nid, key, plate, digits in conn.execute('SELECT id, key, plate, digits FROM names'):
            self.names[key] = {'id': nid, 'plate': plate, 'digits': digits}
        self.areas, self.blocks, self.area_blocks, self.area_key, self.key_digits = {}, {}, {}, {}, {}
        self.by_zone, self.by_area_id = {}, {}
        for row in conn.execute('''SELECT zone, area_id, unit, idx, plate_name, official_name, name_key, name_id, blocks,
                needs_council_choice, place_lat, place_lon, frame FROM areas ORDER BY ord'''):
            self._add_area(*row)
        for v in self.blocks.values():
            v.sort()
        self.aliases = {}
        for akey, official, plate_key, areas in conn.execute('SELECT key, official, plate_key, areas FROM aliases'):
            ids = json.loads(areas)
            self.aliases[akey] = (plate_key, {(self.by_area_id[i]['unit'], self.by_area_id[i]['index']) for i in ids
                                              if i in self.by_area_id})
        self.shapes = []
        self._load_shapes(os.path.join(repo, 'model', 'units'))

    def _add_area(self, zone, area_id, unit, idx, plate, official, key, name_id, blocks, ncc, lat, lon, frame):
        a = {'zone': zone, 'id': area_id, 'unit': unit, 'index': idx, 'plate': plate, 'name': official, 'key': key,
             'nameId': name_id, 'blocks': parse_blocks(blocks), 'needsCouncilChoice': bool(ncc), 'lat': lat, 'lon': lon,
             'frame': tuple(float(x) for x in frame.split()), 'digits': self.names[key]['digits']}
        self.areas.setdefault(unit, []).append(a)
        self.by_zone[zone] = a
        self.by_area_id[area_id] = a
        self.area_key[(unit, idx)] = key
        self.key_digits.setdefault(key, a['digits'])
        for lo, hi in a['blocks']:
            self.blocks.setdefault(key, []).append((lo, hi, unit, idx))
            self.area_blocks.setdefault((unit, idx), []).append((lo, hi))

    def _load_shapes(self, units_dir):
        """Unit polygons for ci_engine.Model.unit_at (spot codes report their unit)."""
        try:
            with open(os.path.join(units_dir, 'abidjan-communes.geojson'), encoding='utf-8') as fh:
                feats = json.load(fh)['features']
            feats.sort(key=lambda f: f['properties']['name'])
            for n, f in enumerate(feats):
                ps = ref._polys(f['geometry'])
                self.shapes.append(('0101%02d' % (11 + n), ps, ref._box(ps)))
            with open(os.path.join(units_dir, 'sous-prefectures.geojson'), encoding='utf-8') as fh:
                for f in json.load(fh)['features']:
                    ps = ref._polys(f['geometry'])
                    self.shapes.append((f['properties']['pcode'][2:], ps, ref._box(ps)))
        except FileNotFoundError:
            self.shapes = []

    # ------------------------------------------------------------ forms

    def forms(self, area, number):
        """Every form of a code (SPEC 2), from the engine."""
        key = area['key']
        unit_name = self.units[area['unit']]['name']
        return {
            'machine': ref.machine(area['unit'], area['index'], number, key),
            'home': '%s %d' % (area['plate'], number),
            'remembered': ref.remembered(area['plate'], number),
            'written': ref.written(area['plate'], number, key, unit_name),
            'spoken': '%s, %s' % (area['plate'], ref.spoken_number(number)),
            'check': ref.check_digit(key, number),
        }

    def spot_short(self, lat, lng):
        """The spot code as the registry prints it: short against the nearest
        reference town ("926H+7Q7 Cocody"), else the full code."""
        return ref.spot(self, lat, lng).get('short') or ref.olc_encode(lat, lng, ref.SPOT_LENGTH)

    def nearest_area(self, lat, lng):
        """The code area whose place point is nearest (equirectangular metres,
        ties to the lower area id): where a new compound goes when no issued
        code lies within 250 m."""
        best, bd = None, math.inf
        k = math.cos(lat * math.pi / 180)
        for a in self.by_area_id.values():
            d = math.hypot((a['lat'] - lat) * geo.M_LAT, (a['lon'] - lng) * geo.M_LON_EQ * k)
            if d < bd or (d == bd and best is not None and a['id'] < best['id']):
                best, bd = a, d
        return best

    # ------------------------------------------------------------ numbering

    def insert(self, area, issued, lat, lng):
        """The number of a new compound of an area (SPEC 5, after issue).

        issued: [(number, lat, lng)] of every number the area holds, retired
        ones included (a number is never given twice). The area's blocks are
        tried in turn with the engine's rule (the free number between the new
        compound's neighbours on the Hilbert curve, else the block's tail
        reserve); when all are full, the engine gives the next block of the
        name (ci_engine.next_block) and the compound takes its first number.
        Returns (number, new block or None), or (None, None) when the name has
        no room left (it then needs a qualifier)."""
        frame = area['frame']
        for lo, hi in area['blocks']:
            inside = [{'number': n, 'h': ref.frame_hilbert(frame, x, y)} for n, y, x in issued if lo <= n <= hi]
            lo_, main_hi, hi_ = ref.block_layout((lo, hi))
            reg = {'compounds': inside, 'range': [lo_, hi_], 'tailReserve': [main_hi + 1, hi_]}
            try:
                return ref.provisional_number(reg, frame, lng, lat), None
            except ValueError:
                continue
        nb = ref.next_block(self, area['key'], len(issued) + 1)
        if nb is None:
            return None, None
        return nb[0], nb

    def add_block(self, area, block):
        """Record a block taken by `insert` (the caller stores it first)."""
        lo, hi = block
        area['blocks'].append((lo, hi))
        self.blocks.setdefault(area['key'], []).append((lo, hi, area['unit'], area['index']))
        self.blocks[area['key']].sort()
        self.area_blocks.setdefault((area['unit'], area['index']), []).append((lo, hi))
