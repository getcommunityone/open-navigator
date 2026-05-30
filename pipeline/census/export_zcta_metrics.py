"""
Build per-state ZCTA metric JSON for the census drilldown ZIP tier.

Output: ``web_app/public/data/census-map/{vintage}/zcta_metrics_{FIPS}.json``
        keyed by ZCTA5 → metric_slug → value, matching the shape
        ``CensusDrilldownMapPage.tsx`` loads via the ``zctaMetricsPayload`` query.

Why a separate script: ZCTA-level ACS isn't covered by
``download_census_acs_data.py`` (which targets state/county/place/tract). The
ZCTA universe is national-only on the Census API (``for=zip code tabulation
area:*``), so we fetch once and split per-state at export time using the
Census 2020 ZCTA→County relationship file already on disk
(``data/cache/census_relationships/zcta_county.txt``).

Why a max-overlap assignment: ZCTAs cross state lines. We assign each ZCTA to
the state holding the largest land-area share (sum of ``AREALAND_PART`` over
all (ZCTA, county) rows whose county FIPS starts with that state). This matches
what ``scripts/frontend/prep_zcta_tiles.sh`` does spatially via mapshaper, so
the choropleth and the polygons line up.

Usage::

    .venv/bin/python packages/scrapers/src/scrapers/census/export_zcta_metrics.py \\
        --year 2023

    # Limit output to specific states (otherwise writes one file per state with
    # at least one ZCTA):
    .venv/bin/python packages/scrapers/src/scrapers/census/export_zcta_metrics.py \\
        --year 2023 --states 06,36,48

    # Force re-fetch of cached ACS parquets:
    .venv/bin/python packages/scrapers/src/scrapers/census/export_zcta_metrics.py \\
        --year 2023 --force

Cost: ~6 Census API requests (one per metric table). ZCTA ACS5 is
free with an API key; without a key you're rate-limited to 500 reqs/day.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd
from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Shared metric definitions — copied here rather than imported to keep this
# script callable from the venv without ``packages/ingestion`` on sys.path.
# Slugs must match METRICS in export_census_map_static.py so the frontend can
# look up a value with the same key at every drilldown tier.
#
# Subject tables (S-prefix, e.g. S0801) are not published at the ZCTA level —
# the Census API returns 404 and ``_fetch_zcta_table`` skips them gracefully,
# so the ZIP tier falls back to neutral fill for those metrics. Keep them in
# the list anyway to make the slug parity explicit.
METRICS: list[dict[str, Any]] = [
    {"slug": "median_household_income",                            "table": "B19013", "estimate_col": "B19013_001E"},
    {"slug": "median_home_value",                                  "table": "B25077", "estimate_col": "B25077_001E"},
    {"slug": "median_gross_rent",                                  "table": "B25064", "estimate_col": "B25064_001E"},
    {"slug": "per_capita_income",                                  "table": "B19301", "estimate_col": "B19301_001E"},
    {"slug": "total_population",                                   "table": "B01003", "estimate_col": "B01003_001E"},
    {"slug": "median_age",                                         "table": "B01002", "estimate_col": "B01002_001E"},
    {"slug": "gini_income_inequality",                             "table": "B19083", "estimate_col": "B19083_001E"},
    {"slug": "median_gross_rent_pct_hhincome",                     "table": "B25071", "estimate_col": "B25071_001E"},
    {"slug": "travel_time_to_work_minutes",                        "table": "S0801",  "estimate_col": "S0801_C01_046E"},
    {"slug": "housing_units",                                      "table": "B25001", "estimate_col": "B25001_001E"},
    {"slug": "poverty_universe",                                   "table": "B17001", "estimate_col": "B17001_001E"},
    {"slug": "labor_force",                                        "table": "B23025", "estimate_col": "B23025_003E"},
    {"slug": "sex_by_age_table_total",                             "table": "B01001", "estimate_col": "B01001_001E"},
    {"slug": "race_table_total",                                   "table": "B02001", "estimate_col": "B02001_001E"},
    {"slug": "hispanic_latino_by_race_total",                      "table": "B03002", "estimate_col": "B03002_001E"},
    {"slug": "population_income_below_poverty_level",              "table": "B17001", "estimate_col": "B17001_002E"},
    {"slug": "employed_civilian",                                  "table": "B23025", "estimate_col": "B23025_004E"},
    {"slug": "unemployed_civilian",                                "table": "B23025", "estimate_col": "B23025_005E"},
    {"slug": "health_insurance_civilian_noninstitutional_total",   "table": "B27001", "estimate_col": "B27001_001E"},
    {"slug": "health_insurance_under19_table_total",               "table": "B27010", "estimate_col": "B27010_001E"},
    {"slug": "population_25_and_over_education_universe",          "table": "B15003", "estimate_col": "B15003_001E"},
    {"slug": "school_enrollment_total",                            "table": "B14001", "estimate_col": "B14001_001E"},
]

DEFAULT_ACS_DIR = _REPO_ROOT / "data" / "cache" / "acs"
DEFAULT_OUT_DIR = _REPO_ROOT / "frontend" / "public" / "data" / "census-map"
DEFAULT_ZCTA_COUNTY_REL = _REPO_ROOT / "data" / "cache" / "census_relationships" / "zcta_county.txt"


def _parse_stat(raw: Any) -> Optional[float]:
    """Census API returns sentinels (``-666666666`` "no estimate",
    ``-555555555`` median falls in open-ended interval, etc.) for suppressed
    cells. They're large-magnitude negatives well below any real metric value,
    so any value below -1e6 is a sentinel."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= -1e6:
        return None
    return v


