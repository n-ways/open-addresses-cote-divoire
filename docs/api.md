# The registry API

This is the JSON API of the registry server in [`server/`](../server/). Every request and response below was made against a server holding the complete published registry of Côte d'Ivoire (7,956,622 codes) and copied as it came back. The formal contract, with every schema, is [`server/openapi.yaml`](../server/openapi.yaml); how to deploy the server is in [`server/README.md`](../server/README.md).

Conventions:

- The base path is `/v1`. Examples use `http://localhost:8080`.
- Every response is a JSON object, UTF-8. Field names are stable; new fields may be added, none is renamed or removed.
- An error is `{"error": {"code": "…", "message": "…"}}`, with the HTTP status that fits. `code` is stable and meant for programs; `message` is a sentence meant for people.
- Coordinates are WGS 84 decimal degrees. Distances are metres.
- Words: a **zone** is a sous-préfecture or a commune of Abidjan (six digits, `010114` is Cocody), and one registry file (`registry/010114.csv.gz`). An **area** is a named quartier, village or cité inside a zone (`010114-083` is Bonoumin, in Cocody); the `zone` column of the registry files holds the area id. A **code** is one compound.
- The examples were run in the order of this page, on a deployment started from the published registry; the issuing and changing examples at the end come last.
- To keep this page readable, a card repeated inside another answer is shortened to its first fields and marked `"…"`, and long lists show their first two items and `"… N more"`. Nothing else is changed.

| Method and path | What it answers |
|---|---|
| `GET /v1/health` | the server is up, and what it holds |
| `GET /v1/info` | country, counts, licences, credit, engine |
| `GET /v1/codes/{machine}` | the full card of one code |
| `GET /v1/find?q=` | a code as people say it or type it, a machine form, an official address or a spot code |
| `GET /v1/at?lat=&lng=` | the code of the compound at a point |
| `GET /v1/near?lat=&lng=&radius=&limit=` | the codes near a point |
| `GET /v1/verify?code=` | every check of a machine form |
| `GET /v1/spot?lat=&lng=`, `GET /v1/spot/decode?code=` | spot codes (Plus Codes) |
| `GET /v1/zones`, `GET /v1/zones/{key}` | the 520 zones, and one with its areas |
| `GET /v1/zones/{key}/codes?after=&limit=` | every code of a zone, page by page |
| `GET /v1/areas/{id}`, `GET /v1/areas?name=` | one area, or the areas of a name |
| `POST /v1/codes` | issue a code (designated issuer only, bearer key) |
| `PATCH /v1/codes/{machine}` | confirm or retire a code, or move its entrance (bearer key) |

## Health

```sh
curl -s http://localhost:8080/v1/health
```

`200`

```json
{
  "status": "ok",
  "country": "CI",
  "codes": 7956622,
  "registryExported": "2026-10-20T14:50:41Z",
  "issuing": true
}
```

## Information

```sh
curl -s http://localhost:8080/v1/info
```

`200`

```json
{
  "country": "CI",
  "name": "Côte d'Ivoire",
  "zones": 520,
  "areas": 9834,
  "names": 8618,
  "codes": {
    "total": 7956622,
    "byStatus": {
      "provisional": 7956622
    },
    "byIssue": {
      "bulk": 7956622
    }
  },
  "registryExported": "2026-10-20T14:50:41Z",
  "imported": "2026-10-21T14:14:25Z",
  "changedHere": null,
  "engine": "internal/addressing/ci (SPEC v1.0)",
  "spec": "engine/SPEC.md",
  "licences": {
    "data": "ODbL 1.0 (LICENSE-DATA)",
    "code": "Apache-2.0 (LICENSE, NOTICE)",
    "documents": "CC BY 4.0 (LICENSE-DOCS)"
  },
  "credit": "N-Ways Addressing for Côte d'Ivoire, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-cote-divoire",
  "issuing": {
    "enabled": true,
    "perKeyPerDay": 5
  },
  "forms": {
    "remembered": "Bonoumin · 61 36",
    "written": "Bonoumin 61 36 (Cocody)",
    "machine": "CI-010114-083-6136-2"
  }
}
```

