# The registry server

A ready-made HTTP service for the N-Ways codes of Côte d'Ivoire. It serves exactly the published registry (`registry/`, 7,956,622 codes) through a JSON API, and a deployment designated as the issuer can issue new codes by the same rules as the N-Ways issuer, so every deployment gives the same answers.

- Python 3.9 or newer, standard library only. The rules come from the reference engine (`engine/reference/ci_engine.py`); the server does not re-implement any of them.
- One SQLite database (WAL mode), about 4 GB for the whole country.
- The API is described in [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1) and shown request by request in [`docs/api.md`](../docs/api.md).

## Deploy with Docker

From the repository root:

```sh
docker compose up -d
curl -s http://localhost:8080/v1/health
```

That is the whole deployment. On its first start the container finds its data volume empty, imports the registry bundled in the image (verifying every file against `registry/MANIFEST.json`), then serves on port 8080. The import of the full registry takes about four minutes and needs about 1.1 GB of memory; the health check reports healthy once the server answers. Later starts reuse the database in the volume and serve at once.

The image is built from `python:3.12-slim`, runs as an unprivileged user (`nways`, uid 10001), keeps its database in the volume `/data`, and has a health check on `/v1/health`.

## Deploy with plain Python

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve --db data/addresses.sqlite --port 8080
```

Run the commands from the repository root (the server reads `engine/` and `model/units/` from there). To keep it running, use the service manager of the host, for example a systemd unit:

```ini
[Unit]
Description=N-Ways Addressing for Côte d'Ivoire
After=network.target

[Service]
User=nways
WorkingDirectory=/opt/open-addresses-cote-divoire
Environment=ADDRESSES_DB=/var/lib/nways/addresses.sqlite
ExecStart=/usr/bin/python3 -m server serve --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Behind a reverse proxy with TLS

