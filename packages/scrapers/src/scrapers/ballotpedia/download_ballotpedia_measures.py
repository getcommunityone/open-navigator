#!/usr/bin/env python3
"""
Scrape Ballotpedia ballot-measure pages into JSON cache.

Two scopes:
  1. **State** — ``/{State}_ballot_measures`` (optional ``_,_{year}`` suffix).
  2. **Jurisdiction** — ``/{City},_{State}_ballot_measures`` per municipality/county.

Output lands under ``data/cache/ballotpedia/{ST}/{state|municipality}/`` as timestamped
JSON snapshots consumed by ``load_ballotpedia_measures_to_bronze.py``.

By default only **2025** and **2026** election years are scraped (``--years 2025,2026``).

Usage
-----
    python packages/scrapers/src/scrapers/ballotpedia/download_ballotpedia_measures.py \\
        --states AL,GA,IN,MA

    python packages/scrapers/src/scrapers/ballotpedia/download_ballotpedia_measures.py \\
        --states AL --years 2025,2026 --include-jurisdictions --limit-per-state 10

    # Headed browser when headless keeps getting challenged:
    BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE=headed \\
        python packages/scrapers/src/scrapers/ballotpedia/download_ballotpedia_measures.py --states AL
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from scrapers.ballotpedia.ballotpedia_integration import BallotpediaDiscovery

CACHE_DIR = _ROOT / "data" / "cache" / "ballotpedia"
DEFAULT_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")
DEFAULT_ELECTION_YEARS = ("2025", "2026")


def _parse_years(raw: str | None, *, legacy_year: int | None = None) -> tuple[str, ...]:
    if legacy_year is not None:
        return (str(legacy_year),)
    if not raw or not raw.strip():
        return DEFAULT_ELECTION_YEARS
    years = tuple(y.strip() for y in raw.split(",") if y.strip())
    if not years:
        return DEFAULT_ELECTION_YEARS
    for y in years:
        if len(y) != 4 or not y.isdigit():
            raise SystemExit(f"Invalid election year {y!r} — use four-digit strings like 2025")
    return years


def _measure_matches_years(measure: dict[str, Any], years: tuple[str, ...]) -> bool:
    """True when measure year (field or title) falls in ``years``."""
    year_val = measure.get("year") or measure.get("election_year")
    if year_val:
        m = re.search(r"\b(20\d{2})\b", str(year_val))
        if m and m.group(1) in years:
            return True
    title = measure.get("measure_title") or measure.get("measure_name") or ""
    for y in years:
        if y in title:
            return True
    return False


def _connect():
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
    url = (
        os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
    )
    if not url:
        return None
    return psycopg2.connect(url)


def _load_jurisdiction_targets(
    conn,
    states: tuple[str, ...],
    include_types: tuple[str, ...],
    limit_per_state: int | None,
    jurisdiction_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    state_ph = ",".join(["%s"] * len(states))
    type_ph = ",".join(["%s"] * len(include_types))
    jur_filter = ""
    params: list[Any] = list(states) + list(include_types)
    if jurisdiction_ids:
        jur_ph = ",".join(["%s"] * len(jurisdiction_ids))
        jur_filter = f"AND j.jurisdiction_id IN ({jur_ph})"
        params.extend(jurisdiction_ids)

    sql = f"""
        WITH ranked AS (
            SELECT
                j.jurisdiction_id,
                j.state_code,
                j.jurisdiction_type,
                COALESCE(NULLIF(BTRIM(j.name), ''), j.jurisdiction_id) AS name
            FROM intermediate.int_jurisdictions j
            WHERE j.state_code IN ({state_ph})
              AND j.jurisdiction_type IN ({type_ph})
              {jur_filter}
        ),
        numbered AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY state_code
                       ORDER BY CASE jurisdiction_type
                           WHEN 'municipality' THEN 0
                           WHEN 'county' THEN 1
                           ELSE 2
                       END,
                       jurisdiction_id
                   ) AS rn
            FROM ranked
        )
        SELECT jurisdiction_id, state_code, jurisdiction_type, name
        FROM numbered
        WHERE (%s IS NULL OR rn <= %s)
        ORDER BY state_code, rn
    """
    params.extend([limit_per_state, limit_per_state])
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [
            {
                "jurisdiction_id": row[0],
                "state_code": row[1],
                "jurisdiction_type": row[2],
                "name": row[3],
            }
            for row in cur.fetchall()
        ]


async def _scrape_state_measures(
    discovery: BallotpediaDiscovery,
    *,
    state_code: str,
    year: str | None,
) -> tuple[int, Path | None]:
    state_name = BallotpediaDiscovery.STATE_NAME_BY_CODE.get(state_code.upper(), state_code)
    year_int = int(year) if year else None
    source_url = BallotpediaDiscovery.build_state_ballot_measures_url(state_name, year_int)
    measures = await discovery.get_ballot_measures(state_name, year=year_int)
    path = discovery.save_measures_snapshot(
        measures,
        state_code=state_code,
        scope="state",
        election_year=year,
        source_url=source_url,
    )
    if not measures:
        logger.warning("No state measures for {} ({}) — wrote empty cache {}", state_code, year, path)
    return len(measures), path


async def _scrape_jurisdiction_measures(
    discovery: BallotpediaDiscovery,
    target: dict[str, Any],
    *,
    years: tuple[str, ...],
) -> tuple[int, Path | None]:
    state_code = target["state_code"]
    name = target["name"]
    source_url = BallotpediaDiscovery.build_jurisdiction_ballot_measures_url(name, state_code)
    measures = await discovery.get_jurisdiction_ballot_measures(name, state_code)
    measures = [m for m in measures if _measure_matches_years(m, years)]
    path = discovery.save_measures_snapshot(
        measures,
        state_code=state_code,
        scope="jurisdiction",
        jurisdiction_id=target["jurisdiction_id"],
        jurisdiction_name=name,
        jurisdiction_type=target.get("jurisdiction_type"),
        election_year=",".join(years),
        source_url=source_url,
    )
    if not measures:
        return 0, path
    return len(measures), path


async def _preflight_playwright() -> None:
    """Fail fast with a helpful message when Chromium is not installed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "playwright is not installed. Run: ./.venv/bin/pip install playwright && "
            "./.venv/bin/playwright install chromium"
        )
        raise SystemExit(2)
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        await browser.close()
        await pw.stop()
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            logger.error(
                "Chromium browser binaries missing. Run: ./.venv/bin/playwright install chromium"
            )
            raise SystemExit(2) from exc
        logger.warning("Playwright preflight warning (continuing): {}", exc)


