#!/usr/bin/env python3
"""
National Association of Counties (NACo) Scraper

Downloads and caches county data from NACo County Explorer (ce.naco.org only).

County catalog: embedded ``county_info`` in https://ce.naco.org/app/data/general.js (FIPS, name, state).

County Explorer profiles (County Seat, GDP, contact HTML, etc.): fetched via
https://ce.naco.org/get/county?fips=##### — same payload as ``county_explorer_url``
(https://ce.naco.org/?county_info=#####) — merged into each county JSON by default.

Run ``load_naco_to_bronze.py`` afterward → ``bronze.bronze_jurisdictions_counties_naco``.

Data Source: https://ce.naco.org/
Organization: National Association of Counties

Fields collected:
- Registry row + merged ``naco_get_county`` from ``/get/county`` (unless ``--skip-profiles``)

Usage:
    # Prefer project venv (has httpx, loguru from requirements.txt):
    ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py
    python3 scripts/datasources/naco/scrape_naco_counties.py --states AL,GA,MA
    python3 scripts/datasources/naco/scrape_naco_counties.py --force
    python3 scripts/datasources/naco/scrape_naco_counties.py --limit 10
    ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py --skip-profiles   # registry only
    ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py --incremental     # only missing/stale profiles
    ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py --incremental --profile-max-age-days 30
"""
import os
import sys
import asyncio
import argparse
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VENV_REEXEC = "_OPEN_NAVIGATOR_NACO_VENV_REEXEC"


def _in_project_venv() -> bool:
    """True when this process is already using repo .venv or .venv-dbt (by sys.prefix)."""
    px = Path(sys.prefix).resolve()
    return px in {
        (_ROOT / ".venv").resolve(),
        (_ROOT / ".venv-dbt").resolve(),
    }


def _maybe_reexec_with_project_venv() -> None:
    """If deps are missing, restart once via .venv/bin/python so site-packages is used (even if it symlinks to system python)."""
    if os.environ.get(_VENV_REEXEC) == "1":
        return
    if _in_project_venv():
        return
    for name in (".venv", ".venv-dbt"):
        vpy = _ROOT / name / "bin" / "python"
        if vpy.is_file():
            os.environ[_VENV_REEXEC] = "1"
            os.execv(str(vpy), [str(vpy)] + sys.argv)


try:
    import httpx
    from loguru import logger
except ImportError:
    _maybe_reexec_with_project_venv()
    hints = [
        "NACo scraper needs packages from the repo (httpx, loguru).",
        "Install dependencies, then retry:",
        f"  cd {_ROOT}",
        "  ./.venv/bin/pip install -r requirements.txt",
        "  ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py   # add your flags, e.g. --states AL,GA,MA",
    ]
    print("\n".join(hints), file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(_ROOT))


NACO_BASE_URL = "https://ce.naco.org"
# Embedded county listing (FIPS → name, state) shipped by County Explorer
NACO_GENERAL_JS_URL = f"{NACO_BASE_URL}/app/data/general.js"
# County profile JSON (equivalent to ?county_info=FIPS)
NACO_COUNTY_DATA_URL = f"{NACO_BASE_URL}/get/county"

CACHE_DIR = Path("data/cache/naco")

# county_info = {"01001":["Autauga County", "AL", pop, flag], ...} in general.js
_COUNTY_REGISTRY_ENTRY = re.compile(
    r'"(?P<fips>\d{5})"\s*:\s*\["(?P<name>[^"]+)"\s*,\s*"(?P<st>[A-Z]{2})"'
)

ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]
DEFAULT_STATES = ["AL", "GA", "IN", "MA", "WA", "WI"]

NACO_HEADERS = {
    "User-Agent": "OpenNavigator/1.0 (Civic Research; https://github.com/getcommunityone/open-navigator)",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://ce.naco.org/",
}

# Pace HTTP GET /get/county calls (be polite to ce.naco.org)
PROFILE_FETCH_DELAY_SEC = 0.35


def _parse_naco_county_registry_from_general_js(js_text: str) -> list[tuple[str, str, str]]:
    """
    Parse ``county_info`` object from NACo general.js → (fips5, county_name, state_code).

    Drops synthetic state rows (FIPS ending in 000, e.g. ``01000`` = Alabama statewide).
    """
    out: list[tuple[str, str, str]] = []
    for m in _COUNTY_REGISTRY_ENTRY.finditer(js_text):
        fips, name, st = m.group("fips"), m.group("name"), m.group("st")
        if fips.endswith("000"):
            continue
        out.append((fips, name, st))
    return out


