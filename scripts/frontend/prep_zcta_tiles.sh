#!/usr/bin/env bash
# Build per-state ZCTA (ZIP) TopoJSON tiles for the census drilldown ZIP tier.
#
# Output: frontend/public/data/zctas/state-XX.json (one per state FIPS)
#   - TopoJSON with objects.zctas
#   - feature.id = ZCTA5 GEOID (5-digit string)
#   - Lng/lat coords (the page's Albers projection is applied client-side)
#
# Why a spatial join: TIGER ZCTA shapefiles don't carry STATEFP — ZCTAs cross
# state lines, so Census doesn't pre-assign one. We assign each ZCTA to the
# state whose polygon contains its centroid (mapshaper's default behavior for
# polygon-to-polygon -join).
#
# Why TopoJSON: ~70% smaller than raw GeoJSON; matches the existing us-atlas
# state/county tiles.
#
# One-time prep — re-run only when a new TIGER vintage drops.
#
# Inputs (configurable via env):
#   ZCTA_SHP    TIGER ZCTA shapefile (default: data/cache/census/shapefiles/2025/tl_2025_us_zcta520/tl_2025_us_zcta520.shp)
#   STATES_SHP  Census state shapefile (default: data/cache/census/shapefiles/2025/cb_2025_us_state_500k/cb_2025_us_state_500k.shp)
#   OUT_DIR     Output dir (default: frontend/public/data/zctas)
#   SIMPLIFY    Mapshaper simplification percent (default: 5%)
#
# Source shapefiles (2025 vintage, fetched by the project's census loader):
#   ZCTA   — TIGER/Line: https://www2.census.gov/geo/tiger/TIGER2025/ZCTA520/tl_2025_us_zcta520.zip
#   STATE  — Cartographic Boundary 1:500k: https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip
#            (cb_500k is generalized; fine here since we only use it for the
#             ZCTA-centroid → STATEFP spatial join, not for rendering)
#
# Heads-up: the original user-supplied command used `tl_2025_us_zcta510.shp`
# and `-split STATEFP` directly. That fails because (a) the 510 ZCTA delineation
# was retired in 2020 (current files are zcta520), and (b) STATEFP isn't on
# ZCTA features. This script fixes both.

set -euo pipefail

CACHE_DIR="data/cache/census/shapefiles/2025"
ZCTA_SHP="${ZCTA_SHP:-$CACHE_DIR/tl_2025_us_zcta520/tl_2025_us_zcta520.shp}"
STATES_SHP="${STATES_SHP:-$CACHE_DIR/cb_2025_us_state_500k/cb_2025_us_state_500k.shp}"
OUT_DIR="${OUT_DIR:-frontend/public/data/zctas}"
SIMPLIFY="${SIMPLIFY:-5%}"

command -v mapshaper >/dev/null 2>&1 || {
  echo "ERR: mapshaper not on PATH. Install with: npm install -g mapshaper" >&2
  exit 1
}

[[ -f "$ZCTA_SHP" ]] || {
  echo "ERR: missing $ZCTA_SHP" >&2
  echo "     Download: https://www2.census.gov/geo/tiger/TIGER2025/ZCTA520/tl_2025_us_zcta520.zip" >&2
  echo "     Unzip to: $CACHE_DIR/tl_2025_us_zcta520/" >&2
  exit 1
}
[[ -f "$STATES_SHP" ]] || {
  echo "ERR: missing $STATES_SHP" >&2
  echo "     Download: https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip" >&2
  echo "     Unzip to: $CACHE_DIR/cb_2025_us_state_500k/" >&2
  exit 1
}

mkdir -p "$OUT_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo ">> Pass 1: simplify ($SIMPLIFY) + spatial-join ZCTAs → states → $TMP_DIR/joined.json"
echo "   (this is the slow step — full national ZCTA set, ~5-10 min)"
mapshaper -i "$ZCTA_SHP" \
  -simplify "$SIMPLIFY" keep-shapes \
  -join "$STATES_SHP" calc='STATEFP=first(STATEFP)' fields=STATEFP \
  -filter '!!STATEFP' \
  -rename-layers zctas \
  -o "$TMP_DIR/joined.json" format=geojson

# 50 states + DC. Territories (60-78) skipped — no ACS data flowing through them.
STATE_FIPS=(
  01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23
  24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44
  45 46 47 48 49 50 51 53 54 55 56
)

echo ">> Pass 2: split into per-state TopoJSON (${#STATE_FIPS[@]} files)"
written=0
empty=0
for FIPS in "${STATE_FIPS[@]}"; do
  OUT="$OUT_DIR/state-$FIPS.json"
  if mapshaper -i "$TMP_DIR/joined.json" \
       -filter "STATEFP === '$FIPS'" \
       -rename-layers zctas \
       -o "$OUT" format=topojson id-field=GEOID20 2>/dev/null \
     && [[ -s "$OUT" ]]; then
    size=$(du -h "$OUT" | cut -f1)
    printf "  %s  %s\n" "$FIPS" "$size"
    written=$((written + 1))
  else
    rm -f "$OUT"
    empty=$((empty + 1))
  fi
done

echo
echo "Done. $written state file(s) in $OUT_DIR, $empty empty/failed."
du -sh "$OUT_DIR" 2>/dev/null || true
