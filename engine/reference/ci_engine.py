#!/usr/bin/env python3
"""N-Ways address engine for Côte d'Ivoire: the reference implementation.

Standard library only. Works offline from the files in model/ of this repository.

What it does (engine/SPEC.md has the rules):
  * spot codes: Open Location Code (Plus Codes), implemented here, 11 characters
    (about 3.5 m x 2.8 m), shown short against the sous-préfecture / commune
    reference town ("MX9V+XX7 Bouaké");
  * code areas: point -> sous-préfecture or Abidjan commune -> named place
    (quartier / village) whose interim cell contains the point;
  * compound registry: groups footprints into compounds, orders compounds
    along a Hilbert curve inside the area frame and numbers them with infill
    gaps and a tail reserve; provisional numbers for new homes;
  * plate names: each area has an official name (small print, never needed)
    and a short PLATE name, at most 12 characters and 2 words, used in the
    code; the official name typed instead still decodes (alias) when it names
    one plate name only (plate_names.py);
  * national name ranges: every area sharing a plate-name key draws a frozen
    block from one national range for that name, so "Name NNNN" alone is
    unique in the country;
  * code forms: remembered ("Sicogi · 18 17"), written ("Sicogi 18 17
    (Yopougon)"), and machine ("CI-010120-034-1817-c", c a Damm check digit over
    the name key and the number, for systems only); parsing and validation;
  * a first building profile (use class, size, floors) from the inputs.

Command line:
  python3 ci_engine.py spot LAT LON
  python3 ci_engine.py locate LAT LON
  python3 ci_engine.py decode-spot "MX9V+XXR Bouaké"
  python3 ci_engine.py check Sicogi 1817
  python3 ci_engine.py parse "Madina 4600"
  python3 ci_engine.py registry engine/reference/sample-cocody-riviera.csv
"""
import collections, csv
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MODEL = os.path.join(REPO, 'model')
sys.path.insert(0, HERE)
import plate_names  # noqa: E402

# Côte d'Ivoire names carry numbers people say ("Riviéra 2", "Zone 4"): a plate
# name may hold one number word (plate_names.NUMBER_WORDS).
plate_names.NUMBER_WORDS = 1
PLATE_MAX_CHARS, PLATE_MAX_WORDS = plate_names.MAX_CHARS, plate_names.MAX_WORDS


def plate_ok(name):
    """A plate name within the limit: at most 12 characters (an accented letter,
    a space, a hyphen or an apostrophe count one each), at most 2 words (linking
    words do not count, a hyphen separates words), at most one number word."""
    return plate_names.fits(name, 'fr')

# ---------------------------------------------------------------------------
# Damm check digit (quasigroup of order 10, Damm 2004). Detects every single
# wrong digit and every swap of two neighbouring digits.
# ---------------------------------------------------------------------------
DAMM = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2),
    (7, 0, 9, 2, 1, 5, 4, 8, 6, 3),
    (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6),
    (6, 1, 2, 3, 0, 4, 5, 9, 7, 8),
    (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4),
    (8, 9, 4, 5, 3, 6, 2, 0, 1, 7),
    (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)


def damm(digits):
    """Check digit for a string of digits."""
    interim = 0
    for ch in digits:
        interim = DAMM[interim][int(ch)]
    return interim


def damm_ok(digits_with_check):
    return damm(digits_with_check) == 0


# ---------------------------------------------------------------------------
# Open Location Code (Plus Codes), after the public specification
# (github.com/google/open-location-code, Apache-2.0). Re-implemented here.
# ---------------------------------------------------------------------------
OLC_ALPHABET = '23456789CFGHJMPQRVWX'
SEP, SEP_POS, PAD = '+', 8, '0'
BASE = 20
LAT_MAX, LNG_MAX = 90, 180
PAIR_LEN = 10
GRID_LEN = 5
MAX_DIGITS = PAIR_LEN + GRID_LEN  # 15
GRID_ROWS, GRID_COLS = 5, 4
PAIR_PRECISION = BASE ** 3  # 8000 units per degree after the pairs
PAIR_FIRST_VALUE = BASE ** 4  # 160000
FINAL_LAT_PRECISION = PAIR_PRECISION * GRID_ROWS ** GRID_LEN  # 25,000,000
FINAL_LNG_PRECISION = PAIR_PRECISION * GRID_COLS ** GRID_LEN  # 8,192,000
GRID_LAT_FIRST = GRID_ROWS ** (GRID_LEN - 1)
GRID_LNG_FIRST = GRID_COLS ** (GRID_LEN - 1)
PAIR_RESOLUTIONS = (20.0, 1.0, 0.05, 0.0025, 0.000125)
SPOT_LENGTH = 11


class CodeArea:
    def __init__(self, lat_lo, lng_lo, lat_hi, lng_hi, length):
        self.lat_lo, self.lng_lo, self.lat_hi, self.lng_hi, self.length = lat_lo, lng_lo, lat_hi, lng_hi, length
        self.lat = min(lat_lo + (lat_hi - lat_lo) / 2, LAT_MAX)
        self.lng = min(lng_lo + (lng_hi - lng_lo) / 2, LNG_MAX)


def _clip_lat(lat):
    return min(90.0, max(-90.0, lat))


def _norm_lng(lng):
    while lng < -180:
        lng += 360
    while lng >= 180:
        lng -= 360
    return lng