def merge_get_county_response_into_record(
    county: dict[str, Any], api_resp: dict[str, Any] | None
) -> None:
    """Attach ``/get/county`` JSON to county dict; flatten common keys for bronze loaders."""
    county.pop("naco_get_county", None)
    county.pop("naco_profile_error", None)
    if not api_resp:
        county["naco_profile_fetched"] = False
        return
    county["naco_get_county"] = api_resp
    if not api_resp.get("found"):
        county["naco_profile_fetched"] = False
        return
    county["naco_profile_fetched"] = True
    inner = api_resp.get("county")
    if not isinstance(inner, dict):
        return
    seat = str(inner.get("County_Seat") or "").strip()
    if seat:
        county["county_seat"] = seat
    web = str(inner.get("County_Website") or "").strip()
    if web:
        county["website"] = web
    # Display-formatted strings from County Explorer (also parsed numerically where safe)
    pl = str(inner.get("Population_Level") or "").strip().replace(",", "")
    digits_pop = "".join(c for c in pl if c.isdigit())
    if digits_pop:
        try:
            county["population"] = int(digits_pop)
        except ValueError:
            county["population_display"] = str(inner.get("Population_Level") or "").strip()
    land = str(inner.get("Land_Area") or "").strip().replace(",", "")
    land_digits = "".join(c for c in land if c in ".0123456789")
    if land_digits:
        try:
            county["area_sq_miles"] = float(land_digits)
        except ValueError:
            county["land_area_display"] = str(inner.get("Land_Area") or "").strip()
    yo = str(inner.get("Year_Founded") or "").strip()
    if yo:
        county["year_organized"] = yo
    fa = inner.get("Full_Address")
    if fa is not None and str(fa).strip():
        county["full_address_html"] = str(fa).strip()


_PROFILE_CACHE_KEYS = (
    "naco_get_county",
    "naco_profile_fetched",
    "profile_fetched_at",
    "county_seat",
    "website",
    "population",
    "area_sq_miles",
    "year_organized",
    "full_address_html",
    "population_display",
    "land_area_display",
)


