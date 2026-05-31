#!/usr/bin/env python3
"""
Spatial county FIPS enrichment for municipalities and school districts.

For jurisdictions whose county_fips_code cannot be derived from GEOID structure
(municipalities, school districts), this script resolves the county using two methods:

  Method 1 — geo_places name match (municipalities only):
    Join municipality (usps, name) to bronze_geo_places (stusps, namelsad) to
    confirm the place, then use its intptlat/intptlong for the county lookup.

  Method 2 — lat/lon point-in-polygon:
    Use the jurisdiction's intptlat/intptlong to test containment against
    county boundary polygons (WKT) from bronze_geo_counties via shapely.

Results are written to bronze.bronze_jurisdictions_county_fips_enriched, which
int_jurisdictions.sql joins as a fallback after the ZCTA-based zip mapping.

Run this script after loading Census shapefiles and gazetteer data:
    python packages/scrapers/src/scrapers/census/load_census_shapefiles.py
    python packages/scrapers/src/scrapers/census/load_census_gazetteer.py

Usage:
    python enrich_jurisdictions_county_fips.py
    python enrich_jurisdictions_county_fips.py --types municipalities
    python enrich_jurisdictions_county_fips.py --types school_districts
    python enrich_jurisdictions_county_fips.py --state CA
    python enrich_jurisdictions_county_fips.py --batch-size 500
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from loguru import logger
from shapely.geometry import Point
from shapely.strtree import STRtree
from shapely.wkt import loads as wkt_loads
from tqdm import tqdm

POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

DDL = """
CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_county_fips_enriched (
    geoid           VARCHAR(10)  PRIMARY KEY,
    county_fips_code VARCHAR(5)  NOT NULL,
    match_method    VARCHAR(50)  NOT NULL,
    enriched_at     TIMESTAMP    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bjcfe_geoid
    ON bronze.bronze_jurisdictions_county_fips_enriched(geoid);
"""

UPSERT = """
INSERT INTO bronze.bronze_jurisdictions_county_fips_enriched
    (geoid, county_fips_code, match_method)
VALUES %s
ON CONFLICT (geoid) DO UPDATE SET
    county_fips_code = EXCLUDED.county_fips_code,
    match_method     = EXCLUDED.match_method,
    enriched_at      = NOW()
"""


def load_county_polygons(conn) -> Tuple[List, List[str]]:
    """
    Load county boundary polygons from bronze_geo_counties.

    Returns (polygons, geoids) in the same order, suitable for building an STRtree.
    """
    logger.info("Loading county boundary polygons...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT geoid, geom_wkt
            FROM bronze.bronze_geo_counties
            WHERE geom_wkt IS NOT NULL
        """)
        rows = cur.fetchall()

    polygons = []
    geoids = []
    for row in rows:
        try:
            poly = wkt_loads(row["geom_wkt"])
            polygons.append(poly)
            geoids.append(row["geoid"])
        except Exception as e:
            logger.warning(f"Skipping county {row['geoid']}: invalid WKT — {e}")

    logger.info(f"Loaded {len(polygons):,} county polygons")
    return polygons, geoids


def build_spatial_index(polygons: List) -> STRtree:
    return STRtree(polygons)


def point_in_county(
    lat: float,
    lon: float,
    tree: STRtree,
    polygons: List,
    geoids: List[str],
) -> Optional[str]:
    """Return the county_geoid whose polygon contains (lon, lat), or None."""
    pt = Point(lon, lat)
    candidates = tree.query(pt)
    for idx in candidates:
        if polygons[idx].contains(pt):
            return geoids[idx]
    return None