def _lat_precision(length):
    if length <= PAIR_LEN:
        return BASE ** (length // -2 + 2)
    return BASE ** -3 / GRID_ROWS ** (length - PAIR_LEN)


def olc_is_valid(code):
    if not code or code.count(SEP) != 1:
        return False
    s = code.find(SEP)
    if s > SEP_POS or s % 2 == 1:
        return False
    if PAD in code:
        p = code.find(PAD)
        if p == 0 or p % 2 == 1:
            return False
        pads = re.findall(PAD + '+', code)
        if len(pads) > 1 or len(pads[0]) % 2 == 1 or len(pads[0]) > SEP_POS - 2:
            return False
        if not code.endswith(SEP):
            return False
    if len(code) - s - 1 == 1:
        return False
    return all(c in OLC_ALPHABET for c in code.upper().replace(SEP, '').replace(PAD, ''))


def olc_is_short(code):
    return olc_is_valid(code) and 0 <= code.find(SEP) < SEP_POS


def olc_is_full(code):
    if not olc_is_valid(code) or olc_is_short(code):
        return False
    c = code.upper()
    if OLC_ALPHABET.find(c[0]) * BASE >= LAT_MAX * 2:
        return False
    if len(c) > 1 and OLC_ALPHABET.find(c[1]) * BASE >= LNG_MAX * 2:
        return False
    return True


def olc_encode(lat, lng, length=PAIR_LEN):
    if length < 2 or (length < PAIR_LEN and length % 2 == 1):
        raise ValueError('invalid code length')
    length = min(length, MAX_DIGITS)
    lat = _clip_lat(lat)
    lng = _norm_lng(lng)
    if lat == 90:
        lat -= _lat_precision(length)
    code = ''
    lat_val = int(round((lat + LAT_MAX) * FINAL_LAT_PRECISION, 6))
    lng_val = int(round((lng + LNG_MAX) * FINAL_LNG_PRECISION, 6))
    if length > PAIR_LEN:
        for _ in range(GRID_LEN):
            ndx = (lat_val % GRID_ROWS) * GRID_COLS + (lng_val % GRID_COLS)
            code = OLC_ALPHABET[ndx] + code
            lat_val //= GRID_ROWS
            lng_val //= GRID_COLS
    else:
        lat_val //= GRID_ROWS ** GRID_LEN
        lng_val //= GRID_COLS ** GRID_LEN
    for _ in range(PAIR_LEN // 2):
        code = OLC_ALPHABET[lng_val % BASE] + code
        code = OLC_ALPHABET[lat_val % BASE] + code
        lat_val //= BASE
        lng_val //= BASE
    code = code[:SEP_POS] + SEP + code[SEP_POS:]
    if length >= SEP_POS:
        return code[:length + 1]
    return code[:length] + PAD * (SEP_POS - length) + SEP


def olc_decode(code):
    if not olc_is_full(code):
        raise ValueError('not a full Plus Code: %r' % code)
    c = code.upper().replace(SEP, '').replace(PAD, '')
    norm_lat = -LAT_MAX * PAIR_PRECISION
    norm_lng = -LNG_MAX * PAIR_PRECISION
    grid_lat = grid_lng = 0
    digits = min(len(c), PAIR_LEN)
    pv = PAIR_FIRST_VALUE
    for i in range(0, digits, 2):
        norm_lat += OLC_ALPHABET.find(c[i]) * pv
        norm_lng += OLC_ALPHABET.find(c[i + 1]) * pv
        if i < digits - 2:
            pv //= BASE
    lat_prec = pv / PAIR_PRECISION
    lng_prec = pv / PAIR_PRECISION
    if len(c) > PAIR_LEN:
        rowpv, colpv = GRID_LAT_FIRST, GRID_LNG_FIRST
        digits = min(len(c), MAX_DIGITS)
        for i in range(PAIR_LEN, digits):
            v = OLC_ALPHABET.find(c[i])
            grid_lat += (v // GRID_COLS) * rowpv
            grid_lng += (v % GRID_COLS) * colpv
            if i < digits - 1:
                rowpv //= GRID_ROWS
                colpv //= GRID_COLS
        lat_prec = rowpv / FINAL_LAT_PRECISION
        lng_prec = colpv / FINAL_LNG_PRECISION
    lat = norm_lat / PAIR_PRECISION + grid_lat / FINAL_LAT_PRECISION
    lng = norm_lng / PAIR_PRECISION + grid_lng / FINAL_LNG_PRECISION
    return CodeArea(round(lat, 14), round(lng, 14), round(lat + lat_prec, 14), round(lng + lng_prec, 14),
                    min(len(c), MAX_DIGITS))


def olc_shorten(code, lat, lng):
    if not olc_is_full(code) or PAD in code:
        raise ValueError('cannot shorten %r' % code)
    code = code.upper()
    area = olc_decode(code)
    rng = max(abs(area.lat - _clip_lat(lat)), abs(area.lng - _norm_lng(lng)))
    for i in range(len(PAIR_RESOLUTIONS) - 2, 0, -1):
        if rng < PAIR_RESOLUTIONS[i] * 0.3:
            return code[(i + 1) * 2:]
    return code


def olc_recover(short, lat, lng):
    if not olc_is_short(short):
        if olc_is_full(short):
            return short.upper()
        raise ValueError('not a valid short code: %r' % short)
    lat = _clip_lat(lat)
    lng = _norm_lng(lng)
    short = short.upper()
    padding = SEP_POS - short.find(SEP)
    resolution = BASE ** (2 - padding / 2)
    half = resolution / 2.0
    area = olc_decode(olc_encode(lat, lng)[:padding] + short)
    clat, clng = area.lat, area.lng
    if lat + half < clat and clat - resolution >= -LAT_MAX:
        clat -= resolution
    elif lat - half > clat and clat + resolution <= LAT_MAX:
        clat += resolution
    if lng + half < clng:
        clng -= resolution
    elif lng - half > clng:
        clng += resolution
    return olc_encode(clat, clng, area.length)


# ---------------------------------------------------------------------------
# Model data: administrative units, code areas, reference towns
# ---------------------------------------------------------------------------
def _polys(g):
    return [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']


def _inside(x, y, ps):
    for P in ps:
        ins = False
        for ring in P:
            j = len(ring) - 1
            for i in range(len(ring)):
                xi, yi = ring[i][0], ring[i][1]
                xj, yj = ring[j][0], ring[j][1]
                if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    ins = not ins
                j = i
        if ins:
            return True
    return False


def _box(ps):
    xs = [c[0] for P in ps for c in P[0]]
    ys = [c[1] for P in ps for c in P[0]]
    return min(xs), min(ys), max(xs), max(ys)


def _rows(path):
    with open(path, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def _json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


class Model:
    """The offline tables an app would ship (a few MB for the whole country)."""

    def __init__(self, model_dir=MODEL):
        self.units = {}
        for r in _rows(os.path.join(model_dir, 'areas', 'admin-units.csv')):
            self.units[r['code']] = dict(r)
        self.shapes = []  # (code, polys, box), Abidjan communes first
        feats = _json(os.path.join(model_dir, 'units', 'abidjan-communes.geojson'))['features']
        feats.sort(key=lambda f: f['properties']['name'])
        for n, f in enumerate(feats):
            ps = _polys(f['geometry'])
            self.shapes.append(('0101%02d' % (11 + n), ps, _box(ps)))
        for f in _json(os.path.join(model_dir, 'units', 'sous-prefectures.geojson'))['features']:
            ps = _polys(f['geometry'])
            self.shapes.append((f['properties']['pcode'][2:], ps, _box(ps)))
        self.areas = {}
        for r in _rows(os.path.join(model_dir, 'areas', 'areas.csv')):
            r['lon'], r['lat'], r['digits'] = float(r['lon']), float(r['lat']), int(r['digits'])
            r['needsCouncilChoice'] = r['needsCouncilChoice'] == '1'
            r['plateCandidates'] = [c for c in r['plateCandidates'].split('|') if c]
            if not r['needsCouncilChoice'] and not plate_ok(r['plate']):
                # only an area waiting for its commune's choice may keep a long provisional name
                raise ValueError('plate name over the limit: %r (%s-%s)' % (r['plate'], r['unit'], r['index']))
            self.areas.setdefault(r['unit'], []).append(r)
        # National name ranges (SPEC.md 4.2): key -> blocks, each block owned by one area.
        self.blocks = {}      # key -> sorted [(lo, hi, unit, index)]
        self.area_blocks = {}  # (unit, index) -> [(lo, hi)]
        self.area_key = {}     # (unit, index) -> key
        self.key_digits = {}   # key -> 4 or 5 (length chosen at freezing)
        for r in _rows(os.path.join(model_dir, 'areas', 'name-blocks.csv')):
            lo, hi = int(r['block_lo']), int(r['block_hi'])
            self.blocks.setdefault(r['key'], []).append((lo, hi, r['unit'], r['index']))
            self.area_blocks.setdefault((r['unit'], r['index']), []).append((lo, hi))
            self.area_key[(r['unit'], r['index'])] = r['key']
            self.key_digits.setdefault(r['key'], int(r['digits']))
        for v in self.blocks.values():
            v.sort()
        # Official names typed instead of the plate name: alias key -> (plate key, areas).
        self.aliases = {}
        for r in _rows(os.path.join(model_dir, 'areas', 'plate-aliases.csv')):
            if r['status'] == 'kept':
                self.aliases[r['alias_key']] = (r['plate_key'], {tuple(x.split('-')) for x in r['areas'].split()})
        self.refs = {}
        for r in _rows(os.path.join(model_dir, 'areas', 'references.csv')):
            self.refs[r['unit']] = (r['name'], float(r['lat']), float(r['lon']))
        self.by_ref_name = {}
        for code, (name, lat, lon) in self.refs.items():
            self.by_ref_name.setdefault(_fold(name), []).append(code)

    def unit_at(self, lat, lon):
        for code, ps, b in self.shapes:
            if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and _inside(lon, lat, ps):
                return code
        return None

    def area_at(self, lat, lon):
        """Interim code area: the nearest named place of the same unit."""
        unit = self.unit_at(lat, lon)
        if unit is None:
            return None, None
        best = None
        k = math.cos(math.radians(lat))
        for a in self.areas.get(unit, []):
            d = ((a['lon'] - lon) * k) ** 2 + (a['lat'] - lat) ** 2
            if best is None or d < best[0]:
                best = (d, a)
        return unit, (best[1] if best else None)

    def area(self, unit, index):
        for a in self.areas.get(unit, []):
            if a['index'] == index:
                return a
        return None

    def plate_key(self, name):
        """The plate-name key a typed name stands for: its own key, or the plate
        key of the official name it is an alias of; None if unknown."""
        k = name_key(name)
        if k in self.blocks:
            return k
        if k in self.aliases:
            return self.aliases[k][0]
        return None

    def find_area_by_name(self, name):
        """Every area whose plate name has this national key (for search, not for decoding)."""
        k = name_key(name)
        if k in self.blocks:
            return [self.area(u, i) for _, _, u, i in self.blocks[k]]
        if k in self.aliases:
            return [self.area(u, i) for u, i in sorted(self.aliases[k][1])]
        return []

    def resolve(self, name, number):
        """'Name NNNN' -> the one area whose block holds the number, else None (SPEC.md 9).
        An official name typed instead of the plate name decodes only to an area
        that carries that official name."""
        k = name_key(name)
        alias = None
        if k not in self.blocks and k in self.aliases:
            k, alias = self.aliases[k]
        for lo, hi, unit, index in self.blocks.get(k, []):
            if lo <= number <= hi:
                if alias is not None and (unit, index) not in alias:
                    return None
                return self.area(unit, index)
        return None

    def block(self, unit, index):
        """The first (main) block of an area: (lo, hi)."""
        return self.area_blocks[(unit, index)][0]

    def owns(self, unit, index, number):
        return any(lo <= number <= hi for lo, hi in self.area_blocks.get((unit, index), []))

    def key_of(self, unit, index):
        return self.area_key[(unit, index)]


def _fold(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


# ---------------------------------------------------------------------------
# National name key (SPEC.md 4.1). Two area names with the same key are "the
# same name" and share one national number range. French plus the spellings
# of Akan (Baoulé, Agni), Mandé (Dioula, Malinké), Krou and Gur names.
# ---------------------------------------------------------------------------
ARTICLES = {'le', 'la', 'les', 'l', 'de', 'du', 'des', 'd', 'et', 'au', 'aux'}
WORD_FOLD = {'st': 'saint', 'ste': 'sainte', 'pk': 'km', 'kilometre': 'km', 'kilometres': 'km',
             'cite': 'cite', 'qtier': 'quartier', 'qt': 'quartier', 'qrt': 'quartier'}
ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}


def name_key(name):
    """Fold an area name to its national key.

    1 first of several OSM names ('A;B' -> 'A'); 2 lower case, accents removed,
    oe/ae ligatures opened; 3 words split on anything but letters and digits
    (so hyphens, apostrophes, dots, brackets do not count); 4 articles and
    linking words dropped (le, la, les, l', de, du, des, d', et, au, aux);
    5 abbreviations unified (St/Ste, PK/Kilomètre -> km, Qtier -> quartier) and
    Roman numerals I-X to digits ('Riviera II' = 'Riviera 2'); 6 a final -s
    dropped on words of 4+ letters ('Lauriers' = 'Laurier'); 7 inside words,
    'ou' before a vowel -> 'w' (Kouassi = Kwassi), 'y' -> 'i', 'ph' -> 'f',
    'c' before a/o/u and 'q(u)' -> 'k' (Cocody = Kokody), then every doubled
    letter single (Koffikro = Kofikro, Adjouffou = Adjoufou); 8 words joined.
    Folding can only merge names, never split them: when in doubt names share."""
    s = name.split(';')[0].replace('œ', 'oe').replace('Œ', 'oe').replace('æ', 'ae').replace('Æ', 'ae')
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()
    words = []
    for w in re.findall(r'[a-z0-9]+', s):
        if w in ARTICLES:
            continue
        w = WORD_FOLD.get(w, ROMAN.get(w, w))
        if not w.isdigit():
            if len(w) >= 4 and w.endswith('s'):
                w = w[:-1]
            w = re.sub(r'ou(?=[aeiy])', 'w', w)
            w = w.replace('y', 'i').replace('ph', 'f')
            w = re.sub(r'qu?', 'k', w)
            w = re.sub(r'c(?=[aou])', 'k', w)
            w = re.sub(r'(.)\1+', r'\1', w)
        words.append(w)
    return ''.join(words) or _fold(name)


# Block sizes (SPEC.md 4.2). A block is the numbers one area may use inside its
# name's national range: twice today's compounds (infill gaps + tail reserve),
# rounded up to whole hundreds, at least 100. The range keeps a spare part for
# areas of the same name that appear later.
BLOCK_UNIT = 100
NAME_SPARE_MIN = 500
NAME_SPARE_SHARE = 0.10


def block_size(compounds):
    return max(BLOCK_UNIT, -(-2 * compounds // BLOCK_UNIT) * BLOCK_UNIT)


def range_for(allocated):
    """(digits, lo, hi) of the national range a name needs, or None (qualifier needed)."""
    need = allocated + max(NAME_SPARE_MIN, math.ceil(allocated * NAME_SPARE_SHARE))
    for d in (4, 5):
        lo, hi = 10 ** (d - 1), 10 ** d - 1
        if need <= hi - lo + 1:
            return d, lo, hi
    return None


def name_digits(key):
    """The name key as digits for the check digit: a-z -> 10-35, 0-9 -> 00-09."""
    return ''.join('%02d' % int(c, 36) for c in key)


# ---------------------------------------------------------------------------
# Spot codes
# ---------------------------------------------------------------------------
def nearest_reference(model, lat, lon):
    """The unit reference town nearest a point: the largest of the latitude and
    longitude differences, ties to the lower unit code (SPEC.md 7)."""
    best = None
    for code in sorted(model.refs):
        name, rlat, rlon = model.refs[code]
        d = max(abs(rlat - lat), abs(rlon - lon))
        if best is None or d < best[0]:
            best = (d, code, name, rlat, rlon)
    return best


def spot(model, lat, lon):
    full = olc_encode(lat, lon, SPOT_LENGTH)
    out = {'plusCode': full, 'unit': model.unit_at(lat, lon)}
    ref = nearest_reference(model, lat, lon)
    if ref:
        _, _, name, rlat, rlon = ref
        short = olc_shorten(full, rlat, rlon)
        out['short'] = short + ' ' + name if short != full else full
        out['reference'] = name
    return out


def decode_spot(model, text):
    text = text.strip()
    m = re.match(r'^([23456789CFGHJMPQRVWX0]*\+[23456789CFGHJMPQRVWX]*)\s*(.*)$', text.upper())
    if not m:
        raise ValueError('not a spot code: %r' % text)
    code, place = m.group(1), text[len(m.group(1)):].strip()
    if olc_is_full(code):
        a = olc_decode(code)
        return {'plusCode': code, 'lat': a.lat, 'lon': a.lng}
    codes = reference_units(model, place)
    if not codes:
        raise ValueError('unknown reference town %r' % place)
    fulls = [olc_recover(code, model.refs[c][1], model.refs[c][2]) for c in codes]
    if len(codes) > 1:
        # A town name shared by several references, typed without its label: only a
        # reading the issuer would have written (the town is the nearest reference to
        # the cell and shortens it to the same characters) is kept; never a guess.
        keep = [(c, f) for c, f in zip(codes, fulls) if _written_against(model, c, f, code)]
        if len(keep) != 1:
            raise ValueError('%s names %d reference towns: write %s' % (
                place, len(codes), ' or '.join('%s %s' % (code, model.refs[c][0]) for c in codes)))
        codes, fulls = [keep[0][0]], [keep[0][1]]
    a = olc_decode(fulls[0])
    return {'plusCode': fulls[0], 'lat': a.lat, 'lon': a.lng, 'reference': model.refs[codes[0]][0]}


# A cell's centre lies within half a cell of the entrance it was written for, so the
# nearest reference town of the entrance is within this much of the nearest of the centre.
SPOT_TOWN_TOLERANCE = 0.0001


def reference_units(model, place):
    """The units whose reference town a typed town names: its label, folded
    ("Lolobo (Béoumi)", "lolobo beoumi"), else the town without its bracketed
    département ("Lolobo" names both Lolobo (Béoumi) and Lolobo (Attiégouakro))."""
    f = _fold(place)
    codes = model.by_ref_name.get(f)
    if codes:
        return sorted(codes)
    return sorted(c for c, (name, _, _) in model.refs.items() if _fold(name.split(' (')[0]) == f)


def _written_against(model, unit, full, short):
    a = olc_decode(full)
    _, rlat, rlon = model.refs[unit]
    d = max(abs(rlat - a.lat), abs(rlon - a.lng))
    best = min(max(abs(la - a.lat), abs(lo - a.lng)) for _, la, lo in model.refs.values())
    return d <= best + SPOT_TOWN_TOLERANCE and olc_shorten(full, rlat, rlon) == short.upper()


# ---------------------------------------------------------------------------
# Code forms
# ---------------------------------------------------------------------------
MACHINE_RE = re.compile(r'^CI-(\d{6})-(\d{3})-(\d{4,5})(?:-(\d))?(?:\.(\d{1,3}))?(?:/(\d{1,2}))?$')


def check_digit(key, number):
    """Damm over the name key (as digits) followed by the number (SPEC.md 3).
    The area is bound through the frozen block table: the number decides the area."""
    return damm(name_digits(key) + str(number))


def machine(unit, index, number, key, structure=None, entrance=None):
    s = 'CI-%s-%s-%d-%d' % (unit, index, number, check_digit(key, number))
    if structure:
        s += '.%d' % structure
    if entrance:
        s += '/%d' % entrance
    return s


def spoken_number(number):
    """'4817' -> '48 17'; '48217' -> '4 82 17' (pairs from the right, as phone numbers are read)."""
    s = str(number)
    groups = []
    while len(s) > 2:
        groups.insert(0, s[-2:])
        s = s[:-2]
    groups.insert(0, s)
    return ' '.join(groups)


def official_display(rec):
    """Display string for an official address, from official fields only."""
    return '%d, %s, %s' % (rec['number'], rec['street'], rec['commune'])


def remembered(area_name, number):
    return '%s · %s' % (area_name, spoken_number(number))


def written(area_name, number, key=None, unit_name=None):
    """'Sicogi 18 17 (Yopougon)': what people see on a plate or a form: the name, the number in
    pairs and the commune in brackets as a label only. No check digit: nobody ever has to read,
    type or remember one; it lives in the machine form only."""
    s = '%s %s' % (area_name, spoken_number(number))
    return s + (' (%s)' % unit_name if unit_name else '')


FR_UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
            'treize', 'quatorze', 'quinze', 'seize']
FR_TENS = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'}


def french_pair(n):
    """A two-digit group read the French way ('48' -> 'quarante-huit', '07' -> 'zéro sept')."""
    if n < 17:
        return FR_UNITS[n]
    if n < 20:
        return 'dix-' + FR_UNITS[n - 10]
    if n < 70:
        t, u = divmod(n, 10)
        return FR_TENS[t] + ('' if u == 0 else ('-et-un' if u == 1 else '-' + FR_UNITS[u]))
    if n < 80:
        return 'soixante-' + ('et-onze' if n == 71 else french_pair(n - 60))
    if n == 80:
        return 'quatre-vingts'
    return 'quatre-vingt-' + french_pair(n - 80)


def say_fr(number):
    parts = []
    for g in spoken_number(number).split():
        parts.append(('zéro ' + FR_UNITS[int(g)]) if len(g) == 2 and g[0] == '0' else french_pair(int(g)))
    return ' '.join(parts)


def parse(model, text):
    """Machine form (validated), official PADA address, or 'Name NNNN[-c][ (label)]'.

    'Name NNNN' is unique in the whole country: it decodes to exactly one area
    or to nothing. A commune or town written after it is only a label; if it
    contradicts the area the code decodes to, the code is rejected."""
    t = text.strip()
    m = MACHINE_RE.match(t.upper())
    if m:
        unit, index, number, check, struct, ent = m.groups()
        if check is None:
            raise ValueError('machine form needs its check digit')
        a = model.area(unit, index)
        if a is None:
            raise ValueError('unknown unit or area: typing error')
        number = int(number)
        if not model.owns(unit, index, number):
            raise ValueError('number %d is not in the block of area %s-%s: typing error' % (number, unit, index))
        key = model.key_of(unit, index)
        if not damm_ok(name_digits(key) + str(number) + check):
            raise ValueError('check digit does not match: typing error')
        return {'form': 'machine', 'unit': unit, 'index': index, 'number': number, 'area': a['plate'],
                'official': a['name'], 'key': key,
                'structure': int(struct) if struct else None, 'entrance': int(ent) if ent else None}
    m = re.match(r'^(\d{1,5})\s*,\s*((?:rue|avenue|boulevard|impasse|bd|av)\b.+?)(?:,\s*(.+))?$', t, re.I)
    if m:
        # An official PADA address is the address of the gate. Resolving it needs the
        # official tables (SPEC.md section 11); the engine never invents or alters one.
        return {'form': 'official', 'system': 'PADA', 'number': int(m.group(1)), 'street': m.group(2).strip(),
                'commune': (m.group(3) or '').strip() or None, 'display': t}
    return _parse_name_number(model, t, text)


def _splits(t):
    """Every way to read 'Name NNNN[-c][, label | (label)]': (name, number, check, label).
    A plate name may end in a number word ('Riviéra 2 18 17'), so the name/number
    boundary is tried at every space; the '·' of the remembered form fixes it."""
    label = None
    m = re.match(r'^(.*?\d)\s*(?:,\s*([^,()]+?)|\(\s*([^)]+?)\s*\))\s*$', t)
    if m:
        t, label = m.group(1), (m.group(2) or m.group(3))
    check = None
    m = re.match(r'^(.*\d[\d\s]*?)\s*-\s*(\d)$', t)
    if m and re.search(r'[\s·.-]\s*[\d\s]{4,}$', m.group(1)):
        t, check = m.group(1), m.group(2)
    if '·' in t:
        name, num = t.rsplit('·', 1)
        digits = re.sub(r'\s', '', num)
        return [(name.strip(), digits, check, label)] if re.fullmatch(r'\d{4,5}', digits) else []
    t = re.sub(r'(?<=[^\W\d_])[.-](?=\d[\d\s]*$)', ' ', t)  # 'Sicogi.1817', 'Sicogi-1817'
    words = t.split()
    out = []
    for j in range(len(words) - 1, 0, -1):
        tail = words[j:]
        if not all(w.isdigit() for w in tail):
            break
        digits = ''.join(tail)
        if 4 <= len(digits) <= 5:
            out.append((' '.join(words[:j]), digits, check, label))
    return out


def _parse_name_number(model, t, text):
    reads = _splits(t)
    if not reads:
        raise ValueError('not an N-Ways code: %r' % text)
    found, errors = [], []
    for name, digits, check, label in reads:
        key = model.plate_key(name)
        if key is None:
            errors.append('no N-Ways area is called %r' % name)
            continue
        number = int(digits)
        a = model.resolve(name, number)
        if a is None:
            errors.append('%s %s is not issued: no %s area holds this number (%s codes have %d digits)'
                          % (name, digits, name, name, model.key_digits[key]))
            continue
        if check is not None and not damm_ok(name_digits(key) + str(number) + check):
            errors.append('check digit does not match: typing error')
            continue
        found.append((name, digits, check, label, key, number, a))
    if not found:
        raise ValueError(errors[0])
    # Several readings (SPEC.md 9): a label keeps only the readings in that commune or
    # département and never redirects; then a plate name, the name on the code people hold,
    # comes before an official name typed instead of it ("Air France 1 10 00" is Air France
    # 11000, not the area officially called Air France I with 1000); only two readings
    # that still differ are refused.
    if label:
        lf = _fold(label)
        here = [f for f in found if lf in (_fold(model.units[f[6]['unit']]['name']),
                                            _fold(model.units[f[6]['unit']]['departement']))]
        if not here:
            name, digits, a = found[0][0], found[0][1], found[0][6]
            raise ValueError('%s %s is in %s, not %s' % (name, digits, model.units[a['unit']]['name'], label))
        found = here
    plate = [f for f in found if name_key(f[0]) == f[4]]
    found = plate or found
    if len({(f[6]['unit'], f[6]['index'], f[5]) for f in found}) > 1:
        raise ValueError('ambiguous: write it as "Name · NNNN" or add the commune (%s)'
                         % ', '.join('%s · %s' % (f[0], f[1]) for f in found))
    name, digits, check, label, key, number, a = found[0]
    unit_name = model.units[a['unit']]['name']
    return {'form': 'written' if check is not None else 'remembered', 'number': number, 'key': key,
            'checked': check is not None, 'unit': a['unit'], 'index': a['index'], 'area': a['plate'],
            'official': a['name'], 'commune': unit_name, 'machine': machine(a['unit'], a['index'], number, key),
            'remembered': remembered(a['plate'], number), 'typedAlias': name_key(name) != key}


# ---------------------------------------------------------------------------
# Building profile (first inference; SPEC.md "Building profile")
# ---------------------------------------------------------------------------
BTAG = {
    'house': 'residential', 'residential': 'residential', 'detached': 'residential', 'apartments': 'residential',
    'hut': 'residential', 'terrace': 'residential', 'semidetached_house': 'residential', 'dormitory': 'residential',
    'commercial': 'commercial', 'retail': 'commercial', 'kiosk': 'commercial', 'supermarket': 'commercial',
    'office': 'office', 'hotel': 'hospitality', 'school': 'education', 'college': 'education',
    'university': 'education', 'kindergarten': 'education', 'hospital': 'health', 'clinic': 'health',
    'church': 'religious', 'mosque': 'religious', 'chapel': 'religious', 'cathedral': 'religious',
    'government': 'government', 'public': 'government', 'civic': 'government', 'military': 'government',
    'industrial': 'industrial', 'warehouse': 'industrial', 'hangar': 'industrial', 'factory': 'industrial',
    'train_station': 'transport', 'garage': 'transport', 'garages': 'transport',
    'farm': 'agricultural', 'barn': 'agricultural', 'construction': 'under_construction', 'ruins': 'ruin',
    'shed': 'annex', 'roof': 'annex',
}
CATS = {
    'shop': 'commercial', 'supermarket': 'commercial', 'market': 'commercial', 'pharmacy': 'health',
    'bank': 'commercial', 'pos': 'commercial', 'phones': 'commercial', 'salon': 'commercial',
    'mechanic': 'commercial', 'food': 'commercial', 'bar': 'commercial', 'cafe': 'commercial',
    'fastfood': 'commercial', 'petrol': 'commercial', 'hotel': 'hospitality', 'school': 'education',
    'hospital': 'health', 'church': 'religious', 'mosque': 'religious', 'police': 'government',
    'office': 'office', 'motorpark': 'transport',
}
LANDUSE = {'industrial': 'industrial', 'commercial': 'commercial', 'retail': 'commercial', 'military': 'government',
           'religious': 'religious', 'farmyard': 'agricultural', 'farmland': 'agricultural'}


def profile(b):
    ev = []
    if b.get('btag') and b['btag'] != 'yes' and b['btag'] in BTAG:
        ev.append((BTAG[b['btag']], 0.85, 'osm:building'))
    if b.get('cats'):
        cs = [CATS.get(c, 'commercial') for c in b['cats'].split('|')]
        ev.append((max(set(cs), key=cs.count), 0.65, 'nways:places-inside'))
    if b.get('landuse') in LANDUSE:
        ev.append((LANDUSE[b['landuse']], 0.5, 'osm:landuse'))
    if not ev:
        if b['area'] < 6:
            ev.append(('annex', 0.4, 'size'))
        elif b['area'] > 2500:
            ev.append(('industrial', 0.3, 'size'))
        else:
            ev.append(('residential', 0.55 if b.get('landuse') == 'residential' else 0.45, 'default'))
    ev.sort(key=lambda e: -e[1])
    cls, conf, src = ev[0]
    if cls == 'residential' and any(e[0] in ('commercial', 'office') for e in ev):
        cls, conf, src = 'mixed', 0.6, 'agreement'
    conf = min(0.95, conf + 0.05 * sum(1 for e in ev[1:] if e[0] == cls))
    # Google/Microsoft heights are a rendering filler (36 values spread evenly over 3.5-7 m),
    # never a measurement: floors come from OpenStreetMap only, else they are unknown.
    floors, fsrc = None, None
    if b.get('levels'):
        try:
            floors, fsrc = max(1, int(round(float(b['levels'])))), 'osm:building:levels'
        except ValueError:
            pass
    if floors is None and b.get('h') and b.get('src') == 'osm':
        floors, fsrc = max(1, int(round(b['h'] / 3.0))), 'osm:height'
    return {'useClass': cls, 'useConfidence': round(conf, 2), 'useSource': src, 'footprintM2': b['area'],
            'perimeterM': b.get('perim'), 'heightM': b.get('h') if b.get('src') == 'osm' else None, 'floors': floors,
            'floorsSource': fsrc, 'floorAreaM2': round(b['area'] * (floors or 1), 1)}


# ---------------------------------------------------------------------------
# Compounds and numbering
# ---------------------------------------------------------------------------
ANNEX_M2, ATTACH_M, ENCLOSURE_MAX_M2 = 25.0, 5.0, 6000.0


def _metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110574)


def group_compounds(buildings):
    """buildings: dicts with id, cx, cy, area, optional eid (enclosure id), ea (its area m2).

    Rules in order (SPEC.md "Compound grouping"): 1 mapped enclosure, 2 annex
    attach (< 25 m2 joins the nearest structure >= 25 m2 within 5 m gap),
    3 otherwise its own compound. Gap here is approximated from centroids and
    equivalent radii; production uses true footprint distance.
    """
    parent = {b['id']: b['id'] for b in buildings}
    rule = {b['id']: 'single' for b in buildings}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    byid = {b['id']: b for b in buildings}
    encl = {}
    for b in buildings:
        if b.get('eid') and b.get('ea') and b['ea'] <= ENCLOSURE_MAX_M2:
            encl.setdefault(b['eid'], []).append(b['id'])
    for ms in encl.values():
        for m in ms[1:]:
            parent[find(m)] = find(ms[0])
        for m in ms:
            rule[m] = 'enclosure'
    for b in buildings:
        if rule[b['id']] != 'single' or b['area'] >= ANNEX_M2:
            continue
        rb = math.sqrt(b['area'] / math.pi)
        best = None
        for o in buildings:
            if o['area'] < ANNEX_M2 or o['id'] == b['id']:
                continue
            gap = _metres((b['cx'], b['cy']), (o['cx'], o['cy'])) - rb - math.sqrt(o['area'] / math.pi)
            if gap <= ATTACH_M and (best is None or gap < best[0]):
                best = (gap, o['id'])
        if best:
            parent[find(b['id'])] = find(best[1])
            rule[b['id']] = 'annex'
    groups = {}
    for b in buildings:
        groups.setdefault(find(b['id']), []).append(b['id'])
    conf = {'enclosure': 0.85, 'annex': 0.6, 'single': 0.4}
    out = []
    for root, ms in groups.items():
        ms.sort(key=lambda m: -byid[m]['area'])  # structure 1 = the largest
        x = sum(byid[m]['cx'] * byid[m]['area'] for m in ms) / sum(byid[m]['area'] for m in ms)
        y = sum(byid[m]['cy'] * byid[m]['area'] for m in ms) / sum(byid[m]['area'] for m in ms)
        out.append({'members': ms, 'cx': x, 'cy': y, 'rule': max((rule[m] for m in ms), key=lambda r: conf[r]),
                    'confidence': max(conf[rule[m]] for m in ms)})
    return out


M_LAT, M_LON = 110574.0, 111320.0


def _ring_inside(p, r):
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def ring_distance(r1, r2):
    """Shortest distance in metres between two footprint outlines (0 when they touch or overlap)."""
    if any(_ring_inside(p, r2) for p in r1) or any(_ring_inside(p, r1) for p in r2):
        return 0.0
    e1, e2 = list(zip(r1, r1[1:] + r1[:1])), list(zip(r2, r2[1:] + r2[:1]))
    return min(min(_seg(p, a, b) for p in r1 for a, b in e2), min(_seg(p, a, b) for p in r2 for a, b in e1))


def group_footprints(fs):
    """Production grouping of one code area (SPEC.md 5, steps 2, 4 and 6).

    fs: dicts with id (stable structure id), ring (outline as (lon, lat)), area (m2),
    eid (the smallest closed enclosure of at most 6,000 m2 holding its centre, or None).
    Footprints are taken in id order, so the result never depends on the order the data
    arrives in. Rules, first that applies:
      enclosure  every footprint inside one enclosure is one compound;
      annex      a footprint under 25 m2 joins the nearest footprint of at least 25 m2
                 within 5 m, outline to outline (only annexes join, and only to a
                 building: two houses are never joined, and nothing chains);
      single     everything else.
    Returns [(member indexes, rule)], members largest first."""
    if not fs:
        return []
    order = sorted(range(len(fs)), key=lambda i: fs[i]['id'])
    lat0 = sum(f['ring'][0][1] for f in fs) / len(fs)
    k = M_LON * math.cos(math.radians(lat0))
    rings = [[(x * k, y * M_LAT) for x, y in f['ring']] for f in fs]
    cent = [(sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)) for r in rings]
    root_of, how = {}, {}
    first_in = {}
    for i in order:
        e = fs[i].get('eid')
        if e:
            root = first_in.setdefault(e, i)
            root_of[i], how[i] = root, 'enclosure'
    CELL = 40.0
    grid = collections.defaultdict(list)
    for i in order:
        if i not in root_of and fs[i]['area'] >= ANNEX_M2:
            grid[(int(cent[i][0] // CELL), int(cent[i][1] // CELL))].append(i)
    for i in order:
        if i in root_of:
            continue
        if fs[i]['area'] < ANNEX_M2:
            best = None
            cx, cy = int(cent[i][0] // CELL), int(cent[i][1] // CELL)
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    for j in grid.get((cx + dx, cy + dy), ()):
                        if math.dist(cent[i], cent[j]) > 80:
                            continue
                        d = ring_distance(rings[i], rings[j])
                        if d <= ATTACH_M and (best is None or (d, fs[j]['id']) < (best[0], fs[best[1]]['id'])):
                            best = (d, j)
            if best:
                root_of[i], how[i] = best[1], 'annex'
                continue
        root_of[i], how[i] = i, 'single'
    comps = collections.defaultdict(list)   # buildings inside an enclosure never take annexes from outside it
    for i in order:
        comps[root_of[i]].append(i)
    out = []
    for r in sorted(comps, key=lambda r: fs[r]['id']):
        ms = sorted(comps[r], key=lambda i: (-fs[i]['area'], fs[i]['id']))
        kinds = {how[i] for i in ms}
        rule = 'enclosure' if 'enclosure' in kinds else ('annex' if len(ms) > 1 else 'single')
        out.append((ms, rule))
    return out


def reference_point(fs, members):
    """Area-weighted centre of a compound's footprints (SPEC.md 5, step 7, without a gate)."""
    w = sum(max(fs[i]['area'], 1.0) for i in members)
    lon = sum(fs[i]['lon'] * max(fs[i]['area'], 1.0) for i in members) / w
    lat = sum(fs[i]['lat'] * max(fs[i]['area'], 1.0) for i in members) / w
    return lat, lon


FRAME_PAD = 0.0005


def area_frame(points):
    """The frozen frame of a code area: the box of its compounds' reference points (lat, lon),
    widened by 0.0005 degrees (about 55 m) on every side, rounded to 1e-6 degrees."""
    las, los = [p[0] for p in points], [p[1] for p in points]
    return (round(min(los) - FRAME_PAD, 6), round(min(las) - FRAME_PAD, 6), round(max(los) + FRAME_PAD, 6), round(max(las) + FRAME_PAD, 6))


def hilbert_index(x, y, order=16):
    """Position of cell (x, y) on a Hilbert curve covering 2**order x 2**order cells."""
    n = 1 << order
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if (x & s) else 0
        ry = 1 if (y & s) else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        s >>= 1
    return d


def frame_hilbert(frame, lon, lat, order=16):
    x0, y0, x1, y1 = frame
    n = (1 << order) - 1
    gx = int(max(0, min(n, (lon - x0) / (x1 - x0) * n)))
    gy = int(max(0, min(n, (lat - y0) / (y1 - y0) * n)))
    return hilbert_index(gx, gy, order)


def block_layout(block):
    """(lo, main_hi, hi) of one area's block: the top third is the block's tail reserve."""
    lo, hi = block
    return lo, lo + (hi - lo + 1) * 2 // 3 - 1, hi


def number_compounds(compounds, frame, block):
    """Assign numbers inside the area's block along the Hilbert order, with infill gaps."""
    n = len(compounds)
    lo, main_hi, hi = block_layout(block)
    capacity = hi - lo + 1
    step = max(1, int(capacity // (n * 1.5))) if n else 1
    for c in compounds:
        c['h'] = frame_hilbert(frame, c['cx'], c['cy'])
    compounds.sort(key=lambda c: (c['h'], str(c.get('key', ''))))
    for i, c in enumerate(compounds):
        c['number'] = lo + i * step
        if c['number'] > main_hi:
            raise ValueError('numbering ran into the tail reserve: the area needs a larger block or a split')
    return {'digits': len(str(lo)), 'step': step, 'range': [lo, hi], 'tailReserve': [main_hi + 1, hi], 'compounds': compounds}


def next_block(model, key, compounds, digits=None):
    """Block for a NEW area of an existing name (or a second block for a full area):
    cut from the name's spare space, above every block already given. Existing blocks
    are never moved. A 4-digit name whose 4-digit space is used up continues in its
    5-digit space; only when both are full does the name need a qualifier (SPEC.md 4.3).
    Five-digit numbers d0000-d9999 are never used by a name when the same name
    followed by d is also a name ('Koffikro' and 'Koffikro 1'), so that
    'Koffikro 1 18 17' reads one way only (SPEC.md 4.2 step 7)."""
    size = block_size(compounds)
    used = model.blocks.get(key, [])
    digits = digits or model.key_digits.get(key) or range_for(size)[0]
    skip = skipped_stretches(model, key)
    for d in (4, 5):
        if d < digits:
            continue
        lo, hi = 10 ** (d - 1), 10 ** d - 1
        top = max([b[1] for b in used if lo <= b[1] <= hi] + [lo - 1])
        start = top + 1
        if d == 5:
            start = skip_forward(start, size, skip)
        if start + size - 1 <= hi:
            return start, start + size - 1
    return None


def skipped_stretches(model, key):
    """Digits d whose five-digit stretch d0000-d9999 the name never uses."""
    return sorted(int(d) for d in '123456789' if key + d in model.blocks)


def skip_forward(start, size, skip):
    moved = True
    while moved:
        moved = False
        for d in skip:
            if start <= d * 10000 + 9999 and d * 10000 <= start + size - 1:
                start, moved = (d + 1) * 10000, True
    return start


def provisional_number(registry, frame, lon, lat):
    """Next number for a new compound: free number between its Hilbert
    neighbours (closest to the midpoint), else the lowest free tail number."""
    h = frame_hilbert(frame, lon, lat)
    cs = sorted(registry['compounds'], key=lambda c: (c['h'], c['number']))
    used = {c['number'] for c in cs}
    lo, hi_tail = registry['range']
    prev = None
    nxt = None
    for c in cs:
        if c['h'] <= h:
            prev = c
        elif nxt is None:
            nxt = c
    a = prev['number'] if prev else lo - 1
    b = nxt['number'] if nxt else registry['tailReserve'][0]
    free = [k for k in range(a + 1, b) if k not in used and lo <= k < registry['tailReserve'][0]]
    if free:
        mid = (a + b) / 2
        return min(free, key=lambda k: (abs(k - mid), k))
    for k in range(registry['tailReserve'][0], registry['tailReserve'][1] + 1):
        if k not in used:
            return k
    raise ValueError('area full')


def load_buildings(path):
    out = []
    with open(path, encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        h = None
        try:
            h = float(r['height']) if r['height'] else None
        except ValueError:
            h = None
        out.append({'id': r['id'], 'src': r['src'], 'cx': float(r['cx']), 'cy': float(r['cy']), 'area': float(r['area']),
                    'perim': float(r['perim']) if r['perim'] else None, 'btag': r['btag'] or None,
                    'levels': r['levels'] or None, 'h': h, 'cats': r['cats'] or None, 'landuse': r['landuse'] or None,
                    'eid': r['eid'] or None, 'ea': float(r['ea']) if r['ea'] else None})
    return out


def build_sample_registry(model, path):
    """Number one area from a sample file of footprints (all in one area)."""
    bs = load_buildings(path)
    lat = sum(b['cy'] for b in bs) / len(bs)
    lon = sum(b['cx'] for b in bs) / len(bs)
    unit, area = model.area_at(lat, lon)
    comps = group_compounds(bs)
    pad = 0.0005
    frame = (min(b['cx'] for b in bs) - pad, min(b['cy'] for b in bs) - pad,
             max(b['cx'] for b in bs) + pad, max(b['cy'] for b in bs) + pad)
    reg = number_compounds(comps, frame, model.block(unit, area['index']))
    key = model.key_of(unit, area['index'])
    byid = {b['id']: b for b in bs}
    for c in reg['compounds']:
        c['machine'] = machine(unit, area['index'], c['number'], key)
        c['written'] = written(area['plate'], c['number'], key, model.units[unit]['name'])
        c['remembered'] = remembered(area['plate'], c['number'])
        c['structures'] = [dict(id=m, **profile(byid[m])) for m in c['members']]
    reg.update({'unit': unit, 'area': area['plate'], 'official': area['name'], 'index': area['index'], 'key': key,
                'frame': frame})
    return reg


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    model = Model()
    if cmd == 'check':
        # check NAME NUMBER -> the written form with its check digit, and the one area it names
        name, number = ' '.join(argv[2:-1]), int(argv[-1])
        a = model.resolve(name, number)
        if a is None:
            raise ValueError('%s %d is in no block' % (name, number))
        key = model.key_of(a['unit'], a['index'])
        print(written(a['plate'], number, key, model.units[a['unit']]['name']), machine(a['unit'], a['index'], number, key),
              '|', a['name'])
        return 0
    if cmd == 'spot':
        print(json.dumps(spot(model, float(argv[2]), float(argv[3])), ensure_ascii=False, indent=1))
    elif cmd == 'decode-spot':
        print(json.dumps(decode_spot(model, ' '.join(argv[2:])), ensure_ascii=False, indent=1))
    elif cmd == 'locate':
        lat, lon = float(argv[2]), float(argv[3])
        unit, area = model.area_at(lat, lon)
        print(json.dumps({'unit': unit, 'unitName': model.units[unit]['name'] if unit else None,
                          'area': area['plate'] if area else None, 'official': area['name'] if area else None,
                          'index': area['index'] if area else None,
                          'spot': spot(model, lat, lon)}, ensure_ascii=False, indent=1))
    elif cmd == 'parse':
        print(json.dumps(parse(model, ' '.join(argv[2:])), ensure_ascii=False, indent=1))
    elif cmd == 'registry':
        reg = build_sample_registry(model, argv[2])
        cs = reg.pop('compounds')
        print(json.dumps(reg, ensure_ascii=False))
        for c in cs[:12]:
            print(c['machine'], '|', c['remembered'], '|', len(c['members']), 'structure(s)', '|', c['rule'],
                  '|', c['structures'][0]['useClass'])
        print('...', len(cs), 'compounds')
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except ValueError as e:
        print('error:', e, file=sys.stderr)
        sys.exit(2)