def stamp_profile_fetched_utc(county: dict[str, Any]) -> None:
    if county.get("naco_profile_fetched"):
        county["profile_fetched_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )


def profile_needs_refresh(county: dict[str, Any], max_age_days: float | None) -> bool:
    """True if county has no usable merged profile, no harvest stamp, or age exceeds ``max_age_days``."""
    if not county.get("naco_profile_fetched"):
        return True
    pkg = county.get("naco_get_county")
    if not isinstance(pkg, dict) or not pkg.get("found"):
        return True
    ts = county.get("profile_fetched_at")
    if ts is None or str(ts).strip() == "":
        return True
    if max_age_days is None:
        return False
    try:
        cleaned = str(ts).strip().replace("Z", "+00:00")
        fetched_dt = datetime.fromisoformat(cleaned)
        if fetched_dt.tzinfo is None:
            fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - fetched_dt
        return age > timedelta(days=max_age_days)
    except (TypeError, ValueError):
        return True


def copy_cached_profile(dst: dict[str, Any], src: dict[str, Any]) -> None:
    """Copy merged profile fields from a prior county row (same FIPS)."""
    for k in _PROFILE_CACHE_KEYS:
        if k in src:
            dst[k] = copy.deepcopy(src[k])


def load_previous_counties_by_fips(cache_path: Path) -> dict[str, dict[str, Any]]:
    """Index existing cache file by 5-digit FIPS for incremental reuse."""
    if not cache_path.is_file():
        return {}
    try:
        rows = json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        f = str(row.get("fips") or "").strip()
        if len(f) == 5:
            out[f] = row
    return out


class NACoScraper:
    """Download county data from the NACo County Explorer."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client: httpx.AsyncClient | None = None
        self._county_registry: list[tuple[str, str, str]] | None = None

    async def _ensure_county_registry(self) -> None:
        if self._county_registry is not None:
            return
        assert self.client is not None
        logger.info(f"Loading NACo county registry from {NACO_GENERAL_JS_URL}…")
        response = await self.client.get(NACO_GENERAL_JS_URL)
        response.raise_for_status()
        self._county_registry = _parse_naco_county_registry_from_general_js(response.text)
        logger.info(f"Parsed {len(self._county_registry):,} counties from NACo county_info registry")

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers=NACO_HEADERS,
        )
        return self

    async def __aexit__(self, *_):
        if self.client:
            await self.client.aclose()

    def _county_cache_path(self, state_code: str, date_str: str) -> Path:
        return self.cache_dir / f"naco_counties_{state_code}_{date_str}.json"

    def _officials_cache_path(self, county_id: str, date_str: str) -> Path:
        return self.cache_dir / "officials" / f"naco_officials_{county_id}_{date_str}.json"

    @staticmethod
    def _normalize_fips(county_id: str) -> str:
        """Keep 5-digit county FIPS (digits only)."""
        digits = "".join(c for c in str(county_id) if c.isdigit())
        if not digits:
            return ""
        return digits[-5:].zfill(5)

    async def _fetch_county_profile_raw(self, fips: str) -> dict[str, Any] | None:
        """GET https://ce.naco.org/get/county?fips=… ; returns decoded JSON or None on failure."""
        assert self.client is not None
        try:
            url = f"{NACO_COUNTY_DATA_URL}?fips={fips}"
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning(f"[{fips}] /get/county failed: {exc}")
            return None

    async def _apply_county_profiles(
        self,
        state_code: str,
        counties: list[dict[str, Any]],
        *,
        fetch_profiles: bool,
        incremental: bool,
        profile_max_age_days: float | None,
        profile_delay_sec: float,
        previous_by_fips: dict[str, dict[str, Any]],
        loaded_from_cache_file: bool,
    ) -> None:
        if not fetch_profiles or not counties:
            return

        row_total = len(counties)
        rows_with_fips = sum(
            1 for c in counties if len(str(c.get("fips") or "").strip()) == 5
        )
        logger.info(
            f"[{state_code}] Profile downloads: {rows_with_fips} counties with FIPS, "
            f"{profile_delay_sec}s spacing between each /get/county — "
            f"first log line appears after the first response (~network latency + DNS)."
        )

        reused = 0
        fetched = 0
        skipped_fresh = 0
        http_calls = 0

        for i, county in enumerate(counties):
            fips = str(county.get("fips") or "").strip()
            if len(fips) != 5:
                continue

            if loaded_from_cache_file:
                if incremental and not profile_needs_refresh(county, profile_max_age_days):
                    skipped_fresh += 1
                    continue

            else:
                if incremental:
                    prev = previous_by_fips.get(fips)
                    if prev is not None and not profile_needs_refresh(
                        prev, profile_max_age_days
                    ):
                        copy_cached_profile(county, prev)
                        reused += 1
                        continue

            resp = await self._fetch_county_profile_raw(fips)
            http_calls += 1
            if http_calls == 1:
                logger.info(
                    f"[{state_code}] First /get/county returned for FIPS {fips} — "
                    "run is progressing (quiet stretches are normal)."
                )

            merge_get_county_response_into_record(county, resp)
            stamp_profile_fetched_utc(county)
            if county.get("naco_profile_fetched"):
                fetched += 1

            if profile_delay_sec > 0:
                await asyncio.sleep(profile_delay_sec)

            if http_calls % 10 == 0:
                logger.info(
                    f"[{state_code}] /get/county HTTP ×{http_calls} "
                    f"(merged ok≈{fetched}, reused={reused}, skipped fresh={skipped_fresh}, "
                    f"rows scanned {i + 1}/{row_total})"
                )

        mode = "incremental" if incremental else "full"
        logger.success(
            f"[{state_code}] Profiles ({mode}): HTTP merged={fetched}, "
            f"reused cache={reused}, skipped (still fresh)={skipped_fresh}"
        )

    async def fetch_counties_for_state(
        self,
        state_code: str,
        date_str: str,
        force: bool = False,
        *,
        fetch_profiles: bool = True,
        incremental: bool = False,
        profile_max_age_days: float | None = None,
        profile_delay_sec: float = PROFILE_FETCH_DELAY_SEC,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build county list for a state from NACo's embedded county_info (general.js).

        When ``fetch_profiles`` is True (default), GET ``/get/county`` and merge.

        ``incremental``: reuse existing merged profiles when still fresh (same-day cache file
        or prior file when ``force`` rebuilding). Use ``profile_max_age_days`` to refetch after N days;
        omit it to only fill missing profiles.
        """
        cache_path = self._county_cache_path(state_code, date_str)

        if cache_path.exists() and not force:
            logger.info(f"[{state_code}] Loading cached county list: {cache_path.name}")
            counties = json.loads(cache_path.read_text())
            if limit is not None:
                counties = counties[: max(0, limit)]

            if fetch_profiles and incremental:
                logger.info(
                    f"[{state_code}] Incremental profile refresh "
                    f"(max_age_days={profile_max_age_days})…"
                )
                await self._apply_county_profiles(
                    state_code,
                    counties,
                    fetch_profiles=True,
                    incremental=True,
                    profile_max_age_days=profile_max_age_days,
                    profile_delay_sec=profile_delay_sec,
                    previous_by_fips={},
                    loaded_from_cache_file=True,
                )
                cache_path.write_text(json.dumps(counties, indent=2, default=str))
            elif fetch_profiles and not incremental:
                logger.info(
                    f"[{state_code}] Using cache as-is (omit --incremental to refresh stale profiles)"
                )

            if counties:
                logger.success(f"[{state_code}] {len(counties)} counties → {cache_path.name}")
            return counties

        previous_by_fips: dict[str, dict[str, Any]] = {}
        if incremental and fetch_profiles:
            previous_by_fips = load_previous_counties_by_fips(cache_path)

        logger.info(f"[{state_code}] Building county list from NACo county_info registry…")

        counties = []

        try:
            await self._ensure_county_registry()
            assert self._county_registry is not None
            st = state_code.strip().upper()
            for fips, name, r_st in self._county_registry:
                if r_st != st:
                    continue
                counties.append(
                    {
                        "name": name,
                        "state": st,
                        "fips": fips,
                        "id": fips,
                        "naco_id": fips,
                        "county_explorer_url": f"{NACO_BASE_URL}/?county_info={fips}",
                    }
                )
        except httpx.HTTPError as exc:
            logger.error(f"[{state_code}] Failed to load NACo registry: {exc}")
        except Exception as exc:
            logger.error(f"[{state_code}] NACo registry error: {exc}")

        if limit is not None:
            counties = counties[: max(0, limit)]

        if fetch_profiles and counties:
            logger.info(
                f"[{state_code}] County Explorer profiles "
                f"({'incremental' if incremental else 'full'}, "
                f"max_age_days={profile_max_age_days})…"
            )
            await self._apply_county_profiles(
                state_code,
                counties,
                fetch_profiles=True,
                incremental=incremental,
                profile_max_age_days=profile_max_age_days,
                profile_delay_sec=profile_delay_sec,
                previous_by_fips=previous_by_fips,
                loaded_from_cache_file=False,
            )

        cache_path.write_text(json.dumps(counties, indent=2, default=str))
        if counties:
            logger.success(f"[{state_code}] Cached {len(counties)} counties → {cache_path.name}")
        else:
            logger.warning(f"[{state_code}] Cached 0 counties → {cache_path.name}")
        return counties

    async def fetch_county_details(
        self,
        county_id: str,
        date_str: str,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """
        Fetch county profile from NACo ``/get/county?fips=`` (same payload as ``?county_info=``).

        Saves raw JSON to cache; returns the object or None if not found.
        """
        officials_dir = self.cache_dir / "officials"
        officials_dir.mkdir(exist_ok=True)
        fips = self._normalize_fips(county_id)
        if len(fips) != 5:
            logger.error(f"Invalid county id (need 5-digit FIPS): {county_id!r}")
            return None
        cache_path = self._officials_cache_path(fips, date_str)

        if cache_path.exists() and not force:
            logger.debug(f"Using cached profile for county FIPS {fips}")
            return json.loads(cache_path.read_text())

        details = await self._fetch_county_profile_raw(fips)
        if not details:
            return None
        if not details.get("found"):
            logger.warning(f"No NACo profile for FIPS {fips} (found=false)")
            return None
        cache_path.write_text(json.dumps(details, indent=2, default=str))
        return details


async def main(
    states: str | None = None,
    force: bool = False,
    limit: int | None = None,
    details: bool = False,
    fetch_profiles: bool = True,
    incremental: bool = False,
    profile_max_age_days: float | None = None,
    profile_delay_sec: float = PROFILE_FETCH_DELAY_SEC,
):
    """
    Download NACo county data and save to cache.

    Args:
        states: Comma-separated state codes (e.g., "AL,GA,MA"). Defaults to dev states.
        force: Re-download even if cache exists.
        limit: Cap on counties fetched per state (for testing).
        details: Also write raw ``/get/county`` JSON under ``officials/naco_officials_{fips}_*.json``
            (legacy mirror; profile data is already merged into county JSON unless ``--skip-profiles``).
        fetch_profiles: Fetch ``/get/county`` for each county and merge (default True).
        incremental: Reuse cached profiles when still fresh; only HTTP for gaps/stale rows.
        profile_max_age_days: With incremental, refetch when older than this many days (optional).
        profile_delay_sec: Sleep between profile requests.
    """
    logger.info("=" * 70)
    logger.info("NACo County Explorer → data/cache/naco/")
    logger.info("=" * 70)

    state_list = (
        [s.strip().upper() for s in states.split(",")]
        if states
        else DEFAULT_STATES
    )
    logger.info(f"States: {', '.join(state_list)}")

    date_str = datetime.now().strftime("%Y%m%d")
    summary_path = CACHE_DIR / f"naco_summary_{date_str}.json"

    total_counties = 0
    summary: list[dict[str, Any]] = []

    async with NACoScraper() as scraper:
        for state_code in state_list:
            counties = await scraper.fetch_counties_for_state(
                state_code,
                date_str,
                force=force,
                fetch_profiles=fetch_profiles,
                incremental=incremental,
                profile_max_age_days=profile_max_age_days,
                profile_delay_sec=profile_delay_sec,
                limit=limit,
            )

            total_counties += len(counties)
            summary.append({"state": state_code, "county_count": len(counties)})

            if details:
                for county in counties:
                    county_id = county.get("id") or county.get("fips") or county.get("geoid")
                    if county_id:
                        await scraper.fetch_county_details(str(county_id), date_str, force=force)
                        await asyncio.sleep(profile_delay_sec)

            await asyncio.sleep(1)

    summary_path.write_text(json.dumps({"date": date_str, "states": summary}, indent=2))

    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"States processed : {len(state_list)}")
    logger.info(f"Counties fetched : {total_counties}")
    logger.info(f"Cache directory  : {CACHE_DIR}")
    logger.info(f"Summary file     : {summary_path}")
    if total_counties == 0:
        logger.warning(
            "No counties from NACo — fix the scraper against ce.naco.org before load_naco_to_bronze.py."
        )
    else:
        logger.success("Done. Run load_naco_to_bronze.py to load into Postgres.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download NACo county data to cache")
    parser.add_argument(
        "--states",
        type=str,
        help="Comma-separated state codes (e.g., AL,GA,MA). Default: dev states.",
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Download all 50 states.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if today's cache exists.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit counties per state (for testing).",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Mirror raw /get/county JSON per FIPS under data/cache/naco/officials/ (legacy).",
    )
    parser.add_argument(
        "--skip-profiles",
        action="store_true",
        help="Only write registry rows from general.js (no /get/county merge).",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Reuse merged profiles when fresh; fetch only missing/stale /get/county rows.",
    )
    parser.add_argument(
        "--profile-max-age-days",
        type=float,
        default=None,
        metavar="DAYS",
        help="With --incremental, refetch profiles older than this many days (default: only missing/stale stamp).",
    )
    parser.add_argument(
        "--profile-delay",
        type=float,
        default=PROFILE_FETCH_DELAY_SEC,
        metavar="SEC",
        help=f"Seconds between /get/county calls (default {PROFILE_FETCH_DELAY_SEC}).",
    )
    args = parser.parse_args()

    states_arg = ",".join(ALL_STATES) if args.all_states else args.states

    asyncio.run(
        main(
            states=states_arg,
            force=args.force,
            limit=args.limit,
            details=args.details,
            fetch_profiles=not args.skip_profiles,
            incremental=args.incremental,
            profile_max_age_days=args.profile_max_age_days,
            profile_delay_sec=max(0.0, args.profile_delay),
        )
    )
