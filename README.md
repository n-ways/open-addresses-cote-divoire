# N-Ways Addressing for Côte d'Ivoire

**Status: issued on 20 October 2026; the registry is complete and frozen.** Every compound in Côte d'Ivoire has an N-Ways code: 7,956,622 of them, provisional until residents confirm them in the N-Ways app. Côte d'Ivoire has no postal code in use; where the State has given a gate an address (PADA in the District of Abidjan, later PAVI in the inland cities), that address is the official one and is shown first, exactly as the State writes it, with the N-Ways code beside it. No part of a code depends on a commune or a sous-préfecture.

A home's code is **the name of a quartier, village or cité people already say plus a number of four or five digits said in pairs**:

| Remembered | Written | Machine form | What it is |
|---|---|---|---|
| `Bonoumin · 61 36` | `Bonoumin 61 36 (Cocody)` | `CI-010114-083-6136-2` | a compound at the Riviera, Cocody |
| `Remblais · 29 66` | `Remblais 29 66 (Koumassi)` | `CI-010115-005-2966-3` | Koumassi Remblais; "Koumassi remblais 2966" finds it too |
| `Madina · 30 00`, `Madina · 40 00` | | | two places of one name, in Sarhala and in Sokoro: one national range, two blocks |
| (a link) | `926H+7Q7 Cocody` | `6CQR926H+7Q7` | any point: its Plus Code |

The remembered form is unique in the whole country on its own: every area with the same plate name shares one national range of numbers, cut into frozen blocks of twice its compounds, so "Name NNNN" never needs a commune after it. People never see or type a check digit: a Damm check over the name and the number lives in the machine form, for systems. The name is a **plate name** of at most 12 characters and 2 words ("Remblais" for "Koumassi remblais", "II Plateaux" for "Deux Plateaux"); the official name still finds it. 1,197 areas wait for their commune to choose a short name; their codes are issued with the first candidate, and the number never changes.

