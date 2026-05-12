"""
Build static JSON + GeoJSON for the Census map SPA (county choropleth + state place drill-down).

Reads ACS parquet files produced by ``download_census_acs_data.py`` (same default cache layout)
and writes artifacts under ``frontend/public/data/census-map`` for Vite to serve at
``/data/census-map/...``.

County layer uses metrics only (boundaries come from us-atlas in the browser). Place drill-down
embeds simplified geometries + metrics in one GeoJSON per state. Writes ``state_metrics.json`` when
``*_state_*_{year}.parquet`` files exist (from ``download_census_acs_data.py --geography state``).

Usage (from repo root, project venv):

  .venv/bin/python scripts/datasources/census/export_census_map_static.py

  # After caching ACS county tables (default download = all U.S. counties):
  .venv/bin/python scripts/datasources/census/download_census_acs_data.py --year 2022

  # City/places for a state (repeat per state you want in the SPA):
  .venv/bin/python scripts/datasources/census/download_census_acs_data.py --geography place --state 01 --year 2022

  .venv/bin/python scripts/datasources/census/export_census_map_static.py \\
      --all-years --place-states 01

  # Place (city) layer for every state + DC + PR (large: needs place ACS parquets per state):
  .venv/bin/python scripts/datasources/census/export_census_map_static.py --all-place-states --year 2022

  # Optionally fetch missing county / place parquets (same tables as METRICS) before export:
  .venv/bin/python scripts/datasources/census/export_census_map_static.py --fetch --place-states 01
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

import geopandas as gpd
import httpx
import pandas as pd
from loguru import logger

# Project root on sys.path (same pattern as download_census_acs_data.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.datasources.census.load_acs import ACSDataIngestion  # noqa: E402
from scripts.datasources.census.download_census_acs_data import DEFAULT_DOWNLOAD_TABLES  # noqa: E402

# One choropleth value per slug; ``estimate_col`` resolved via ``_estimate_col_for_table``.
# **Table coverage**: include every table in ``DEFAULT_DOWNLOAD_TABLES`` (default ACS download) so
# a standard county/state cache can populate the map bundle. Re-run export after adding columns.
METRICS: list[dict[str, Any]] = [
    {
        "slug": "median_household_income",
        "label": "Median household income",
        "table": "B19013",
        "estimate_col": "B19013_001E",
        "format": "currency",
    },
    {
        "slug": "median_home_value",
        "label": "Median home value",
        "table": "B25077",
        "estimate_col": "B25077_001E",
        "format": "currency",
    },
    {
        "slug": "median_gross_rent",
        "label": "Median gross rent",
        "table": "B25064",
        "estimate_col": "B25064_001E",
        "format": "currency",
    },
    {
        "slug": "per_capita_income",
        "label": "Per capita income",
        "table": "B19301",
        "estimate_col": "B19301_001E",
        "format": "currency",
    },
    {
        "slug": "total_population",
        "label": "Total population",
        "table": "B01003",
        "estimate_col": "B01003_001E",
        "format": "count",
    },
    {
        "slug": "median_age",
        "label": "Median age (total)",
        "table": "B01002",
        "estimate_col": "B01002_001E",
        "format": "years",
    },
    {
        "slug": "gini_income_inequality",
        "label": "Gini index of income inequality",
        "table": "B19083",
        "estimate_col": "B19083_001E",
        "format": "ratio",
    },
    {
        "slug": "median_gross_rent_pct_hhincome",
        "label": "Median gross rent as % of household income",
        # B25070_001E is the distribution table “Total” (a count), not a median %.
        # B25071_001E is the published median gross rent as % of household income.
        "table": "B25071",
        "estimate_col": "B25071_001E",
        "format": "percent",
    },
    {
        "slug": "travel_time_to_work_minutes",
        "label": "Mean travel time to work (minutes)",
        "table": "S0801",
        "estimate_col": "S0801_C01_046E",
        "format": "minutes",
    },
    {
        "slug": "housing_units",
        "label": "Housing units",
        "table": "B25001",
        "estimate_col": "B25001_001E",
        "format": "count",
    },
    {
        "slug": "poverty_universe",
        "label": "Population for poverty status",
        "table": "B17001",
        "estimate_col": "B17001_001E",
        "format": "count",
    },
    {
        "slug": "labor_force",
        "label": "Civilian labor force",
        "table": "B23025",
        "estimate_col": "B23025_003E",
        "format": "count",
    },
    # --- Additional metrics: one (or more) per table in ``DEFAULT_DOWNLOAD_TABLES`` ---
    {
        "slug": "sex_by_age_table_total",
        "label": "Population (sex by age, table total)",
        "table": "B01001",
        "estimate_col": "B01001_001E",
        "format": "count",
    },
    {
        "slug": "race_table_total",
        "label": "Population (race, table total)",
        "table": "B02001",
        "estimate_col": "B02001_001E",
        "format": "count",
    },
    {
        "slug": "hispanic_latino_by_race_total",
        "label": "Population (Hispanic or Latino by race, table total)",
        "table": "B03002",
        "estimate_col": "B03002_001E",
        "format": "count",
    },
    {
        "slug": "population_income_below_poverty_level",
        "label": "Population with income below poverty level",
        "table": "B17001",
        "estimate_col": "B17001_002E",
        "format": "count",
    },
    {
        "slug": "employed_civilian",
        "label": "Civilian employed (16+)",
        "table": "B23025",
        "estimate_col": "B23025_004E",
        "format": "count",
    },
    {
        "slug": "unemployed_civilian",
        "label": "Civilian unemployed (16+)",
        "table": "B23025",
        "estimate_col": "B23025_005E",
        "format": "count",
    },
    {
        "slug": "health_insurance_civilian_noninstitutional_total",
        "label": "Civilian noninstitutionalized population (health insurance universe)",
        "table": "B27001",
        "estimate_col": "B27001_001E",
        "format": "count",
    },
    {
        "slug": "health_insurance_under19_table_total",
        "label": "Population (health insurance by age under 19, table total)",
        "table": "B27010",
        "estimate_col": "B27010_001E",
        "format": "count",
    },
    {
        "slug": "population_25_and_over_education_universe",
        "label": "Population 25 years and over (educational attainment universe)",
        "table": "B15003",
        "estimate_col": "B15003_001E",
        "format": "count",
    },
    {
        "slug": "school_enrollment_total",
        "label": "Population enrolled in school (enrollment table total)",
        "table": "B14001",
        "estimate_col": "B14001_001E",
        "format": "count",
    },
]

assert frozenset(DEFAULT_DOWNLOAD_TABLES) <= frozenset(
    m["table"] for m in METRICS
), "METRICS must list at least one metric per DEFAULT_DOWNLOAD_TABLES entry"

TIGER_PLACE_ZIP = (
    "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_{statefp}_place_500k.zip"
)

# States + DC + PR (two-digit FIPS) for optional county trend sidecars.
_CENSUS_STATE_FIPS_ALL: tuple[str, ...] = (
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
    "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
    "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
    "47", "48", "49", "50", "51", "53", "54", "55", "56", "72",
)


def _parse_stat(raw: Any) -> Optional[float]:
    """Parse ACS estimate; ``None`` for suppression / missing."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    iv = int(v)
    if iv in (-666666666, -555555555):
        return None
    if not (-1e12 < v < 1e12):
        return None
    return v


