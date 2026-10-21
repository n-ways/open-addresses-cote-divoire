# The N-Ways address model for Côte d'Ivoire

Design notes: how each choice of the model was made and why. Figures marked *design sample* were measured on a 10 % sample of buildings while the rules were chosen; all other figures are those of the issued registry. The rules in force are those of [engine/SPEC.md](../engine/SPEC.md), and the paper ([paper.md](paper.md)) gives the mathematics and the evaluation; the examples below are real issued codes. Machine-readable version: [model/design.json](../model/design.json). Existing systems: [existing-systems.md](existing-systems.md).

The model is made for Côte d'Ivoire, and each choice below is argued from Ivorian facts.

## 0. Official addresses first

Where the State has already given a gate an address, that address is the address: a second, competing address for the same gate would confuse residents and services and weaken the State's own programme. N-Ways therefore **shows the official address first, exactly as written**, and never displays the N-Ways code before or in place of the State's address. The compound still carries its N-Ways code, shown beside the official address: it is said easily on the phone, and it tells apart the households of a cour commune behind one numbered gate. N-Ways adds navigation aids: the gate position, the building profile and a Plus Code for sharing a point. P.O. boxes (and La Poste's 2-digit office codes) are not addresses; they stay as pointers on business profiles.

| Area | Official system | Data obtainable? | What N-Ways does |
|---|---|---|---|
| Abidjan, 13 communes, compounds PADA numbered | PADA: street name + metric number (MCLU/DARRU) | Not open. Street list with ID_VOIE is public (MCLU PDF, Sep 2025); address points are on the PADA partner geoportal under the data-sharing convention of 24 Jan 2023: N-Ways requests access | Imports and shows the PADA address first, exactly ("115, Rue des Moineaux, Le Plateau"); the N-Ways code beside it; gate pin, profile, Plus Code. Until access is granted, PADA addresses come only from people (photo of the plate, typed address), checked against the street list |
| Abidjan, precarious quarters (excluded by PADA, ~20% of residents) | none | n/a | N-Ways code |
| Abidjan, compounds PADA did not number (back compounds of cours communes reached by an alley, new builds after the survey) | none for that gate | n/a | N-Ways code, marked "hors PADA"; becomes an alias if PADA later numbers the gate |
| Yamoussoukro, Daloa, Korhogo (PAVI, study validated Sep 2024) | coming | not yet | N-Ways codes; when PAVI delivers, the official address is shown first and the N-Ways code stays beside it |
| Bouaké, San-Pédro (announced, not started) | none yet | n/a | N-Ways codes; the same rule when a programme delivers |
| Rest of the country (other towns, villages, campements) | none | n/a | N-Ways codes |
| Everywhere | La Poste B.P. + office code | public on request | pointer on business profiles only; never treated as an address |
| Everywhere | PADA numeric code d'adresse: five digits, département (3) + commune (2), written after the street ("495, boulevard de la République, 00217") | the format is public; the table of codes is not | shown with the official address where one is attached; a mapping table unit → official code as the codes are published |

The rest of this document describes the N-Ways code.

## 1. The format in one line

| Form | Example | Who uses it |
|---|---|---|
| In Abidjan, where PADA numbered the gate | **115, Rue des Moineaux, Le Plateau** (official, as written) | everyone; shown first, with the compound's N-Ways code beside it |
| Remembered | **Bonoumin · 61 36** | residents, visitors, couriers on the phone. Unique in the whole country on its own (section 4.1). The name is the area's short **plate name**, at most 12 characters and 2 words (section 4.2) |
| Written | Bonoumin 61 36 (Cocody) | forms, invoices, WhatsApp. The commune in brackets is a label, never needed to decode; no check digit |
| Machine | CI-010114-083-6136-2 | the app, partners' systems, plates (small print), QR |
| Spot (any point) | 926H+7Q7 Cocody (Plus Code) | sharing a precise point by link |

A code names a **compound** (cour, concession, villa with its fence, immeuble with its plot). The driver is taken to its **gate**. The Bonoumin example is the real code of a building in the Cocody sample (engine/reference/sample-cocody-riviera.csv, OSM building 75715). Bonoumin lies in Cocody, inside PADA's area: where PADA numbered a Bonoumin gate, its PADA address is shown first.

## 2. First criterion: easy to remember, nothing to do to get it

The first criterion is that people remember their code easily and get it with no effort: an address nobody can recall, or that takes effort to obtain, is not used. We compared four ways of writing a code for the same compound, using the real building counts in [model/stats](../model/stats).

### Options compared

Arithmetic uses the Abidjan sous-préfecture, the hardest case (*design sample*: 679,808 structures grouped into 566,892 compounds, ratio 0.834, see section 5), and a capacity rule of **twice today's compounds** (room for growth and for infill numbers). Capacity is sized for every compound, those with a PADA address included, since every compound carries an N-Ways code.

| Option | Example | Length people must hold | Works on a basic keypad | Verdict |
|---|---|---|---|---|
| A. Commune + number | Cocody 274 117 | Cocody has 140,412 compounds in the registry; x 2 = 280,824, so **6 digits** | yes | too long to remember; rejected |
| B. Alphanumeric (base 20, Plus Code letters) | COC-7HQ2X | 20^5 = 3.2 million > 280,824, so 5 characters, but letters such as Q, X, W, V are spelt out in French ("double vé") and mixed letter/digit strings are the hardest to recall | no (letters need multi-tap) | rejected |
| C. Digits only, machine style | 010114 083 4817 8 | 14 digits | yes | not memorable; also looks like PADA's coming numeric code d'adresse; kept only as the machine form |
| **D. Place name + 4 digits (5 for some names)** | **Bonoumin · 61 36** | a short name people already say + two pairs of digits | yes | **chosen** |

Why D works in Côte d'Ivoire:

- **The name is free.** People already say where they live by quartier or village: "Yopougon Sicogi", "Abobo PK18", "Koumassi Remblais", "Bonoumin". The name costs no memory. It is kept short: at most 12 characters and 2 words (section 4.2), so "Koumassi remblais" is `Remblais` in the code.
- **Four digits fit nearly everywhere.** With 4 digits (1000 to 9999, 9,000 numbers) and the x2 rule, an area can hold 4,500 compounds today.
  - Abidjan (*design sample*): 452 named places give 415 areas; median 861 compounds, 90th percentile 3,028; **398 of 415 areas fit** (119 would even fit 3 digits). 17 would need splitting to keep four digits (largest: Adjouffou 11,514; Akeikoi 8,864; Avocatier 8,266; Gonzagueville 7,960; Cité Gestoci 7,050).
  - Whole country, as issued: 10,220 named places, 9,834 areas (9,800 with compounds), 7,956,622 compounds. Median 382 compounds per area, 90th percentile 1,870. 230 areas with more than 4,500 compounds (1,681,123 compounds, 21.1 %) are mostly towns mapped with a single place point (Bouaflé 23,047, the largest), which take five-digit numbers. With same-named areas sharing national ranges (section 4.1), 70.9 % of compounds have four digits and 29.1 % five. The design-sample figures are in [model/stats/national-areas.json](../model/stats/national-areas.json).
- **Two pairs, like phone numbers.** Ivorian numbers are read in pairs ("zéro sept, quarante-huit..."); "48 17" is read "quarante-huit dix-sept". Four digits is two chunks, well inside what people hold after hearing it once.
- **Unique nationally, with nothing after it.** Côte d'Ivoire repeats place names (818 plate names are carried by 2,034 areas; Akakro and Koffikro by 16 each). A code must never need the commune or town after it, so every area with the same name draws its numbers from one national range for that name (section 4.1). "Madina 52 00" is a Madina of Korhogo; "Madina 15 00" the Madina of Touba.
- **Four digits, five for 323 names, fixed per name.** We do not use 3-digit numbers even in small villages: a fixed length tells a courier "this is an N-Ways code", and keeps it apart from PADA numbers, which follow a street name and run from 1 to a few thousand metres. The length belongs to the name and is fixed when the name is first issued: 8,295 plate names (9,195 areas) have four digits; 323 names (639 areas) have five, either because they are shared (such as Belleville, Akakro, Koko, Sicogi) or because one area is a whole town (section 4.1).
- **No letters, and no check digit for people.** The check digit lives only in the machine form (APIs, QR codes, partners' systems); plates, forms and messages show the name and the number. It is computed over the name and the number, so a system receiving a mistyped machine code catches it even when the wrong number belongs to another area of the same name. A remembered code decodes to exactly one area, and the app shows that area and its commune before anyone drives.

### Getting the code: steps counted

| Situation | Steps |
|---|---|
| App user with a saved home | 0 to see it ("Votre adresse N-Ways" card), 1 tap to share by WhatsApp or SMS link (nways.ng/a/...) |
| Standing at the gate | open the app, "Mon adresse ici" (1 tap), "c'est mon portail" (1 tap) |
| New house | "Ajouter ma maison": 5 short steps, provisional code at once (section 8) |
| No smartphone | the plate or sticker on the gate; a relative, courier or shop looks it up |
| Courier or company | looks it up in the partner API from the point, the PADA address or name + number |

There is no USSD service; a code is looked up in the app, on the web or through the open registry and API.

## 3. Units: why the sous-préfecture and the communes of Abidjan

Côte d'Ivoire has 14 districts autonomes, 31 régions, 108 départements, 509 sous-préfectures and 201 communes (MIS-CNFCI 2021 figures). The machine form hangs off **the sous-préfecture, and, inside the Abidjan sous-préfecture, the 10 historical communes**: 520 units.

- **PADA's code d'adresse uses the same level.** It is "based on the codification of geographic circonscriptions ... identifiers of the Département and the Commune/Sous-Préfecture" (KOACI, 27 Feb 2025). Using that level means one mapping table, unit by unit, turns an N-Ways code into the official code the day it is published.
- **Districts and régions are too large** (12 of 14 districts are flagged in [model/regions.json](../model/regions.json); building counts run to 1.28 million per district).
- **Départements change more** and are less precise than sous-préfectures; communes alone do not cover rural land.
- **Interim codes.** The official codification is not public, so the 6-digit unit code is the OCHA/CNTIG pcode digits (CI110301 → 110301, Bouaké). The 10 communes of Abidjan get interim codes 010111 to 010120. When the official codes appear, they are published as aliases; issued codes are not rewritten.

The unit is not in the remembered form and is never needed to decode it: "Bonoumin 61 36" names one compound in the whole country. The app may show the commune next to it ("Bonoumin 61 36 (Cocody)") as a label; if a typed commune contradicts the code, the code is rejected rather than moved.

## 4. Code areas and numbering

A **code area** is a frozen polygon named after a quartier, village or campement, inside one unit. It has two names: its official name (the full name, printed small for context) and its **plate name**, the short name in the code (section 4.2). Its numbers come from its **block** in the national range of its plate name (section 4.1), so a number is unique for its name in the whole country, not only inside the area.

- **Interim areas** are the nearest named place inside the unit (9,834 areas, [model/areas/areas.csv](../model/areas/areas.csv)), built from OpenStreetMap place points. PADA's street list gives a quartier for each street; when the street geometry can be matched, PADA quartier names replace or refine these areas before freezing.
- **Frozen at first issue.** After the first code, the boundary moves only over land with no code yet. Official renamings change the spoken alias, never the code.
- **Large areas.** When compounds x 2 exceed 9,000, the area is a whole town mapped with one point (Bonon, Bouaflé, Soubré...). It keeps one 5-digit block; quartier names, where they become available, give new areas for new compounds, and issued codes stay.
- **Order.** Compounds are numbered along a Hilbert curve over the area's frame, so neighbours have close numbers. Numbers are spaced inside the area's block (step = block size / (N x 1.5)), leaving free numbers between neighbours for infill, and the top third of the block is its reserve.
- **New homes** take the free number between their neighbours closest to the midpoint, else the lowest reserve number of the block; when the block is full, the area gets a second block from its name's spare space (section 4.1).

### 4.1 One name, one national number range

Letting the commune or town tell same-named areas apart ("Sicogi 48 17, Yopougon") was considered and rejected. A code read over the phone or written on a parcel often travels without its commune, and Côte d'Ivoire repeats place names widely, so the remembered code must be unique in the whole country **on its own**. The rule:

1. **Same name, one range.** All code areas whose plate names (section 4.2) fold to the same **name key** share one national range of numbers for that name. Folding (engine/SPEC.md 4.1), for French and the Akan, Mandé, Krou and Gur spellings used in Côte d'Ivoire: case and accents ignored; hyphens, apostrophes, brackets and spaces ignored; articles and linking words dropped (le, la, les, l', de, du, des, d', et, au, aux); St/Ste = Saint/Sainte, PK = Kilomètre = km; Roman numerals I to X = digits (Riviéra II = Riviera 2); a final -s dropped (Lauriers = Laurier); "ou" before a vowel = w (Kouassi = Kwassi), y = i, ph = f, c before a, o, u and qu = k (Cocody = Kokody); doubled letters single (Koffikro = Kofikro, Adjouffou = Adjoufou). Folding only ever merges names, so two spellings of one name can never get two ranges.
2. **Blocks.** The range is cut into one **block** per area: twice the area's compounds today, rounded up to a hundred, at least 100 numbers (room for infill and the block's tail reserve). Blocks follow a frozen order (unit code, then area index), so the first digits of the number tell which area it is: Madina 1000–2799 is Touba, 2800–3799 Sarhala, 3800–4799 Sokoro, 4800–4999 Allosso, 5000–5499 and 5500–6199 the two Madinas of Korhogo, 6200–8099 Gouiné; 8100–9999 is spare.
3. **Length per name.** A name has 4 digits (1000–9999) if its blocks plus a spare of max(500, 10%) fit there, else 5 digits (10000–99999). Numbers never exceed 5 digits.
4. **Spare and growth.** Everything above the last block is the name's spare. A new area with an existing name (a new quartier, a frozen split) gets the next block from the spare; a full area gets a second block. A 4-digit name whose 4-digit space is used up continues in its 5-digit space; its earlier 4-digit codes do not change.
5. **Qualifier, only if a name cannot fit.** If a name's blocks would not fit even in 5 digits (90,000 numbers), the name takes the one qualifier people already put before a quartier in Côte d'Ivoire: the commune or town ("Yopougon Sicogi", "Koumassi Remblais", "Abobo Belleville"). That is decided once per name, listed in [model/stats/name-repeats.json](../model/stats/name-repeats.json) (`qualifiedNames`), and the qualified name is then a name of its own with its own range. **No name needs one**: the largest shared range, Belleville, uses 63,000 of its 90,000 numbers (70,000 once the stretch of rule 8 is set aside). A qualified name must still fit the plate limit (section 4.2); if it does not, the commune chooses its plate name.
6. **Frozen at issue.** A block, once a code is issued from it, never moves, shrinks or is renumbered. Renaming an area adds an alias; its codes keep the old name's range.
7. **The check digit binds name, number and area.** It is the Damm digit over the name key (as digits) and the number, carried in the machine form. The area is bound to both by the frozen block table: a wrong digit or swapped pair in the number fails the check even when it lands in another block of the same name, and a wrong unit or area index fails because that area does not own the number's block.
8. **A number in the name never meets the code's number.** Some plate names end with a number people say ("Koffikro 1", "Riviéra 2", "Zone 4"). Typed without the dot, "Koffikro 1 12 00" could also be read as Koffikro with the number 11200. So a name never uses the five-digit numbers d0000–d9999 when the same name followed by the digit d is also a name: Koffikro, with Koffikro 1 and Koffikro 2 beside it, starts at 30000. Every typed form then reads one way only among plate names; the parser also accepts "Koffikro 1 · 12 00", where the dot fixes the boundary. An official name typed instead of a plate name (an alias, section 4.2) can still collide, since the rule looks at plate names only and the blocks are frozen: "Air France 1 10 00" is Air France 11000 in Korhogo, and also Air France I (the official name of France I in Bouaké) with 1000. The parser then keeps the readings in the commune given, if any, and prefers the plate name, the name on the code people hold; it refuses only if two codes still remain. Every issued code decodes to itself from its written and remembered forms (`tools/check-decoding.py`).

**Counts** (*design sample* for the compounds; the issued blocks are in engine/SPEC.md 4.2 and the issued counts in the paper: [tools/name_ranges.py](../tools/name_ranges.py), [model/areas/name-blocks.csv](../model/areas/name-blocks.csv), [model/stats/name-repeats.json](../model/stats/name-repeats.json)). Ranges are cut by plate name; the column "full names" is the same count on the full official names, before the plate rule:

| | Plate names | Full names (before) |
|---|---|---|
| Distinct name keys | 8,618 | 8,903 |
| Names carried by more than one area | **818**, in **2,034 areas** (≈1.73 million compounds) | 636, in 1,567 areas (≈1.34 million) |
| ... in 2 areas / 3 / 4 / 5 to 9 / 10 or more | 638 / 105 / 36 / 31 / 8 | 500 / 86 / 17 / 27 / 6 |
| ... with two or more areas inside one unit | 210 (Sicogi: 2 in Cocody; Adjouffou: 3 in Port-Bouët) | 115 |
| ... including an Abidjan area | 73 | 39 |
| Most repeated | Akakro 16 areas (5 digits), Koffikro 16, Kouadiokro 14, N'Guessankro 13, Yaokro 12, Kouamékro 12 | Akakro 16 |
| Largest shared range | **Belleville**: 7 areas (2 in Abobo; Yamoussoukro, Grand-Lahou, Zoukougbeu, Buyo, Dapéoua), 31,339 compounds at issue, 63,000 numbers, **5 digits** (30000–92999: 10000–29999 is set aside because Belleville 1 and Belleville 2 are names too, rule 8) | the same |
| Next | Soubré 43,600 (2 areas), Adjouffou 42,600 (3), Koko 39,800 (10), Kennedy 39,000 (4), Gbapleu 35,000 (4) | Soubré, Adjouffou, Koko 36,100 (8) |
| Shared names that keep 4 digits | 704 of 818 (Madina: 7 areas in 1000–7999) | 544 of 636 |
| Names with 5 digits | 311 at design (619 areas, 27.8% of compounds); 323 as issued (639 areas, 29.1 %) | 305 (550 areas, 26.8%) |
| Names needing a qualifier | 0 | 0 |

Shortening merges names: "Cité Sicogi" (two areas in Cocody), "Koumassi Sicogi", "Cité Sicogi Reconciliation" (Yopougon) and "Cité résidentielle Sicogi" (Bouaké) all have the plate name Sicogi, so Sicogi now has 6 areas and five digits: "Sicogi · 1 05 00" is the Cité Sicogi of Cocody, "Sicogi · 1 88 17" the Sicogi of Koumassi. The number tells them apart, as for Madina.

The issued blocks were cut on the compounds counted at issue and are frozen.

- **Never reused.** A demolished compound's number is retired. A split keeps the number on the largest part; a merge keeps the older number and lists the other as an alias.

### 4.2 Plate names: at most 12 characters and 2 words

Taken as they are, the map's names are often too long for a code people say: 1,414 of the 9,834 area names are too long: 1,395 have more than 12 characters and 192 more than 2 words ("Cité Rosiers 6e Programme extension", "Échangeur Félix Houphouët Boigny (FHB)", "Kouadio-Kouassikro"). Each area now has two names:

- the **official name**, the full name from the map or the commune's list, printed small on cards and plates for context, never required;
- the **plate name**, the name in the code: **at most 12 characters** (letters, spaces, hyphens and apostrophes count one each; an accented letter is one) and **at most 2 words** (linking words such as de, du, des, la, les, à do not count; a hyphen separates words, so "Assié-Kouamékro" is two words). Ivorian names carry numbers people say ("Riviéra 2", "Zone 4", "Lauriers 9", "PK 18", "SAPH V5"): a plate name may hold one such number word, counted as a word and in the characters. The whole remembered code stays short: "Bonoumin · 61 36", "Remblais · 15 00", "II Plateaux · 20 00".

**How the plate name is derived** ([tools/ci_plates.py](../tools/ci_plates.py), with the general rule in [engine/reference/plate_names.py](../engine/reference/plate_names.py)):

1. **A documented short form wins**, with its source (SOURCES.md): "Deux Plateaux" → `II Plateaux` (Wikipédia, Cocody; business addresses "Cocody II Plateaux"), "Gonzagueville" → `Gonzague` (Wikipédia, Port-Bouët).
2. **Clean**: drop text in brackets or after a slash ("Quai Ouest (Q6-Q14)" → `Quai Ouest`), generic words (Quartier, Cité, Lotissement, Zone, Secteur, Village, Campement, Résidence(s)) and a linking word left at either end ("Cité Gestoci" → `Gestoci`, "Campement Assouam" → `Assouam`, "Les résidences Akwaba" → `Akwaba`). A bracketed number is kept ("Yobloke (2)" → `Yobloke 2`). A generic word is kept when nothing would be left but a number or a weak word ("Zone 4", "Zone Industrielle").
3. If the cleaned name fits, it is the plate name. Else **Saint/Sainte → St/Ste** ("Saint-Georges" → `St-Georges`; the name key reads them back as Saint/Sainte).
4. Else the **most distinctive whole words**, never cutting a word: the rarest one or two words among all Ivorian area names, with a preference for the end of the name. In Côte d'Ivoire this is taken automatically only when the words dropped are generic or settlement words (Cité, Carrefour, Camp, Gare, Ville) or the commune or sous-préfecture people put in front of a quartier: "Koumassi remblais" → `Remblais`, "Attécoubé Nimatoulaye" → `Nimatoulaye`, "Anyama Ahouabo" → `Ahouabo`, "Kouadiobakro carrefour" → `Kouadiobakro`. Any other dropped word is part of the name: Akan village names such as "Amian Kouassikro" or "Kofi Kouadiokro" have two real parts, and "Petit", "Grand", "Ancien", "Nord", a number after the name ("Cité Angré Star 10") change the place.
5. **Otherwise the commune chooses** (`needsCouncilChoice`), with up to three candidates; the first is used provisionally so the area can be numbered. A hyphenated village name over the limit ("Assié-Kouamékro") offers its parts. A short form equal to a sous-préfecture seat, a département, an Abidjan commune or a large city of the region (Yamoussoukro, Bamako, Ouagadougou, Accra...) is never taken automatically: a plate reading like another city would mislead; the area's own commune or sous-préfecture is allowed. Where the only candidates are such towns ("Petit Odienné" → Odienné), the full name stays provisionally. The commune or sous-préfecture confirms every flagged plate name. The codes carry the first candidate until then; a later choice is added as an alias and never changes a number.

**Counts** ([model/stats/name-repeats.json](../model/stats/name-repeats.json) `plateNames`, [model/areas/areas.csv](../model/areas/areas.csv) columns `plate`, `plateRule`, `needsCouncilChoice`, `plateCandidates`, `plateReason`, `plateSource`):

| | Areas |
|---|---|
| Official name fits as it is | 8,378 |
| Cleaned (generic word, brackets, slash) | 212 |
| Abbreviated (St, Ste) | 2 |
| Documented short form | 2 |
| Most distinctive words, taken automatically | 44 |
| **Commune to choose** (`needsCouncilChoice`) | **1,197**: the short form drops part of the name 399; one word longer than 12 letters, no short form possible ("Kouakoudougou", "Tiongofolokaha") 340; hyphenated name, one part to choose 288; no clear choice 68; every short form drops a qualifier (a number, Nord, Extension...) 61; short form equals a well-known town 19; too short alone 19; generic word part of the name ("Cité des Arts") 3 |
| ... still over the limit provisionally | 363 (all among the 1,197; none of the others) |

In the 535 areas of the Abidjan district (units 010101 to 010120: Anyama, Bingerville, Brofodoumé, Songon, the 10 communes and the rest of the Abidjan sous-préfecture): 331 as they are, 80 cleaned, 9 shortened automatically or by a documented form, 115 for the commune. Long single words are mostly villages (-dougou, -kaha, -kro names); the commune or the village chief may know a shorter form people say, else the commune decides.

**Typing the official name still works.** The official name (and the full OSM spelling) is an alias of the plate name in [model/areas/plate-aliases.csv](../model/areas/plate-aliases.csv) (1,070 aliases): "Koumassi remblais 1500" decodes to `Remblais · 15 00`. An alias decodes only to the areas that carry that official name ("Cité Sicogi 18817" is rejected: 18817 is the Sicogi of Koumassi, which does not carry the official name Cité Sicogi). An alias that would be claimed by two plate names, or that equals another area's plate name, is dropped: 4 today ("Abole Kouassikro", "Ya Kouakoukro", "Konan koffikro", "Kouami-Kofikro", each also the plate name of another area).

**Longest remembered codes.** Among areas not waiting for the commune: "Soungalovogo · 1 00 00" (22 characters). Among all, provisionally: "Industriele de Treichville · 10 00", until the commune chooses.

## 5. The compound is the address

Ivorian homes are mostly plots behind a wall with one gate: villas with a guardian's room, cours communes (rooms around a shared yard, each a household), immeubles with many flats, shops built into the front wall. The footprint is the wrong unit: a courier needs the gate.

Grouping rules, in order (engine/SPEC.md §5):

1. **Enclosure**: structures inside one closed OSM wall, fence or hedge (≤ 6,000 m²) are one compound (confidence 0.85). Larger enclosures with many compounds are **estates** (cités SICOGI or SOGEFIHA, gated lotissements, military or government sites): their gates become estate gates; compounds inside keep their own codes.
2. **Annex**: a structure under 25 m² (kitchen, shower, guérite) joins the nearest structure of 25 m² or more within 5 m (0.6). Abidjan's buildings stand close together, so the distance is short enough to keep a neighbour's kitchen out.
3. **Cadastral parcel** where SIGFU, IDUFCI or an ACD plan is given by the property owner or a partner (0.9).
4. **People**: "ces bâtiments sont une seule maison", "voici le portail", from residents, visitors and couriers; agreement settles it.
5. Otherwise the structure is its own compound (0.4).

Regrouping never changes an issued code (merge and split rules above).

**Abidjan sous-préfecture, first run of rules 1, 2 and 5** (*design sample*; the issued counts for the whole country are in the paper, section 4.11) ([model/stats/capital-stats.json](../model/stats/capital-stats.json)):

| | Count |
|---|---|
| Structures (287,366 OSM + 392,442 Google/Microsoft) | 679,808 |
| Compounds | 566,892 |
| ... with 1 structure | 475,971 |
| ... with 2 | 74,889 |
| ... with 3 to 5 | 15,545 |
| ... with 6 or more | 487 |
| Grouped by a mapped enclosure | 1,496 compounds |
| Structures inside large enclosures (estates and sites) | 35,151 |
| Mapped enclosures, median area | 1,209 m² (p10 326, p90 4,186) |
| OSM gate nodes / wall and fence ways in the box | 1,822 / 6,493 |

Only 4,806 closed enclosures are mapped for more than half a million compounds, so most grouping today comes from the annex rule and will come from people. The **compound class** from this first run: one household 423,551 (74.7%), several households (cours communes and row buildings) 77,597 (13.7%), unclassified small structures 34,675, industrial 13,340, commercial 10,865, institutional 5,004, mixed 991, multi-storey residential 869. Per-commune load, for comparison with option A: Cocody 164,976 structures, Yopougon 155,404, Abobo 128,734, Port-Bouët 92,226, Koumassi 34,040, Attécoubé 29,333, Marcory 26,056, Adjamé 25,938, Treichville 8,962, Le Plateau 3,724.

## 6. Building profile

Every structure carries a profile, and every compound a summary. The full schema is in design.json.

- **Use class**, with Ivorian forms: villa (basse, duplex), logement de cité (SICOGI, SOGEFIHA), immeuble R+n, cour commune, baraque (habitat précaire), case, habitation de campement, maison de village; boutique, magasin, kiosque, maquis, marché, station-service, banque, pharmacie; mairie, sous-préfecture, police, gendarmerie, caserne; école, collège, lycée, université; CSU, hôpital, clinique; église, mosquée, temple; usine, entrepôt, hangar; hôtel; gare routière (gbaka, woro-woro), port, aéroport; agricultural; annexe, en construction, ruine, inconnu.
- **How it is inferred**, with a confidence: OSM building tag 0.85, OSM shop/amenity tag on the footprint 0.75, an N-Ways place inside the footprint 0.65, OSM landuse 0.5, size 0.3 to 0.4, default residential 0.45 (0.55 in residential landuse). Agreeing sources add 0.05; residential plus commercial evidence gives "mixed". A statement by the property owner or a resident, or confirmed visits, raise it to 0.9.
- **Size**: footprint area and perimeter (geodesic), height (OSM height), floors (OSM building:levels, else OSM height / 3, at least 1; otherwise unknown), floor area. The Google/Microsoft height is a rendering filler, not a measurement, and never gives floors.
- **Source and date per attribute**, and status (existing, under construction, ruin, demolished).
- **Name** for businesses and public buildings only.

**Abidjan sample statistics.** Footprints: median 66.7 m² (p10 16.7, p25 28.5, p75 155.2, p90 273.8); perimeter median 34.9 m. 57.7% have a height; median 5.3 m (p10 3.9, p90 6.7). Floors: 1 floor 560,066, 2 floors 118,494, 3 or more 1,248. Footprint total 88.6 km² over a 553 km² sous-préfecture; floor area 101.8 km². Use class: residential 93.9%, industrial 2.3%, commercial 1.6%, government 0.4%, education 0.16%, religious 0.14%, health 0.09%.

What this shows honestly: **92.9% of classes are still the default guess** (631,222 structures); only 10,361 OSM tags, 9,334 N-Ways places inside footprints and 25,425 landuse hits give evidence. Heights from the machine-learned layer cluster between 4 and 7 m (36 values spread evenly), which is why they never give floors. The profile is a starting point that people, couriers and partners correct (section 9).

## 7. Spot codes: Plus Codes

Any point, including fields, lagoon banks and empty plots, has a spot code: an 11-character **Open Location Code** (about 2.8 m x 3.5 m), shown short against the unit's reference town ("PWPQ+2J2 Bouaké").

- **No two towns are written alike.** Five town names are the reference town of two units each (Lolobo, Santa, Nafana, Guézon and N'Guessankro, the last in two spellings); each of them is written with its département in brackets, "QHW6+44J Lolobo (Béoumi)" and "Lolobo (Attiégouakro)", so a short code names one town. Only the town written after the code changed, for 79,412 compounds; the Plus Code, the code and its number did not. A short code typed with the bare town decodes when only one of the towns could have produced it, and is refused otherwise, never placed near the wrong town.

- It is **open** (Apache-2.0), free and works **offline**; the CI engine implements it itself.
- La Poste CI promotes what3words, which is proprietary. N-Ways gives the open alternative and does not depend on what3words.
- Spots are shared by link, not memorised, so the letters do not hurt the first criterion.
- A home-grown 3 m grid would need 7 to 8 characters per district (model/regions.json); OLC needs no tables at all.

## 8. Ajouter ma maison (new homes)

1. **At the gate**: GPS averaged 5 to 10 seconds and one photo of the gate.
2. **Outline the plot**, one of three ways: tap the corners on imagery; walk the inside of the wall with the camera (ARKit/ARCore world tracking gives the shape to centimetres, anchored by GPS averaged over the walk and checked against imagery and nearby footprints; plain phone GPS, 3 to 10 m off, is too rough on its own); or import a géomètre's plan or a SIGFU/IDUFCI parcel, beacon coordinates typed or photographed. Plans must state their datum: ITRF2014 epoch 2010.0 is the legal reference (Décret 2019-220); older plans in Abidjan 1987 / Clarke 1880 are converted; plans with no datum are not imported. The projection is most likely UTM 30N (29N in the far west); not verified.
3. **Describe it**: households (private), structures, floors, use.
4. **Provisional code at once**: the next reserved number of the area, by the infill rule, so it can be painted on the gate today.
5. **Confirmed** when deliveries or visits arrive at the gate, no neighbour disputes it, or new imagery shows the buildings.

Checks, the same in the app and in the issuer (engine/SPEC.md section 10, server/README.md): a point within 3 m of an issued entrance already has its code; an outline is a closed loop of 3 to 500 points enclosing 6 to 20,000 m²; an outline covering more than half of an issued outline, or holding the entrance of an issued code, is a building that already has its code; another door of a compound must lie within 80 m of its entrance. In the app, the GPS and AR shapes must also agree within 5 m. Offline, the Plus Code is shown at once and the compound code comes from the downloaded area pack, confirmed on the next connection.

**Legal angle.** An N-Ways code is an address. It is not a land title, an ACD, an IDUFCI, a certificat foncier or a plan, and the flow says so before showing the code. In towns, only a plan by a géomètre-expert agréé, checked by the MCLU, has legal value; in rural land, the AFOR certificat foncier (Loi 98-750 as amended in 2019). N-Ways does not settle land disputes; it flags overlaps and waits.

## 9. Corrections and stability

Corrections come from the same consensus N-Ways uses for the map: people arriving at a gate, couriers delivering, residents confirming, partners' data. Nobody queues them for review. What can change: profiles, groupings before issue, gate positions, names. What never changes: an issued number. Doors nobody reaches for a long time, and closed businesses, are asked about again.

## 10. PADA data, used as it is

- **Where PADA has numbered a gate, PADA is the address.** N-Ways stores ID_VOIE, the official street name and the metric number on the entrance, shows them exactly as written and first, and keeps the compound's N-Ways code beside them (every compound has one). The official address is keyed `PADA:<ID_VOIE>:<number>` (numbers are unique per street).
- **Getting the data.** The MCLU street list (ID_VOIE, name, length, quartier, commune) is published as a PDF (Sep 2025) and is imported. Address points sit on PADA's partner geoportal under the 24 Jan 2023 data-sharing convention (partners named then: La Poste, DGI, INS, network operators). N-Ways asks the MCLU to join it, with the terms (licence, refresh) to be agreed. Until then, PADA addresses enter only from people (a photo of the plate, the address typed at the gate), validated against the street list; they are never guessed from the metric rule.
- **Keeping in sync.** On each PADA release: new addresses are attached to their compounds and shown first, the N-Ways code staying beside them; renamed streets update by ID_VOIE; nothing official is edited by N-Ways. Mismatches seen on the ground (a plate differing from the data) are reported to the MCLU, not "corrected".
- **Where PADA did not go** (precarious quarters, unnumbered back compounds, new builds) and in the rest of the country, the N-Ways code is the address. If PADA or PAVI later numbers the gate, the official address is shown first.
- The remembered form always starts with a name, so it can never be confused with PADA's numeric code d'adresse.
- N-Ways offers its compound registry, gate positions and mapping tables to the MCLU (PADA, PAVI).

## 11. Privacy

Law 2013-450 and ARTCI apply. Codes describe places, never people. The published registry holds every compound in the country, in every quarter alike: code, area, entrance position, use class (homes only as "residential"), kind, size and the names of businesses and public buildings. It holds nothing about people: not who lives there, household counts, Add-my-home photos, parcel references or who confirmed what, and never the NNI or any identity number; nothing links a code to the NNI-linked MaPoste box. A code is an address, not a right or an eviction list; requests about people are answered only under a legal order, logged and reported. N-Ways files its declaration to ARTCI, and the authorisations for phone numbers and hosting outside Côte d'Ivoire, through CERTINUM.

## 12. Limits of this design

- The blocks were cut on the compounds counted at issue; an area that outgrows its block takes an extension block of its name (engine/SPEC.md 4.2, step 6).
- Areas come from OSM place points; some names are odd (a Plateau area is called "Quai Fruitier (QB1 – QB2)") and some towns have one point only. PADA quartiers, communes' lists and local review refine them: since areas are frozen, a refinement adds new areas for new compounds and aliases for names.
- 1,197 plate names wait for the commune's choice; 363 of them are still over the limit provisionally. Only two short forms are documented with a source today; more come from the communes, PADA's quartier names and the people who live there.
- Unit codes are the CNTIG/OCHA pcodes; if an official codification is published, it is recorded beside them and issued codes are not rewritten.
- The class inference is mostly a default today.
- PADA data is not open; the matching plan depends on an agreement.
- Projection used by Ivorian cadastral plans is not verified; how people read digits (pairs in French) is common practice, not a measured fact. Both are tested in the pilot.
