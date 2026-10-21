#!/bin/bash
# 10% sample of building centroids (run from WORK): sample.sh CI ivory-coast
# NWAYS_ROOT is the N-Ways data folder (data/detail/...).
cc="$1"; slug="$2"; lc=$(echo "$cc" | tr A-Z a-z); root="${NWAYS_ROOT:-.}"
duckdb -csv > "out/$lc/sample.csv" <<SQL
SET memory_limit='3GB'; SET threads=4; LOAD spatial;
SELECT round(ST_X(c),6) x, round(ST_Y(c),6) y FROM (
 SELECT ST_Centroid(ST_GeomFromGeoJSON(json_extract(ltrim(line, chr(30)), '\$.geometry'))) c
   FROM read_csv('$root/data/detail/countries/$slug/buildings-src.geojsonseq', columns={'line':'VARCHAR'}, header=false, delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line)>2 AND hash(line) % 10 = 0
 UNION ALL SELECT ST_Centroid(geometry) FROM '$root/data/detail/ml/$cc.parquet' WHERE hash(ST_AsWKB(geometry)) % 10 = 0);
SQL
wc -l "out/$lc/sample.csv"
