# N-Ways Côte d'Ivoire engine — specification

Specification 1.0, in force since the issue of 20 October 2026: 7,956,622 codes, one for every compound, frozen in `engine/data/register.json` (areas, blocks, frames) and published in `registry/`. Reference implementation: [reference/ci_engine.py](reference/ci_engine.py) (Python standard library only), tests: [reference/test_ci.py](reference/test_ci.py), vectors: [reference/test_vectors.json](reference/test_vectors.json). Words MUST, SHOULD, MAY as in RFC 2119.

## 1. Objects

| Object | Identifier | Example |
|---|---|---|
| Official address (PADA) | key `PADA:<ID_VOIE>:<number>`; shown first, exactly as PADA writes it; the compound keeps its N-Ways code beside it (§11) | PADA:92799:115 → "115, Rue des Moineaux, Le Plateau" (number illustrative) |
| Unit | 6 digits: sous-préfecture pcode digits, or Abidjan commune 010111-010120 | 010120 (Yopougon) |
| Plate name | the area's short name used in the code: ≤ 12 characters, ≤ 2 words (§4.4); the official name is kept beside it | `Remblais` (official "Koumassi remblais") |
| Name key | folded plate name (§4.1); owns one national number range | `bonoumin` (Bonoumin) |
| Code area | unit + 3-digit index; owns one or more blocks of its plate name's range (§4.2) and a frozen frame | 010114-083 (Bonoumin, block 4000–8399) |
| Compound | unit + area + number (4 or 5 digits, fixed per name) + Damm over name key + number | CI-010114-083-6136-2 |
| Structure | compound + `.n` | CI-010114-083-6136-2.2 |
| Entrance | compound + `/n` (`/1` = primary gate) | CI-010114-083-6136-2/1 |
| Spot | Open Location Code, 11 characters | 6CQR926H+7Q7, short "926H+7Q7 Cocody" |

## 2. Forms

- **Remembered**: `<plate name> · <NN NN>`. Number split in pairs from the right (`1817` → `18 17`, `48217` → `4 82 17`). No check digit. It MUST decode to at most one area in the whole country with nothing else (§4.2).
- **Written**: `<plate name> <number in pairs>[ (<unit name>)]`, e.g. `Bonoumin 61 36 (Cocody)`: what plates and forms show. No check digit is ever shown to people or asked of them, since a digit nobody can check by eye only adds something to mistype; the check lives in the machine form only, and a decoder accepts `<number>-<check>` from systems that send it. The unit name is a display label only: decoders MUST NOT need it and MUST reject the code if a given label contradicts the decoded area (§9).
- **Machine**: `CI-<unit>-<area>-<number>-<check>[.<structure>][/<entrance>]`, regex `^CI-(\d{6})-(\d{3})-(\d{4,5})-(\d)(?:\.(\d{1,3}))?(?:/(\d{1,2}))?$`. The number is the same as in the remembered form.
- **Link**: `https://nways.ng/a/<machine>`; QR on plates encodes the link.

- **Plate** (on a gate): the plate name in large type, the number in pairs, then in small type the gate's Plus Code or the official name (context only), the commune (label only) and the QR (which carries the machine form). No check digit.

Parsing (§9) MUST accept all three, case-insensitive, with any of space, `·`, `.` or `-` between name and number, and digits with or without spaces; the official name typed instead of the plate name is accepted through the alias table (§4.4).

## 3. Check digit (Damm)

Input: `name_digits(key) + number`, where `name_digits` writes each character of the name key (§4.1) as two digits (`a`–`z` → 10–35, `0`–`9` → 00–09) and `number` is the 4- or 5-digit number. Table: the standard order-10 weakly totally anti-symmetric quasigroup (Damm 2004), in `DAMM` in the reference code. `interim = 0; for d: interim = T[interim][d]`; the check digit is the final `interim`. A code is valid when running the table over digits + check gives 0. Damm detects every single-digit substitution and every transposition of adjacent digits (tested exhaustively on 300 random 14-digit strings). Vectors: `572` → 4; `0101140834817` → 8 (plain Damm); key `sikogi` → `281820241618`, number 18817 → 7; `madina` 4600 → 7; `belevile` 45000 → 0; `bonoumin` 5552 → 0, 6136 → 2.

