#!/usr/bin/env python3
"""
Build place-centric crosswalks in the bronze schema.

Produces two tables that answer the day-to-day questions:

  bronze.bronze_jurisdictions_place_county
      "What county does this city/town belong to?"
      One row per (place, county) pair when a place spans multiple counties,
      with is_primary=TRUE marking the county that holds the largest portion
      of the place's land area.

  bronze.bronze_jurisdictions_place_zcta
      "What is the primary postal code (ZCTA) for this city/town?"
      One row per (place, zcta) pair, with is_primary=TRUE marking the ZCTA
      whose land overlap with the place is the largest.

Inputs (must already be downloaded by `python scripts/download_bronze.py`):
  - data/cache/census/shapefiles/<year>/cb_<year>_us_place_500k.zip
  - data/cache/census/shapefiles/<year>/cb_<year>_us_county_500k.zip
  - data/cache/census_relationships/zcta_place.txt

Method:
  - place → county: GeoPandas spatial overlay of the place and county
    polygons, reprojected to EPSG:5070 (NAD83 / Conus Albers) for accurate
    area math, then aggregated to a (place, county) overlap area. Census
    does not publish a 2020 place→county relationship file, so we compute
    it directly from the cartographic boundary shapefiles.
  - place → zcta: read the existing Census 2020 ZCTA-Place relationship
    file (already downloaded by download_census_relationships.py) and
    rotate it to a place-centric view, marking the largest-overlap ZCTA
    as primary.

Usage:
    python scripts/datasources/census/load_place_crosswalks.py
    python scripts/datasources/census/load_place_crosswalks.py --year 2024
    python scripts/datasources/census/load_place_crosswalks.py --truncate
    python scripts/datasources/census/load_place_crosswalks.py --dry-run
    python scripts/datasources/census/load_place_crosswalks.py --only place_county
    python scripts/datasources/census/load_place_crosswalks.py --limit 100
"""
import argparse
import os
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.calendar_year_util import calendar_year_label

SHAPEFILE_CACHE = PROJECT_ROOT / "data" / "cache" / "census" / "shapefiles"
RELATIONSHIPS_CACHE = PROJECT_ROOT / "data" / "cache" / "census_relationships"

POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

# NAD83 / Conus Albers — equal-area projection that keeps area calculations
# accurate across the lower 48 + AK/HI/PR (with small distortion at the edges).
EQUAL_AREA_CRS = 5070

BATCH_SIZE = 1000


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL_PLACE_COUNTY = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_place_county (
    place_geoid     VARCHAR(7)  NOT NULL,
    place_name      VARCHAR(120),
    place_state     VARCHAR(2),
    county_geoid    VARCHAR(5)  NOT NULL,
    county_name     VARCHAR(120),
    state_fips      VARCHAR(2),
    overlap_area_m2 BIGINT,
    place_area_m2   BIGINT,
    overlap_pct     NUMERIC(6, 3),
    is_primary      BOOLEAN     NOT NULL,
    vintage_year    VARCHAR(4),
    source          VARCHAR(255),
    ingestion_date  TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (place_geoid, county_geoid)
);

CREATE INDEX IF NOT EXISTS idx_bjpc_place   ON bronze.bronze_jurisdictions_place_county(place_geoid);
CREATE INDEX IF NOT EXISTS idx_bjpc_county  ON bronze.bronze_jurisdictions_place_county(county_geoid);
CREATE INDEX IF NOT EXISTS idx_bjpc_state   ON bronze.bronze_jurisdictions_place_county(state_fips);
CREATE INDEX IF NOT EXISTS idx_bjpc_primary ON bronze.bronze_jurisdictions_place_county(place_geoid) WHERE is_primary;

COMMENT ON TABLE  bronze.bronze_jurisdictions_place_county IS
    'Place (city/town) to county crosswalk derived from a spatial overlay of Census cartographic boundary shapefiles. is_primary=TRUE marks the county containing the largest share of the place''s land area.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.place_geoid     IS '7-digit place GEOID (state FIPS + place FIPS)';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.county_geoid    IS '5-digit county GEOID (state FIPS + county FIPS)';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.overlap_area_m2 IS 'Land area of (place ∩ county) in square metres, EPSG:5070';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.place_area_m2   IS 'Total land area of the place in square metres, EPSG:5070';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.overlap_pct     IS 'Percent of the place''s land area falling inside the county (0–100)';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_county.is_primary      IS 'TRUE for the county with the largest overlap with this place';
