#!/bin/sh
# First start: import the bundled registry into the (empty) data volume, then serve.
set -eu
DB="${ADDRESSES_DB:-/data/addresses.sqlite}"
if [ ! -s "$DB" ]; then
    echo "No database at $DB: importing ${REGISTRY_DIR:-registry} (verified against its MANIFEST.json)."
    python3 -m server import --registry "${REGISTRY_DIR:-registry}" --db "$DB"
fi
exec python3 -m server serve --db "$DB" --port "${PORT:-8080}"