## What is where

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md), [paper.fr.md](docs/paper.fr.md) and the PDFs in [docs/](docs/) | the research paper, in English and French: the existing systems, the data, the model with every formula and a worked example, the implementation, the evaluation of the issued registry, the designs considered, and the benefits for citizens, logistics, emergency services and government |
| [docs/paper/](docs/paper/), [docs/figures/](docs/figures/) | the typesetting of the paper (LaTeX template, style, references) and its figures (TikZ and pgfplots sources with their data, compiled to PDF and SVG) |
| [docs/existing-systems.md](docs/existing-systems.md) | the existing systems: La Poste, PADA and its code d'adresse, PAVI, land systems; verdict and sources |
| [docs/model.md](docs/model.md) | the design notes behind every choice |
| [docs/api.md](docs/api.md) | the registry API, every endpoint with a real request and response |
| [engine/SPEC.md](engine/SPEC.md) | the engine specification (normative) |
| [engine/reference/](engine/reference/) | the reference engine ([ci_engine.py](engine/reference/ci_engine.py), [plate_names.py](engine/reference/plate_names.py)), the national border and its 300 m rule ([border.py](engine/reference/border.py)), its tests ([test_ci.py](engine/reference/test_ci.py), [test_border.py](engine/reference/test_border.py)) and the conformance vectors every port must reproduce ([vectors.json](engine/reference/vectors.json), [test_vectors.json](engine/reference/test_vectors.json)); standard library only |
| [engine/data/](engine/data/) | what a decoder ships: [register.json](engine/data/register.json) (the 520 units with their reference towns, every name with its blocks, every area with its plate and official names, blocks and frame, and the aliases) and [outline.geojson](engine/data/outline.geojson) (the national border: OpenStreetMap's admin_level 2 boundary, simplified to about 50 m, with its largest deviation; the border decides who can have a code) |
| [registry/](registry/) | every issued code, nothing held back: one gzip CSV per unit (`010114.csv.gz` is Cocody), the frozen area table `areas.csv.gz` and `MANIFEST.json` (counts and the SHA-256 of every file) |
| [server/](server/) | the registry server: a ready-made JSON API over the registry, deployable with `docker compose up` ([server/README.md](server/README.md), [openapi.yaml](server/openapi.yaml)) |
| [model/](model/) | `areas/` (units, areas, name blocks, aliases, reference towns), `units/` (the sous-préfecture and commune polygons), `stats/` (the figures of the paper), `design.json` |
| [tools/](tools/) | the scripts that built the inputs, the areas, the compounds, the names and the registry ([tools/README.md](tools/README.md)) |
| [GOVERNANCE.md](GOVERNANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | the rules (including the one-issuer rule), how to propose a change, how to report a problem |
| [LICENSING.md](LICENSING.md), [NOTICE](NOTICE), [SOURCES.md](SOURCES.md), [CITATION.cff](CITATION.cff) | licences and how to credit, sources, how to cite |

## Run the reference engine

```sh
python3 engine/reference/test_ci.py                                   # tests
python3 -m unittest discover -s engine/reference -p 'test_border.py'  # the border
python3 engine/reference/ci_engine.py parse "Bonoumin 61 36"          # remembered form: one area in the whole country
python3 engine/reference/ci_engine.py parse "Bonoumin 61 36 (Cocody)"
python3 engine/reference/ci_engine.py parse "CI-010114-083-6136-2"    # validate a machine code
python3 engine/reference/ci_engine.py parse "Koumassi remblais 2966"  # official name typed: decodes to "Remblais · 29 66"
python3 engine/reference/ci_engine.py check Bonoumin 6136             # written form, and the machine form with its check digit
python3 engine/reference/ci_engine.py spot 5.3606529 -3.9705867       # Plus Code and short form: 926H+7Q7 Cocody
python3 engine/reference/ci_engine.py decode-spot "926H+7Q7 Cocody"
python3 engine/reference/ci_engine.py locate 5.3606529 -3.9705867     # unit and code area
```

Python 3.9 or newer, no packages (see [requirements.txt](requirements.txt)).

## Run the server

```sh
docker compose up -d                       # imports the registry on first start, then serves on :8080
curl -s 'http://localhost:8080/v1/find?q=Bonoumin%2061%2036'
```

or without Docker:

```sh
python3 -m server import --registry registry --db data/addresses.sqlite   # about 4 minutes, 4 GB of disk
python3 -m server serve --db data/addresses.sqlite --port 8080
python3 -m unittest discover -s server/tests -t .                         # tests
```

The server answers exactly what the published registry holds, and an export of its database (`python3 -m server export`) is byte for byte the published registry. A deployment runs read-only unless the State or N-WAYS LIMITED has designated it as Côte d'Ivoire's issuer: two issuers would give the same number to two compounds ([server/README.md](server/README.md), "One issuer"). The API is documented in [docs/api.md](docs/api.md) and [server/openapi.yaml](server/openapi.yaml).

## Build the paper

The paper is written in pandoc Markdown with TeX mathematics ([docs/paper.md](docs/paper.md), [docs/paper.fr.md](docs/paper.fr.md)) and cites [docs/paper/references.bib](docs/paper/references.bib). The PDFs in `docs/` are typeset with LaTeX:

```sh
python3 tools/paper-figures.py      # figure data from registry/ and model/ (docs/figures/*.dat, map.tex, ranges.tex, *-fr.tex)
python3 tools/paper-evaluation.py   # the measurements of the evaluation chapter (model/stats/evaluation.json)
python3 tools/check-decoding.py     # every issued code decoded from its remembered, written and short Plus Code forms
sh docs/paper/build.sh              # figures to PDF and SVG, then both PDFs (pandoc 3, tectonic, pdftocairo)
```

## How the registry was made

```sh
python3 tools/prepare-inputs.py <work>              # enclosures, cités, gates, places, units, national boundary
python3 engine/reference/border.py simplify <work>/country.geojson engine/data/outline.geojson   # the border the server ships
python3 tools/extract-buildings.py <work>           # every footprint inside Côte d'Ivoire (DuckDB, 3 GB cap)
python3 tools/assign-areas.py <work>                # each footprint's code area
python3 tools/sort-buildings.py <work>              # sorted by area
python3 tools/issue_registry.py group <work>        # compounds and profiles, one area at a time
python3 tools/build-register.py <work> --freeze     # plate names, national ranges and blocks on the real compounds, frames
python3 tools/issue_registry.py number <work> <work>/lotes.jsonl.gz   # drops any compound more than 300 m across the border
python3 tools/vectors.py                            # engine/reference/vectors.json
python3 tools/paper-stats.py <work> <work>/lotes.jsonl.gz
python3 engine/reference/border.py check <work>/country.geojson registry   # no code more than 300 m across the border
```

**The border decides.** A code is only ever issued for a building whose entrance lies inside Côte d'Ivoire's national border (the OpenStreetMap admin_level 2 boundary) or within 300 m of it. The sous-préfecture and commune outlines spill over the border in places; they never decide. The build keeps only footprints whose centre is inside the border, numbering drops any compound more than 300 m across it, and the server refuses to issue there (`422 outside_country`). The published registry has no code more than 300 m outside the border (engine/SPEC.md section 5, "The border decides").

The N-Ways backend then issues the codes (`homecodes issue -country CI`), checking every number against the reference's, and exports `registry/`. The register is frozen: a new run adds codes for new compounds and never renumbers an issued one.

## Licence and credit

Code (engine, tools): Apache License 2.0, with [NOTICE](NOTICE). Data (registry, model, engine data): ODbL 1.0. Documents: CC BY 4.0. Credit every use: **"N-Ways Addressing for Côte d'Ivoire, © N-WAYS LIMITED (nways.ng)"**, with a link to this repository ([LICENSING.md](LICENSING.md)). Derived from OpenStreetMap (© OpenStreetMap contributors, ODbL), Google Open Buildings (CC BY 4.0), Microsoft building footprints (ODbL) and the CNTIG/OCHA sous-préfecture boundaries (CC BY-IGO).