def build_zcta_state_assignment(rel_path: Path) -> dict[str, str]:
    """
    Return ``{ZCTA5: state_fips}`` using max ``AREALAND_PART`` overlap.

    Census 2020 ZCTA→County relationship file format (pipe-delimited):
        OID_ZCTA5_20 | GEOID_ZCTA5_20 | NAMELSAD_ZCTA5_20 | AREALAND_ZCTA5_20 |
        AREAWATER_ZCTA5_20 | MTFCC_ZCTA5_20 | CLASSFP_ZCTA5_20 | FUNCSTAT_ZCTA5_20 |
        OID_COUNTY_20 | GEOID_COUNTY_20 | NAMELSAD_COUNTY_20 | AREALAND_COUNTY_20 |
        AREAWATER_COUNTY_20 | MTFCC_COUNTY_20 | CLASSFP_COUNTY_20 | FUNCSTAT_COUNTY_20 |
        AREALAND_PART | AREAWATER_PART
    """
    if not rel_path.exists():
        raise SystemExit(
            f"Missing relationship file: {rel_path}\n"
            "Run: python packages/scrapers/src/scrapers/census/download_census_relationships.py"
        )
    by_state: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with rel_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            zcta = (row.get("GEOID_ZCTA5_20") or "").strip()
            county = (row.get("GEOID_COUNTY_20") or "").strip()
            land = row.get("AREALAND_PART") or "0"
            if not zcta or len(county) < 2:
                continue
            try:
                land_f = float(land)
            except ValueError:
                continue
            state = county[:2]
            by_state[zcta][state] += land_f
    out: dict[str, str] = {}
    for zcta, states in by_state.items():
        out[zcta] = max(states.items(), key=lambda kv: kv[1])[0]
    return out


# ── Census API fetch ────────────────────────────────────────────────────────


_CENSUS_BASE = "https://api.census.gov/data"


async def _fetch_zcta_table(
    client: httpx.AsyncClient,
    *,
    table: str,
    year: int,
    estimate_cols: list[str],
    api_key: Optional[str],
) -> pd.DataFrame:
    """One ACS5 ZCTA table → DataFrame.

    All ``estimate_cols`` for a table are fetched in a single Census API call
    and cached together at ``data/cache/acs/{table}_zcta_us_{year}.parquet``.
    Fetching per-column would issue one request per slug (B23025 alone has 3),
    burning rate-limit quota and producing inconsistent caches when slugs are
    added later — the cached parquet would only hold the first column fetched.
    """
    cache_path = DEFAULT_ACS_DIR / f"{table}_zcta_us_{year}.parquet"
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        if all(c in cached.columns for c in estimate_cols):
            return cached
        # Cache is missing one or more newly-requested columns. Fall through to
        # re-fetch with the full set so all slugs sharing this table resolve.
        logger.info(f"  cache miss on cols for {table}: refetching")

    url = f"{_CENSUS_BASE}/{year}/acs/acs5"
    params: dict[str, str] = {
        "get": f"{','.join(estimate_cols)},NAME",
        "for": "zip code tabulation area:*",
    }
    if api_key:
        params["key"] = api_key

    logger.info(f"GET {url}  table={table}  cols={estimate_cols}  year={year}  (~33k rows)")
    resp = await client.get(url, params=params, timeout=120.0)
    # Census returns 404 for unknown geographies and 400 for valid geographies
    # that simply don't publish this table (Subject S-tables aren't released at
    # ZCTA). Both mean "skip this metric" rather than fail the whole export.
    if resp.status_code in (400, 404):
        logger.warning(f"{table} not available at ZCTA for ACS5 {year}: HTTP {resp.status_code}")
        return pd.DataFrame()
    resp.raise_for_status()
    payload = resp.json()
    if not payload or len(payload) < 2:
        return pd.DataFrame()
    header, *rows = payload
    df = pd.DataFrame(rows, columns=header)

    # Coerce variable cols to numeric; leave NAME and zip code field as strings.
    for c in estimate_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    logger.info(f"  cached {cache_path.relative_to(_REPO_ROOT)}  ({len(df)} rows)")
    return df


