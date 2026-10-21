"""What the API answers: cards, lookups, verification, spot codes, zones and
areas, and issuing.

Issuing follows the N-Ways issuer rule for rule (engine/SPEC.md 5 and 10):

* a point within 3 m of an issued compound (or inside an outline issued
  here) already has a code: 409 with that code;
* an outline is 3 or more [lng, lat] points enclosing 6 m2 to 20,000 m2, and
  an outline covering more than half of an outline issued here (or holding
  the entrance of a published code) is the same building: 409;
* "of": another door of an existing compound, within 80 m of its entrance,
  takes a number in that compound's area;
* otherwise the new compound takes the area of the nearest issued code within
  250 m, so a new house joins its neighbours, else the area whose place point
  is nearest;
* the number comes from the engine (Register.insert): the free number between
  its neighbours on the area's Hilbert curve, else the tail reserve, else the
  first number of a new block of the name;
* the code is provisional, issued "on-demand", and each issuing key has a
  daily limit;
* the border decides: an entrance more than 300 m outside the national
  border (OpenStreetMap admin_level 2, geo.Outline) is refused with 422
  outside_country, whatever the zone or spot rule would give, and so is an
  entrance moved there.
"""
import datetime
import hashlib
import json
import math
import threading

from . import geo
from . import register as regmod
from .register import ref
from .store import CODE_COLUMNS, CODE_SELECT, code_row, fold

AT_FOUND_M = 12.0      # a point this close to a compound's entrance is at that compound
SPOT_FOUND_M = 15.0    # a spot code this close to an entrance names that compound
EXISTS_M = 3.0         # a new compound this close to an issued one is that one
PLACE_NEAR_M = 250.0   # a new compound joins the area of an issued code this close
DOOR_MAX_M = 80.0      # another door is at most this far from the compound's entrance
MOVE_MAX_M = 80.0      # an entrance moves at most this far from the compound's position
OUTSIDE_MSG = ('That point is more than 300 m outside Côte d\'Ivoire\'s national border, '
               'so it cannot have a code here: the border decides, whatever the zone.')
MIN_AREA_M2, MAX_AREA_M2 = 6.0, 20000.0
MAX_OUTLINE_POINTS = 500
NEAR_MAX_M, NEAR_MAX_N = 500.0, 100
PAGE_MAX = 1000


class ApiError(Exception):
    def __init__(self, status, code, message, extra=None):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def sentence(s):
    """A reason as a sentence: capital first letter, full stop."""
    s = s.strip()
    if not s:
        return s
    return s[:1].upper() + s[1:] + ('' if s.endswith('.') else '.')


def round1(x):
    """One decimal, halves to even (as the issuer rounds floor areas)."""
    return round(x * 10) / 10