**Binding name + number + area.** The area is a function of (name key, number) through the frozen block table (§4.2), so the check binds all three:

- written form: a wrong digit or an adjacent swap in the number always fails the check (the name key digits are unchanged), including when the wrong number lies in another block of the same name; a number that lies in no block of the name is rejected before the check;
- machine form: the decoder MUST verify that the area `<unit>-<area>` owns a block containing `<number>`, then the check over that area's name key; a wrong unit or area index therefore fails the ownership test even if the check happened to match.

The area digits are deliberately not hashed into the check: a number typo that changes the area would then change several input digits at once, which Damm does not guarantee to catch.

The check is in the machine form only (APIs, QR codes, partners' systems); it is never shown to people or asked of them.

## 4. Units and code areas

Data files (in `model/`):

| File | Content | Licence of the source |
|---|---|---|
| units/sous-prefectures.geojson | 510 SP polygons, simplified to ~40 m | CNTIG/OCHA via HDX, CC BY-IGO |
| units/abidjan-communes.geojson | 10 Abidjan communes | OpenStreetMap, ODbL |
| areas/admin-units.csv | 520 units: code, name, kind, département, région, box, area count | derived |
| areas/areas.csv | 9,834 interim code areas: unit, index, name (official), plate, plateRule, needsCouncilChoice, plateCandidates (`|`-separated, ≤ 3), plateReason, plateSource, place kind, point, digits (the length of its name's numbers) | OpenStreetMap, ODbL; plate columns derived (tools/name_ranges.py) |
| areas/name-blocks.csv | one row per block: name key, plate name, unit, index, estimated compounds, digits, block_lo, block_hi, qualifier | derived (tools/name_ranges.py) |
| areas/plate-aliases.csv | official names typed instead of a plate name: alias key, official name, plate key, areas, status (kept/dropped), note | derived (tools/name_ranges.py) |
| areas/references.csv | reference town per unit for short Plus Codes, as it is written after the code (§7) | OpenStreetMap / derived |
| units/sous-prefectures.csv | structures per SP | OSM + Google/Microsoft |

**Lookup** `unit_at(lat, lon)`: Abidjan communes first, then SPs; bounding-box filter then even-odd point-in-polygon. Points on the simplified boundary are ambiguous within ~40 m; the registry (not the polygon) is authoritative for issued compounds.

**Area of a footprint** `area_at(lat, lon)`: the nearest place point of the same unit (equirectangular distance); a footprint in no unit polygon takes the nearest place point in the country. City nodes inside Abidjan communes are excluded. This is the rule the first issue used (tools/assign-areas.py).

**Frozen areas.** Every area was frozen at the first issue (20 October 2026): unit, index, plate and official names, name key and id, digits, blocks and **frame**, the box of its compounds' reference points widened by 0.0005° on every side (`area_frame`; an area with no compound yet takes the box around its place point), stored in `engine/data/register.json`. A new home takes the area of the nearest issued code within 250 m, else the area whose place point is nearest (§10).

**Index**: 3 digits, rank of the place in the unit north→south then west→east at freezing; stored, never recomputed. Max 999 per unit (largest today: Bouaké 165).

**Split rule**: if `compounds × 2 > 9,000`, the area MUST be split into named sub-areas before issue. Where no names exist, the area keeps one large block in a 5-digit range; it is flagged for later split (existing codes stay; the new sub-areas get new blocks of their own names for new compounds only).

### 4.1 Name key (normalisation)

`name_key(name)`, applied to the plate name (§4.4) for ranges and the check digit, and to the official name for aliases:

1. NFKD, combining marks removed, lower case; `œ` → `oe`, `æ` → `ae`.
2. Split into words on every character that is not `a`–`z` or `0`–`9` (hyphens, apostrophes `'` `’`, dots, brackets, spaces).
3. Drop the words `le la les l de du des d et au aux`.
4. Word folds: `st` → `saint`, `ste` → `sainte`, `pk`/`kilometre(s)` → `km`, `qt`/`qrt`/`qtier` → `quartier`; Roman numerals `i`–`x` → `1`–`10`.
5. In each word that is not all digits, in this order: a final `s` dropped if the word has 4+ letters; `ou` before `a e i y` → `w`; `y` → `i`; `ph` → `f`; `qu`/`q` → `k`; `c` before `a o u` → `k`; every run of a repeated letter → one letter.
6. Join the words with nothing between.

Folding can only merge names, never split one name in two. Vectors (test_vectors.json `nameKeys`): Koffikro = Kofikro → `kofikro`; Adjouffou = Adjoufou → `adjoufou`; Riviéra II = Riviera 2 = RIVIERA-2 → `riviera2`; Les Lauriers = Lauriers → `laurier`; Kouassikro = Kwassikro → `kwasikro`; Cocody = Kokody → `kokodi`; PK 18 = Kilomètre 18 → `km18`; N'Guessankro = N’Guéssankro → `nguesankro`; Saint-Michel = St Michel → `saintmichel`.

### 4.2 National ranges and blocks

Every name key owns the numbers 1000–99999 nationally. Allocation, computed by `tools/name_ranges.py` until the first issue and then frozen:

1. `block_size(c) = max(100, ceil(2c / 100) × 100)` for an area with `c` compounds.
2. Areas of one key are ordered by unit code, then area index; blocks are laid end to end from the bottom of the name's range.
3. `allocated = Σ block_size`; `spare = max(500, ceil(0.10 × allocated))`. If `allocated + spare ≤ 9,000` the name has **4 digits** (blocks from 1000); else if `≤ 90,000`, **5 digits** (blocks from 10000; 1000–9999 is never issued for that name, so a 4-digit "Belleville" code is a typing error); else the name needs a **qualifier** (§4.3).
4. Decoding `resolve(name, number)`: the one block of `name_key(name)` with `lo ≤ number ≤ hi`, else nothing. Blocks of one key never overlap, so the result is unique in the country.
5. **Frozen.** After a block's first issued code it MUST NOT move, shrink or be renumbered. Changing an area's name adds an alias; the area keeps its blocks in the old key's range.
6. **New area with an existing name**, or **an area whose block is full**: `next_block(key, c)` gives `[top + 1, top + block_size(c)]`, where `top` is the highest number of any block of that key in the same digit space; if the 4-digit space is used up, the block is taken from the name's 5-digit space (10000 upward). Earlier codes never change.
7. **Skipped stretches.** A key `k` MUST NOT use the five-digit numbers `d0000`–`d9999` when the key `k + d` (the same name followed by the digit `d`) also exists: Koffikro does not use 10000–29999 because Koffikro 1 and Koffikro 2 exist. `skipped_stretches(key)`; a block that would overlap a skipped stretch starts after it (`skip_forward`), at allocation and in `next_block`. A name with skipped stretches needs a qualifier when its blocks and spare exceed `90,000 − 10,000 × stretches`. With this rule, "Name d NN NN" typed without the `·` reads one way only among plate names (§9); the build checks it (`ambiguousWithoutSeparator`, empty). The rule looks at plate names only, and blocks never move after issue, so an official name `k + d` typed instead of another plate name can still read the same text as the plate name `k` with a number in `d0000`–`d9999` (Air France, plate name of areas in Korhogo and Man, and Air France I and Air France II, official names of France I and France II in Bouaké: "Air France 1 10 00" and "Air France 2 21 00" each read two ways; no other name does). §9 decides between such readings, so every issued code still reads one way.

Real counts (model/stats/name-repeats.json): 8,618 plate-name keys for 9,834 areas (8,903 keys on the full official names); 818 keys repeat, in 2,034 areas (636 in 1,567 on the full names); largest range Belleville (7 areas, 52,400 numbers, 5 digits, 30000–82399); most areas Akakro and Koffikro (16 each, 5 digits); 8,307 keys have 4 digits, 311 have 5; none needs a qualifier.

### 4.3 Qualifiers

If `allocated + spare > 90,000`, the name is qualified once: each of its areas takes the name of its unit (commune of Abidjan or sous-préfecture) in front, the way Ivorians already say "Yopougon Sicogi" or "Koumassi Remblais", and the qualified names get their own keys and ranges. The decision is stored in name-blocks.csv (`qualifier`) and listed in name-repeats.json (`qualifiedNames`, empty today). A qualifier is never added to a name after its first issue. The qualified name MUST still pass `plate_ok` (§4.4); if it does not, the commune chooses the plate name.

### 4.4 Plate names

Every code area carries its **official name** (`name`, the full name, printed small, never required) and its **plate name** (`plate`, the name in all three forms and on the plate).

**Limit** (`plate_ok`, in ci_engine.py through plate_names.py): `plate_length(p) ≤ 12`, where every character of the NFC form counts one (letters, an accented letter, spaces, hyphens, apostrophes); `word_count(p) ≤ 2`, where words are the parts between spaces or hyphens that are not linking words (`de du des d la le les l et sur en au aux à`); at most one word containing digits (`number_words`). Engines MUST refuse to load an area whose plate fails the limit unless the area has `needsCouncilChoice = 1` (a provisional plate, confirmed by the commune before first issue).

**Derivation** (tools/ci_plates.py, rule in engine/reference/plate_names.py), in order, first match wins:

1. `known`: a documented short form, with its source in `plateSource` and SOURCES.md (Deux Plateaux → II Plateaux; Gonzagueville → Gonzague).
2. `clean`: the spoken form (first of `A;B`, no-break spaces, ` – ` and ` & `, `n°`, `(2)` → `2`); then drop text in brackets, text after `/`, a second spelling after `ou`/`dit`, generic words (`quartier lotissement cité zone secteur village hameau campement`, `village de`, `résidence(s)`, `les résidences`) and linking words left at either end. A generic word stays when removing it leaves only weak words or a number. If the result fits: `as-is` (unchanged) or `cleaned`.
3. `abbreviated`: `Saint` → `St`, `Sainte` → `Ste`, `Notre-Dame` → `N.-D.` before another word, if the result fits (`name_key` folds St/Ste back).
4. `distinctive`: candidates are runs of whole words that fit, never starting or ending on a linking word, never only weak or settlement words, never a number alone, never cutting between a binding word and the next (Saint, Jean...); scored by the rarity of their words among all area names, × 1.5 when they keep the last word; a candidate that drops a trailing qualifier (number, Nord, Extension, droite...) is never automatic. The best is taken when it is at least 1.5 × the next, has 4+ letters, is not in `AVOID` and drops only generic or settlement words (`cité carrefour camp gare ville rue route marché...`) or the name of the area's own unit, département or an Abidjan commune.
5. `council`: everything else, `needsCouncilChoice = 1`, `plateCandidates` (≤ 3, non-town first), `plateReason`; the plate is the first candidate, or the cleaned name if there is none or if every candidate is a town. A hyphenated name with no candidate offers its parts.

`AVOID` = name keys of every sous-préfecture, département, Abidjan commune and of the large cities of the region (a plate reading like another city would mislead: Abidjan, Yamoussoukro, Dakar, Lomé, Cotonou, Porto-Novo, Accra, Kumasi, Lagos, Bamako, Ouagadougou, Bobo-Dioulasso, Conakry, Freetown, Monrovia, Bissau, Praia, Libreville, Yaoundé, Douala, Niamey, Nouakchott), minus the area's own unit and département (and Abidjan for an area in the Abidjan district).

**Aliases.** For every area whose official name (or full OSM spelling) has a key different from its plate key, `plate-aliases.csv` maps the official key to the plate key and the areas. `resolve(name, number)` MUST: use the key directly if it is a plate key; else, if it is a kept alias, resolve in the plate key's range and return the area only if it is one of the alias's areas. An alias MUST be dropped (status `dropped`) when it equals a plate key or when two plate keys claim it. A text that reads both through a plate name and through an alias is decided by §9 step 2: the plate name first.

Counts (name-repeats.json `plateNames`): official names over the limit 1,414 of 9,834 (1,395 by characters, 192 by words); as-is 8,378, cleaned 212, abbreviated 2, known 2, distinctive 44, council 1,196 (+1 cleaned name equal to a town elsewhere): 1,197 `needsCouncilChoice`, 363 of them over the limit provisionally; 1,070 aliases kept, 4 dropped.

## 5. Registry construction

Input per area: footprints (OSM, Google Open Buildings, Microsoft, N-Ways), enclosures (closed OSM `barrier=wall|fence|hedge`, the compounds of the N-Ways routing data), gates (OSM `barrier=gate|lift_gate|...`, the gates of the N-Ways routing data), N-Ways places, parcels where given, people's confirmations.

Steps, in order. **Grouping happens before numbering.**

1. **Footprints**: OpenStreetMap buildings and the Google/Microsoft footprints that no OpenStreetMap building overlaps (the Overture conflation N-Ways' map data is built from), whose centre is inside the national border (below, "The border decides").
2. **Enclosures**: structures whose centroid is in the smallest closed enclosure ≤ 6,000 m² form one compound (rule `enclosure`, confidence 0.85). Enclosures > 6,000 m² that contain ≥ 15 structures are **estates**: their gates become `estate-gate` entrances; grouping continues inside.
3. **Parcels**: a provided cadastral parcel (SIGFU/IDUFCI/ACD plan) groups the structures whose centroid it contains (0.9).
4. **Annexes**: each remaining structure < 25 m² joins the nearest structure ≥ 25 m² whose footprint is within 5 m (true polygon distance) (0.6). The reference code approximates the gap with centroids and equivalent radii.
5. **People**: confirmed statements override rules 2–4 before issue.
6. **Singles**: everything else is its own compound (0.4).
7. **Reference point** per compound: the primary gate if known; else the area-weighted centroid of its structures.
8. **Order**: Hilbert index (order 16, i.e. 65,536 × 65,536 cells) of the reference point in the area frame `(x0, y0, x1, y1)`: `gx = floor((lon − x0)/(x1 − x0) × 65535)`, `gy` likewise, clamped; index by the standard rotate-and-flip loop (`hilbert_index`).
9. **Number**: `N` compounds; the area's block `[lo, hi]` (§4.2); `capacity = hi − lo + 1`; `step = max(1, floor(capacity / (N × 1.5)))`; compound i (0-based, Hilbert order) gets `lo + i × step`. The top third of the block, from `lo + floor(2 × capacity / 3)`, is the **tail reserve**. If a number would enter the tail reserve, the area MUST get a larger block before issue (or be split).
10. **Structures** inside a compound: `.1` = largest footprint, then decreasing area; later structures take the next free index.
11. **Entrances**: `/1` primary gate (OSM gate on the enclosure, else the point of the compound outline nearest the street the footprint faces, flagged "inferred"), then others.

**The border decides.** The national border is OpenStreetMap's admin_level 2 boundary of Côte d'Ivoire. A code MUST only be issued for a compound whose entrance (its reference point, step 7) lies inside the border or within 300 m of it, measured on a local plane at the point's latitude (110,574 m per degree of latitude, 111,320 m × cos(latitude) per degree of longitude). Unit, zone and area outlines from other sources (the sous-préfecture and commune polygons, geoBoundaries, GADM and the like) may spill over the border; they never decide, and a point they hold that is more than 300 m outside the border is in a neighbouring country and gets no code. A build MUST read the border from the same OpenStreetMap extract as its footprints, keep only footprints whose centre is inside it (step 1), and drop any compound whose reference point lies more than 300 m outside it before numbering. An issuer that ships a simplified border MUST record the simplification's largest deviation d and accept a point only within 300 − d m of the simplified line, so that no point more than 300 m outside the true border is accepted (`engine/data/outline.geojson`: about 50 m tolerance, `maxDeviationM`; `engine/reference/border.py`). The same holds when an entrance is moved.

**After issue** (incremental):

- **New compound** (new footprint or Ajouter ma maison): compute its Hilbert index; take the previous and next issued compounds in Hilbert order (numbers a, b); choose the free number in (a, b) closest to (a+b)/2, lowest on ties; if none, the lowest free number in the block's tail reserve; if the block is full, the first number of a new block for that area (§4.2 step 6). Provisional until confirmed.
- **Demolished**: number retired (status `demolished`), never reused.
- **Split** (one compound becomes several): the part with the largest floor area keeps the number; others take new numbers by the new-compound rule.
- **Merge**: the oldest number survives; the others become aliases resolving to it.
- **Regrouping evidence never changes an issued code**; it only adds aliases or new numbers.

## 6. Building profile

Per structure, each attribute is `{value, source, observedAt, confirmedAt, confidence}`.

| Attribute | Rule |
|---|---|
| useClass | evidence list, highest confidence wins: OSM `building=*` (not `yes`) 0.85; OSM shop/amenity/office/tourism/healthcare tag on the footprint 0.75; N-Ways place point inside the footprint 0.65; OSM landuse polygon containing the centroid 0.5; size: < 6 m² annex 0.4, > 2,500 m² industrial 0.3; default residential 0.45 (0.55 in residential landuse). +0.05 per agreeing source (max 0.95). Residential + commercial/office evidence → `mixed` 0.6. A statement by the owner or a resident, or confirmed visits → 0.9. |
| subClass | Ivorian forms (design.json `structure.profile.useClass.values`); set by tags, places, people; `cour commune` when ≥ 2 dwellings ≥ 25 m² share a compound or a residential structure ≥ 40 m² has aspect ratio ≥ 3 (row of rooms) |
| footprintM2, perimeterM | geodesic (spheroid) area and perimeter of the footprint |
| heightM | OSM `height`, else null |
| floors | OSM `building:levels`; else OSM `height` / 3 (rounded, at least 1); else unknown. The Google/Microsoft `h` is a rendering filler (36 values spread evenly over 3.5–7 m) and MUST NOT give floors. |
| floorAreaM2 | footprint × floors (× 1 when floors are unknown) |
| status | existing, under-construction (OSM `construction` or the compound's owner), ruin, demolished |
| name | businesses and public buildings only |

Per compound: class (one-household, multi-household, multi-storey, mixed, commercial, institutional, industrial, agricultural, unknown) from its structures; plotAreaM2 (enclosure, parcel or outline); structures; floorAreaM2 (sum); gates; private: households, parcel references.

## 7. Spot codes (Open Location Code)

Implemented per the public OLC specification (alphabet `23456789CFGHJMPQRVWX`, separator after 8 characters, pairs then 4×5 grid refinement). Spot codes use 11 characters (cell 1/40000° × 1/32000°, about 2.8 m × 3.5 m in Côte d'Ivoire). `olc_encode`, `olc_decode`, `olc_shorten`, `olc_recover` follow the reference algorithms (integer arithmetic: 25,000,000 latitude units and 8,192,000 longitude units per degree). Short display: shorten against the nearest unit reference town (`references.csv`; the largest of the latitude and longitude differences, ties to the lower unit code) by the OLC rule (4, 6 or 8 characters within 0.3°, 0.015° or 0.00075°) and append the town as written in `references.csv`; recovery against the town named reverses it. Test vectors from the OLC test suite are in test_vectors.json (e.g. `20.3701125, 2.782234375, 11` → `7FG49QCJ+2VX`; shorten `9C3W9QCJ+2VX` near `51.3708675, -1.217765625` → `CJ+2VX`).

**Town names.** A short code is only as good as the town after it, so no two reference towns are written alike. A town whose name (folded as in §4.1 step 1: accents, case and punctuation aside) is also the reference town of another unit is written with its département in brackets, the way the country tells such places apart: Lolobo (Attiégouakro) and Lolobo (Béoumi), Santa (Ouaninou) and Santa (Biankouma), N'Guéssankro (Béoumi) and N'Guessankro (Bongouanou), Guézon (Duékoué) and Guézon (Facobly), Nafana (Prikro) and Nafana (Kong) (`tools/build_areas.py`). Decoding folds the typed town the same way, so "Lolobo (Béoumi)", "Lolobo, Béoumi" and "LOLOBO BEOUMI" are one town.

**A town typed without its département** ("QJGF+RJ2 Lolobo") names every reference town of that name. The decoder recovers the code against each, and keeps a reading only if the issuer would have written it: that town is, within 0.0001° (more than twice the half-cell by which a cell's centre can lie from the point it was written for), the nearest reference town to the recovered cell, and shortening the cell against it gives back the typed characters. Exactly one reading kept → that cell; otherwise the decoder MUST refuse and name the labelled towns to choose from. The true reading always passes this test, so a refusal is the only possible failure, never a wrong cell (on the registry: 73,824 of the 79,412 codes written against these towns decode from the bare name, 5,588 are refused, none goes wrong).

**Stored forms.** The town is a display label, not part of the code: the full Plus Code, the machine form, the number and the check digit of every compound are unchanged, and the registry's `plus_code` column carries the labelled town for the 79,412 compounds whose nearest reference town is one of these ten (`QHW6+44J Lolobo (Béoumi)`). A short code written earlier with the bare town still decodes by the rule above or is refused; it is never recovered against the wrong town.

## 8. Offline behaviour

- Every app carries the **national block table** (name-blocks.csv, 9,834 rows, about 0.5 MB, ~150 KB compressed), so any "Name NNNN" in the country decodes offline to its one area, even outside the downloaded packs.
- The app ships, per download pack (one unit or one département): unit polygons, areas, references (~2 MB for the whole country) and the registry of compounds (number, reference point as two int32 in 1e-7°, Hilbert index, status): about 12 bytes per compound, so about 9.6 MB for the District of Abidjan's 797,421 compounds and about 95 MB for the whole country's 7,956,622, before compression. Packs are per unit or per département.
- With no network: the Plus Code is always available; name + number lookups and "Mon adresse ici" work from the pack; Ajouter ma maison reserves the next number locally and marks it provisional; the server confirms or re-assigns on next connection (re-assignment only if another device took the same number first; the earlier claim wins).
- Packs are versioned (`registryVersion`, monotonic); diffs carry only new, retired and alias records.

## 9. Parsing and validation

1. If the text matches the machine regex: validate Damm; unknown unit/area → error; return the record.
   Machine form checks, in order: area exists; the area owns a block containing the number; the check digit over the area's name key and the number.
2. Else if it matches `<name>[ ·.-]<4–5 digits, spaces allowed>[-<check>][, <label> | (<label>)]`: if a `·` is present, it separates name and number; else every split at a space where the rest is 4–5 digits is tried (a plate name may end in a number: "Koffikro 1 12 00"). For each split: `name_key(name)` must be a plate key or a kept alias (§4.4); `resolve(key, number)` → one area, or "not issued" (a number outside every block of the name, including a 4-digit number for a 5-digit name). If a check digit is given, it MUST verify. The splits that resolve are the **readings**; then, in this order:
   1. a label keeps only the readings whose area's unit or département name (folded) it equals; if none, error: a label never redirects a code;
   2. a reading through a plate name comes before a reading through an alias: the plate name is the name on the code people hold (plate, card, written form), the alias only a convenience for the official name typed instead. "Air France 1 10 00 (Korhogo)" and "Air France 1 10 00" are Air France 11000 in Korhogo; "Air France I 10 00 (Bouaké)" and "Air France 1 · 10 00" are France I 1000 in Bouaké;
   3. if readings of more than one code remain, the decoder MUST refuse and ask for the `·` form or the commune. Plate names never collide (§4.2 step 7), so this happens only between two aliases.

   Every issued code therefore decodes to itself from its written and remembered forms (`tools/check-decoding.py` checks all 7,956,622 of them). The app shows the decoded area and its commune before guiding.
3. Else if it is a full or short Plus Code (+ town): decode (§7; a town typed without the département it is written with decodes only when one reading is possible).
4. Else: free-text search (PADA street + number, landmark), outside this engine.

## 10. Ajouter ma maison: checks

**In the app** (SHOULD): the gate point is averaged over at least 5 s with its accuracy reported, with a photo of the gate and the outline (taps on imagery, an AR walk, or an imported plan); the gate lies within 3 m of the outline; the outline is closed and does not cross itself; for AR walks, the Hausdorff distance between the AR shape (placed by the GPS track) and the GPS track is at most 5 m. Plans MUST state their datum (ITRF2014@2010.0, WGS84, or Abidjan 1987 converted with published parameters); others are rejected.

**At the issuer** (MUST; `server/` implements them, and its tests check them against the N-Ways issuer). First, the border decides (§5): an entrance more than 300 m outside the national border is refused (`422 outside_country`), whatever the zone or spot rules would give it. Then:

1. A point within 3 m of an issued compound (its entrance, or a footprint holding the point) already has its code: the issuer answers with that code and issues nothing.
2. An outline has 3 to 500 points and encloses 6 m² to 20,000 m²; an outline that covers more than half of an issued compound's footprint (of the smaller of the two) is that building, and gets its code back.
3. Another door of an existing compound (`of`) lies within 80 m of that compound's entrance and takes a number in the same area.
4. A new compound takes the area of the nearest issued code within 250 m, else the area whose place point is nearest (§4).
5. The number follows §5, "After issue"; the code is provisional, issued on demand; each device or issuing key has a daily limit.

## 11. Official addresses: import and precedence

Where an official door-level address exists, it **is** the address and is shown first, exactly as the State writes it. Every compound also has its N-Ways code (one code for every home, the official address first wherever one exists), to be said on the phone and to tell apart the households of a cour that shares the door.

**Sources.** (a) PADA street list (MCLU PDF, Sep 2025): columns ORD, ID_VOIE, LINEAIRE (m), DENOMINATION PADA, QUARTIER, COMPETENCE, per commune; imported as `official/pada-streets.csv` by the issuer (it is the State's data and is not redistributed here). (b) PADA address points (street ID + metric number + position) from the partner geoportal, once access under the 24 Jan 2023 convention is granted. (c) People: a plate photo or typed address at a gate, accepted only if the street exists in (a) and the number is consistent with the street length (0 ≤ number ≤ LINEAIRE + 20).

**Records.** Compound key `PADA:<ID_VOIE>:<number>` (numbers unique per street). Entrance `official: {system: "PADA", idVoie, street, number, commune, receivedFrom, receivedAt}`. Display string built only from official fields: `<number>, <street>, <commune>`, official spelling and case preserved (display may title-case PADA's upper-case names).

**Precedence.** 1 official address (PADA, later PAVI); 2 N-Ways code; 3 Plus Code. When an official address arrives for a compound (PADA's address points shared with N-Ways, or a resident confirming the plate on the gate), it is attached to the compound's profile (`official`) and shown first; the N-Ways code never changes.

**Sync.** On each official release: add new addresses, update street names by ID_VOIE, retire addresses the release retires (aliases kept). N-Ways never edits official data; a mismatch seen on the ground is a report to the MCLU.

**Never**: inferring a PADA number from the metric rule, or showing an N-Ways code before the State's address on a PADA-numbered gate.

## 12. Interoperability records

- Entrance `official` (above) for PADA/PAVI.
- Unit `officialCode` when the PADA code d'adresse codification is published (alias table, one row per unit).
- Compound `parcelRefs` (private): IDUFCI (20 characters), ACD number, AFOR certificate number, lotissement îlot/lot.

## 13. Versioning

Spec semver. Breaking changes to the machine form are not allowed after the first issued code; additions only (new fields, new aliases).