## A code

`GET /v1/codes/{machine}` gives the full card: every column of the registry row under `registry`, exactly as published, and the same values typed and grouped, with the spot code, the area and the zone.

```sh
curl -s http://localhost:8080/v1/codes/CI-010114-083-6136-2
```

`200`

```json
{
  "machine": "CI-010114-083-6136-2",
  "home": "Bonoumin 6136",
  "remembered": "Bonoumin · 61 36",
  "written": "Bonoumin 61 36 (Cocody)",
  "spoken": "Bonoumin, 61 36",
  "number": 6136,
  "check": 2,
  "status": "provisional",
  "issued": "bulk",
  "issuedAt": "2026-10-20T14:18:24Z",
  "entrance": {
    "lat": 5.3606529,
    "lng": -3.9705867,
    "kind": "centre"
  },
  "spot": {
    "plusCode": "6CQR926H+7Q7",
    "short": "926H+7Q7 Cocody"
  },
  "officialAddress": null,
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floorAreaM2": 77.7,
    "rule": "single",
    "estate": null
  },
  "area": {
    "id": "010114-083",
    "plateName": "Bonoumin",
    "officialName": "Bonoumin",
    "nameKey": "bonoumin",
    "nameId": 1481,
    "provisionalName": false
  },
  "zone": {
    "key": "010114",
    "name": "Cocody",
    "kind": "commune-abidjan",
    "departement": "Abidjan",
    "region": "Abidjan"
  },
  "registry": {
    "machine": "CI-010114-083-6136-2",
    "home": "Bonoumin 6136",
    "remembered": "Bonoumin · 61 36",
    "written": "Bonoumin 61 36 (Cocody)",
    "zone": "010114-083",
    "official_name": "Bonoumin",
    "number": "6136",
    "check": "2",
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T14:18:24Z",
    "entrance_lat": "5.3606529",
    "entrance_lng": "-3.9705867",
    "entrance_kind": "centre",
    "plus_code": "926H+7Q7 Cocody",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "77.7",
    "rule": "single",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Côte d'Ivoire, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-cote-divoire"
}
```

A machine form whose check digit is wrong is refused; the right digit is never suggested, since a wrong check means a digit was mistyped somewhere.

```sh
curl -s http://localhost:8080/v1/codes/CI-010114-083-6136-3
```

`422`