def county_geoid(row: pd.Series) -> str:
    st = str(int(row["state"])).zfill(2)
    co = str(int(row["county"])).zfill(3)
    return f"{st}{co}"


def place_geoid(row: pd.Series) -> str:
    st = str(int(row["state"])).zfill(2)
    pl = str(int(row["place"])).zfill(5)
    return f"{st}{pl}"


def _read_metric_frame(
    acs_dir: Path, table: str, geography: str, state_key: str, year: int
) -> Optional[pd.DataFrame]:
    path = acs_dir / f"{table}_{geography}_{state_key}_{year}.parquet"
    if not path.exists():
        logger.warning(f"Missing parquet: {path}")
        return None
    return pd.read_parquet(path)


def discover_county_parquet_years(acs_dir: Path) -> list[int]:
    """ACS 5-year vintages that have a national county file for B19013 (anchor table)."""
    years: set[int] = set()
    for p in acs_dir.glob("B19013_county_*_*.parquet"):
        m = re.search(r"_(\d{4})\.parquet$", p.name)
        if m:
            years.add(int(m.group(1)))
    return sorted(years)


def _estimate_col_for_table(df: pd.DataFrame, table: str, preferred: str) -> Optional[str]:
    """Pick the ACS estimate column for ``preferred``, with safe fallbacks for B/C tables only.

    Subject tables (``S*``) expose many columns; ``S0801_001E`` is a **universe total** (worker count),
    not mean travel time. Older code fell back to any ``*_001E`` when ``S0801_C01_046E`` was missing,
    which produced “commutes” in the thousands of hours after the UI formatted counts as minutes.
    """
    cols = list(df.columns)
    if not cols:
        return None

    def norm(s: object) -> str:
        return str(s).strip()

    tbl = norm(table)
    pref = norm(preferred)

    for c in cols:
        if norm(c) == pref:
            return norm(c)
    by_lower = {norm(c).lower(): norm(c) for c in cols}
    if pref.lower() in by_lower:
        return by_lower[pref.lower()]

    is_subject = bool(re.match(r"^S[0-9]", tbl, re.I))
    if is_subject:
        if pref.lower().startswith(tbl.lower() + "_"):
            rest = pref[len(tbl) :].lstrip("_")
        else:
            rest = pref
        if rest:
            rlow = rest.lower()
            tlow = tbl.lower()
            for c in cols:
                sc = norm(c)
                slo = sc.lower()
                if slo.startswith(tlow + "_") and slo.endswith(rlow):
                    return sc
        return None

    candidates = [norm(c) for c in cols if str(c).endswith("_001E") and str(c).startswith(tbl)]
    if candidates:
        return candidates[0]
    alt = [norm(c) for c in cols if re.match(rf"^{re.escape(tbl)}_[0-9]+E$", str(c))]
    return alt[0] if alt else None


