#!/usr/bin/env python3
"""Plate names for Côte d'Ivoire: the name in a remembered code is at most 12
characters and 2 words.

The rule is engine/reference/plate_names.py. This file is its Ivorian
configuration:

  * language 'fr' (area names are French or Akan, Mandé, Krou and Gur names
    written the French way);
  * numbers people say are kept: a plate name may hold ONE number word
    ("Riviéra 2", "Zone 4", "Lauriers 9", "PK 18", "SAPH V5"), counted as a
    word and in the characters. A number after the name is a qualifier: a short
    form never drops it ("Cité Angré Star 10" -> "Star 10", never "Angré");
  * extra generic words: Résidence(s); extra weak words (never a name alone,
    never dropped automatically): droite, gauche, industrielle, résidentiel(le),
    extension;
  * KNOWN: documented short forms people already say, each with a source;
  * AVOID: every sous-préfecture seat and département name, the Abidjan communes
    and the large cities of West and Central Africa that Ivorians know by name,
    minus the area's own unit (and "Abidjan" for an area inside Abidjan). A short
    form equal to one of them is not taken automatically: a plate reading like
    another city would mislead;
  * Ivorian check on automatic short forms: a word may be dropped automatically
    only when it is a generic or settlement word (Cité, Carrefour, Camp...), the
    name of the area's own commune or sous-préfecture put in front of a quartier
    ("Koumassi Remblais" -> "Remblais", "Attécoubé Nimatoulaye" -> "Nimatoulaye"),
    or text in brackets or after a slash. Any other word is part of the name
    (Akan village names such as "Amian Kouassikro", "Kofi Kouadiokro" have two
    real parts; "Grand" and "Ancien" change the place): the area goes to the
    commune with its candidates (needsCouncilChoice);
  * a hyphenated village name too long for a plate ("Assié-Kouamékro") has no
    automatic short form; its parts are offered to the commune as candidates,
    the best first, used provisionally.

  python3 tools/ci_plates.py "Cité Angré Star 10" "Deux Plateaux"
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'engine', 'reference'))
import plate_names as P  # noqa: E402
from ci_engine import name_key  # noqa: E402

P.NUMBER_WORDS = 1
LANG = 'fr'
GENERIC_EXTRA = ['les résidences', 'la résidence', 'résidences', 'résidence', 'residences', 'residence']
WEAK_EXTRA = ['droite', 'gauche', 'industrielle', 'industriele', 'résidentiel', 'résidentielle', 'residentiel',
              'extension', 'extention', 'militaire', 'policière', 'policier', 'universitaire', 'pêche']
# Documented short forms: official name -> (plate name, source). Sources are
# also listed in SOURCES.md.
KNOWN = {
    'Deux Plateaux': ('II Plateaux',
                      'fr.wikipedia.org/wiki/Cocody ("2 Plateaux" in the sub-commune list); business addresses '
                      '"Cocody II Plateaux", e.g. annuaireci.com/en/entreprises/cabinet-de-pediatrie-des-ii-plateaux-abidjan-cote-divoire/'),
    'Gonzagueville': ('Gonzague',
                      'fr.wikipedia.org/wiki/Port-Bouët (quartiers: "Adjouffou, Derrière Wharf, Gonzague, Vridi")'),
}
ABIDJAN_COMMUNES = ['Abobo', 'Adjamé', 'Attécoubé', 'Cocody', 'Koumassi', 'Marcory', 'Le Plateau', 'Plateau',
                    'Port-Bouët', 'Treichville', 'Yopougon', 'Bingerville', 'Songon', 'Anyama']
# Large cities of the region: a plate name equal to one would read as that city.
REGION_CITIES = ['Abidjan', 'Yamoussoukro', 'Dakar', 'Lomé', 'Cotonou', 'Porto-Novo', 'Accra', 'Kumasi', 'Lagos',
                 'Bamako', 'Ouagadougou', 'Bobo-Dioulasso', 'Conakry', 'Freetown', 'Monrovia', 'Bissau', 'Praia',
                 'Libreville', 'Yaoundé', 'Douala', 'Niamey', 'Nouakchott']


def pre(official):
    """Spoken name from the OSM name: first of 'A;B', no-break spaces, dashes
    used as separators, 'n°', and a bracketed number kept as a number
    ('Yobloke (2)' is Yobloke 2, not Yobloke)."""
    s = official.split(';')[0].replace('\xa0', ' ').replace(' ', ' ')
    s = re.sub(r'\s+[-–—]\s+', ' ', s).replace('n°', '').replace(' & ', ' et ')
    s = re.sub(r'\(\s*(\d+|[IVX]+)\s*\)', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


class Plates:
    def __init__(self, areas, units):
        """areas: rows with unit, name; units: code -> row (name, departement)."""
        self.units = units
        self.freq = P.word_freq([pre(a['name']) for a in areas], LANG)
        towns = {u['name'] for u in units.values()} | {u['departement'] for u in units.values()}
        self.avoid = {name_key(t) for t in towns | set(ABIDJAN_COMMUNES) | set(REGION_CITIES)}

    def own(self, unit):
        u = self.units[unit]
        own = {u['name'], u['departement']}
        if unit.startswith('0101'):
            own |= {'Abidjan', 'Plateau'} if u['name'] == 'Le Plateau' else {'Abidjan'}
        return own

    def derive(self, official, unit):
        spoken = pre(official)
        own = self.own(unit)
        avoid = self.avoid - {name_key(t) for t in own}
        kw = dict(generic_extra=GENERIC_EXTRA, weak_extra=WEAK_EXTRA)
        if spoken in KNOWN:
            p, src = KNOWN[spoken]
            return {'official': spoken, 'plate': p, 'rule': 'known', 'source': src, 'needsCouncilChoice': False,
                    'candidates': []}
        r = P.derive(spoken, LANG, self.freq, avoid=avoid, avoid_key=name_key, **kw)
        cleaned, _ = P.clean(spoken, LANG, **kw)
        if r['rule'] == 'distinctive':
            kept = {P.plain(w) for w in P.content_words(r['plate'], LANG)}
            free = {P.plain(w) for w in P.HEADS[LANG]} | {P.plain(g) for g in P.GENERIC[LANG] + GENERIC_EXTRA}
            lost = [w for w in P.content_words(cleaned, LANG) if P.plain(w) not in kept and P.plain(w) not in free]
            # the commune or sous-préfecture put in front of a quartier may go
            if lost and name_key(' '.join(lost)) not in {name_key(t) for t in own | set(ABIDJAN_COMMUNES)}:
                r.update(rule='council', needsCouncilChoice=True,
                         reason='the short form drops part of the name (%s)' % ' '.join(lost))
        gen = {P.plain(g) for g in P.GENERIC[LANG] + GENERIC_EXTRA if ' ' not in g}
        m = re.match(r"^(\S+)\s+(?:des|du|de)\s|^(\S+)\s+d['’]", spoken, re.I)
        if r['rule'] == 'cleaned' and m and P.plain(m.group(1) or m.group(2)) in gen:
            # "Cité des Arts" -> "des Arts": the generic word was part of the name
            if P.fits(spoken, LANG):
                r.update(plate=spoken, rule='as-is')
            else:
                rest = r['plate']
                r.update(plate=P._cap(rest, LANG), rule='council', needsCouncilChoice=True, candidates=[P._cap(rest, LANG)],
                         reason='the generic word is part of the name (%s)' % spoken)
        if r['needsCouncilChoice'] and not r['candidates'] and '-' in cleaned:
            cs = P.candidates(cleaned.replace('-', ' '), LANG, self.freq, WEAK_EXTRA)
            cs = [P._cap(c[0], LANG) for c in cs if 'qualifier' not in c[2]][:3]
            if cs:
                r.update(plate=cs[0], candidates=cs,
                         reason='hyphenated name over the limit: one part to be chosen by the commune')
        if r['needsCouncilChoice'] and len(r['candidates']) > 1:
            # offer first a candidate that is not a town name and does not start with a number
            towns = self.avoid | {name_key(t) for t in own}
            r['candidates'].sort(key=lambda c: (name_key(c) in towns, bool(P.ROMAN.match(c.split()[0]))))
            r['plate'] = r['candidates'][0]
        if r['needsCouncilChoice'] and r['candidates'] and r['rule'] != 'cleaned':
            towns = self.avoid | {name_key(t) for t in own}
            if all(name_key(c) in towns for c in r['candidates']) and name_key(cleaned) not in towns:
                # "Petit Odienné" is not Odienné: keep the full name until the commune chooses
                r['plate'] = P._cap(cleaned, LANG)
        if spoken.isupper() and re.search(r'\b(?:RESIDENCES?|QUARTIER|CITE|CITÉ|VILLAGE)\b', spoken):
            # an all-capitals OSM name: write the plate the usual way ("RESIDENCE LES FADIGA" -> "Les Fadiga")
            fix = lambda t: ' '.join(w.capitalize() if len(w) > 3 else w.lower() if w in ('LES', 'LA', 'LE', 'DE', 'DES', 'DU') else w
                                     for w in t.split())
            r['plate'] = fix(r['plate'])
            r['candidates'] = [fix(c) for c in r['candidates']]
            r['plate'] = r['plate'][:1].upper() + r['plate'][1:]
        r['official'] = spoken
        return r


def fits(plate):
    return P.fits(plate, LANG)


if __name__ == '__main__':
    import csv
    M = os.path.join(HERE, 'model', 'areas')
    units = {r['code']: r for r in csv.DictReader(open(os.path.join(M, 'admin-units.csv'), encoding='utf-8'))}
    areas = list(csv.DictReader(open(os.path.join(M, 'areas.csv'), encoding='utf-8')))
    pl = Plates(areas, units)
    for n in sys.argv[1:]:
        print(pl.derive(n, '010114'))