```json
{
  "error": {
    "code": "bad_check_digit",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

A valid machine form of a number no compound holds yet:

```sh
curl -s http://localhost:8080/v1/codes/CI-010114-083-8399-5
```

`404`

```json
{
  "error": {
    "code": "not_issued",
    "message": "CI-010114-083-8399-5 is a valid code, but no compound has it yet."
  }
}
```

## Find

`GET /v1/find?q=` reads what a person says or types: the remembered form with or without the `·`, any spacing, upper or lower case, with or without accents, the commune in brackets or after a comma, or the official name of the area instead of its plate name. It also takes a machine form, an official address (when the State has given the gate one) and a spot code.

When a text reads two ways (an official name typed instead of a plate name can end in the same digit as a number: "Air France 1 10 00" is Air France 11000 in Korhogo, and Air France I, the official name of France I in Bouaké, with 1000), the commune given decides, and otherwise the plate name, the name on the code people hold, comes first; a text that still names two codes is refused (`not_found`) with both readings. Every issued code is found from its remembered and written forms.

```sh
curl -s 'http://localhost:8080/v1/find?q=bonoumin%2061%2036'
```

`200`

```json
{
  "form": "remembered",
  "count": 1,
  "results": [
    {
      "machine": "CI-010114-083-6136-2",
      "home": "Bonoumin 6136",
      "remembered": "Bonoumin · 61 36",
      "written": "Bonoumin 61 36 (Cocody)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ]
}
```

The written form, with its commune:

```sh
curl -s 'http://localhost:8080/v1/find?q=Bonoumin%2061%2036%20(Cocody)'
```

`200`

```json
{
  "form": "remembered",
  "count": 1,
  "results": [
    {
      "machine": "CI-010114-083-6136-2",
      "home": "Bonoumin 6136",
      "remembered": "Bonoumin · 61 36",
      "written": "Bonoumin 61 36 (Cocody)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ]
}
```

The official name typed instead of the plate name ("Koumassi remblais" for the plate name "Remblais"):

```sh
curl -s 'http://localhost:8080/v1/find?q=Koumassi%20remblais%202966'
```

`200`

```json
{
  "form": "remembered",
  "count": 1,
  "results": [
    {
      "machine": "CI-010115-005-2966-3",
      "home": "Remblais 2966",
      "remembered": "Remblais · 29 66",
      "written": "Remblais 29 66 (Koumassi)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ],
  "typedOfficialName": true
}
```

A spot code, short form with its town:

```sh
curl -s 'http://localhost:8080/v1/find?q=926H%2B7Q7%20Cocody'
```

`200`

```json
{
  "form": "spot",
  "count": 1,
  "results": [
    {
      "machine": "CI-010114-083-6136-2",
      "home": "Bonoumin 6136",
      "remembered": "Bonoumin · 61 36",
      "written": "Bonoumin 61 36 (Cocody)",
      "status": "provisional",
      "distanceM": 1.4,
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ]
}
```

A commune that contradicts the code: the code is refused, never redirected.

```sh
curl -s 'http://localhost:8080/v1/find?q=Bonoumin%206136%20(Yopougon)'
```

`404`

```json
{
  "error": {
    "code": "not_found",
    "message": "No code in Côte d'Ivoire reads \"Bonoumin 6136 (Yopougon)\": Bonoumin 6136 is in Cocody, not Yopougon."
  }
}
```

A machine form with a wrong check digit:

```sh
curl -s 'http://localhost:8080/v1/find?q=CI-010114-083-6163-2'
```

`422`

```json
{
  "error": {
    "code": "bad_check_digit",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

No query:

```sh
curl -s 'http://localhost:8080/v1/find?q='
```

`400`

```json
{
  "error": {
    "code": "missing_query",
    "message": "Give q: a remembered or written code, a machine form, an official address or a spot code."
  }
}
```

## The code at a point

`GET /v1/at` gives the compound whose entrance is within 12 m of the point (or whose outline, for a compound issued by this server, holds it). Otherwise the answer is `"status": "none"`, with the area a new compound there would join.

```sh
curl -s 'http://localhost:8080/v1/at?lat=5.3606529&lng=-3.9705867'
```

`200`

```json
{
  "status": "found",
  "distanceM": 0.0,
  "code": {
    "machine": "CI-010114-083-6136-2",
    "home": "Bonoumin 6136",
    "remembered": "Bonoumin · 61 36",
    "written": "Bonoumin 61 36 (Cocody)",
    "status": "provisional",
    "…": "the full card, as GET /v1/codes/{machine}"
  },
  "area": {
    "id": "010114-083",
    "plateName": "Bonoumin",
    "officialName": "Bonoumin",
    "nameKey": "bonoumin",
    "nameId": 1481,
    "provisionalName": false,
    "zone": {
      "key": "010114",
      "name": "Cocody",
      "kind": "commune-abidjan",
      "departement": "Abidjan",
      "region": "Abidjan"
    }
  }
}
```

```sh
curl -s 'http://localhost:8080/v1/at?lat=5.3610529&lng=-3.9705867'
```

`200`

```json
{
  "status": "none",
  "canIssue": true,
  "area": {
    "id": "010114-083",
    "plateName": "Bonoumin",
    "officialName": "Bonoumin",
    "nameKey": "bonoumin",
    "nameId": 1481,
    "provisionalName": false,
    "zone": {
      "key": "010114",
      "name": "Cocody",
      "kind": "commune-abidjan",
      "departement": "Abidjan",
      "region": "Abidjan"
    }
  }
}
```

```sh
curl -s 'http://localhost:8080/v1/at?lat=4.8000&lng=-4.0000'
```

`422`

```json
{
  "error": {
    "code": "outside_country",
    "message": "That point is outside Côte d'Ivoire."
  }
}
```

## Codes near a point

`radius` is in metres (default 100, at most 500); `limit` is 1 to 100 (default 20). Results are nearest first.

```sh
curl -s 'http://localhost:8080/v1/near?lat=5.3606529&lng=-3.9705867&radius=40&limit=3'
```

`200`

```json
{
  "point": {
    "lat": 5.3606529,
    "lng": -3.9705867
  },
  "radiusM": 40.0,
  "count": 3,
  "more": true,
  "results": [
    {
      "machine": "CI-010114-083-6136-2",
      "home": "Bonoumin 6136",
      "remembered": "Bonoumin · 61 36",
      "written": "Bonoumin 61 36 (Cocody)",
      "status": "provisional",
      "distanceM": 0.0,
      "…": "the full card, as GET /v1/codes/{machine}"
    },
    {
      "machine": "CI-010114-083-6135-6",
      "home": "Bonoumin 6135",
      "remembered": "Bonoumin · 61 35",
      "written": "Bonoumin 61 35 (Cocody)",
      "status": "provisional",
      "distanceM": 10.9,
      "…": "the full card, as GET /v1/codes/{machine}"
    },
    {
      "machine": "CI-010114-083-6137-0",
      "home": "Bonoumin 6137",
      "remembered": "Bonoumin · 61 37",
      "written": "Bonoumin 61 37 (Cocody)",
      "status": "provisional",
      "distanceM": 12.5,
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ]
}
```

```sh
curl -s 'http://localhost:8080/v1/near?lat=5.3606529&lng=-3.9705867&radius=900'
```

`400`

```json
{
  "error": {
    "code": "bad_radius",
    "message": "radius is in metres, more than 0 and at most 500."
  }
}
```

## Verify a machine form

`GET /v1/verify` runs the checks of engine/SPEC.md section 9 in order and says which passed: the form, the area, the number inside one of the area's blocks, the check digit, and whether a compound holds the code.

```sh
curl -s 'http://localhost:8080/v1/verify?code=CI-010114-083-6136-2'
```

`200`

```json
{
  "code": "CI-010114-083-6136-2",
  "syntax": true,
  "area": true,
  "inBlock": true,
  "check": true,
  "issued": true,
  "status": "provisional",
  "valid": true,
  "reason": null,
  "machine": "CI-010114-083-6136-2"
}
```

```sh
curl -s 'http://localhost:8080/v1/verify?code=CI-010114-083-6163-2'
```

`200`

```json
{
  "code": "CI-010114-083-6163-2",
  "syntax": true,
  "area": true,
  "inBlock": true,
  "check": false,
  "issued": false,
  "status": null,
  "valid": false,
  "reason": "the check digit does not match: a digit is wrong or two are swapped"
}
```

## Spot codes

A short spot code is written with the nearest reference town. No two towns are written alike: a town that is the reference town of two units is written with its département in brackets ("QHW6+44J Lolobo (Béoumi)", "Lolobo (Attiégouakro)"). Accents, case and punctuation of the town do not matter. A short code typed with the bare town ("QHW6+44J Lolobo") is decoded only when one of the towns of that name could have produced it, and is otherwise refused (`422 bad_spot`) with the towns to choose from.

```sh
curl -s 'http://localhost:8080/v1/spot?lat=5.3606529&lng=-3.9705867'
```

`200`

```json
{
  "plusCode": "6CQR926H+7Q7",
  "short": "926H+7Q7 Cocody",
  "reference": "Cocody",
  "zone": {
    "key": "010114",
    "name": "Cocody",
    "kind": "commune-abidjan",
    "departement": "Abidjan",
    "region": "Abidjan"
  },
  "point": {
    "lat": 5.3606529,
    "lng": -3.9705867
  }
}
```

```sh
curl -s 'http://localhost:8080/v1/spot/decode?code=926H%2B7Q7%20Cocody'
```

`200`

```json
{
  "plusCode": "6CQR926H+7Q7",
  "lat": 5.3606625,
  "lng": -3.970578125,
  "reference": "Cocody",
  "code": {
    "machine": "CI-010114-083-6136-2",
    "home": "Bonoumin 6136",
    "remembered": "Bonoumin · 61 36",
    "written": "Bonoumin 61 36 (Cocody)",
    "status": "provisional",
    "distanceM": 1.4,
    "…": "the full card, as GET /v1/codes/{machine}"
  }
}
```

```sh
curl -s 'http://localhost:8080/v1/spot/decode?code=926H%2B7Q7%20Atlantis'
```

`422`

```json
{
  "error": {
    "code": "bad_spot",
    "message": "Unknown reference town 'Atlantis'."
  }
}
```

## Zones

```sh
curl -s http://localhost:8080/v1/zones
```

`200`

```json
{
  "count": 520,
  "zones": [
    {
      "key": "010101",
      "name": "Abidjan",
      "kind": "sous-prefecture",
      "departement": "Abidjan",
      "region": "District Autonome D'Abidjan",
      "areas": 6,
      "codes": 8805
    },
    {
      "key": "010102",
      "name": "Anyama",
      "kind": "sous-prefecture",
      "departement": "Abidjan",
      "region": "District Autonome D'Abidjan",
      "areas": 22,
      "codes": 67622
    },
    "… 518 more"
  ]
}
```

```sh
curl -s http://localhost:8080/v1/zones/010114
```

`200`

```json
{
  "key": "010114",
  "name": "Cocody",
  "kind": "commune-abidjan",
  "departement": "Abidjan",
  "region": "Abidjan",
  "codes": 140412,
  "referenceTown": "Cocody",
  "areas": [
    {
      "id": "010114-001",
      "plateName": "Kofakoua",
      "officialName": "Kofakoua",
      "nameKey": "kofakwa",
      "nameId": 4390,
      "provisionalName": false,
      "zone": {
        "key": "010114",
        "name": "Cocody",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "index": "001",
      "digits": 4,
      "blocks": [
        {
          "lo": 1000,
          "hi": 1999,
          "tailReserveFrom": 1666
        }
      ],
      "place": {
        "lat": 5.427509,
        "lng": -3.926063
      },
      "frame": {
        "west": -3.955226,
        "south": 5.408084,
        "east": -3.916078,
        "north": 5.443538
      },
      "codes": 458
    },
    {
      "id": "010114-002",
      "plateName": "Djibi",
      "officialName": "Djibi",
      "nameKey": "djibi",
      "nameId": 2230,
      "provisionalName": false,
      "zone": {
        "key": "010114",
        "name": "Cocody",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "index": "002",
      "digits": 5,
      "blocks": [
        {
          "lo": 16800,
          "hi": 28499,
          "tailReserveFrom": 24600
        }
      ],
      "place": {
        "lat": 5.422022,
        "lng": -3.981929
      },
      "frame": {
        "west": -3.99007,
        "south": 5.414048,
        "east": -3.956571,
        "north": 5.441758
      },
      "codes": 5844
    },
    "… 126 more"
  ]
}
```

```sh
curl -s http://localhost:8080/v1/zones/999999
```

`404`

```json
{
  "error": {
    "code": "unknown_zone",
    "message": "No zone '999999': a zone is a sous-préfecture or a commune of Abidjan, 6 digits (010114 is Cocody)."
  }
}
```

Every code of a zone, ordered by machine form. Pass the `next` value as `after` to get the following page; `limit` is 1 to 1,000 (default 100).

```sh
curl -s 'http://localhost:8080/v1/zones/010114/codes?limit=2'
```

`200`

```json
{
  "zone": {
    "key": "010114",
    "name": "Cocody",
    "kind": "commune-abidjan",
    "departement": "Abidjan",
    "region": "Abidjan"
  },
  "count": 2,
  "next": "CI-010114-001-1001-4",
  "results": [
    {
      "machine": "CI-010114-001-1000-9",
      "home": "Kofakoua 1000",
      "remembered": "Kofakoua · 10 00",
      "written": "Kofakoua 10 00 (Cocody)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    },
    {
      "machine": "CI-010114-001-1001-4",
      "home": "Kofakoua 1001",
      "remembered": "Kofakoua · 10 01",
      "written": "Kofakoua 10 01 (Cocody)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  ]
}
```

## Areas

```sh
curl -s http://localhost:8080/v1/areas/010114-083
```

`200`

```json
{
  "id": "010114-083",
  "plateName": "Bonoumin",
  "officialName": "Bonoumin",
  "nameKey": "bonoumin",
  "nameId": 1481,
  "provisionalName": false,
  "zone": {
    "key": "010114",
    "name": "Cocody",
    "kind": "commune-abidjan",
    "departement": "Abidjan",
    "region": "Abidjan"
  },
  "index": "083",
  "digits": 4,
  "blocks": [
    {
      "lo": 4000,
      "hi": 8399,
      "tailReserveFrom": 6933
    }
  ],
  "place": {
    "lat": 5.364714,
    "lng": -3.972579
  },
  "frame": {
    "west": -3.977501,
    "south": 5.358897,
    "east": -3.963872,
    "north": 5.37201
  },
  "codes": {
    "total": 2193,
    "provisional": 2193,
    "confirmed": 0,
    "retired": 0,
    "lowest": 4000,
    "highest": 6192
  },
  "sameName": [
    {
      "id": "010114-067",
      "zone": {
        "key": "010114",
        "name": "Cocody",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "blocks": [
        {
          "lo": 1000,
          "hi": 3999
        }
      ]
    }
  ]
}
```

```sh
curl -s http://localhost:8080/v1/areas/010114-999
```

`404`

```json
{
  "error": {
    "code": "unknown_area",
    "message": "No area '010114-999': an area id is the zone and a 3-digit index, as 010114-083."
  }
}
```

By name: a plate name or an official name, folded for case and accents, and through the alias table of engine/SPEC.md section 4.4.

```sh
curl -s 'http://localhost:8080/v1/areas?name=Sicogi'
```

`200`

```json
{
  "name": "Sicogi",
  "nameKey": "sikogi",
  "count": 6,
  "areas": [
    {
      "id": "010114-019",
      "plateName": "Sicogi",
      "officialName": "Cité Sicogi",
      "nameKey": "sikogi",
      "nameId": 7222,
      "provisionalName": false,
      "zone": {
        "key": "010114",
        "name": "Cocody",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "index": "019",
      "digits": 5,
      "blocks": [
        {
          "lo": 10000,
          "hi": 10599,
          "tailReserveFrom": 10400
        }
      ],
      "place": {
        "lat": 5.400974,
        "lng": -3.988313
      },
      "frame": {
        "west": -3.991333,
        "south": 5.398279,
        "east": -3.985131,
        "north": 5.403424
      },
      "matchedBy": "plate"
    },
    {
      "id": "010114-071",
      "plateName": "Sicogi",
      "officialName": "Cité Sicogi",
      "nameKey": "sikogi",
      "nameId": 7222,
      "provisionalName": false,
      "zone": {
        "key": "010114",
        "name": "Cocody",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "index": "071",
      "digits": 5,
      "blocks": [
        {
          "lo": 10600,
          "hi": 14899,
          "tailReserveFrom": 13466
        }
      ],
      "place": {
        "lat": 5.376957,
        "lng": -3.91799
      },
      "frame": {
        "west": -3.922462,
        "south": 5.368935,
        "east": -3.91328,
        "north": 5.391795
      },
      "matchedBy": "plate"
    },
    "… 4 more"
  ]
}
```

```sh
curl -s 'http://localhost:8080/v1/areas?name=Koumassi%20remblais'
```

`200`

```json
{
  "name": "Koumassi remblais",
  "nameKey": "koumasiremblai",
  "count": 1,
  "areas": [
    {
      "id": "010115-005",
      "plateName": "Remblais",
      "officialName": "Koumassi remblais",
      "nameKey": "remblai",
      "nameId": 6797,
      "provisionalName": false,
      "zone": {
        "key": "010115",
        "name": "Koumassi",
        "kind": "commune-abidjan",
        "departement": "Abidjan",
        "region": "Abidjan"
      },
      "index": "005",
      "digits": 4,
      "blocks": [
        {
          "lo": 1000,
          "hi": 8599,
          "tailReserveFrom": 6066
        }
      ],
      "place": {
        "lat": 5.300383,
        "lng": -3.964435
      },
      "frame": {
        "west": -3.971559,
        "south": 5.292951,
        "east": -3.957061,
        "north": 5.306132
      },
      "matchedBy": "alias"
    }
  ]
}
```

## Issue a code

Only the deployment the State or N-WAYS LIMITED has designated as Côte d'Ivoire's issuer issues codes (server/README.md, "One issuer"). Every other deployment runs without `ISSUE_KEYS` and answers `403 read_only`.

The body is `{"lat", "lng"}` (the entrance of the new compound), with an optional `outline` (at most 500 `[lng, lat]` points of the building) or `of` (the machine form of the compound this is another door of). The examples below are from a test deployment with the key `$ISSUE_KEY`.

A new compound with no outline:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.3610529, "lng": -3.9705867}' http://localhost:8080/v1/codes
```

`201`

```json
{
  "machine": "CI-010114-083-6933-7",
  "home": "Bonoumin 6933",
  "remembered": "Bonoumin · 69 33",
  "written": "Bonoumin 69 33 (Cocody)",
  "status": "provisional",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

With the outline of the building (6 m² to 2 ha):

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.36005, "lng": -3.9702, "outline": [[-3.97025, 5.36], [-3.97015, 5.36], [-3.97015, 5.3601], [-3.97025, 5.3601]]}' http://localhost:8080/v1/codes
```

`201`

```json
{
  "machine": "CI-010114-083-6934-5",
  "home": "Bonoumin 6934",
  "remembered": "Bonoumin · 69 34",
  "written": "Bonoumin 69 34 (Cocody)",
  "status": "provisional",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

Another door of an existing compound, within 80 m of its entrance:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.3607, "lng": -3.9706, "of": "CI-010114-083-6136-2"}' http://localhost:8080/v1/codes
```

`201`

```json
{
  "machine": "CI-010114-083-6935-9",
  "home": "Bonoumin 6935",
  "remembered": "Bonoumin · 69 35",
  "written": "Bonoumin 69 35 (Cocody)",
  "status": "provisional",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

A point that already has its code:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.3606529, "lng": -3.9705867}' http://localhost:8080/v1/codes
```

`409`

```json
{
  "error": {
    "code": "already_has_code",
    "message": "This compound already has its code: Bonoumin 6136.",
    "existing": {
      "machine": "CI-010114-083-6136-2",
      "home": "Bonoumin 6136",
      "remembered": "Bonoumin · 61 36",
      "written": "Bonoumin 61 36 (Cocody)",
      "status": "provisional",
      "…": "the full card, as GET /v1/codes/{machine}"
    }
  }
}
```

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.362, "lng": -3.97, "outline": [[-3.97, 5.362], [-3.96999, 5.362], [-3.97, 5.36201]]}' http://localhost:8080/v1/codes
```

`422`

```json
{
  "error": {
    "code": "bad_outline",
    "message": "That outline is 1 m2; a compound's is between 6 m2 and 2 ha."
  }
}
```

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.37, "lng": -3.9706, "of": "CI-010114-083-6136-2"}' http://localhost:8080/v1/codes
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "That door is more than 80 m from Bonoumin 6136."
  }
}
```

```sh
curl -s -X POST -H 'Content-Type: application/json' -d '{"lat": 5.3610529, "lng": -3.9705867}' http://localhost:8080/v1/codes
```

`401`

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Send an issuing key: Authorization: Bearer <key>."
  }
}
```

Each key issues at most `ISSUE_PER_DAY` codes in any 24 hours (5 by default). The same key issues two more codes, its fourth and fifth:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.3672, "lng": -3.9662}' http://localhost:8080/v1/codes
```

`201`

```json
{
  "machine": "CI-010114-083-6936-8",
  "home": "Bonoumin 6936",
  "remembered": "Bonoumin · 69 36",
  "written": "Bonoumin 69 36 (Cocody)",
  "status": "provisional",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.3676, "lng": -3.9668}' http://localhost:8080/v1/codes
```

`201`

```json
{
  "machine": "CI-010114-083-6937-6",
  "home": "Bonoumin 6937",
  "remembered": "Bonoumin · 69 37",
  "written": "Bonoumin 69 37 (Cocody)",
  "status": "provisional",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

and its sixth is refused:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 5.367, "lng": -3.966}' http://localhost:8080/v1/codes
```

`429`

```json
{
  "error": {
    "code": "daily_limit",
    "message": "This key has issued 5 codes in the last 24 hours, its daily limit."
  }
}
```

## Change a code

`PATCH /v1/codes/{machine}` with `{"status": "confirmed" | "provisional" | "retired"}`, or `{"entrance": {"lat", "lng"}}` to move the entrance (at most 80 m from the compound's position), or both.

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "confirmed"}' http://localhost:8080/v1/codes/CI-010114-083-6136-2
```

`200`

```json
{
  "machine": "CI-010114-083-6136-2",
  "home": "Bonoumin 6136",
  "remembered": "Bonoumin · 61 36",
  "written": "Bonoumin 61 36 (Cocody)",
  "status": "confirmed",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"entrance": {"lat": 5.3607, "lng": -3.9706}}' http://localhost:8080/v1/codes/CI-010114-083-6136-2
```

`200`

```json
{
  "machine": "CI-010114-083-6136-2",
  "home": "Bonoumin 6136",
  "remembered": "Bonoumin · 61 36",
  "written": "Bonoumin 61 36 (Cocody)",
  "status": "confirmed",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"entrance": {"lat": 5.365, "lng": -3.9706}}' http://localhost:8080/v1/codes/CI-010114-083-6136-2
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "An entrance moves at most 80 m from the compound's position."
  }
}
```

A retired code never comes back, and its number is never given to another compound:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "retired"}' http://localhost:8080/v1/codes/CI-010114-083-6935-9
```

`200`

```json
{
  "machine": "CI-010114-083-6935-9",
  "home": "Bonoumin 6935",
  "remembered": "Bonoumin · 69 35",
  "written": "Bonoumin 69 35 (Cocody)",
  "status": "retired",
  "…": "the full card, as GET /v1/codes/{machine}"
}
```

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "confirmed"}' http://localhost:8080/v1/codes/CI-010114-083-6935-9
```

`409`

```json
{
  "error": {
    "code": "retired",
    "message": "CI-010114-083-6935-9 is retired; a retired code never comes back and its number is never reused."
  }
}
```

A retired code is still recognised, and reported as retired:

```sh
curl -s 'http://localhost:8080/v1/find?q=Bonoumin%2069%2035'
```

`410`

```json
{
  "error": {
    "code": "retired",
    "message": "Bonoumin 6935 was retired: there is no compound there any more."
  }
}
```

## Unknown endpoint

```sh
curl -s http://localhost:8080/v1/nothing
```

`404`

```json
{
  "error": {
    "code": "no_such_endpoint",
    "message": "No endpoint /v1/nothing. See /v1/info and server/openapi.yaml."
  }
}
```
