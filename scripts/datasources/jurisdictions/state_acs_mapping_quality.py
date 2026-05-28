"""
State-level ACS (Census downloads) + mapping-quality rollups for the jurisdiction dashboard.

Population tiers use official ACS 5-year state total population (B01003). Income tiers use
state median household income (B19013). Mapping counts come from ``jurisdiction_mapping_analysis`` rows with
``jurisdiction_type = 'state'`` (one state government per ``state_code``) — not summed
from cities, counties, or districts in that state.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# USPS code, name, Census state FIPS (2-digit)
US_STATES: tuple[tuple[str, str, str], ...] = (
    ("AL", "Alabama", "01"),
    ("AK", "Alaska", "02"),
    ("AZ", "Arizona", "04"),
    ("AR", "Arkansas", "05"),
    ("CA", "California", "06"),
    ("CO", "Colorado", "08"),
    ("CT", "Connecticut", "09"),
    ("DE", "Delaware", "10"),
    ("DC", "District of Columbia", "11"),
    ("FL", "Florida", "12"),
    ("GA", "Georgia", "13"),
    ("HI", "Hawaii", "15"),
    ("ID", "Idaho", "16"),
    ("IL", "Illinois", "17"),
    ("IN", "Indiana", "18"),
    ("IA", "Iowa", "19"),
    ("KS", "Kansas", "20"),
    ("KY", "Kentucky", "21"),
    ("LA", "Louisiana", "22"),
    ("ME", "Maine", "23"),
    ("MD", "Maryland", "24"),
    ("MA", "Massachusetts", "25"),
    ("MI", "Michigan", "26"),
    ("MN", "Minnesota", "27"),
    ("MS", "Mississippi", "28"),
    ("MO", "Missouri", "29"),
    ("MT", "Montana", "30"),
    ("NE", "Nebraska", "31"),
    ("NV", "Nevada", "32"),
    ("NH", "New Hampshire", "33"),
    ("NJ", "New Jersey", "34"),
    ("NM", "New Mexico", "35"),
    ("NY", "New York", "36"),
    ("NC", "North Carolina", "37"),
    ("ND", "North Dakota", "38"),
    ("OH", "Ohio", "39"),
    ("OK", "Oklahoma", "40"),
    ("OR", "Oregon", "41"),
    ("PA", "Pennsylvania", "42"),
    ("PR", "Puerto Rico", "72"),
    ("RI", "Rhode Island", "44"),
    ("SC", "South Carolina", "45"),
    ("SD", "South Dakota", "46"),
    ("TN", "Tennessee", "47"),
    ("TX", "Texas", "48"),
    ("UT", "Utah", "49"),
    ("VT", "Vermont", "50"),
    ("VA", "Virginia", "51"),
    ("WA", "Washington", "53"),
    ("WV", "West Virginia", "54"),
    ("WI", "Wisconsin", "55"),
    ("WY", "Wyoming", "56"),
)

FIPS_TO_STATE: dict[str, str] = {fips: code for code, _name, fips in US_STATES}
STATE_TO_FIPS: dict[str, str] = {code: fips for code, _name, fips in US_STATES}

STATE_POPULATION_TIER_ORDER: tuple[str, ...] = (
    "Very Large",
    "Large",
    "Major Mid-Sized",
    "Mid-Sized",
    "Small",
)

STATE_INCOME_TIER_ORDER: tuple[str, ...] = (
    "High Earner",
    "Middle Class",
    "Lower Middle",
    "Low Income",
)


def state_population_tier(population: int | float | None) -> str | None:
    """Bucket state total population (ACS B01003)."""
    if population is None:
        return None
    p = int(population)
    if p > 20_000_000:
        return "Very Large"
    if p > 10_000_000:
        return "Large"
    if p > 5_000_000:
        return "Major Mid-Sized"
    if p > 2_000_000:
        return "Mid-Sized"
    return "Small"


def state_income_tier(median_household_income: int | float | None) -> str | None:
    """Bucket state median household income (ACS B19013)."""
    if median_household_income is None:
        return None
    v = float(median_household_income)
    if v >= 72_000:
        return "High Earner"
    if v >= 60_000:
        return "Middle Class"
    if v >= 50_000:
        return "Lower Middle"
    return "Low Income"


def _parse_stat(raw: Any) -> Optional[float]:
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


def _read_parquet(acs_dir: Path, table: str, geography: str, state_key: str, year: int) -> Optional[pd.DataFrame]:
    path = acs_dir / f"{table}_{geography}_{state_key}_{year}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def discover_state_acs_year(acs_dir: Path) -> int:
    years: set[int] = set()
    for p in acs_dir.glob("B01003_state_*_*.parquet"):
        m = re.search(r"_(\d{4})\.parquet$", p.name)
        if m:
            years.add(int(m.group(1)))
    if years:
        return max(years)
    return int(os.environ.get("JURIS_MAPPING_QUALITY_ACS_YEAR", "2022"))


def _merge_state_df_into_metrics(
    out: dict[str, dict[str, Optional[float]]],
    df: pd.DataFrame,
    *,
    value_col: str,
    value_key: str,
) -> None:
    if df is None or df.empty or "state" not in df.columns:
        return
    if value_col not in df.columns:
        return
    for _, row in df.iterrows():
        st = str(int(row["state"])).zfill(2)
        block = out.setdefault(st, {})
        block[value_key] = _parse_stat(row.get(value_col))
        if "NAME" in df.columns:
            nm = row.get("NAME")
            if isinstance(nm, str) and nm.strip():
                block["NAME"] = nm.strip()


def load_state_acs_metrics(acs_dir: Path, year: int) -> dict[str, dict[str, Optional[float]]]:
    """``state_fips`` → ``{ population, median_household_income, NAME }`` from state geography parquets."""
    out: dict[str, dict[str, Optional[float]]] = {}
    pop_df = _read_parquet(acs_dir, "B01003", "state", "*", year)
    if pop_df is not None:
        _merge_state_df_into_metrics(out, pop_df, value_col="B01003_001E", value_key="population")
    inc_df = _read_parquet(acs_dir, "B19013", "state", "*", year)
    if inc_df is not None:
        _merge_state_df_into_metrics(out, inc_df, value_col="B19013_001E", value_key="median_household_income")
    return out


def _cache_state_parquet(acs_dir: Path, table: str, df: pd.DataFrame, year: int) -> None:
    acs_dir.mkdir(parents=True, exist_ok=True)
    path = acs_dir / f"{table}_state_*_{year}.parquet"
    df.to_parquet(path, index=False)


async def _fetch_state_acs_metrics_api(acs_dir: Path, year: int, cache_parquets: bool) -> dict[str, dict[str, Optional[float]]]:
    """Pull B01003 + B19013 for ``for=state:*`` from the Census API when parquets are absent."""
    from ingestion.census.acs import ACSDataIngestion

    acs = ACSDataIngestion(data_dir=acs_dir)
    out: dict[str, dict[str, Optional[float]]] = {}
    pop_df = await acs.download_acs_data_api("B01003", "state", "*", year=year)
    _merge_state_df_into_metrics(out, pop_df, value_col="B01003_001E", value_key="population")
    if cache_parquets and not pop_df.empty:
        _cache_state_parquet(acs_dir, "B01003", pop_df, year)
    inc_df = await acs.download_acs_data_api("B19013", "state", "*", year=year)
    _merge_state_df_into_metrics(out, inc_df, value_col="B19013_001E", value_key="median_household_income")
    if cache_parquets and not inc_df.empty:
        _cache_state_parquet(acs_dir, "B19013", inc_df, year)
    return out


def load_state_acs_metrics_with_fallback(acs_dir: Path, year: int) -> tuple[dict[str, dict[str, Optional[float]]], str]:
    """Parquets first; optional Census API when ``JURIS_MAPPING_QUALITY_FETCH_STATE_ACS=1`` (default on)."""
    metrics = load_state_acs_metrics(acs_dir, year) if acs_dir.is_dir() else {}
    has_pop = any(v.get("population") is not None for v in metrics.values())
    if has_pop:
        return metrics, (
            f"ACS 5-year state geography parquets under {acs_dir} "
            f"(B01003 / B19013 for vintage {year})"
        )

    fetch = os.environ.get("JURIS_MAPPING_QUALITY_FETCH_STATE_ACS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    if not fetch:
        return metrics, f"No state ACS parquets under {acs_dir}; API fetch disabled."

    try:
        api_metrics = asyncio.run(_fetch_state_acs_metrics_api(acs_dir, year, cache_parquets=True))
    except Exception as exc:  # noqa: BLE001 — export should still write mapping-only JSON
        hint = (
            " Set CENSUS_API_KEY in .env (free: https://api.census.gov/data/key_signup.html) "
            "or run: download_census_acs_data.py --geography state --state '*'"
        )
        return metrics, f"State ACS parquets missing; Census API fetch failed: {exc}.{hint}"

    if any(v.get("population") is not None for v in api_metrics.values()):
        return api_metrics, (
            f"ACS 5-year state estimates via Census API (vintage {year}), cached under {acs_dir}"
        )
    return metrics, f"No state ACS data from parquets or API for vintage {year}."


def _aggregate_mapping_by_bucket(
    states: list[dict[str, Any]],
    tier_field: str,
    tier_order: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Count state governments (with / without a primary portal) in each ACS state tier."""
    buckets: dict[str, dict[str, int | float | None]] = {}
    for st in states:
        tier = st.get(tier_field)
        if not tier:
            continue
        b = buckets.setdefault(
            str(tier),
            {"total_jurisdictions": 0, "with_primary_website": 0},
        )
        b["total_jurisdictions"] = int(b["total_jurisdictions"]) + int(st.get("total_jurisdictions") or 0)
        b["with_primary_website"] = int(b["with_primary_website"]) + int(st.get("with_primary_website") or 0)

    rows: list[dict[str, Any]] = []
    for tier in tier_order:
        if tier not in buckets:
            continue
        b = buckets[tier]
        total = int(b["total_jurisdictions"])
        with_url = int(b["with_primary_website"])
        pct = round(100.0 * with_url / total, 1) if total > 0 else None
        rows.append(
            {
                tier_field: tier,
                "state_count": sum(1 for s in states if s.get(tier_field) == tier),
                "total_jurisdictions": total,
                "with_primary_website": with_url,
                "pct_with_primary_website": pct,
            }
        )
    return rows


