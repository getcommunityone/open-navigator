#!/usr/bin/env python3
"""Census place crosswalks pipeline: load the place->ZCTA crosswalk into bronze.

Ported from load_place_crosswalks.py to the core_lib DataSourcePipeline
contract.

The legacy loader builds two place-centric crosswalk tables in the bronze
schema:

  bronze.bronze_jurisdictions_place_county
      "What county does this city/town belong to?" Computed by a GeoPandas
      spatial overlay of the Census place and county cartographic boundary
      shapefiles (EPSG:5070 equal-area). The pure helpers and DDL for this
      table are preserved verbatim below (``_find_shp`` / ``build_place_county``
      / ``DDL_PLACE_COUNTY``); the overlay is not expressible as a streaming
      RawRow extract, so it is kept as module-level helpers rather than wired
      into the streaming pipeline.

  bronze.bronze_jurisdictions_place_zcta
      "What is the primary postal code (ZCTA) for this city/town?" Read from
      the Census 2020 ZCTA-Place relationship file and rotated to a
      place-centric view, marking the largest-overlap ZCTA as primary. This is
      the file-driven, discoverable flow and is what the DataSourcePipeline
      drives via ``extract`` / ``load_batch``.

Inputs (must already be downloaded by `python scripts/download_bronze.py`):
  - data/cache/census/shapefiles/<year>/cb_<year>_us_place_500k.zip
  - data/cache/census/shapefiles/<year>/cb_<year>_us_county_500k.zip
  - data/cache/census_relationships/zcta_place.txt

Usage:
    python -m ingestion.census.place_crosswalks
    python scripts/datasources/census/place_crosswalks.py --year 2024
    python scripts/datasources/census/place_crosswalks.py --truncate
    python scripts/datasources/census/place_crosswalks.py --only place_county
    python scripts/datasources/census/place_crosswalks.py --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 / localhost:5433 / open_navigator).
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


SHAPEFILE_CACHE = Path("data/cache/census/shapefiles")
RELATIONSHIPS_CACHE = Path("data/cache/census_relationships")

# NAD83 / Conus Albers — equal-area projection that keeps area calculations
# accurate across the lower 48 + AK/HI/PR (with small distortion at the edges).
EQUAL_AREA_CRS = 5070


# ---------------------------------------------------------------------------
# DDL  (preserved verbatim from the legacy loader; split into separate text()
#       statements per the package convention)
# ---------------------------------------------------------------------------

DDL_PLACE_COUNTY = (
    text("CREATE SCHEMA IF NOT EXISTS bronze"),
    text(
        """
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
        )
        """
    ),
    text("CREATE INDEX IF NOT EXISTS idx_bjpc_place   ON bronze.bronze_jurisdictions_place_county(place_geoid)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpc_county  ON bronze.bronze_jurisdictions_place_county(county_geoid)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpc_state   ON bronze.bronze_jurisdictions_place_county(state_fips)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpc_primary ON bronze.bronze_jurisdictions_place_county(place_geoid) WHERE is_primary"),
)


INSERT_PLACE_COUNTY = text(
    """
    INSERT INTO bronze.bronze_jurisdictions_place_county
        (place_geoid, place_name, place_state, county_geoid, county_name,
         state_fips, overlap_area_m2, place_area_m2, overlap_pct,
         is_primary, vintage_year, source)
    VALUES (:place_geoid, :place_name, :place_state, :county_geoid, :county_name,
            :state_fips, :overlap_area_m2, :place_area_m2, :overlap_pct,
            :is_primary, :vintage_year, :source)
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
)


DDL_PLACE_ZCTA = (
    text("CREATE SCHEMA IF NOT EXISTS bronze"),
    text(
        """
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
        )
        """
    ),
    text("CREATE INDEX IF NOT EXISTS idx_bjpz_place           ON bronze.bronze_jurisdictions_place_zcta(place_geoid)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpz_zcta            ON bronze.bronze_jurisdictions_place_zcta(zcta)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpz_state           ON bronze.bronze_jurisdictions_place_zcta(state_fips)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpz_primary         ON bronze.bronze_jurisdictions_place_zcta(place_geoid) WHERE is_primary"),
    text("CREATE INDEX IF NOT EXISTS idx_bjpz_jurisdiction_id ON bronze.bronze_jurisdictions_place_zcta(jurisdiction_id)"),
)


INSERT_PLACE_ZCTA = text(
    """
    INSERT INTO bronze.bronze_jurisdictions_place_zcta
        (place_geoid, place_name, zcta, state_fips,
         arealand_part, areawater_part, is_primary, source)
    VALUES (:place_geoid, :place_name, :zcta, :state_fips,
            :arealand_part, :areawater_part, :is_primary, :source)
    ON CONFLICT (place_geoid, zcta) DO UPDATE SET
        place_name     = EXCLUDED.place_name,
        state_fips     = EXCLUDED.state_fips,
        arealand_part  = EXCLUDED.arealand_part,
        areawater_part = EXCLUDED.areawater_part,
        is_primary     = EXCLUDED.is_primary,
        source         = EXCLUDED.source,
        ingestion_date = NOW()
    """
)

