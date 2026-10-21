# N-Ways Addressing for Côte d'Ivoire: the registry server.
# Build from the repository root (docker compose up does it):
#   docker build -f server/Dockerfile -t nways-addresses-ci .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADDRESSES_DB=/data/addresses.sqlite \
    REGISTRY_DIR=/app/registry \
    PORT=8080

RUN useradd --system --uid 10001 --user-group --home-dir /app --no-create-home nways \
    && mkdir -p /app /data \
    && chown nways:nways /data

WORKDIR /app
COPY engine/reference/ci_engine.py engine/reference/plate_names.py engine/reference/border.py engine/reference/
COPY engine/data/ engine/data/
COPY model/units/ model/units/
COPY registry/ registry/
COPY server/ server/
COPY LICENSE LICENSE-DATA NOTICE ./

USER nways
VOLUME ["/data"]
EXPOSE 8080

# The first start imports the whole registry (several minutes); the health
# check only counts once the import is done.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60m --retries=3 \
    CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '8080'), timeout=4)"

ENTRYPOINT ["sh", "/app/server/entrypoint.sh"]