def build_states_payload(
    mapping_by_state: list[dict[str, Any]],
    acs_dir: Path | None = None,
    acs_year: int | None = None,
) -> dict[str, Any]:
    """
    Merge per-state mapping rollups with ACS state downloads.

    ``mapping_by_state``: rows from ``jurisdiction_type = 'state'`` with ``state_code``,
    ``total_jurisdictions`` (1), ``with_primary_website`` (0 or 1), ``pct_with_primary_website``.
    """
    acs_root = acs_dir or Path(os.environ.get("ACS_DATA_DIR", "data/cache/acs"))
    if not acs_root.is_absolute():
        repo_root = Path(__file__).resolve().parents[3]
        acs_root = repo_root / acs_root

    year = acs_year or discover_state_acs_year(acs_root)
    acs_root.mkdir(parents=True, exist_ok=True)
    acs_by_fips, acs_source_note = load_state_acs_metrics_with_fallback(acs_root, year)

    mapping_index = {str(r["state_code"]).strip().upper(): r for r in mapping_by_state}

    states: list[dict[str, Any]] = []
    for state_code, _name, fips in US_STATES:
        m = mapping_index.get(state_code, {})
        acs = acs_by_fips.get(fips, {})
        pop = acs.get("population")
        inc = acs.get("median_household_income")
        pop_f = int(pop) if pop is not None else None
        inc_f = int(inc) if inc is not None else None
        with_portal = 1 if int(m.get("with_primary_website") or 0) > 0 else 0
        primary_url = m.get("primary_website_url")
        primary_url_s = str(primary_url).strip() if primary_url else None
        if primary_url_s == "":
            primary_url_s = None
        states.append(
            {
                "state_code": state_code,
                "state_fips": fips,
                "state_name": _name,
                "acs_population": pop_f,
                "acs_median_household_income": inc_f,
                "state_population_tier": state_population_tier(pop_f),
                "state_income_level": state_income_tier(inc_f),
                "total_jurisdictions": 1,
                "with_primary_website": with_portal,
                "pct_with_primary_website": 100.0 if with_portal else 0.0,
                "has_state_portal": bool(with_portal),
                "primary_website_url": primary_url_s,
                "primary_website_source": m.get("primary_website_source"),
                "n_website_candidate_rows": int(m.get("n_website_candidate_rows") or 0),
                "has_gsa_source": bool(m.get("has_gsa_source")),
                "has_override_source": bool(m.get("has_override_source")),
                "website_candidates": m.get("website_candidates") or [],
            }
        )

    states.sort(key=lambda r: r["state_code"])

    return {
        "acs_vintage_year": str(year),
        "acs_source": acs_source_note,
        "states": states,
        "summary_by_state_population_tier": _aggregate_mapping_by_bucket(
            states, "state_population_tier", STATE_POPULATION_TIER_ORDER
        ),
        "summary_by_state_income_level": _aggregate_mapping_by_bucket(
            states, "state_income_level", STATE_INCOME_TIER_ORDER
        ),
        "state_population_tiers_explained": {
            "Very Large": "> 20 million (e.g. CA, TX, FL, NY)",
            "Large": "10M – 20M (e.g. PA, IL, OH, GA, NC, MI)",
            "Major Mid-Sized": "5M – 10M",
            "Mid-Sized": "2M – 5M",
            "Small": "< 2M",
        },
        "state_income_levels_explained": {
            "High Earner": "State median household income ≥ $72,000 (ACS B19013)",
            "Middle Class": "$60,000 – $71,999",
            "Lower Middle": "$50,000 – $59,999",
            "Low Income": "< $50,000",
        },
    }