def build_state_trends(acs_dir: Path, years: list[int]) -> dict[str, Any]:
    """Multi-year state series for METRICS (JSON string years as keys per project convention)."""
    vintages = [str(y) for y in years]
    by_state: dict[str, dict[str, Any]] = {}
    for y in years:
        vy = str(y)
        sv = build_state_values(acs_dir, y)
        if not sv:
            sv = build_state_values_fallback_from_county_medians(acs_dir, y)
        for st, row in sv.items():
            block = by_state.setdefault(st, {"NAME": ""})
            if isinstance(row.get("NAME"), str) and row["NAME"].strip():
                block["NAME"] = row["NAME"].strip()
            for m in METRICS:
                slug = m["slug"]
                block.setdefault(slug, {})[vy] = row.get(slug)
    return {"geography": "state", "vintages": vintages, "by_state": by_state}


def build_county_trends_for_state(acs_dir: Path, state_fips: str, years: list[int]) -> dict[str, Any]:
    stp = state_fips.zfill(2)
    vintages = [str(y) for y in years]
    by_geoid: dict[str, dict[str, Any]] = {}
    for y in years:
        vy = str(y)
        for m in METRICS:
            df = _read_metric_frame(acs_dir, m["table"], "county", "*", y)
            if df is None:
                continue
            col = _estimate_col_for_table(df, m["table"], m["estimate_col"])
            if not col:
                continue
            for _, row in df.iterrows():
                gid = county_geoid(row)
                if not gid.startswith(stp):
                    continue
                block = by_geoid.setdefault(gid, {"GEOID": gid, "NAME": ""})
                block.setdefault(m["slug"], {})[vy] = _parse_stat(row.get(col))
                if "NAME" in df.columns:
                    nm = row.get("NAME")
                    if isinstance(nm, str) and nm.strip():
                        block["NAME"] = nm.strip()
    return {"geography": "county", "state": stp, "vintages": vintages, "byGeoid": by_geoid}