"""


INSERT_PLACE_COUNTY = """
INSERT INTO bronze.bronze_jurisdictions_place_county
    (place_geoid, place_name, place_state, county_geoid, county_name,
     state_fips, overlap_area_m2, place_area_m2, overlap_pct,
     is_primary, vintage_year, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (place_geoid, county_geoid) DO UPDATE SET
    place_name      = EXCLUDED.place_name,
    place_state     = EXCLUDED.place_state,
    county_name     = EXCLUDED.county_name,
    state_fips      = EXCLUDED.state_fips,
    overlap_area_m2 = EXCLUDED.overlap_area_m2,
    place_area_m2   = EXCLUDED.place_area_m2,
    overlap_pct     = EXCLUDED.overlap_pct,
    is_primary      = EXCLUDED.is_primary,
    vintage_year    = EXCLUDED.vintage_year,
    source          = EXCLUDED.source,
    ingestion_date  = NOW()
"""


DDL_PLACE_ZCTA = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_place_zcta (
    place_geoid     VARCHAR(7)  NOT NULL,
    place_name      VARCHAR(255),
    zcta            VARCHAR(10) NOT NULL,
    state_fips      VARCHAR(2),
    arealand_part   BIGINT,
    areawater_part  BIGINT,
    is_primary      BOOLEAN     NOT NULL,
    source          VARCHAR(255),
    ingestion_date  TIMESTAMP   DEFAULT NOW(),
    -- 'z-' || state_fips || '-' || zcta; NOT unique — same zcta spans multiple places
    jurisdiction_id        TEXT GENERATED ALWAYS AS ('z-' || state_fips || '-' || zcta) STORED,
    jurisdiction_type      bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'zcta',
    jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'zip_code',
    PRIMARY KEY (place_geoid, zcta)
);

CREATE INDEX IF NOT EXISTS idx_bjpz_place           ON bronze.bronze_jurisdictions_place_zcta(place_geoid);
CREATE INDEX IF NOT EXISTS idx_bjpz_zcta            ON bronze.bronze_jurisdictions_place_zcta(zcta);
CREATE INDEX IF NOT EXISTS idx_bjpz_state           ON bronze.bronze_jurisdictions_place_zcta(state_fips);
CREATE INDEX IF NOT EXISTS idx_bjpz_primary         ON bronze.bronze_jurisdictions_place_zcta(place_geoid) WHERE is_primary;
CREATE INDEX IF NOT EXISTS idx_bjpz_jurisdiction_id ON bronze.bronze_jurisdictions_place_zcta(jurisdiction_id);

COMMENT ON TABLE  bronze.bronze_jurisdictions_place_zcta IS
    'Place (city/town) to ZCTA crosswalk derived from the Census 2020 ZCTA-Place relationship file. is_primary=TRUE marks the ZCTA whose land overlap with the place is the largest — i.e. the place''s primary postal code.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_zcta.arealand_part IS 'Land area of (place ∩ ZCTA) in square metres (Census AREALAND_PART)';
COMMENT ON COLUMN bronze.bronze_jurisdictions_place_zcta.is_primary    IS 'TRUE for the ZCTA with the largest land overlap with this place';
"""


INSERT_PLACE_ZCTA = """
INSERT INTO bronze.bronze_jurisdictions_place_zcta
    (place_geoid, place_name, zcta, state_fips,
     arealand_part, areawater_part, is_primary, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (place_geoid, zcta) DO UPDATE SET
    place_name     = EXCLUDED.place_name,
    state_fips     = EXCLUDED.state_fips,
    arealand_part  = EXCLUDED.arealand_part,
    areawater_part = EXCLUDED.areawater_part,
    is_primary     = EXCLUDED.is_primary,
    source         = EXCLUDED.source,
    ingestion_date = NOW()
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_shp(year: int, shapefile_type: str) -> Path | None:
    """Locate a .shp inside the cached zip, extracting it if needed."""
    pattern = {
        "place":   "cb_{year}_us_place_500k.zip",
        "county":  "cb_{year}_us_county_500k.zip",
    }[shapefile_type]
    zip_path = SHAPEFILE_CACHE / str(year) / pattern.format(year=year)
    extract_dir = zip_path.with_suffix("")

    if not zip_path.exists():
        logger.error(f"Missing cached shapefile: {zip_path}")
        logger.error(
            f"  Run: python scripts/download_bronze.py --only shapefiles --year {year} --extract"
        )
        return None

    if not extract_dir.exists():
        logger.info(f"Extracting {zip_path.name}...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

    shp = next(iter(extract_dir.glob("*.shp")), None)
    if shp is None:
        logger.error(f"No .shp file found inside {extract_dir}")
    return shp


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# place → county
# ---------------------------------------------------------------------------

def build_place_county(year: int, limit: int | None = None) -> pd.DataFrame:
    """
    Compute place → county overlap rows by spatially overlaying the place
    polygons with the county polygons in an equal-area projection.

    Returns a DataFrame ready to be inserted into bronze_jurisdictions_place_county.
    """
    place_shp = _find_shp(year, "place")
    county_shp = _find_shp(year, "county")
    if place_shp is None or county_shp is None:
        return pd.DataFrame()

    logger.info(f"Reading places:   {place_shp.name}")
    places = gpd.read_file(place_shp)
    if limit:
        places = places.head(limit)
    logger.info(f"  {len(places):,} places (CRS: {places.crs})")

    logger.info(f"Reading counties: {county_shp.name}")
    counties = gpd.read_file(county_shp)
    logger.info(f"  {len(counties):,} counties (CRS: {counties.crs})")

    logger.info(f"Reprojecting both to EPSG:{EQUAL_AREA_CRS} for accurate area math...")
    places_eq = places.to_crs(EQUAL_AREA_CRS)[
        ["GEOID", "NAME", "STATEFP", "geometry"]
    ].rename(columns={
        "GEOID": "place_geoid",
        "NAME": "place_name",
        "STATEFP": "place_state",
    })
    counties_eq = counties.to_crs(EQUAL_AREA_CRS)[
        ["GEOID", "NAME", "STATEFP", "geometry"]
    ].rename(columns={
        "GEOID": "county_geoid",
        "NAME": "county_name",
        "STATEFP": "state_fips",
    })

    # Capture each place's total land area before the overlay so we can later
    # express each county's slice as a percentage of the place.
    place_total_area = (
        places_eq.assign(place_area_m2=lambda df: df.geometry.area)
                 .set_index("place_geoid")["place_area_m2"]
                 .astype("int64")
    )

    logger.info("Computing spatial overlay (place ∩ county) — this can take ~30-60s for the whole US...")
    overlay = gpd.overlay(
        places_eq, counties_eq, how="intersection", keep_geom_type=False,
    )
    if overlay.empty:
        logger.warning("Overlay produced 0 rows — something is wrong with the input shapefiles.")
        return pd.DataFrame()

    overlay["overlap_area_m2"] = overlay.geometry.area.astype("int64")

    # Multi-polygon places can yield multiple overlay rows per (place, county)
    # pair (one per geometry piece). Sum them up.
    df = (
        overlay.groupby(
            ["place_geoid", "place_name", "place_state", "county_geoid", "county_name", "state_fips"],
            as_index=False,
        )["overlap_area_m2"]
        .sum()
    )

    df["place_area_m2"] = df["place_geoid"].map(place_total_area).astype("int64")
    df["overlap_pct"] = (df["overlap_area_m2"] / df["place_area_m2"] * 100).round(3)

    # Mark the largest-overlap county for each place as primary.
    df["is_primary"] = False
    primary_idx = df.groupby("place_geoid")["overlap_area_m2"].idxmax()
    df.loc[primary_idx, "is_primary"] = True

    df["vintage_year"] = year
    df["source"] = f"Census CB shapefiles {year} (spatial overlay, EPSG:{EQUAL_AREA_CRS})"

    # Diagnostics
    n_places = df["place_geoid"].nunique()
    n_multi = (df.groupby("place_geoid").size() > 1).sum()
    logger.info(
        f"Built {len(df):,} (place,county) rows for {n_places:,} places "
        f"({n_multi:,} span multiple counties)"
    )
    return df


# ---------------------------------------------------------------------------
# place → zcta
# ---------------------------------------------------------------------------

def build_place_zcta(limit: int | None = None) -> pd.DataFrame:
    """
    Rotate the Census 2020 zcta_place relationship file into a place-centric
    view, marking the largest-overlap ZCTA per place as primary.
    """
    src = RELATIONSHIPS_CACHE / "zcta_place.txt"
    if not src.exists():
        logger.error(f"Missing relationship file: {src}")
        logger.error("  Run: python scripts/download_bronze.py --only relationships")
        return pd.DataFrame()

    logger.info(f"Reading {src.name}...")
    raw = pd.read_csv(src, sep="|", dtype=str, low_memory=False)
    logger.info(f"  {len(raw):,} (zcta,place) rows")

    df = pd.DataFrame({
        "place_geoid": raw["GEOID_PLACE_20"].astype(str).str.strip(),
        "place_name":  raw["NAMELSAD_PLACE_20"].astype(str).str.strip(),
        "zcta":        raw["GEOID_ZCTA5_20"].astype(str).str.strip(),
        "arealand_part":  raw["AREALAND_PART"].map(_safe_int),
        "areawater_part": raw["AREAWATER_PART"].map(_safe_int),
    })

    df = df.dropna(subset=["place_geoid", "zcta"])
    df = df[(df["place_geoid"] != "") & (df["zcta"] != "")]
    df["state_fips"] = df["place_geoid"].str.zfill(7).str[:2]

    if limit:
        keep = df["place_geoid"].drop_duplicates().head(limit)
        df = df[df["place_geoid"].isin(keep)]

    # Mark the ZCTA with the largest land overlap as primary for each place.
    df["is_primary"] = False
    df_sorted = df.sort_values(
        ["place_geoid", "arealand_part"], ascending=[True, False], na_position="last",
    )
    primary_idx = df_sorted.drop_duplicates("place_geoid", keep="first").index
    df.loc[primary_idx, "is_primary"] = True

    df["source"] = "Census 2020 ZCTA-Place Relationship File"

    n_places = df["place_geoid"].nunique()
    n_multi  = (df.groupby("place_geoid").size() > 1).sum()
    logger.info(
        f"Built {len(df):,} (place,zcta) rows for {n_places:,} places "
        f"({n_multi:,} span multiple ZCTAs)"
    )
    return df


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _ensure_table(conn, ddl: str) -> None:
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def _insert_place_county(conn, df: pd.DataFrame, truncate: bool) -> int:
    if df.empty:
        return 0
    with conn.cursor() as cur:
        if truncate:
            logger.info("TRUNCATE bronze.bronze_jurisdictions_place_county")
            cur.execute("TRUNCATE TABLE bronze.bronze_jurisdictions_place_county")
        rows = [
            (
                r.place_geoid, r.place_name, r.place_state,
                r.county_geoid, r.county_name, r.state_fips,
                int(r.overlap_area_m2), int(r.place_area_m2),
                float(r.overlap_pct) if pd.notna(r.overlap_pct) else None,
                bool(r.is_primary),
                calendar_year_label(r.vintage_year),
                r.source,
            )
            for r in df.itertuples(index=False)
        ]
        execute_batch(cur, INSERT_PLACE_COUNTY, rows, page_size=BATCH_SIZE)
    conn.commit()
    return len(df)


def _insert_place_zcta(conn, df: pd.DataFrame, truncate: bool) -> int:
    if df.empty:
        return 0
    with conn.cursor() as cur:
        if truncate:
            logger.info("TRUNCATE bronze.bronze_jurisdictions_place_zcta")
            cur.execute("TRUNCATE TABLE bronze.bronze_jurisdictions_place_zcta")
        rows = [
            (
                r.place_geoid, r.place_name, r.zcta, r.state_fips,
                r.arealand_part, r.areawater_part,
                bool(r.is_primary), r.source,
            )
            for r in df.itertuples(index=False)
        ]
        execute_batch(cur, INSERT_PLACE_ZCTA, rows, page_size=BATCH_SIZE)
    conn.commit()
    return len(df)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(conn) -> None:
    with conn.cursor() as cur:
        for tbl, has_pct in [
            ("bronze.bronze_jurisdictions_place_county", True),
            ("bronze.bronze_jurisdictions_place_zcta",   False),
        ]:
            cur.execute(f"""
                SELECT COUNT(*),
                       COUNT(DISTINCT place_geoid),
                       COUNT(*) FILTER (WHERE is_primary)
                FROM {tbl}
            """)
            total, distinct_places, primary = cur.fetchone()
            logger.info(
                f"  {tbl}: rows={total:,}  places={distinct_places:,}  "
                f"primary_rows={primary:,}"
            )

        # Sample lookups: pick a well-known city and show its primary county + ZIP.
        cur.execute("""
            SELECT place_name, place_geoid, county_name, county_geoid, overlap_pct
            FROM bronze.bronze_jurisdictions_place_county
            WHERE place_name IN ('Boston city', 'Chicago city', 'Los Angeles city',
                                 'Tuscaloosa city', 'New York city')
              AND is_primary
            ORDER BY place_name
            LIMIT 10
        """)
        for row in cur.fetchall():
            logger.info(f"    primary county: {row[0]} ({row[1]}) → {row[2]} ({row[3]})  {row[4]}%")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build place→county and place→ZCTA crosswalks in the bronze schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--year", type=int, default=2025,
                        help="Census shapefile vintage to use (default: 2025)")
    parser.add_argument("--only", nargs="+",
                        choices=["place_county", "place_zcta"],
                        help="Run only one of the crosswalks (default: both)")
    parser.add_argument("--truncate", action="store_true",
                        help="TRUNCATE the target tables before loading")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build dataframes and print stats but skip DB writes")
    parser.add_argument("--limit", type=int,
                        help="Process only the first N places (smoke test)")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only run verification queries against the existing tables")
    args = parser.parse_args()

    targets = set(args.only or ["place_county", "place_zcta"])

    logger.info("=" * 80)
    logger.info("BRONZE PLACE CROSSWALKS")
    logger.info("=" * 80)
    logger.info(f"Targets: {', '.join(sorted(targets))}")
    logger.info(f"Vintage: {args.year}")
    logger.info(f"DB:      {DATABASE_URL.split('@')[-1]}")
    if args.dry_run:
        logger.warning("--dry-run active: dataframes will be built but not written to the DB.")

    conn = None
    if not args.dry_run:
        try:
            conn = psycopg2.connect(DATABASE_URL)
        except psycopg2.OperationalError as e:
            logger.error(f"Cannot connect to Postgres: {e}")
            return 1

    if args.verify_only:
        if conn is None:
            logger.error("--verify-only requires a DB connection (don't combine with --dry-run).")
            return 1
        verify(conn)
        conn.close()
        return 0

    n_pc = n_pz = 0

    if "place_county" in targets:
        logger.info("-" * 80)
        logger.info("place → county")
        logger.info("-" * 80)
        df_pc = build_place_county(year=args.year, limit=args.limit)
        if not df_pc.empty and not args.dry_run:
            _ensure_table(conn, DDL_PLACE_COUNTY)
            n_pc = _insert_place_county(conn, df_pc, truncate=args.truncate)
            logger.success(f"Loaded {n_pc:,} rows → bronze.bronze_jurisdictions_place_county")
        elif args.dry_run:
            logger.info(f"[dry-run] Would load {len(df_pc):,} rows")

    if "place_zcta" in targets:
        logger.info("-" * 80)
        logger.info("place → zcta")
        logger.info("-" * 80)
        df_pz = build_place_zcta(limit=args.limit)
        if not df_pz.empty and not args.dry_run:
            _ensure_table(conn, DDL_PLACE_ZCTA)
            n_pz = _insert_place_zcta(conn, df_pz, truncate=args.truncate)
            logger.success(f"Loaded {n_pz:,} rows → bronze.bronze_jurisdictions_place_zcta")
        elif args.dry_run:
            logger.info(f"[dry-run] Would load {len(df_pz):,} rows")

    if conn is not None:
        logger.info("-" * 80)
        logger.info("Verification")
        logger.info("-" * 80)
        verify(conn)
        conn.close()

    logger.info("=" * 80)
    logger.success(f"Done. place_county={n_pc:,}  place_zcta={n_pz:,}")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