class Service:
    def __init__(self, store, outline, issue_keys=(), per_day=5):
        self.store = store
        self.outline = outline
        self.issue_keys = {k for k in issue_keys if k}
        self.per_day = per_day
        self.lock = threading.Lock()  # one issue or change at a time: a number is given once
        self.reg = regmod.Register(store.conn())

    # ------------------------------------------------------------ cards

    def _row(self, where, args):
        return self.store.one('SELECT id, %s, anchor_lat, anchor_lng, outline FROM codes WHERE %s' % (CODE_SELECT, where), args)

    def card(self, row, distance=None):
        """The full card of a code: every registry column, named, and what
        follows from them."""
        fields = code_row(row[1:24])
        registry = dict(zip(CODE_COLUMNS, fields))
        area = self.reg.by_zone[registry['zone']]
        unit = self.reg.units[area['unit']]
        number = row[7]
        forms = self.reg.forms(area, number)
        lat, lng = row[12], row[13]
        out = {
            'machine': registry['machine'],
            'home': registry['home'],
            'remembered': registry['remembered'],
            'written': registry['written'],
            'spoken': forms['spoken'],
            'number': number,
            'check': row[8],
            'status': registry['status'],
            'issued': registry['issued'],
            'issuedAt': registry['issued_at'],
            'entrance': {'lat': lat, 'lng': lng, 'kind': registry['entrance_kind']},
            'spot': {'plusCode': ref.olc_encode(lat, lng, ref.SPOT_LENGTH), 'short': registry['plus_code']},
            'officialAddress': registry['official_address'] or None,
            'profile': {'class': registry['class'] or None, 'use': registry['use'], 'kind': registry['kind'],
                        'structures': row[20], 'floorAreaM2': float(registry['floor_area_m2']),
                        'rule': registry['rule'] or None, 'estate': registry['estate'] or None},
            'area': self.area_brief(area),
            'zone': self.zone_brief(unit),
            'registry': registry,
            'credit': regmod.CREDIT,
            'creditUrl': regmod.CREDIT_URL,
        }
        if distance is not None:
            out['distanceM'] = round(distance, 1)
        return out

    def area_brief(self, a):
        return {'id': a['zone'], 'plateName': a['plate'], 'officialName': a['name'], 'nameKey': a['key'], 'nameId': a['nameId'],
                'provisionalName': a['needsCouncilChoice']}

    def zone_brief(self, u):
        return {'key': u['code'], 'name': u['name'], 'kind': u['kind'], 'departement': u['departement'], 'region': u['region']}

    def get(self, machine):
        m = machine.strip().upper().replace(' ', '')
        base = ref.MACHINE_RE.match(m)
        if not base:
            raise ApiError(400, 'bad_machine_form', '%r is not a machine form (CI-<unit>-<area>-<number>-<check>).' % machine)
        row = self._row('machine = ?', (self._base(m),))
        if row is None:
            self.verify_or_raise(m)
            raise ApiError(404, 'not_issued', '%s is a valid code, but no compound has it yet.' % self._base(m))
        return self.card(row)

    @staticmethod
    def _base(machine):
        m = ref.MACHINE_RE.match(machine)
        unit, index, number, check = m.group(1), m.group(2), m.group(3), m.group(4)
        return 'CI-%s-%s-%s-%s' % (unit, index, number, check) if check is not None else 'CI-%s-%s-%s' % (unit, index, number)

    # ------------------------------------------------------------ verify

    def verify(self, code):
        """Every check of a machine form, in the engine's order (SPEC 9)."""
        m_text = code.strip().upper().replace(' ', '')
        out = {'code': code, 'syntax': False, 'area': False, 'inBlock': False, 'check': False, 'issued': False, 'status': None,
               'valid': False, 'reason': None}
        m = ref.MACHINE_RE.match(m_text)
        if not m:
            out['reason'] = 'not a machine form: CI-<unit 6 digits>-<area 3 digits>-<number 4 or 5 digits>-<check digit>'
            return out
        unit, index, number, check = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        if check is None:
            out['reason'] = 'the machine form needs its check digit'
            return out
        out['syntax'] = True
        a = self.reg.by_zone.get('%s-%s' % (unit, index))
        if a is None:
            out['reason'] = 'no unit or area %s-%s: a typing error' % (unit, index)
            return out
        out['area'] = True
        if not self.reg.owns(unit, index, number):
            out['reason'] = 'number %d is not in a block of area %s-%s: a typing error' % (number, unit, index)
            return out
        out['inBlock'] = True
        if not ref.damm_ok(ref.name_digits(a['key']) + str(number) + check):
            # A wrong check is refused, never corrected: the right digit is not given.
            out['reason'] = 'the check digit does not match: a digit is wrong or two are swapped'
            return out
        out['check'] = True
        machine = 'CI-%s-%s-%d-%s' % (unit, index, number, check)
        row = self.store.one('SELECT status FROM codes WHERE machine = ?', (machine,))
        out['machine'] = machine
        if row is None:
            out['reason'] = 'a valid code, but no compound has it yet'
            return out
        out['issued'], out['status'] = True, row[0]
        out['valid'] = row[0] != 'retired'
        if row[0] == 'retired':
            out['reason'] = 'retired: there is no compound there any more (a number is never given again)'
        return out

    def verify_or_raise(self, machine):
        v = self.verify(machine)
        why = sentence(v['reason'] or '')
        if not v['syntax']:
            raise ApiError(400, 'bad_machine_form', why)
        if not (v['area'] and v['inBlock']):
            raise ApiError(404, 'unknown_area', why)
        if not v['check']:
            raise ApiError(422, 'bad_check_digit', why)
        return v

    # ------------------------------------------------------------ find

    def find(self, q):
        text = (q or '').strip()
        if not text:
            raise ApiError(400, 'missing_query', 'Give q: a remembered or written code, a machine form, an official address or a spot code.')
        if len(text) > 200:
            raise ApiError(400, 'query_too_long', 'q is at most 200 characters.')
        compact = text.upper().replace(' ', '')
        if ref.MACHINE_RE.match(compact):
            self.verify_or_raise(compact)
            row = self._row('machine = ?', (self._base(compact),))
            if row is None:
                raise ApiError(404, 'not_issued', '%s is a valid code, but no compound has it yet.' % self._base(compact))
            return self._found('machine', [row])
        if compact.startswith('CI-'):
            v = self.verify(compact)
            raise ApiError(400, 'bad_machine_form', sentence(v['reason']))
        if self._looks_spot(text):
            try:
                d = ref.decode_spot(self.reg, text)
            except ValueError as e:
                raise ApiError(404, 'unknown_spot', sentence(str(e)))
            hit = self.code_at(d['lat'], d['lon'], SPOT_FOUND_M)
            if hit is None:
                raise ApiError(404, 'no_code_at_spot', 'The spot %s is not at a compound with a code.' % text,
                               {'point': {'lat': round(d['lat'], 9), 'lng': round(d['lon'], 9)}})
            return self._found('spot', [hit[0]], hit[1])
        official = fold(text)
        if official:
            rows = self.store.q('SELECT id, %s, anchor_lat, anchor_lng, outline FROM codes WHERE official_fold = ? ORDER BY machine LIMIT 20'
                                % CODE_SELECT, (official,))
            if rows:
                return self._found('official', rows)
        try:
            p = self._parse(text)
        except ValueError as e:
            why = str(e).rstrip('.')
            if why.startswith('not an N-Ways code'):
                why = 'it is not a code, a machine form, an official address or a spot code'
            raise ApiError(404, 'not_found', 'No code in Côte d\'Ivoire reads "%s": %s.' % (text, why))
        if p['form'] == 'official':
            raise ApiError(404, 'unknown_official_address', 'No compound in this registry has the official address "%s" yet.' % text)
        row = self._row('machine = ?', (p['machine'],))
        if row is None:
            raise ApiError(404, 'not_issued', '%s is in the range of %s (%s), but no compound has it yet.'
                           % (p['remembered'], p['area'], p['commune']))
        if row[9] == 'retired':
            raise ApiError(410, 'retired', '%s was retired: there is no compound there any more.' % row[2])
        return self._found(p['form'], [row], typed_alias=p.get('typedAlias'))

    def _parse(self, text):
        """The engine's parser, with one convenience: a name and a number typed
        together ("Bonoumin6136") are read as "Bonoumin 6136"."""
        try:
            return ref.parse(self.reg, text)
        except ValueError as first:
            spaced = ref.re.sub(r'(?<=[^\W\d_])(?=\d{4,5}\s*(?:[,(].*)?$)', ' ', text)
            if spaced != text:
                try:
                    return ref.parse(self.reg, spaced)
                except ValueError:
                    pass
            raise first

    @staticmethod
    def _looks_spot(text):
        t = text.strip().upper().split()
        if not t:
            return False
        c = t[0]
        i = c.find('+')
        if i not in (2, 4, 6, 8):
            return False
        if any(ch not in ref.OLC_ALPHABET + '0' for j, ch in enumerate(c) if j != i):
            return False
        return len(c) - i - 1 >= 2

    def _found(self, form, rows, distance=None, typed_alias=None):
        out = {'form': form, 'count': len(rows), 'results': [self.card(r, distance) for r in rows]}
        if typed_alias:
            out['typedOfficialName'] = True
        return out

    # ------------------------------------------------------------ points

    def check_point(self, lat, lng):
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180) or math.isnan(lat) or math.isnan(lng):
            raise ApiError(400, 'bad_point', 'Give lat and lng in decimal degrees (WGS 84).')

    def near_rows(self, lat, lng, metres):
        ids = self.store.ids_in_box(lat, lng, metres + 1)
        out = []
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for r in self.store.q('SELECT id, %s, anchor_lat, anchor_lng, outline FROM codes WHERE id IN (%s)'
                                  % (CODE_SELECT, ','.join('?' * len(part))), part):
                d = geo.ground_m(lat, lng, r[12], r[13])
                if d <= metres:
                    out.append((d, r))
        out.sort(key=lambda t: (t[0], t[1][1]))
        return out

    def code_at(self, lat, lng, metres):
        """The live code at a point: the compound whose outline (issued here)
        holds the point, else the nearest entrance within `metres`."""
        for d, r in self.near_rows(lat, lng, 150.0):
            if r[26] and r[9] != 'retired' and geo.in_ring(lng, lat, json.loads(r[26])):
                return r, 0.0
        for d, r in self.near_rows(lat, lng, metres):
            if r[9] != 'retired':
                return r, d
        return None

    def place_for(self, lat, lng):
        """The area of a new compound: that of the nearest issued code within
        250 m, else the area whose place point is nearest."""
        hit = self.code_at(lat, lng, PLACE_NEAR_M)
        if hit is not None:
            return self.reg.by_zone[hit[0][5]]
        return self.reg.nearest_area(lat, lng)

    def at(self, lat, lng):
        self.check_point(lat, lng)
        if not self.outline.contains(lat, lng):
            raise ApiError(422, 'outside_country', 'That point is outside Côte d\'Ivoire.')
        a = self.place_for(lat, lng)
        area = dict(self.area_brief(a), zone=self.zone_brief(self.reg.units[a['unit']]))
        hit = self.code_at(lat, lng, AT_FOUND_M)
        if hit is not None:
            return {'status': 'found', 'distanceM': round(hit[1], 1), 'code': self.card(hit[0]), 'area': area}
        return {'status': 'none', 'canIssue': bool(self.issue_keys), 'area': area}

    def near(self, lat, lng, radius, limit):
        self.check_point(lat, lng)
        if radius is None:
            radius = 100.0
        if not (0 < radius <= NEAR_MAX_M):
            raise ApiError(400, 'bad_radius', 'radius is in metres, more than 0 and at most %d.' % NEAR_MAX_M)
        if limit is None:
            limit = 20
        if not (1 <= limit <= NEAR_MAX_N):
            raise ApiError(400, 'bad_limit', 'limit is 1 to %d.' % NEAR_MAX_N)
        rows = self.near_rows(lat, lng, radius)
        return {'point': {'lat': lat, 'lng': lng}, 'radiusM': radius, 'count': min(len(rows), limit), 'more': len(rows) > limit,
                'results': [self.card(r, d) for d, r in rows[:limit]]}

    def spot(self, lat, lng):
        self.check_point(lat, lng)
        s = ref.spot(self.reg, lat, lng)
        unit = s.get('unit')
        return {'plusCode': s['plusCode'], 'short': s.get('short', s['plusCode']), 'reference': s.get('reference'),
                'zone': self.zone_brief(self.reg.units[unit]) if unit in self.reg.units else None,
                'point': {'lat': lat, 'lng': lng}}

    def spot_decode(self, code):
        if not code or not code.strip():
            raise ApiError(400, 'missing_code', 'Give code: a Plus Code, full ("6CQR926H+7Q7") or short with its town ("926H+7Q7 Cocody").')
        try:
            d = ref.decode_spot(self.reg, code)
        except ValueError as e:
            raise ApiError(422, 'bad_spot', sentence(str(e)))
        out = {'plusCode': d['plusCode'], 'lat': round(d['lat'], 9), 'lng': round(d['lon'], 9), 'reference': d.get('reference')}
        hit = self.code_at(d['lat'], d['lon'], SPOT_FOUND_M)
        out['code'] = self.card(hit[0], hit[1]) if hit else None
        return out

    # ------------------------------------------------------------ zones and areas

    def zones(self):
        counts = dict(self.store.q('SELECT unit, count(*) FROM codes GROUP BY unit'))
        out = []
        for code in sorted(self.reg.units):
            u = self.reg.units[code]
            out.append(dict(self.zone_brief(u), areas=len(self.reg.areas.get(code, [])), codes=counts.get(code, 0)))
        return {'count': len(out), 'zones': out}

    def zone(self, key):
        u = self.reg.units.get(key)
        if u is None:
            raise ApiError(404, 'unknown_zone', 'No zone %r: a zone is a sous-préfecture or a commune of Abidjan, 6 digits (010114 is Cocody).' % key)
        counts = dict(self.store.q('SELECT zone, count(*) FROM codes WHERE unit = ? GROUP BY zone', (key,)))
        areas = [dict(self.area_full(a), codes=counts.get(a['zone'], 0)) for a in self.reg.areas.get(key, [])]
        ref_town = self.reg.refs.get(key)
        return dict(self.zone_brief(u), codes=sum(counts.values()), referenceTown=ref_town[0] if ref_town else None,
                    areas=areas)

    def area_full(self, a):
        return dict(self.area_brief(a), zone=self.zone_brief(self.reg.units[a['unit']]), index=a['index'], digits=a['digits'],
                    blocks=[{'lo': lo, 'hi': hi, 'tailReserveFrom': ref.block_layout((lo, hi))[1] + 1} for lo, hi in a['blocks']],
                    place={'lat': a['lat'], 'lng': a['lon']},
                    frame={'west': a['frame'][0], 'south': a['frame'][1], 'east': a['frame'][2], 'north': a['frame'][3]})

    def area(self, zone_id):
        a = self.reg.by_zone.get(zone_id)
        if a is None:
            raise ApiError(404, 'unknown_area', 'No area %r: an area id is the zone and a 3-digit index, as 010114-083.' % zone_id)
        stats = self.store.one('''SELECT count(*), sum(status = 'provisional'), sum(status = 'confirmed'), sum(status = 'retired'),
            min(number), max(number) FROM codes WHERE zone = ?''', (zone_id,))
        out = self.area_full(a)
        out['codes'] = {'total': stats[0], 'provisional': stats[1] or 0, 'confirmed': stats[2] or 0, 'retired': stats[3] or 0,
                        'lowest': stats[4], 'highest': stats[5]}
        same = [self.reg.area(u, i) for _, _, u, i in self.reg.blocks.get(a['key'], []) if (u, i) != (a['unit'], a['index'])]
        seen, others = set(), []
        for x in same:
            if x['zone'] not in seen:
                seen.add(x['zone'])
                others.append({'id': x['zone'], 'zone': self.zone_brief(self.reg.units[x['unit']]),
                               'blocks': [{'lo': lo, 'hi': hi} for lo, hi in x['blocks']]})
        out['sameName'] = others
        return out

    def areas_by_name(self, name):
        if not name or not name.strip():
            raise ApiError(400, 'missing_name', 'Give name: a plate name or an official name.')
        found = {}
        for a in ref.Model.find_area_by_name(self.reg, name):
            if a is not None:
                found[a['zone']] = (a, 'plate' if ref.name_key(name) == a['key'] else 'alias')
        f = fold(name)
        for (z,) in self.store.q('SELECT zone FROM areas WHERE plate_fold = ? OR official_fold = ? ORDER BY ord', (f, f)):
            found.setdefault(z, (self.reg.by_zone[z], 'official'))
        out = []
        for z in sorted(found):
            a, how = found[z]
            out.append(dict(self.area_full(a), matchedBy=how))
        if not out:
            raise ApiError(404, 'unknown_name', 'No area of Côte d\'Ivoire is called %r.' % name)
        return {'name': name, 'nameKey': ref.name_key(name), 'count': len(out), 'areas': out}

    def zone_codes(self, key, after, limit):
        if key not in self.reg.units:
            raise ApiError(404, 'unknown_zone', 'No zone %r.' % key)
        if limit is None:
            limit = 100
        if not (1 <= limit <= PAGE_MAX):
            raise ApiError(400, 'bad_limit', 'limit is 1 to %d.' % PAGE_MAX)
        rows = self.store.q('SELECT id, %s, anchor_lat, anchor_lng, outline FROM codes WHERE unit = ? AND machine > ? ORDER BY machine LIMIT ?'
                            % CODE_SELECT, (key, after or '', limit + 1))
        more = len(rows) > limit
        rows = rows[:limit]
        return {'zone': self.zone_brief(self.reg.units[key]), 'count': len(rows), 'next': rows[-1][1] if more else None,
                'results': [self.card(r) for r in rows]}

    # ------------------------------------------------------------ info

    def health(self):
        n = self.store.one('SELECT count(*) FROM codes')[0]
        m = self.store.meta
        return {'status': 'ok', 'country': regmod.COUNTRY, 'codes': n, 'registryExported': m.get('exported'),
                'issuing': bool(self.issue_keys)}

    def info(self):
        counts = dict(self.store.q('SELECT status, count(*) FROM codes GROUP BY status'))
        issued = dict(self.store.q('SELECT issued, count(*) FROM codes GROUP BY issued'))
        m = self.store.meta
        return {'country': regmod.COUNTRY, 'name': regmod.COUNTRY_NAME, 'zones': len(self.reg.units),
                'areas': len(self.reg.by_zone), 'names': len(self.reg.names),
                'codes': {'total': sum(counts.values()), 'byStatus': counts, 'byIssue': issued},
                'registryExported': m.get('exported'), 'imported': m.get('imported'), 'changedHere': m.get('changed') or None,
                'engine': regmod.ENGINE, 'spec': 'engine/SPEC.md', 'licences': regmod.LICENCES,
                'credit': regmod.CREDIT, 'creditUrl': regmod.CREDIT_URL,
                'issuing': {'enabled': bool(self.issue_keys), 'perKeyPerDay': self.per_day},
                'forms': {'remembered': 'Bonoumin · 61 36', 'written': 'Bonoumin 61 36 (Cocody)', 'machine': 'CI-010114-083-6136-2'}}

    # ------------------------------------------------------------ issuing

    def key_id(self, key):
        """Which issuing key a request carries (its hash, never the key), or an error."""
        if not self.issue_keys:
            raise ApiError(403, 'read_only', 'This deployment does not issue codes. Only the issuer the State or N-WAYS LIMITED '
                                             'designates for Côte d\'Ivoire issues codes.')
        if not key or key not in self.issue_keys:
            raise ApiError(401, 'unauthorized', 'Send an issuing key: Authorization: Bearer <key>.')
        return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]

    def _exists(self, row, msg):
        return ApiError(409, 'already_has_code', msg % row[2], {'existing': self.card(row)})

    def issue(self, key, body, now=None):
        kid = self.key_id(key)
        if not isinstance(body, dict):
            raise ApiError(400, 'bad_body', 'Send a JSON object: {"lat", "lng", "outline"?, "of"?}.')
        try:
            lat, lng = float(body.get('lat')), float(body.get('lng'))
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_point', 'Give lat and lng of the new compound\'s entrance, in decimal degrees.')
        self.check_point(lat, lng)
        outline = body.get('outline')
        of = (body.get('of') or '').strip().upper()
        if outline is not None:
            # An empty list means no outline; one or two points cannot enclose a building.
            ok = isinstance(outline, list) and len(outline) not in (1, 2) and len(outline) <= MAX_OUTLINE_POINTS and all(
                isinstance(p, (list, tuple)) and len(p) == 2 and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p) for p in outline)
            if not ok:
                raise ApiError(400, 'bad_outline', 'outline is a list of 3 to %d [lng, lat] points.' % MAX_OUTLINE_POINTS)
        now = now or now_utc()
        since = stamp(now - datetime.timedelta(hours=24))
        with self.lock:
            n = self.store.one('SELECT count(*) FROM issue_log WHERE key_id = ? AND at >= ?', (kid, since))[0]
            if n >= self.per_day:
                raise ApiError(429, 'daily_limit', 'This key has issued %d codes in the last 24 hours, its daily limit.' % n)
            if not self.outline.contains(lat, lng):
                raise ApiError(422, 'outside_country', OUTSIDE_MSG)
            ring, area_m2 = None, 0.0
            if not of:
                hit = self.code_at(lat, lng, EXISTS_M)
                if hit is not None:
                    raise self._exists(hit[0], 'This compound already has its code: %s.')
                if outline and len(outline) >= 3:
                    ring = [[float(p[0]), float(p[1])] for p in outline]
                    if ring[0] == ring[-1]:
                        ring = ring[:-1]
                    area_m2 = geo.ring_area(ring)
                    if len(ring) < 3 or area_m2 < MIN_AREA_M2 or area_m2 > MAX_AREA_M2:
                        raise ApiError(422, 'bad_outline', 'That outline is %.0f m2; a compound\'s is between 6 m2 and 2 ha.' % area_m2)
                    clash = self._overlap(ring)
                    if clash is not None:
                        raise self._exists(clash, 'This building already has its code: %s.')
            if of:
                o = self._row('machine = ?', (self._base(of),)) if ref.MACHINE_RE.match(of) else None
                if o is None:
                    raise ApiError(404, 'unknown_code', 'There is no code %s to add a door to.' % of)
                if geo.dist_m(o[12], o[13], lat, lng) > DOOR_MAX_M:
                    raise ApiError(422, 'too_far', 'That door is more than 80 m from %s.' % o[2])
                area = self.reg.by_zone[o[5]]
            else:
                area = self.place_for(lat, lng)
            if area is None:
                raise ApiError(422, 'outside_country', 'There is no code area for this point.')
            issued = self.store.q('SELECT number, anchor_lat, anchor_lng FROM codes WHERE zone = ?', (area['zone'],))
            number, block = self.reg.insert(area, issued, lat, lng)
            if number is None:
                raise ApiError(409, 'name_full', '%s has used every number of its name; it needs a qualifier first.' % area['plate'])
            f = self.reg.forms(area, number)
            kind = 'door' if of else 'building'
            row = {
                'machine': f['machine'], 'home': f['home'], 'remembered': f['remembered'], 'written': f['written'],
                'zone': area['zone'], 'official_name': area['name'], 'number': number, 'check_digit': f['check'],
                'status': 'provisional', 'issued': 'on-demand', 'issued_at': stamp(now),
                'entrance_lat': lat, 'entrance_lng': lng, 'entrance_kind': 'door' if of else 'centre',
                'plus_code': self.reg.spot_short(lat, lng), 'official_address': '',
                'class': 'residential' if ring else '', 'use': 'residential', 'kind': kind,
                'structures': 1 if ring else 0, 'floor_area_m2': '%.1f' % round1(area_m2), 'rule': '', 'estate': '',
                'unit': area['unit'], 'name_id': area['nameId'], 'anchor_lat': lat, 'anchor_lng': lng,
                'outline': json.dumps(ring) if ring else None, 'local': 1,
            }
            conn = self.store.conn()
            with self.store.write_lock:
                conn.execute('BEGIN IMMEDIATE')
                try:
                    cur = conn.execute('INSERT INTO codes (%s) VALUES (%s)' % (','.join(row), ','.join('?' * len(row))), list(row.values()))
                    self.store.add_point(conn, cur.lastrowid, lat, lng)
                    if block is not None:
                        blocks = area['blocks'] + [tuple(block)]
                        conn.execute('UPDATE areas SET blocks = ? WHERE zone = ?', (regmod.format_blocks(blocks), area['zone']))
                    conn.execute('INSERT INTO issue_log VALUES (?,?,?)', (kid, stamp(now), f['machine']))
                    conn.execute("INSERT OR REPLACE INTO meta VALUES ('changed', ?)", (stamp(now),))
                    conn.execute('COMMIT')
                except Exception:
                    conn.execute('ROLLBACK')
                    raise
            if block is not None:
                self.reg.add_block(area, block)
            self.store.meta['changed'] = stamp(now)
            return self.card(self._row('machine = ?', (f['machine'],)))

    def _overlap(self, ring):
        """An issued compound the outline is the same building as: an outline
        issued here that it covers by more than half (of the smaller), or a
        published entrance inside it."""
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        clat, clng = sum(ys) / len(ys), sum(xs) / len(xs)
        span = max(geo.ground_m(clat, clng, y, x) for x, y in ring)
        for d, r in self.near_rows(clat, clng, span + 150.0):
            if r[9] == 'retired':
                continue
            if r[26]:
                if geo.overlap_share(ring, json.loads(r[26])) > 0.5:
                    return r
            elif geo.in_ring(r[13], r[12], ring):
                return r
        return None

    def change(self, key, machine, body, now=None):
        kid = self.key_id(key)
        if not isinstance(body, dict) or not (set(body) & {'status', 'entrance'}):
            raise ApiError(400, 'bad_body', 'Send {"status": "confirmed" | "provisional" | "retired"} and/or {"entrance": {"lat", "lng"}}.')
        m = machine.strip().upper()
        if not ref.MACHINE_RE.match(m):
            raise ApiError(400, 'bad_machine_form', '%r is not a machine form.' % machine)
        now = now or now_utc()
        with self.lock:
            row = self._row('machine = ?', (self._base(m),))
            if row is None:
                raise ApiError(404, 'unknown_code', 'There is no code %s.' % self._base(m))
            if row[9] == 'retired':
                raise ApiError(409, 'retired', '%s is retired; a retired code never comes back and its number is never reused.' % row[1])
            sets = {}
            status = body.get('status')
            if status is not None:
                if status not in ('confirmed', 'provisional', 'retired'):
                    raise ApiError(400, 'bad_status', 'status is confirmed, provisional or retired.')
                sets['status'] = status
            ent = body.get('entrance')
            if ent is not None:
                try:
                    elat, elng = float(ent['lat']), float(ent['lng'])
                except (TypeError, ValueError, KeyError):
                    raise ApiError(400, 'bad_point', 'entrance is {"lat", "lng"} in decimal degrees.')
                self.check_point(elat, elng)
                if geo.dist_m(row[24], row[25], elat, elng) > MOVE_MAX_M:
                    raise ApiError(422, 'too_far', 'An entrance moves at most 80 m from the compound\'s position.')
                if not self.outline.contains(elat, elng):
                    raise ApiError(422, 'outside_country', OUTSIDE_MSG)
                sets.update(entrance_lat=elat, entrance_lng=elng, entrance_kind='gate', plus_code=self.reg.spot_short(elat, elng))
            conn = self.store.conn()
            with self.store.write_lock:
                conn.execute('BEGIN IMMEDIATE')
                try:
                    conn.execute('UPDATE codes SET %s, local = 1 WHERE id = ?' % ', '.join('%s = ?' % k for k in sets),
                                 list(sets.values()) + [row[0]])
                    if 'entrance_lat' in sets:
                        self.store.add_point(conn, row[0], sets['entrance_lat'], sets['entrance_lng'])
                    conn.execute("INSERT OR REPLACE INTO meta VALUES ('changed', ?)", (stamp(now),))
                    conn.execute('COMMIT')
                except Exception:
                    conn.execute('ROLLBACK')
                    raise
            self.store.meta['changed'] = stamp(now)
            return self.card(self._row('id = ?', (row[0],)))
