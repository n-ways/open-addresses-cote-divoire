#!/usr/bin/env python3
"""Rebuild engine/reference/test_vectors.json from the committed model (stdlib only)."""
import json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
from ci_engine import *  # noqa: E402,F401,F403

m = Model()
pts = [('Cocody, Riviera: OSM building, building=apartments (capital sample id 75715)', 5.3606529, -3.9705867),
       ('Le Plateau: OSM building, apartments, 3 levels, pharmacy and office inside (id 280566)', 5.3198562, -4.0168613),
       ('Yopougon: Google/Microsoft footprint, h=6.0 m (id 293417)', 5.3440781, -4.0770469),
       ('Koumassi Remblais: OSM building (id 94937)', 5.3003922, -3.9643765),
       ('Port-Bouët, Adjouffou: OSM building (id 46588)', 5.2436407, -3.9208946),
       ('Bouaké: OSM place=city node', 7.689021, -5.028355),
       ('Yamoussoukro: OSM place=city node', 6.820007, -5.277603),
       ('Campement Assouam (rural farm camp, Nawa/San-Pédro area): OSM place=hamlet node', 5.005232, -7.056605)]
vec = []
for label, lat, lon in pts:
    u, a = m.area_at(lat, lon)
    s = spot(m, lat, lon)
    vec.append({'label': label, 'lat': lat, 'lon': lon, 'unit': u, 'unitName': m.units[u]['name'], 'areaIndex': a['index'],
                'areaName': a['name'], 'plateName': a['plate'], 'plusCode': s['plusCode'], 'short': s.get('short')})