async def run(args: argparse.Namespace) -> int:
    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    if not states:
        raise SystemExit("--states must list at least one state code")

    years = _parse_years(args.years, legacy_year=args.year)
    if not args.skip_playwright_check:
        await _preflight_playwright()
    discovery = BallotpediaDiscovery(cache_dir=str(CACHE_DIR))

    total_measures = 0
    total_files = 0
    failures = 0

    logger.info("=" * 70)
    logger.info("Ballotpedia ballot measures → {}", CACHE_DIR)
    logger.info(
        "States: {} | years={} | jurisdictions={}",
        ", ".join(states),
        ", ".join(years),
        args.include_jurisdictions,
    )
    logger.info("=" * 70)

    for i, state_code in enumerate(states):
        if i > 0 and discovery.state_scrape_delay > 0:
            logger.info(
                "Waiting {:.0f}s before next state (BALLOTPEDIA_STATE_DELAY)",
                discovery.state_scrape_delay,
            )
            await asyncio.sleep(discovery.state_scrape_delay)
        for year in years:
            try:
                n, path = await _scrape_state_measures(discovery, state_code=state_code, year=year)
                total_measures += n
                if path:
                    total_files += 1
                logger.info("State {} / {}: {} measure(s)", state_code, year, n)
            except Exception as exc:
                failures += 1
                logger.error("State scrape failed for {} / {}: {}", state_code, year, exc)

    if args.include_jurisdictions:
        conn = _connect()
        if conn is None:
            logger.warning("No database URL — skipping jurisdiction scrapes (set NEON_DATABASE_URL_DEV)")
        else:
            try:
                include_types = tuple(
                    t.strip().lower() for t in args.include_types.split(",") if t.strip()
                )
                jurisdiction_ids = tuple(
                    j.strip() for j in args.jurisdiction_ids.split(",") if j.strip()
                )
                targets = _load_jurisdiction_targets(
                    conn,
                    states,
                    include_types,
                    args.limit_per_state,
                    jurisdiction_ids,
                )
                logger.info("Loaded {} jurisdiction target(s) for local ballot-measure pages", len(targets))
                for target in targets:
                    try:
                        n, path = await _scrape_jurisdiction_measures(
                            discovery, target, years=years,
                        )
                        total_measures += n
                        if path:
                            total_files += 1
                        if n:
                            logger.info(
                                "  {} / {}: {} measure(s)",
                                target["state_code"],
                                target["jurisdiction_id"],
                                n,
                            )
                    except Exception as exc:
                        failures += 1
                        logger.warning(
                            "Jurisdiction scrape failed for {}: {}",
                            target.get("jurisdiction_id"),
                            exc,
                        )
            finally:
                conn.close()

    await discovery.close()

    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "states": list(states),
        "years": list(years),
        "total_measures": total_measures,
        "files_written": total_files,
        "failures": failures,
    }
    summary_path = CACHE_DIR / "fetch_debug" / f"download_summary_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.success(
        "Done: {} measure(s) across {} file(s), {} failure(s). Summary → {}",
        total_measures, total_files, failures, summary_path,
    )
    return 1 if failures and total_measures == 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--states", default=",".join(DEFAULT_STATES), help="Comma-separated USPS codes")
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_ELECTION_YEARS),
        help=f"Comma-separated election years (default: {','.join(DEFAULT_ELECTION_YEARS)})",
    )
    parser.add_argument("--year", type=int, help=argparse.SUPPRESS)  # legacy single-year override
    parser.add_argument("--include-jurisdictions", action="store_true",
                        help="Also scrape per-jurisdiction ballot-measures pages (requires DB)")
    parser.add_argument("--include-types", default="municipality,county",
                        help="Jurisdiction types when --include-jurisdictions (default: municipality,county)")
    parser.add_argument("--limit-per-state", type=int, default=20,
                        help="Cap jurisdictions per state (default: 20)")
    parser.add_argument("--jurisdiction-ids", default="",
                        help="Optional comma-separated jurisdiction_id filter")
    parser.add_argument("--skip-playwright-check", action="store_true",
                        help="Skip Chromium preflight (not recommended)")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
