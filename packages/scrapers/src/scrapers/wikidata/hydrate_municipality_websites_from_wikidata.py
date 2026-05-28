#!/usr/bin/env python3
"""
Hydrate ``official_website`` on ``bronze.bronze_jurisdictions_municipalities_wikidata`` from Wikidata.

Uses ``wbgetentities`` (no bulk WDQS) for rows that already have a ``wikidata_id`` but no website.
Sets ``official_website_updated_at`` and ``wikidata_last_updated`` when a website is written.

Prerequisites:
  - Census + bronze municipality rows (``ensure_bronze_jurisdictions_cloud.py``)
  - ``wikidata_id`` on rows (parquet apply or prior loader run)

Examples::

  # One state
  .venv/bin/python packages/scrapers/src/scrapers/wikidata/hydrate_municipality_websites_from_wikidata.py --states AL

  # Priority dev states
  .venv/bin/python packages/scrapers/src/scrapers/wikidata/hydrate_municipality_websites_from_wikidata.py --priority-states

  # All USPS with municipality bronze rows
  .venv/bin/python packages/scrapers/src/scrapers/wikidata/hydrate_municipality_websites_from_wikidata.py --all-us-states
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from loguru import logger

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from scripts.deployment.neon.ensure_bronze_jurisdictions_cloud import ensure_wikidata_tables  # noqa: E402
from scrapers.wikidata.load_jurisdictions_wikidata import (  # noqa: E402
    DATABASE_URL,
    PRIORITY_STATES,
    STATE_MAP,
    CheckpointManager,
    JurisdictionsWikiDataLoader,
    _apply_wikidata_happy_path_env_defaults,
    _wikidata_fips_gnis_parquet_path,
)

MUNI_TABLE = "bronze.bronze_jurisdictions_municipalities_wikidata"


def _snapshot_municipality_websites(conn, states: List[str]) -> Dict[str, Dict[str, int]]:
    import psycopg2

    out: Dict[str, Dict[str, int]] = {}
    cur = conn.cursor()
    try:
        for us in states:
            cur.execute(
                f"""
                SELECT
                    COUNT(*)::int,
                    COUNT(*) FILTER (
                        WHERE wikidata_id IS NOT NULL AND BTRIM(wikidata_id::text) <> ''
                    )::int,
                    COUNT(*) FILTER (
                        WHERE official_website IS NOT NULL
                          AND BTRIM(official_website::text) <> ''
                    )::int,
                    COUNT(*) FILTER (WHERE official_website_updated_at IS NOT NULL)::int
                FROM {MUNI_TABLE}
                WHERE usps = %s
                """,
                (us,),
            )
            t, q, w, wts = cur.fetchone() or (0, 0, 0, 0)
            out[us] = {
                "total": t,
                "with_qid": q,
                "with_website": w,
                "with_official_website_updated_at": wts,
            }
    finally:
        cur.close()
    return out


def _apply_hydrate_env() -> None:
    os.environ["WIKIDATA_HYDRATE_MISSING_WEBSITES"] = "1"
    os.environ["WIKIDATA_INCREMENTAL_MERGE"] = "1"
    os.environ["WIKIDATA_HYBRID_ENRICH"] = "1"
    if _wikidata_fips_gnis_parquet_path().is_file():
        os.environ.setdefault("WIKIDATA_SKIP_BULK_WDQS", "1")
        os.environ.setdefault("WIKIDATA_WARM_FROM_PARQUET", "1")
    os.environ["WIKIDATA_HAPPY_PATH"] = "1"
    _apply_wikidata_happy_path_env_defaults()


async def _run_states(
    database_url: str,
    states: List[str],
    *,
    force: bool,
    checkpoint_file: Path,
) -> Dict[str, Any]:
    loader = JurisdictionsWikiDataLoader(database_url)
    checkpoint = None if force else CheckpointManager(str(checkpoint_file))
    per_state: Dict[str, Any] = {}

    try:
        for us in states:
            logger.info(f"=== Hydrate municipality websites: {us} ===")
            before = loader._municipality_website_stats(us)
            await loader.load_state(us, ["city"], checkpoint)
            after = loader._municipality_website_stats(us)
            per_state[us] = {
                "before": before,
                "after": after,
                "websites_added": max(
                    0,
                    after.get("with_website", 0) - before.get("with_website", 0),
                ),
            }
    finally:
        loader.close()

    return per_state


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Hydrate official_website on bronze municipalities_wikidata via Wikidata API"
    )
    ap.add_argument("--states", default="", help="Comma-separated USPS codes")
    ap.add_argument("--priority-states", action="store_true", help=f"Use {', '.join(PRIORITY_STATES)}")
    ap.add_argument("--all-us-states", action="store_true", help="Every code in STATE_MAP")
    ap.add_argument("--force", action="store_true", help="Ignore checkpoint")
    ap.add_argument(
        "--checkpoint-file",
        type=Path,
        default=Path(
            os.getenv("WIKIDATA_LOAD_CHECKPOINT_FILE", "")
            or _ROOT / "data/cache/wikidata/wikidata_jurisdictions_checkpoint.json"
        ),
    )
    ap.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="JSON run summary (default: data/logs/municipality_website_hydrate_<ts>.json)",
    )
    ap.add_argument("--database-url", default="", help="Postgres URL (default: NEON_* env)")
    args = ap.parse_args()

    if args.all_us_states:
        states = sorted(STATE_MAP.keys())
    elif args.priority_states:
        states = list(PRIORITY_STATES)
    elif args.states.strip():
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    else:
        ap.error("Pass --states, --priority-states, or --all-us-states")

    unknown = [s for s in states if s not in STATE_MAP]
    if unknown:
        raise SystemExit(f"Unknown USPS: {unknown}")

    db_url = args.database_url.strip() or DATABASE_URL
    _apply_hydrate_env()

    import psycopg2

    conn = psycopg2.connect(db_url)
    try:
        ensure_wikidata_tables(conn)
    finally:
        conn.close()

    log_dir = _ROOT / "data/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = args.log_file or (log_dir / f"municipality_website_hydrate_{stamp}.json")

    conn = psycopg2.connect(db_url)
    try:
        before_all = _snapshot_municipality_websites(conn, states)
    finally:
        conn.close()

    per_state = asyncio.run(
        _run_states(db_url, states, force=args.force, checkpoint_file=args.checkpoint_file)
    )

    conn = psycopg2.connect(db_url)
    try:
        after_all = _snapshot_municipality_websites(conn, states)
    finally:
        conn.close()

    payload = {
        "started_at": stamp,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "states": states,
        "force": args.force,
        "before": before_all,
        "after": after_all,
        "per_state": per_state,
    }
    log_path.write_text(json.dumps(payload, indent=2))
    logger.success(f"Run summary → {log_path}")

    total_added = sum(v.get("websites_added", 0) for v in per_state.values())
    logger.info(f"Total new official_website values across run: {total_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