The server speaks plain HTTP; put it behind a proxy that holds the certificate. With Caddy (certificates from Let's Encrypt, automatically):

```
adresses.example.ci {
    reverse_proxy 127.0.0.1:8080
}
```

With nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name adresses.example.ci;
    ssl_certificate     /etc/letsencrypt/live/adresses.example.ci/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/adresses.example.ci/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Bind the server to `127.0.0.1` (`--host 127.0.0.1`) when the proxy is on the same machine, so that only the proxy reaches it. Issuing keys travel in the `Authorization` header: never expose an issuing deployment without TLS.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ADDRESSES_DB` | `data/addresses.sqlite` (`/data/addresses.sqlite` in Docker) | the database file |
| `PORT` | `8080` | the port to listen on |
| `HOST` | `0.0.0.0` | the address to listen on |
| `ISSUE_KEYS` | empty | comma-separated bearer keys allowed to issue and change codes; empty means read-only |
| `ISSUE_PER_DAY` | `5` | codes each key may issue in any 24 hours |
| `CORS_ORIGINS` | empty (`*` in docker-compose.yml) | comma-separated origins allowed to call the API from a browser, or `*` |
| `REGISTRY_DIR` | `/app/registry` | Docker only: the registry imported on first start |

Create issuing keys with, for example, `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`, one per system or office that issues, so a key can be withdrawn on its own. The server stores only a hash of the key with each code it issues.

## One issuer

A number may be given to one compound only. The issuer guarantees it by giving numbers one at a time from the register it holds. Two servers issuing independently would each see a number as free and could hand the same "Bonoumin 69 33" to two different compounds; once printed on two gates, such a clash cannot be undone without renumbering a household. So Côte d'Ivoire has one issuer:

- a deployment issues codes only if the State, or N-WAYS LIMITED, has designated it as the issuer for Côte d'Ivoire;
- every other deployment (a ministry's mirror, a post office, a courier, a developer) runs without `ISSUE_KEYS` and is read-only: it answers every lookup and refuses `POST` and `PATCH` with `403 read_only`;
- the issuer publishes its registry (the `export` command) so that every read-only deployment can update to it.

Within the issuer, all writes pass through one lock and one database transaction, so a single process never gives a number twice. Run one server process per database.

## What issuing does

`POST /v1/codes` with `{"lat", "lng", "outline"?, "of"?}`, the rules of the N-Ways issuer (engine/SPEC.md section 5, "After issue", and section 10):

**The border decides first.** An entrance more than 300 m outside Côte d'Ivoire's national border (OpenStreetMap's admin_level 2 boundary, `engine/data/outline.geojson`) is refused with `422 outside_country`, whatever area the zone or spot rules would give it; so is moving an entrance there. The shipped border is simplified to about 50 m, and its largest deviation (`maxDeviationM`) is taken off the 300 m, so a point more than 300 m across the true border is always refused.

1. A point within 3 m of an issued compound's entrance, or inside an outline issued here, already has its code: `409 already_has_code`, with that code.
2. An outline, when given, is 3 to 500 `[lng, lat]` points enclosing 6 m² to 20,000 m² (`422 bad_outline` otherwise). An outline covering more than half of an outline issued here, or holding the entrance of a published code, is a building that has its code: `409`.
3. `of` names a compound this is another door of; the door must be within 80 m of that compound's entrance (`422 too_far`) and takes a number in the same area.
4. Otherwise the new compound joins the area of the nearest issued code within 250 m, so a new house takes its neighbours' name; with no code that close, it takes the area whose place point is nearest.
5. The number: the free number between the compound's neighbours along the area's Hilbert curve, closest to their midpoint; else the lowest free number of the block's tail reserve; else the first number of a new block of the same name, above every block of that name (five-digit names skip the stretches that would read as another name). The new block is stored, and appears in `export`.
6. The code is `provisional`, issued `on-demand`; each key may issue `ISSUE_PER_DAY` codes in 24 hours (`429 daily_limit`).

`PATCH /v1/codes/{machine}` confirms a code (`provisional` to `confirmed`, or back), retires it (a retired number is never given again), or moves its entrance by at most 80 m from the compound's position.

The test suite checks these rules against the N-Ways issuer itself: `server/testdata/parity.json` holds 310 numbers and forms that the issuer's own engine (`Register.Insert` and `AddressForms`) gave to new compounds in the fixture areas, including blocks that fill up and take an extension block; the server must give exactly the same.

## Back up

The database is a single SQLite file in WAL mode. Copy it while the server runs with the online backup:

```sh
python3 -m server backup --db data/addresses.sqlite --out backups/addresses-$(date +%F).sqlite
```

A read-only deployment needs no backup: it can always be rebuilt from the registry. An issuing deployment must back up after every working day, and should also `export` its registry regularly.

## Update to a newer registry

```sh
git pull                                    # the new registry/
python3 -m server import --registry registry --db data/addresses.new.sqlite
# stop the server, move addresses.new.sqlite over addresses.sqlite, start it again
```

With Docker: `git pull`, `docker compose build`, then remove the data volume (`docker compose down -v`) and `docker compose up -d`; the new registry is imported on start.

`import` builds the new database beside the target and replaces it only when every file matched the manifest, so a refused import leaves the old database untouched. It refuses to replace a database that holds codes issued or changed by this deployment, because those would be lost; export them first (`python3 -m server export`), or pass `--force` to discard them.

## Export

```sh
python3 -m server export --db data/addresses.sqlite --out exported/
```

writes the registry in the published format: `areas.csv.gz`, one `<zone>.csv.gz` per sous-préfecture or commune of Abidjan, and `MANIFEST.json` with the counts and the SHA-256 of every file uncompressed. The columns, their order, the row order (by name, then number) and the CSV quoting are those of the published files; after importing the published registry, an export is identical to it byte for byte once uncompressed (the tests check it, and it was checked on the full registry).

## How a point is matched

`GET /v1/at` finds the compound whose entrance is within 12 m of the point, as the N-Ways service does, and `GET /v1/find` with a spot code looks within 15 m. The N-Ways service also matches a point that falls inside a building's footprint; the published registry carries each compound's entrance but not its footprints, so a point well inside a large building, more than 12 m from its entrance, is answered `"status": "none"` here, with the area it is in. Outlines sent with `POST /v1/codes` are kept, and points inside them are matched.

## Endpoints

| Method and path | |
|---|---|
| `GET /v1/health` | status, country, codes, registry export date |
| `GET /v1/info` | zones, areas, counts, licences, credit, engine |
| `GET /v1/codes/{machine}` | the full card |
| `GET /v1/find?q=` | remembered or written form, machine form, official address or spot code |
| `GET /v1/at?lat=&lng=` | the code at a point |
| `GET /v1/near?lat=&lng=&radius=&limit=` | codes within `radius` m (at most 500, 100 results) |
| `GET /v1/verify?code=` | syntax, area, block, check digit, issued |
| `GET /v1/spot?lat=&lng=` / `GET /v1/spot/decode?code=` | spot codes |
| `GET /v1/zones` / `GET /v1/zones/{key}` | zones, and a zone with its areas |
| `GET /v1/zones/{key}/codes?after=&limit=` | a zone's codes, paged by machine form |
| `GET /v1/areas/{id}` / `GET /v1/areas?name=` | an area, or areas by name |
| `POST /v1/codes` | issue (bearer key) |
| `PATCH /v1/codes/{machine}` | status, entrance (bearer key) |

## Tests

```sh
python3 -m unittest discover -s server/tests -t .
```

They run on `server/testdata/registry/`: the full area table and every code of zone 080104 (Parc National de Bona, 787 codes in 7 areas), copied from the published registry with its manifest.

## Credit

Every application that shows these codes credits them: **"N-Ways Addressing for Côte d'Ivoire, © N-WAYS LIMITED (nways.ng)"** (every card carries the line). Code: Apache License 2.0; data: ODbL 1.0 ([LICENSING.md](../LICENSING.md)).
