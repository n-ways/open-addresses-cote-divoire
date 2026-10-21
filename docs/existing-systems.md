# Côte d'Ivoire: existing postal and address systems

Sources were consulted between 17 and 20 October 2026. "Opened" means the page or file was read; "snippet" means it was seen only in a search result and is not verified. Full list in [SOURCES.md](../SOURCES.md).

## Verdict

**No postal code in use, at any level.** Mail goes to post-office boxes identified by a two-digit post-office number ("06 B.P. 37 Abidjan 06"). A door-level street address system exists in the **District of Abidjan** (PADA: named streets and metric building numbers, State project, 2017 to 2025), and is planned for **Yamoussoukro, Daloa and Korhogo** (PAVI, 2024). A numeric "code d'adresse" built on département and commune/sous-préfecture identifiers was approved in February 2025; its format is now public: five digits, the département (3) and the commune (2), written after the street ("495, BOULEVARD DE LA REPUBLIQUE, 00217"). The government still listed a "code postal national" as future work in April 2025.

Where the State already gives an address, that address must come first: a second address for the same gate would compete with the State's programme and confuse residents and services. The N-Ways model for Côte d'Ivoire therefore:

1. **shows PADA addresses first, exactly as written**, wherever PADA numbered a gate, and never shows the N-Ways code before or in place of them; the compound's N-Ways code stays beside the official address, for the phone and for the households of a cour behind one gate (data: MCLU street list, public PDF; address points on the PADA partner geoportal under the 24 Jan 2023 data-sharing convention, not open: N-Ways requests access);
2. shows the official address first in PAVI towns (Yamoussoukro, Daloa, Korhogo, Bouaké) as soon as PAVI delivers; until then the N-Ways code is the address there;
3. is the address where nothing official exists: precarious quarters PADA excludes, gates PADA did not number, and the rest of the country;
4. never calls itself a postal code, and never looks like the numeric code d'adresse (an N-Ways code always starts with a name). P.O. boxes and office codes are not addresses; they stay as pointers.

## 1. La Poste de Côte d'Ivoire

| Item | Finding | Source |
|---|---|---|
| Delivery | "Deliveries are made to P.O. Boxes. However, home deliveries are being tested for a single building." | UPU addressing sheet, dated 09/2004 (opened) |
| Office code | "For home and P.O. Box deliveries alike, the two-digit post office code must be included." Format: office code + B.P. + number + locality + office code, e.g. `06 B.P. 37 ABIDJAN 06` | same |
| Home delivery code | "the delivery office code is preceded by a 1 ... The code 104 therefore indicates a home delivery made by post office 04" (a test, not a system) | same |
| Digital P.O. box | adresse-postale.maposte.ci: subscribe, renew, pay, obtain address certificates; "Boîte Postale Digitale" | La Poste site (opened) |
| MaPoste app | Launched 16 Jan 2026 by ONECI and La Poste: a digital P.O. box linked to the national identity number (NNI) | Osiris, 19 Jan 2026 (opened) |
| Mandatory digital box | NNI-linked digital box compulsory from 1 Mar 2026; ~5,000 independent couriers enrolled on La Poste's POLI platform (poli.ci) | Government bulletin, 3 Feb 2026 (opened) |
| what3words | Adopted by La Poste in Dec 2016; page still live, "Bien adresser pour mieux livrer" | laposte.ci.post/adresse-what3words (opened); what3words partner page (snippet) |
| "99326" | Circulates online as an Abidjan postal code; no authoritative source; do not use | Datahub licensing notes (snippet) |

The UPU sheet is 22 years old; no newer one was found. Nothing found from 2026 describes a postal code.

## 2. PADA: Projet d'Adressage du District d'Abidjan

