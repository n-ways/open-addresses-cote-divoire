# Tools: Côte d'Ivoire's registry

All inputs are read-only: the N-Ways data folder (`NWAYS_ROOT`: OpenStreetMap extract, building footprints, routing compounds and gates) and the N-Ways database (`NWAYS_DB`, a libpq connection string; tables `regions` and `places`). Outside N-Ways, start from the published `registry/` and `model/` instead. Run one heavy step at a time: DuckDB runs with `memory_limit='3GB'` and spills to the work folder; the grouping reads the footprints one code area at a time.

| Step | Script | Writes |
|---|---|---|
| 1 | osmium exports (below) | `admin`, `bar`, `place` `.geojsonseq` in the work folder |
| 2 | `prepare-inputs.py <work>` | `enclosures.geojson`, `estates.geojson`, `gates.csv`, `places.csv`, `units.geojson`, `country.geojson` (the national border: OpenStreetMap's admin_level 2 boundary, unsimplified) |
| 2b | `engine/reference/border.py simplify <work>/country.geojson engine/data/outline.geojson` | the border the server ships: simplified to about 50 m (Douglas-Peucker in metres), with its largest deviation (`maxDeviationM`), under 1 MB |
| 3 | `extract-buildings.py <work>` | `buildings-raw.csv` (every footprint whose centre is inside the border, with its enclosure, estate, unit and places), `buildings-pts.csv` (centre, unit, density), `enclosure-gates.csv` |
| 4 | `assign-areas.py <work>` | `area-of.csv` (each footprint's code area: the nearest place point of its unit) |
| 5 | `sort-buildings.py <work>` | `buildings.csv`, sorted by area |
| 6 | `issue_registry.py group <work>` | `compounds.jsonl.gz` (compounds and profiles), `area-counts.json`, `group-stats.json` |
| 7 | `build-register.py <work> --freeze` | plate names, national ranges and blocks on the real compounds (`name_ranges.py --counts`), every area's frame: `model/areas/*.csv`, `engine/data/register.json`, `model/stats/register.json` |
| 8 | `issue_registry.py number <work> <work>/lotes.jsonl.gz` | the issue batches (lotes), unit by unit, with the reference's numbers; any compound whose point lies more than 300 m outside `country.geojson` is dropped before numbering and counted (`acrossBorder`) |
| 9 | the N-Ways backend: `homecodes issue -country CI -lotes <work>/lotes.jsonl.gz`, then `homecodes export -country CI -out <dir>` | the codes, after checking every number against the reference's; the registry, gzipped into `registry/` |
| 10 | `vectors.py`, `paper-stats.py <work> <work>/lotes.jsonl.gz` | `engine/reference/vectors.json`, `model/stats/building-stats.json` |
| 11 | `engine/reference/border.py check <work>/country.geojson registry` | the count of published codes whose entrance lies more than 300 m outside the border; fails if there is any (the published registry: 0 of 7,956,622) |

### The border decides

A code is only ever issued for a building whose entrance lies inside Côte d'Ivoire's national border, OpenStreetMap's admin_level 2 boundary (`country.geojson`, from the same extract as everything else), or within 300 m of it. The sous-préfecture and commune polygons (`units.geojson`) come from other sources and spill over the border in places: they give a footprint its unit, never its country. So, if you re-run the build:

- step 3 keeps a footprint only when its centre is inside the border (stricter than 300 m), whatever unit holds it;
- step 8 checks every compound's reference point against the unsimplified border again and drops any more than 300 m outside, so no lote can code a building in a neighbouring country (the N-Ways issuer refuses a batch with any such lote whole);
- step 11 checks the published registry.

`engine/reference/border.py` measures on a local plane at the point's latitude (standard library only). The server ships the simplified border and takes its recorded deviation off the 300 m, so it never accepts a point more than 300 m across the true border.

The paper's figures and evaluation are computed from the published `registry/` and `model/` alone: `paper-figures.py` writes the data and the computed TikZ sources in `docs/figures/` (with their French versions), and `paper-evaluation.py` writes `model/stats/evaluation.json` (one pass over every code, about ten minutes and 2.5 GB of memory). `check-decoding.py` decodes every issued code from its remembered and written forms and its short Plus Code with its town, and fails if any does not come back to its own code and cell (a few minutes, one process per core).

`ci_plates.py` holds Côte d'Ivoire's plate-name rules; `build_areas.py` built the code areas from OpenStreetMap place points; `make_vectors.py` writes the design vectors (`engine/reference/test_vectors.json`). The statistics scripts of the design (`stats.py`, `analyse.py`, `places_areas.py`, `national_areas.py`, `abidjan_communes.py`, `sample.sh`) reproduce the figures of docs/model.md and model/stats/.

### osmium exports

```
P=data/osm/ivory-coast-latest.osm.pbf
osmium tags-filter -o b.osm.pbf $P r/boundary=administrative
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o admin.geojsonseq b.osm.pbf
osmium tags-filter -o bar.osm.pbf $P w/barrier=wall,fence,hedge,retaining_wall n/barrier=gate,entrance,lift_gate,sliding_gate,swing_gate n/entrance
osmium export -a type,id -f geojsonseq -o bar.geojsonseq bar.osm.pbf
osmium tags-filter -o place.osm.pbf $P n/place
osmium export -a type,id -f geojsonseq -o place.geojsonseq place.osm.pbf
```