def load_geo_places_index(conn) -> Dict[Tuple[str, str], str]:
    """
    Build a lookup: (stusps, normalised_name) → place_geoid.

    normalised_name strips the LSAD suffix (e.g. " city", " town") from namelsad
    so it matches the plain name stored in bronze_jurisdictions_municipalities.
    """
    logger.info("Loading bronze_geo_places name index...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT geoid, stusps,
                   LOWER(TRIM(name))    AS plain_name,
                   LOWER(TRIM(namelsad)) AS lsad_name
            FROM bronze.bronze_geo_places
            WHERE stusps IS NOT NULL
        """)
        rows = cur.fetchall()

    index: Dict[Tuple[str, str], str] = {}
    for row in rows:
        index[(row["stusps"], row["plain_name"])] = row["geoid"]
        index[(row["stusps"], row["lsad_name"])]  = row["geoid"]
    logger.info(f"Indexed {len(rows):,} places ({len(index):,} name variants)")
    return index


def fetch_jurisdictions(
    conn,
    jurisdiction_type: str,
    state: Optional[str] = None,
) -> List[dict]:
    """
    Fetch municipalities or school_districts that still need county_fips resolution.

    Only returns rows not already present in bronze_jurisdictions_county_fips_enriched.
    """
    table = {
        "municipalities":  "bronze.bronze_jurisdictions_municipalities",
        "school_districts": "bronze.bronze_jurisdictions_school_districts",
    }[jurisdiction_type]

    state_filter = "AND usps = %(state)s" if state else ""

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"""
            SELECT j.geoid, j.usps, j.name, j.intptlat AS lat, j.intptlong AS lon
            FROM {table} j
            WHERE j.intptlat IS NOT NULL
              AND j.intptlong IS NOT NULL
              AND j.geoid NOT IN (
                  SELECT geoid FROM bronze.bronze_jurisdictions_county_fips_enriched
              )
              {state_filter}
        """, {"state": state} if state else {})
        return [dict(row) for row in cur.fetchall()]


def enrich_batch(
    records: List[dict],
    jurisdiction_type: str,
    tree: STRtree,
    polygons: List,
    geoids: List[str],
    places_index: Optional[Dict],
) -> List[Tuple]:
    """
    Resolve county_fips for a list of jurisdiction records.

    Returns a list of (geoid, county_fips_code, match_method) tuples.
    """
    results = []

    for rec in records:
        county_fips = None
        method = None

        # Method 1: name match to geo_places (municipalities only)
        if jurisdiction_type == "municipalities" and places_index is not None:
            usps = rec["usps"]
            name_key = (usps, rec["name"].lower().strip())
            place_geoid = places_index.get(name_key)
            if place_geoid:
                method = "geo_places_name"

        # Method 2: lat/lon point-in-polygon (always attempted if no method yet)
        try:
            lat = float(rec["lat"])
            lon = float(rec["lon"])
        except (TypeError, ValueError):
            continue

        county_fips = point_in_county(lat, lon, tree, polygons, geoids)
        if county_fips and method is None:
            method = "latlon_point_in_polygon"
        elif county_fips and method == "geo_places_name":
            method = "geo_places_name+latlon"

        if county_fips:
            results.append((rec["geoid"], county_fips, method))

    return results


def write_results(conn, results: List[Tuple], batch_size: int = 500):
    with conn.cursor() as cur:
        for i in range(0, len(results), batch_size):
            psycopg2.extras.execute_values(
                cur, UPSERT, results[i : i + batch_size]
            )
        conn.commit()


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def run(
    jurisdiction_types: List[str],
    state: Optional[str],
    batch_size: int,
    db_url: str,
):
    conn = psycopg2.connect(db_url)
    try:
        ensure_table(conn)

        polygons, poly_geoids = load_county_polygons(conn)
        if not polygons:
            logger.error("No county polygons found — run load_census_shapefiles.py first")
            sys.exit(1)

        tree = build_spatial_index(polygons)

        places_index = None
        if "municipalities" in jurisdiction_types:
            places_index = load_geo_places_index(conn)

        for jtype in jurisdiction_types:
            logger.info(f"\nProcessing {jtype}...")
            records = fetch_jurisdictions(conn, jtype, state=state)
            logger.info(f"  {len(records):,} records to enrich")

            if not records:
                continue

            all_results = []
            for i in tqdm(range(0, len(records), batch_size), desc=jtype, unit="batch"):
                batch = records[i : i + batch_size]
                batch_results = enrich_batch(
                    batch, jtype, tree, polygons, poly_geoids, places_index
                )
                all_results.extend(batch_results)

            matched = len(all_results)
            unmatched = len(records) - matched
            logger.success(
                f"  Matched {matched:,} / {len(records):,} "
                f"({unmatched:,} unresolved)"
            )

            if all_results:
                write_results(conn, all_results, batch_size=batch_size)
                logger.info(f"  Written {matched:,} rows to bronze_jurisdictions_county_fips_enriched")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Enrich municipality and school district county FIPS via spatial lookup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enrich_jurisdictions_county_fips.py
  python enrich_jurisdictions_county_fips.py --types municipalities
  python enrich_jurisdictions_county_fips.py --types school_districts
  python enrich_jurisdictions_county_fips.py --state CA
  python enrich_jurisdictions_county_fips.py --db-url postgresql://user:pass@host:5433/db
        """,
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=["municipalities", "school_districts"],
        default=["municipalities", "school_districts"],
        help="Jurisdiction types to process (default: both)",
    )
    parser.add_argument(
        "--state",
        type=str,
        help="Limit to a single state abbreviation (e.g. CA)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Records per processing batch (default: 500)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=DATABASE_URL,
        help="PostgreSQL connection string",
    )

    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("Jurisdiction County FIPS Spatial Enrichment")
    logger.info("=" * 60)

    run(
        jurisdiction_types=args.types,
        state=args.state,
        batch_size=args.batch_size,
        db_url=args.db_url,
    )

    logger.info("=" * 60)
    logger.success("Done")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