reg = build_sample_registry(m, os.path.join(REPO, 'engine', 'reference', 'sample-cocody-riviera.csv'))
c = [c for c in reg['compounds'] if '75715' in c['members']][0]
out = {
    'about': 'Real points (OpenStreetMap, ODbL; Google Open Buildings CC BY 4.0 / Microsoft ODbL footprints via N-Ways). '
             'Computed by ci_engine.py from model/ as committed (tools/make_vectors.py). Area names are the interim '
             'nearest-named-place areas and will change when areas are frozen; OLC vectors are from the public OLC test suite.',
    'spots': vec,
    'olc': [{'lat': 20.375, 'lon': 2.775, 'length': 6, 'code': '7FG49Q00+'},
            {'lat': 20.3700625, 'lon': 2.7821875, 'length': 10, 'code': '7FG49QCJ+2V'},
            {'lat': 20.3701125, 'lon': 2.782234375, 'length': 11, 'code': '7FG49QCJ+2VX'},
            {'lat': 47.0000625, 'lon': 8.0000625, 'length': 10, 'code': '8FVC2222+22'},
            {'lat': -41.2730625, 'lon': 174.7859375, 'length': 10, 'code': '4VCPPQGP+Q9'},
            {'lat': 1, 'lon': 1, 'length': 11, 'code': '6FH32222+222'}],
    'olcShorten': [{'code': '9C3W9QCJ+2VX', 'lat': 51.3701125, 'lon': -1.217765625, 'short': '+2VX'},
                   {'code': '9C3W9QCJ+2VX', 'lat': 51.3708675, 'lon': -1.217765625, 'short': 'CJ+2VX'},
                   {'code': '9C3W9QCJ+2VX', 'lat': 51.3852125, 'lon': -1.217765625, 'short': '9QCJ+2VX'}],
    'olcRecover': [{'short': '22+', 'lat': 42.899, 'lon': 9.012, 'full': '8FJFW222+'},
                   {'short': '22+', 'lat': 14.95125, 'lon': -23.5001, 'full': '796RXG22+'}],
    'damm': [{'digits': '572', 'check': 4}, {'digits': '0101140834817', 'check': damm('0101140834817')}],
    'check': [{'key': k, 'number': n, 'nameDigits': name_digits(k), 'check': check_digit(k, n)}
              for k, n in (('sikogi', 18817), ('madina', 4600), ('belevile', 45000), ('bonoumin', 5552))],
    'sampleRegistry': {'file': 'sample-cocody-riviera.csv', 'note': 'numbers only the 209-footprint sample, as if it were the whole area',
                       'buildings': 209, 'compounds': len(reg['compounds']), 'digits': reg['digits'], 'step': reg['step'],
                       'tailReserve': reg['tailReserve'],
                       'block': reg['range'],
                       'building75715': {'number': c['number'], 'machine': c['machine'], 'remembered': c['remembered'],
                                         'written': c['written'],
                                         'members': c['members']},
                       'provisional': {'lat': 5.3600, 'lon': -3.9700,
                                       'number': provisional_number(reg, reg['frame'], -3.9700, 5.3600)}},
    'nameKeys': [{'names': g, 'key': name_key(g[0])} for g in (
        ['Koffikro', 'Kofikro'], ['Adjouffou', 'Adjoufou'], ['Riviéra II', 'Riviera 2', 'RIVIERA-2'],
        ['Les Lauriers', 'Lauriers'], ['Kouassikro', 'Kwassikro'], ['Cocody', 'Kokody'],
        ['PK 18', 'Kilomètre 18'], ["N'Guessankro", 'Nguessankro', 'N’Guéssankro'], ['Saint-Michel', 'St Michel'])],
    # Same-named areas share one national range, so the
    # number alone says which one is meant. Madina: 7 areas, 4 digits (two in
    # Korhogo); Belleville: 7 areas, 5 digits (two in Abobo, one in Yamoussoukro).
    'sameName': [dict(text=t, **{k: v for k, v in parse(m, t).items() if k in ('unit', 'index', 'area', 'commune', 'machine')},
                      written=written(parse(m, t)['area'], parse(m, t)['number'], parse(m, t)['key'], parse(m, t)['commune']))
                 for t in ('Madina 1500', 'Madina 46 00', 'Madina 5800', 'Belleville 31200', 'Belleville 3 85 00', 'Belleville 45000')],
    # Belleville 12000: 10000-29999 is never used by Belleville because "Belleville 1"
    # and "Belleville 2" are names too (SPEC.md 4.2 step 7).
    'notIssued': ['Madina 9000', 'Belleville 4817', 'Belleville 12000', 'Sicogi 4817', 'Koffikro 11200'],
    # Plate names: at most 12 characters and 2 words.
    # (a) a long official name -> its plate name; typing the official name still decodes.
    'plateNames': [dict(official=o, plate=a['plate'], rule=a['plateRule'], text=t,
                        machine=parse(m, t)['machine'], remembered=parse(m, t)['remembered'])
                   for o, t in (('Koumassi remblais', 'Koumassi remblais 1500'), ('Deux Plateaux', 'Deux Plateaux 2000'),
                                ('Gonzagueville', 'Gonzagueville 12000'))
                   for a in [m.find_area_by_name(o)[0]]],
    # (b) two areas whose plate names collide only after shortening ("Cité Sicogi" in
    # Cocody and "Sicogi" in Yopougon are both "Sicogi"): the number tells them apart.
    'plateCollision': [dict(text=t, **{k: v for k, v in parse(m, t).items() if k in ('unit', 'index', 'area', 'official', 'commune', 'machine')})
                       for t in ('Sicogi 1 05 00', 'Sicogi 1 88 17')],
    # an official name decodes only to its own areas, never to another area of the same plate name
    'aliasNotIssued': ['Cité Sicogi 18817'],
    # a plate name ending in a number: "Koffikro 1 12 00" is Koffikro 1, never Koffikro 11200
    'numberInName': [dict(text=t, **{k: v for k, v in parse(m, t).items() if k in ('area', 'machine')})
                     for t in ('Koffikro 1 12 00', 'Koffikro 1 · 12 00', 'Zone 4 1000')],
    'plateLimit': {'ok': ['II Plateaux', 'Riviéra 2', 'Lém-Ferreira', "N'Guessankro", 'Zone 4C'],
                   'over': ['Koumassi remblais', 'Cité Angré Star 10', 'Abri 2000 Émeraude 4', 'Kouakoudougou']},
    'spoken': [{'number': n, 'pairs': spoken_number(n), 'fr': say_fr(n)} for n in (1817, 4817, 1071, 48217, 9080, 1007)],
}
json.dump(out, open(os.path.join(REPO, 'engine', 'reference', 'test_vectors.json'), 'w'), ensure_ascii=False, indent=1)
print('written', len(vec), 'spot vectors; compound 75715 ->', c['machine'], c['remembered'], c['written'])
print(out['plateNames'], out['plateCollision'], out['numberInName'], out['sameName'], sep='\n')