def build_place_trends_for_state(acs_dir: Path, state_fips: str, years: list[int]) -> dict[str, Any]:
    stp = state_fips.zfill(2)
    vintages = [str(y) for y in years]
    by_geoid: dict[str, dict[str, Any]] = {}
    for y in years:
        vy = str(y)
        for m in METRICS:
            df = _read_metric_frame(acs_dir, m["table"], "place", stp, y)
            if df is None:
                continue
            col = _estimate_col_for_table(df, m["table"], m["estimate_col"])
            if not col:
                continue
            for _, row in df.iterrows():
                gid = place_geoid(row)
                block = by_geoid.setdefault(gid, {"GEOID": gid, "NAME": ""})
                block.setdefault(m["slug"], {})[vy] = _parse_stat(row.get(col))
                if "NAME" in df.columns:
                    nm = row.get("NAME")
                    if isinstance(nm, str) and nm.strip():
                        block["NAME"] = nm.strip()
    return {"geography": "place", "state": stp, "vintages": vintages, "byGeoid": by_geoid}


def build_county_values(acs_dir: Path, year: int) -> dict[str, dict[str, Optional[float]]]:
    out: dict[str, dict[str, Optional[float]]] = {}
    state_star = "*"
    for m in METRICS:
        df = _read_metric_frame(acs_dir, m["table"], "county", state_star, year)
        if df is None:
            continue
        col = _estimate_col_for_table(df, m["table"], m["estimate_col"])
        if not col:
            logger.warning(f"No estimate column for {m['table']} in county frame ({m['slug']})")
            continue
        for _, row in df.iterrows():
            gid = county_geoid(row)
            out.setdefault(gid, {})
            out[gid][m["slug"]] = _parse_stat(row.get(col))
            if "NAME" in df.columns:
                nm = row.get("NAME")
                if isinstance(nm, str) and nm.strip():
                    out[gid]["NAME"] = nm.strip()
    return out


def build_state_values(acs_dir: Path, year: int) -> dict[str, dict[str, Optional[float]]]:
    """One row per state FIPS (2-digit), same metric keys as county export."""
    out: dict[str, dict[str, Optional[float]]] = {}
    state_star = "*"
    for m in METRICS:
        df = _read_metric_frame(acs_dir, m["table"], "state", state_star, year)
        if df is None:
            continue
        col = _estimate_col_for_table(df, m["table"], m["estimate_col"])
        if not col:
            logger.warning(f"No estimate column for {m['table']} in state frame ({m['slug']})")
            continue
        for _, row in df.iterrows():
            st = str(int(row["state"])).zfill(2)
            out.setdefault(st, {})
            out[st][m["slug"]] = _parse_stat(row.get(col))
            if "NAME" in df.columns:
                nm = row.get("NAME")
                if isinstance(nm, str) and nm.strip():
                    out[st]["NAME"] = nm.strip()
    return out


def build_state_values_fallback_from_county_medians(acs_dir: Path, year: int) -> dict[str, dict[str, Optional[float]]]:
    """Approximate state metrics from county parquets when ``*_state_*_{year}`` files are absent.

    For each state and metric, uses the **median of county-level estimates**. This differs from
    the Census-published state 5-year estimate (different estimation universe). It restores
    multi-year **US state map** coloring when only national county files exist.
    """
    county_by_geoid = build_county_values(acs_dir, year)
    if not county_by_geoid:
        return {}
    series: dict[str, dict[str, list[int]]] = {}
    for gid, row in county_by_geoid.items():
        st = gid[:2] if len(gid) >= 2 else ""
        if len(st) != 2 or not st.isdigit():
            continue
        per_st = series.setdefault(st, {})
        for m in METRICS:
            slug = m["slug"]
            v = row.get(slug)
            if isinstance(v, (int, float)) and v == v and v >= 0:
                per_st.setdefault(slug, []).append(float(v))
    out: dict[str, dict[str, Optional[float]]] = {}
    for st, slugs in series.items():
        block: dict[str, Optional[float]] = {}
        for m in METRICS:
            slug = m["slug"]
            vals = slugs.get(slug) or []
            block[slug] = float(statistics.median(vals)) if vals else None
        out[st] = block
    return out