_TRUNCATE_PLACE_COUNTY = text("TRUNCATE TABLE bronze.bronze_jurisdictions_place_county")
_TRUNCATE_PLACE_ZCTA = text("TRUNCATE TABLE bronze.bronze_jurisdictions_place_zcta")


# ---------------------------------------------------------------------------
# Helpers  (preserved verbatim from the legacy loader)
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
# place → county  (GeoPandas spatial overlay; preserved verbatim)
# ---------------------------------------------------------------------------

def build_place_county(year: int, limit: int | None = None) -> pd.DataFrame:
    """
    Compute place → county overlap rows by spatially overlaying the place
    polygons with the county polygons in an equal-area projection.

    Returns a DataFrame ready to be inserted into bronze_jurisdictions_place_county.
    """
    # geopandas is an optional/heavy dependency; imported lazily so the module
    # (and the place->zcta pipeline) remains importable without it, matching
    # the hifld/locations.py convention.
    import geopandas as gpd

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
# place → zcta  (relationship file; preserved verbatim)
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

    return _build_place_zcta_from(src, limit=limit)


def _build_place_zcta_from(src: Path, limit: int | None = None) -> pd.DataFrame:
    """Rotate a ZCTA-Place relationship file at an explicit path into a
    place-centric DataFrame. Body preserved verbatim from the legacy
    ``build_place_zcta`` (only the source-path resolution is hoisted out so the
    pipeline can be pointed at a `--file` / test fixture)."""
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
# Row schema
# ---------------------------------------------------------------------------

class PlaceZctaRow(RawRow):
    """One place->ZCTA crosswalk row, validated before upsert into
    bronze.bronze_jurisdictions_place_zcta. Nullability mirrors the legacy
    loader (place_geoid / zcta / is_primary required; everything else
    optional); max lengths mirror the VARCHAR DB column types."""

    place_geoid: str = Field(min_length=1, max_length=7)
    place_name: str | None = Field(default=None, max_length=255)
    zcta: str = Field(min_length=1, max_length=10)
    state_fips: str | None = Field(default=None, max_length=2)
    arealand_part: int | None = None
    areawater_part: int | None = None
    is_primary: bool
    place_source: str | None = Field(default=None, max_length=255)


class CensusPlaceCrosswalksPipeline(DataSourcePipeline[PlaceZctaRow]):
    source = "census_place_crosswalks"
    batch_size = 1_000  # legacy execute_batch page_size
    row_schema = PlaceZctaRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        # Build the place-centric ZCTA view from the relationship file (same
        # pure helper as the legacy loader), then emit one envelope per row.
        if self._path is not None:
            df = _build_place_zcta_from(self._path, limit=self._limit)
            version = self._path.stem
        else:
            df = build_place_zcta(limit=self._limit)
            version = (RELATIONSHIPS_CACHE / "zcta_place.txt").stem
        for r in df.itertuples(index=False):
            yield {
                "source": self.source,
                "source_version": version,
                "natural_key": f"{r.place_geoid}:{r.zcta}",
                "place_geoid": r.place_geoid,
                "place_name": r.place_name,
                "zcta": r.zcta,
                "state_fips": r.state_fips,
                "arealand_part": r.arealand_part,
                "areawater_part": r.areawater_part,
                "is_primary": bool(r.is_primary),
                "place_source": r.source,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[PlaceZctaRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "place_geoid": r.place_geoid,
                "place_name": r.place_name,
                "zcta": r.zcta,
                "state_fips": r.state_fips,
                "arealand_part": r.arealand_part,
                "areawater_part": r.areawater_part,
                "is_primary": r.is_primary,
                "source": r.place_source,
            }
            for r in rows
        ]
        await session.execute(INSERT_PLACE_ZCTA, params)


async def _prepare_target(truncate: bool) -> None:
    # Create the schema + both crosswalk tables (each DDL statement as a
    # separate text() call), then optionally truncate both targets.
    async with async_session() as session:
        for stmt in DDL_PLACE_COUNTY:
            await session.execute(stmt)
        for stmt in DDL_PLACE_ZCTA:
            await session.execute(stmt)
        if truncate:
            await session.execute(_TRUNCATE_PLACE_COUNTY)
            await session.execute(_TRUNCATE_PLACE_ZCTA)


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument("--file", type=Path,
                        help="Path to the zcta_place.txt relationship file (default: cache)")
    parser.add_argument("--limit", type=int,
                        help="Process only the first N places (smoke test)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CensusPlaceCrosswalksPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