| Item | Finding | Source |
|---|---|---|
| Responsible body | Ministère de la Construction, du Logement et de l'Urbanisme (MCLU), Direction de l'Adressage (DARRU; director Alphonse N'Guessan) | KOACI 2023, Le360 2025 (opened) |
| Funding, contractors | World Bank via PACOGA; IGN FI + GEOFIT + Défis & Stratégies; BNETD implements and controls; planned Jul 2021 to Jul 2024, 13 communes, ~15,000 roads | IGN FI reference page (opened) |
| Streets | Three tiers: boulevards, avenues, rues; ~70% named after people; names proposed by CAPEC/CIRES (Université Félix Houphouët-Boigny), validated by the District (main roads) and communes, adopted by the Council of Ministers | KOACI, 27 Jul 2023 (opened) |
| Street IDs | Official list (182 pages, modified 8 Sep 2025): ORD, **ID_VOIE** (5-6 digits), length in metres, name, quartier, competence; ~11,450 rows, Yopougon looks incomplete | construction.gouv.ci PDF (opened, parsed) |
| Building numbers | **Metric**: the number is the distance in metres from the start of the street ("numéro 115 ... à 115 mètres du début de la voie"); even on one side, odd on the other; no bis/ter | KOACI, 18 Jan 2023 (opened) |
| Signs | Orange boulevards, green avenues, blue streets (Marcory) | Le360, 18 May 2025 (opened) |
| Certificates | First 14 certificats d'adresse on 16 Dec 2021 (Koumassi, Marcory) | Fraternité Matin (opened) |
| Progress | Feb 2025: 14,279 streets identified, 348,216 occupied units planned, >295,000 surveyed, ~256,000 marked. Apr 2025: 12,000 of 14,000 names validated, 400,000 units counted, 2,300 names put into Google Maps. Nov 2025: ~500,000 addresses, 210,000 plates | KOACI 27 Feb 2025, gouv.ci newsletter 2025, Team France Export 24 Nov 2025 (opened) |
| End date | Completion announced for 31 Dec 2025; cost 12 billion FCFA; **precarious quarters excluded**; ~15 cities by 2030 | Fraternité Matin, 1 Oct 2025 (opened) |
| "Postal code" | Director: a "code postal au standard international" was set up; an address = "une adresse, un numéro, une rue et un code postal"; no format | Le360, 18 May 2025 (opened) |
| Code d'adresse | "le Conseil a validé un code d'adresse numérique composé d'une série de 0 à 9 chiffres, basé sur la codification des circonscriptions géographiques ... les identifiants du Département et de la Commune/Sous-Préfecture." Which council, length and example not given | KOACI, 27 Feb 2025 (opened) |
| Data sharing | Convention-cadre de partage de données, 24 Jan 2023; partner geoportal and data-sharing platform (Apr 2024); no public lookup or open data found | Abidjan.net/AIP 2023, Fraternité Matin 8 Apr 2024 (opened) |
| Code d'adresse format | Now public: **five digits, département (3) + commune (2)**, written after the street: "Hôtel de Ville, 495, BOULEVARD DE LA REPUBLIQUE, 00217" (002 = Abidjan, 17 = Le Plateau). 14,276 roads named; 290,805 house plates installed (about 95% of the target); 25,750 of 87,914 street signs up, sign installation suspended in November 2025 to fix defects; PAVI now names Yamoussoukro, Bouaké, Korhogo and Daloa; 15 regional hubs by 2030 | Abidjan Planet, 2026 (opened) |
| 2026 | No completion report; no open data or public lookup of PADA address points found | search, October 2026 |

**Earlier programme.** The World Bank's review of street addressing in African cities (Farvacque-Vitkovic et al., *Street Addressing and the Management of Cities*, 2005, opened) records an earlier Abidjan programme run by BNETD: the ten municipalities divided into 55 lettered addressing zones, even-numbered streets parallel to the coast and odd-numbered streets perpendicular to it ("Bd A5 Latrille" in Cocody), signs in Abidjan, Abengourou and San-Pédro, and metric building numbers that were planned but not applied. The same review measures US$5.7 per addressed doorway over 21 completed programmes (2005 prices).

**PAVI** (Projet d'Adressage des Villes de l'Intérieur): preliminary study validated 10 Sep 2024 for Yamoussoukro, Daloa and Korhogo, kick-off in Yamoussoukro 12 Sep 2024 (Connection Ivoirienne, opened). Bouaké and San-Pédro announced earlier; no evidence they started.

**Precarious quarters**: 199 in 2024, about 20% of Abidjan's population; PADA does not address them (Fraternité Matin, Oct 2025). The 2024 demolitions (Gesco, Boribana, Banco 1, Abattoir) moved tens of thousands of people (Council of Ministers, 13 Mar 2024, opened; Amnesty figure snippet only).

## 3. Land parcels (not addresses, but they identify plots)

| System | Finding | Source |
|---|---|---|
| IDUFCI | Unique parcel identifier, Décret 2019-221 (13 Mar 2019): 20 characters = country (3) + circonscription foncière (3) + 11-digit sequence + destination code (3), with a hidden QR security code; mandatory on every act; changes on split, merger or boundary change | MCLU PDF (opened, OCR) |
| ACD | Arrêté de Concession Définitive, issued by MCLU: 269,173 signed 2013 to 2025 | construction.gouv.ci (opened) |
| SIGFU | MCLU land information system: ~887,000 parcels vectorised for Grand Abidjan (Apr 2023); public check of lotissement status | SIGFU News n°3 (opened) |
| Rural | Loi 98-750 (amended 2004, 2013, 2019-868): AFOR issues certificats fonciers | afor.ci (opened) |
| Datum | Décret 2019-220: **ITRF2014 epoch 2010.0** is the sole legal reference; legacy Clarke 1880 / Abidjan 1987 (EPSG:4143) and WGS84 | SIGFU News (opened), epsg.io (opened) |
| Survey | "Toute personne ... doit solliciter un géomètre-expert agréé pour établir le plan de sa parcelle"; MCLU's DTC checks plans | SIGFU News (opened) |

Typical lotissement references ("Îlot 23, Lot 456") and real IDUFCI examples were not verified.

## 4. Digital location codes

- **what3words**: promoted by La Poste CI (proprietary, licensed).
- **Plus Codes (Open Location Code)**: open (Apache-2.0), offline, no official use found in Côte d'Ivoire.
- **CNTIG** (Comité National de Télédétection et d'Information Géographique, Cocody Danga): E-Commune, map library, Géoportail; produces the boundary datasets OCHA republishes (cntig.net, opened).

## 5. OpenStreetMap

A count of addr:* tags through Overpass could not be made (the service was unreachable). In the OpenStreetMap extract used for this repository (Abidjan box, 17 October 2026): 9,101 of 46,091 highway ways carry a name; no "NN.NNN"-style street codes; 452 named place points (quartiers, neighbourhoods, villages); 1,822 gate nodes and 6,493 wall/fence ways. Whether PADA names were imported into OSM is unverified.

## 6. Administration (the hierarchy codes hang off)

14 districts autonomes (Décret 2021-276 made the 12 others autonomous like Abidjan and Yamoussoukro), 31 régions, 108 départements, 509 sous-préfectures, 201 communes, 8,571 villages (MIS-CNFCI data, economie-ivoirienne.ci, page dated 16 Jan 2025, opened). Abidjan: 13 communes (10 historical + Anyama, Bingerville, Songon). RGPH 2021: 29,389,150 inhabitants (snippet); Abidjan about 21.5% (about 6.3 million, computed).

## 7. What this repo takes from each

| Existing system | Use in the N-Ways model |
|---|---|
| PADA street + metric number | Shown first; stored on each gate (ID_VOIE, number); N-Ways code links to it |
| PADA code d'adresse (5 digits, département + commune: 00217) | Shown beside an official PADA address when one is known; the remembered N-Ways form starts with a name, so it can never be mistaken for it; the unit table maps each Abidjan commune to its code as the codes are published |
| La Poste B.P. + office code | Free text on the profile of businesses that publish it; never inferred for homes |
| IDUFCI / ACD / certificat foncier | Optional cross-reference on a compound when the property owner adds it; never displayed publicly without consent; never treated as proof |
| what3words | Not used |
| Plus Codes | The spot code (implemented in this repo's engine) |
