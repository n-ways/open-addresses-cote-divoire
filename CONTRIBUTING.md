# Contributing

Thank you for helping. This repository holds the address model of Côte d'Ivoire: its rules, its engine, its registry and the server that publishes it. Contributions are welcome in English or in French.

## What you can propose

- **A correction to the data**: a wrong entrance, a compound that is two homes, a building that is gone, a misspelt area name, a plate name a commune has chosen. Open an issue with the code (machine form, such as `CI-010114-083-6136-2`) and what is wrong. Corrections to entrances, uses and names are settled by the consensus rules of [GOVERNANCE.md](GOVERNANCE.md); a commune's choice of a plate name is recorded with its source.
- **A source**: an official list of quartiers, a PADA or PAVI release, a documented short form people use for a place name. Add it to [SOURCES.md](SOURCES.md) with its date and URL.
- **Code**: a fix or an improvement to the reference engine (`engine/reference/`), the tools (`tools/`) or the server (`server/`). Keep to the Python standard library; run the tests below.
- **A port** of the engine to another language: it must reproduce every case of `engine/reference/vectors.json` and `engine/reference/test_vectors.json`.

## What cannot change

An issued number never changes and is never given to another compound. The machine form, the check digit and the numbering rules are fixed (engine/SPEC.md, section 13): a proposal may add (fields, aliases, areas, blocks), never renumber. A pull request that would change an issued code is declined.

## The issuer rule

Codes are issued by one issuer for the whole country (GOVERNANCE.md, "One issuer"). A pull request cannot add codes to `registry/` by hand: new compounds get their codes from the issuer, whose next registry export then appears here. If you run the server, run it read-only (no `ISSUE_KEYS`) unless the State or N-WAYS LIMITED has designated your deployment as the issuer.

## Before you send a pull request

```sh
python3 engine/reference/test_ci.py                    # the reference engine
python3 -m unittest discover -s engine/reference -p 'test_border.py'   # the border
python3 -m unittest discover -s server/tests -t .      # the server
```

Describe what the change does and why, and its effect on issued codes (normally none). Write comments as notes for the next engineer: what the rule is and why it holds.

## Licences

By contributing you agree that your contribution is licensed as the part of the repository it goes into: code under the Apache License 2.0, data under ODbL 1.0, documents under CC BY 4.0 ([LICENSING.md](LICENSING.md)).

## Contact

hello@nways.ng. Security problems: see [SECURITY.md](SECURITY.md).