def build_national_reference(acs_dir: Path, years: list[int]) -> dict[str, dict[str, dict[str, Optional[float]]]]:
    """Per-vintage national benchmarks: Census ``us:1`` row and state composite weighted by B01003 population.

    The population-weighted state composite is **not** a published Census median; it is a
    transparent index (Σ value×pop / Σ pop) for comparing areas to a single reference number.
    """
    by_vintage: dict[str, dict[str, dict[str, Optional[float]]]] = {}
    for y in years:
        vy = str(y)
        st_vals = build_state_values(acs_dir, y)
        if not st_vals:
            st_vals = build_state_values_fallback_from_county_medians(acs_dir, y)
        pops: dict[str, float] = {}
        pop_df = _read_metric_frame(acs_dir, "B01003", "state", "*", y)
        if pop_df is not None and "B01003_001E" in pop_df.columns:
            for _, row in pop_df.iterrows():
                st = str(int(row["state"])).zfill(2)
                p = _parse_stat(row.get("B01003_001E"))
                if p is not None and p > 0:
                    pops[st] = p
        per_slug: dict[str, dict[str, Optional[float]]] = {}
        for m in METRICS:
            slug = m["slug"]
            us_df = _read_metric_frame(acs_dir, m["table"], "us", "1", y)
            us_val: Optional[float] = None
            if us_df is not None and len(us_df.index):
                col = _estimate_col_for_table(us_df, m["table"], m["estimate_col"])
                if col:
                    us_val = _parse_stat(us_df.iloc[0][col])
            w_num = 0.0
            w_den = 0.0
            for st, row in (st_vals or {}).items():
                pop = pops.get(st)
                if not pop:
                    continue
                raw = row.get(slug)
                if raw is None:
                    continue
                try:
                    fv = float(raw)
                except (TypeError, ValueError):
                    continue
                w_num += fv * pop
                w_den += pop
            w_avg = (w_num / w_den) if w_den > 0 else None
            per_slug[slug] = {"us": us_val, "pop_weighted_states": w_avg}
            if slug == "median_household_income" and us_val is None and w_avg is None:
                logger.warning(
                    f"National benchmark missing for {slug} ACS {vy}: "
                    f"need B19013_us_1_{y}.parquet and/or state-level B19013 + B01003 parquets."
                )
        by_vintage[vy] = per_slug
    return by_vintage


def build_place_metrics_by_geoid(
    acs_dir: Path, state_fips: str, year: int
) -> dict[str, dict[str, Any]]:
    metrics_by_geoid: dict[str, dict[str, Any]] = {}
    for m in METRICS:
        df = _read_metric_frame(acs_dir, m["table"], "place", state_fips, year)
        if df is None:
            continue
        col = _estimate_col_for_table(df, m["table"], m["estimate_col"])
        if not col:
            continue
        name_col = "NAME" if "NAME" in df.columns else None
        for _, row in df.iterrows():
            gid = place_geoid(row)
            block = metrics_by_geoid.setdefault(gid, {"GEOID": gid, "NAME": ""})
            block[m["slug"]] = _parse_stat(row.get(col))
            if name_col:
                block["NAME"] = str(row.get(name_col) or block["NAME"])
    return metrics_by_geoid


async def _ensure_parquets(
    acs_dir: Path, year: int, place_states: list[str], fetch: bool
) -> None:
    if not fetch:
        return
    acs = ACSDataIngestion(data_dir=acs_dir)
    tables = list({m["table"] for m in METRICS})

    async def _fetch_one(table: str, geography: str, state: str) -> None:
        try:
            await acs.download_acs_data_api(table, geography, state, year=year)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.warning(
                    f"--fetch: skip {table} {geography} state={state!r} year={year} "
                    f"(HTTP 400 — table often absent for early ACS 5-year vintages)"
                )
                return
            raise

    logger.info(f"--fetch: downloading county tables {tables} …")
    for t in tables:
        await _fetch_one(t, "county", "*")
        await asyncio.sleep(1.2)
    logger.info("--fetch: downloading state tables (all states) …")
    for t in tables:
        await _fetch_one(t, "state", "*")
        await asyncio.sleep(1.2)
    logger.info("--fetch: downloading US (national) summary rows …")
    for t in tables:
        await _fetch_one(t, "us", "1")
        await asyncio.sleep(1.2)
    for st in place_states:
        logger.info(f"--fetch: downloading place tables for state {st} …")
        for t in tables:
            await _fetch_one(t, "place", st)
            await asyncio.sleep(1.0)


