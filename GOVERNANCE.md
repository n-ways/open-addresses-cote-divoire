# Governance: N-Ways Addressing for Côte d'Ivoire

In force since the first issue of codes, on 20 October 2026.

## Steward and issuer

N-WAYS LIMITED maintains the model, the engine and the registry, and is the issuer of N-Ways codes for Côte d'Ivoire. It runs this repository as an open public good that can be handed over: if Côte d'Ivoire adopts the model, the repository (data, engine, rules) and the role of issuer can move to a national body named by the State (for example the MCLU's addressing directorate, CNTIG or La Poste), under the open licences, without forking the engine.

## One issuer

A number may belong to one compound only. Codes are therefore issued by one issuer for the whole country: N-WAYS LIMITED, or the body the State designates in its place.

- The issuer gives numbers one at a time from the register it holds, and publishes the registry (`registry/`) so that every copy can be brought up to date.
- Anyone may run the registry server (`server/`) to look codes up, verify them and give the same answers as the issuer. Such a deployment runs read-only. A deployment issues codes only if the State or N-WAYS LIMITED has designated it as the issuer.
- Two issuers working from separate copies would each see the same number as free and give it to two compounds. Once a number is painted on two gates, the clash can only be undone by renumbering a household, which the rules below forbid.

## What is never decided here

- **Official addresses.** PADA (and later PAVI) addresses belong to the State. N-Ways imports them, shows them first exactly as written and never edits them. A mismatch seen on the ground is reported to the MCLU.
- **Land rights.** An N-Ways code is not a title, an ACD, an IDUFCI, a certificat foncier or a plan. Disputes go to the competent authorities; N-Ways only flags overlaps.

## How data changes

Corrections are settled by agreement among independent people, as for the N-Ways map, and take effect without waiting for an administrator.

| Change | Settled by |
|---|---|
| Gate position, building use, floors, name of a business | independent confirmations: arrivals and deliveries at the gate, residents, couriers, partner data; a statement by the resident or the owner counts twice |
| New compound (Ajouter ma maison) | provisional at once; confirmed by arrivals and deliveries with no dispute, or by new imagery or footprints |
| Dispute (a neighbour contests an outline) | the code stays provisional; nothing new is issued on the overlap; settled by more evidence or by an official document the parties provide |
| Area names and spoken aliases | official names (communes, PADA quartiers) first; local usage by agreement |
| Plate name (the short name in the code, at most 12 characters and 2 words) | a documented short form, else the rule in tools/ci_plates.py; for the areas flagged `needsCouncilChoice`, the commune or sous-préfecture chooses among the candidates. Codes carry the first candidate meanwhile; any later change adds an alias and never changes a number |
| Stale entrances, closed businesses | asked about again by the same signals |

## What never changes

An issued number. Merges create aliases; a split gives new numbers to the smaller parts; a demolished compound's number is retired and never given again. Unit codes follow the OCHA/CNTIG pcodes (and 010111 to 010120 for the communes of Abidjan) until the official codification is published; the official codes are then added as aliases.

## Changes to the format or the rules

- The machine form, the check algorithm and the numbering rules are fixed since the first issue. Changes only add: new fields, aliases, areas, blocks.
- Proposals are made as issues or pull requests to this repository ([CONTRIBUTING.md](CONTRIBUTING.md)), with the reason and the effect on issued codes, and decided by the maintainers with a public record. Partners named in the paper are invited to comment.

## Maintainers

N-WAYS LIMITED (hello@nways.ng). Seats are open to a representative of the MCLU addressing directorate, of the communes (through UVICOCI) and of a courier partner, with at least one maintainer resident in Côte d'Ivoire.

## Privacy and requests from authorities

Law 2013-450 and ARTCI apply (docs/model.md, section 11). The registry describes places and holds nothing about people; it is published in full, the same in every quarter. Requests for data about people (who asked for a code, who confirmed what) are answered only under a legal order, logged, and counted in a yearly transparency note. An address is not a right and not an eviction list.