async def fetch_all_metrics(year: int, force: bool) -> dict[str, pd.DataFrame]:
    """Return ``{table_code: DataFrame}`` for every ZCTA-available metric.

    Groups slugs by ACS table so each table is fetched once with all the
    estimate columns its slugs need (vs once per slug).
    """
    load_dotenv(_REPO_ROOT / ".env")
    api_key = os.getenv("CENSUS_API_KEY", "").strip() or None
    if not api_key:
        logger.warning("No CENSUS_API_KEY in .env — rate-limited to 500 reqs/day")

    cols_by_table: dict[str, list[str]] = defaultdict(list)
    for m in METRICS:
        if m["estimate_col"] not in cols_by_table[m["table"]]:
            cols_by_table[m["table"]].append(m["estimate_col"])

    if force:
        for table in cols_by_table:
            p = DEFAULT_ACS_DIR / f"{table}_zcta_us_{year}.parquet"
            if p.exists():
                p.unlink()

    out: dict[str, pd.DataFrame] = {}
    async with httpx.AsyncClient() as client:
        for table, cols in cols_by_table.items():
            df = await _fetch_zcta_table(
                client,
                table=table,
                year=year,
                estimate_cols=cols,
                api_key=api_key,
            )
            if not df.empty:
                out[table] = df
    return out


# ── Per-state JSON output ──────────────────────────────────────────────────


def _zcta_id_col(df: pd.DataFrame) -> str:
    """Census returns ZCTA in a column literally named with spaces."""
    for c in ("zip code tabulation area", "ZCTA5", "GEO_ID"):
        if c in df.columns:
            return c
    raise KeyError(f"No ZCTA column in {list(df.columns)}")


def build_per_state_values(
    frames: dict[str, pd.DataFrame],
    zcta_to_state: dict[str, str],
) -> dict[str, dict[str, dict[str, Optional[float]]]]:
    """
    Returns ``{state_fips: {zcta: {metric_slug: value}}}``.

    A ZCTA appears in exactly one state file (max-overlap assignment).
    """
    out: dict[str, dict[str, dict[str, Optional[float]]]] = defaultdict(lambda: defaultdict(dict))
    for m in METRICS:
        df = frames.get(m["table"])
        if df is None or df.empty:
            continue
        try:
            zid_col = _zcta_id_col(df)
        except KeyError:
            logger.warning(f"Skipping {m['slug']}: no ZCTA column")
            continue
        for _, row in df.iterrows():
            raw_zid = str(row[zid_col]).strip()
            # GEO_ID looks like "8600000US00601" — keep the trailing 5 digits.
            zid = raw_zid[-5:] if len(raw_zid) >= 5 else raw_zid
            if not zid.isdigit() or len(zid) != 5:
                continue
            state = zcta_to_state.get(zid)
            if not state:
                continue
            v = _parse_stat(row.get(m["estimate_col"]))
            out[state][zid][m["slug"]] = v
    return out


def write_per_state_files(
    per_state: dict[str, dict[str, dict[str, Optional[float]]]],
    *,
    out_dir: Path,
    year: int,
    state_filter: Optional[set[str]] = None,
) -> int:
    """Write ``{out_dir}/{year}/zcta_metrics_{FIPS}.json``. Returns file count."""
    vintage_dir = out_dir / str(year)
    vintage_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for state_fips, zctas in sorted(per_state.items()):
        if state_filter and state_fips not in state_filter:
            continue
        path = vintage_dir / f"zcta_metrics_{state_fips}.json"
        payload = {
            "year": year,
            "state_fips": state_fips,
            "values": dict(sorted(zctas.items())),
        }
        path.write_text(json.dumps(payload, separators=(",", ":")))
        size_kb = path.stat().st_size / 1024
        logger.info(f"  {state_fips}: {len(zctas):>5d} ZCTAs  {size_kb:>6.1f} KB  {path.name}")
        written += 1
    return written


# ── CLI ────────────────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--year", type=int, default=2023,
                   help="ACS5 vintage (default: 2023; ZCTA available 2009+)")
    p.add_argument("--states", default="",
                   help="Comma-separated 2-digit state FIPS to write (default: all states with ZCTAs)")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                   help=f"Output base dir (default: {DEFAULT_OUT_DIR.relative_to(_REPO_ROOT)})")
    p.add_argument("--zcta-county-rel", default=str(DEFAULT_ZCTA_COUNTY_REL),
                   help="Census ZCTA→County relationship file")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch ZCTA ACS parquets even when cached")
    args = p.parse_args(argv)

    state_filter: Optional[set[str]] = None
    if args.states.strip():
        state_filter = {s.strip().zfill(2) for s in args.states.split(",") if s.strip()}

    logger.info(f"Building ZCTA→state assignment from {args.zcta_county_rel}")
    zcta_to_state = build_zcta_state_assignment(Path(args.zcta_county_rel))
    logger.info(f"  {len(zcta_to_state)} ZCTAs assigned across "
                f"{len(set(zcta_to_state.values()))} states")

    logger.info(f"Fetching ACS5 {args.year} ZCTA tables ({len(METRICS)} metrics)")
    frames = asyncio.run(fetch_all_metrics(args.year, args.force))
    if not frames:
        logger.error("No ACS frames fetched — aborting")
        return 1

    per_state = build_per_state_values(frames, zcta_to_state)
    logger.info(f"Built values for {len(per_state)} states")

    written = write_per_state_files(
        per_state,
        out_dir=Path(args.out_dir),
        year=args.year,
        state_filter=state_filter,
    )
    logger.info(f"Wrote {written} state file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