def _download_place_shapefile(year: int, state_fips: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = TIGER_PLACE_ZIP.format(year=year, statefp=state_fips)
    zip_path = dest_dir / f"cb_{year}_{state_fips}_place_500k.zip"
    if zip_path.exists():
        logger.info(f"Using cached Tiger ZIP {zip_path.name}")
    else:
        logger.info(f"Downloading {url}")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            zip_path.write_bytes(r.content)
    extract_root = dest_dir / f"cb_{year}_{state_fips}_place_500k"
    shp = extract_root / f"cb_{year}_{state_fips}_place_500k.shp"
    if shp.exists():
        return shp
    extract_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)
    return shp


def export_place_geojson(
    acs_dir: Path,
    tiger_cache: Path,
    state_fips: str,
    year: int,
    out_path: Path,
    simplify_tolerance: float,
) -> bool:
    metrics_by_geoid = build_place_metrics_by_geoid(acs_dir, state_fips, year)
    if not metrics_by_geoid:
        logger.error(f"No place ACS metrics for state {state_fips}; skip GeoJSON")
        return False
    try:
        shp = _download_place_shapefile(year, state_fips, tiger_cache)
    except Exception as e:
        logger.error(f"Tiger download/read failed for {state_fips}: {e}")
        return False
    gdf = gpd.read_file(shp)
    if gdf.crs is not None and gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs(4326)
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(7)
    rows = []
    for _, row in gdf.iterrows():
        gid = row["GEOID"]
        m = metrics_by_geoid.get(gid)
        if not m:
            continue
        geom = row.geometry.simplify(simplify_tolerance, preserve_topology=True)
        feat = {
            "type": "Feature",
            "id": gid,
            "properties": {
                "GEOID": gid,
                "NAME": m.get("NAME") or row.get("NAME") or "",
                **{k: m.get(k) for k in [x["slug"] for x in METRICS] if k in m},
            },
            "geometry": geom.__geo_interface__,
        }
        rows.append(feat)
    fc = {"type": "FeatureCollection", "features": rows}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc), encoding="utf-8")
    logger.success(f"Wrote {out_path} ({len(rows)} places)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acs-dir",
        type=Path,
        default=Path("data/cache/census/acs"),
        help="ACS parquet directory",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("frontend/public/data/census-map"),
        help="Output directory (Vite public/)",
    )
    parser.add_argument(
        "--tiger-cache",
        type=Path,
        default=Path("data/cache/census/tiger_place_shp"),
        help="Cache directory for downloaded Tiger place shapefiles",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2022,
        help="ACS 5-year / Tiger vintage (default 2022)",
    )
    parser.add_argument(
        "--place-states",
        nargs="*",
        default=[],
        metavar="FIPS",
        help="State FIPS codes to emit place GeoJSON for (e.g. 01 06). Default: none.",
    )
    parser.add_argument(
        "--all-place-states",
        action="store_true",
        help=(
            "Emit place GeoJSON (and place trends when using --all-years) for all U.S. states, "
            "DC, and PR (same 52 FIPS as county trend sidecars). Overrides --place-states."
        ),
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download missing ACS parquets via Census API before export",
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.003,
        help="Place polygon simplify tolerance (degrees WGS84). Default 0.003.",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help=(
            "Discover every ACS vintage with B19013 county parquets and export each "
            "to out-dir/{year}/. When 2+ years export, also write state_trends.json and "
            "per-state county_trends_{fips}.json / place_trends_{fips}.json for animation."
        ),
    )
    args = parser.parse_args()

    if args.all_place_states:
        args.place_states = list(_CENSUS_STATE_FIPS_ALL)

    if args.all_years:
        years_plan = discover_county_parquet_years(args.acs_dir)
        if not years_plan:
            logger.error("No B19013_county_*_{year}.parquet files found — cannot --all-years.")
            return 1
        logger.info(f"--all-years: found {len(years_plan)} vintages ({years_plan[0]}–{years_plan[-1]})")
    else:
        years_plan = [args.year]

    if args.fetch:
        for y in years_plan:
            asyncio.run(_ensure_parquets(args.acs_dir, y, args.place_states or [], True))

    exported_years: list[int] = []
    place_states_union: set[str] = set()

    for year in years_plan:
        vintage = str(year)
        county_values = build_county_values(args.acs_dir, year)
        if not county_values:
            logger.warning(f"Skipping vintage {year}: no county metrics built.")
            continue

        out_vintage = args.out_dir / vintage
        out_vintage.mkdir(parents=True, exist_ok=True)

        county_path = out_vintage / "county_metrics.json"
        payload = {
            "geography": "county",
            "vintage": vintage,
            "values": county_values,
        }
        county_path.write_text(json.dumps(payload), encoding="utf-8")
        logger.success(f"Wrote {county_path} ({len(county_values)} counties)")

        state_values = build_state_values(args.acs_dir, year)
        if state_values:
            state_path = out_vintage / "state_metrics.json"
            state_payload = {
                "geography": "state",
                "vintage": vintage,
                "values": state_values,
            }
            state_path.write_text(json.dumps(state_payload), encoding="utf-8")
            logger.success(f"Wrote {state_path} ({len(state_values)} states/areas)")
        else:
            logger.warning(
                f"No state_metrics.json for {year} — download state ACS parquets "
                "(e.g. --geography state --state '*')."
            )

        place_states_ok: list[str] = []
        for st in args.place_states:
            st = st.zfill(2)
            geo_path = out_vintage / f"place_{st}.geojson"
            if export_place_geojson(
                args.acs_dir,
                args.tiger_cache,
                st,
                year,
                geo_path,
                args.simplify,
            ):
                place_states_ok.append(st)
        place_states_union.update(place_states_ok)
        exported_years.append(year)

    if not exported_years:
        logger.error("No county exports succeeded. Download ACS county tables first.")
        return 1

    vintages_str = [str(y) for y in exported_years]
    top_vintage = str(max(exported_years))

    paths: dict[str, str] = {
        "county_metrics": "/data/census-map/{vintage}/county_metrics.json",
        "state_metrics": "/data/census-map/{vintage}/state_metrics.json",
        "place_geojson": "/data/census-map/{vintage}/place_{state}.geojson",
    }

    if len(exported_years) > 1:
        st_tr = build_state_trends(args.acs_dir, exported_years)
        (args.out_dir / "state_trends.json").write_text(json.dumps(st_tr), encoding="utf-8")
        logger.success(f"Wrote {args.out_dir / 'state_trends.json'}")

        for st in _CENSUS_STATE_FIPS_ALL:
            ct = build_county_trends_for_state(args.acs_dir, st, exported_years)
            if ct["byGeoid"]:
                p = args.out_dir / f"county_trends_{st}.json"
                p.write_text(json.dumps(ct), encoding="utf-8")
                logger.info(f"Wrote {p.name} ({len(ct['byGeoid'])} counties)")

        for st in sorted(place_states_union):
            pt = build_place_trends_for_state(args.acs_dir, st, exported_years)
            if pt["byGeoid"]:
                p = args.out_dir / f"place_trends_{st}.json"
                p.write_text(json.dumps(pt), encoding="utf-8")
                logger.info(f"Wrote {p.name} ({len(pt['byGeoid'])} places)")

        paths["state_trends"] = "/data/census-map/state_trends.json"
        paths["county_trends"] = "/data/census-map/county_trends_{state}.json"
        paths["place_trends"] = "/data/census-map/place_trends_{state}.json"

    national_ref = build_national_reference(args.acs_dir, exported_years)

    manifest = {
        "vintage": top_vintage,
        "vintages": vintages_str,
        "tiger_year": top_vintage,
        "county_topo_cdn": "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json",
        "state_topo_cdn": "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json",
        "metrics": METRICS,
        "place_states": sorted(place_states_union),
        "paths": paths,
        "national_ref": national_ref,
    }
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.success(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
