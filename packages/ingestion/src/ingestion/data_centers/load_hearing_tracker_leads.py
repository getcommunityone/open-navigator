"""Load data center hearing leads from the CC BY 4.0 trackers into bronze (#956).

    python -m ingestion.data_centers.load_hearing_tracker_leads              # both trackers
    python -m ingestion.data_centers.load_hearing_tracker_leads --tracker sitingradar
    python -m ingestion.data_centers.load_hearing_tracker_leads --dry-run    # fetch, don't write

Two trackers publish their meeting lists under CC BY 4.0 as a file meant to be downloaded
(see web_docs/docs/development/data-center-source-review.md):

* Data Center Fights, ``https://datacenterfights.com/data.json`` (its ``meetings`` list)
* Siting Radar, ``https://sitingradar.com/data/siting-radar-upcoming.csv``

Each record is stored as given, one row per (tracker, record_id), in
``bronze.bronze_data_center_hearing_tracker_lead``. A tracker record is a LEAD, not a fact:
dbt (``stg_data_center_hearing_tracker_lead`` → ``int_data_center_hearing_lead``) turns it into a
lead, and a hearing is shown only after the government's own page confirms it
(``fetch_hearing_sources`` then ``data_center_hearing``). The trackers' text is never served.

Politeness: one request per tracker per run, through ``community_events.PoliteFetcher``
(descriptive User-Agent, robots.txt, the never-fetch list). Run it at most daily.

Writes only to the local / dev warehouse: ``--database-url``, else ``NEON_DATABASE_URL_DEV``.
It never falls back to the production database.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg2
from loguru import logger
from psycopg2.extras import Json

from ingestion.data_centers.community_events import PoliteFetcher


@dataclass(frozen=True)
class Tracker:
    key: str
    feed_url: str
    attribution: str


TRACKERS: dict[str, Tracker] = {
    "datacenterfights": Tracker(
        "datacenterfights",
        "https://datacenterfights.com/data.json",
        "Data Center Fights (datacenterfights.com), CC BY 4.0",
    ),
    "sitingradar": Tracker(
        "sitingradar",
        "https://sitingradar.com/data/siting-radar-upcoming.csv",
        "Siting Radar (sitingradar.com/pending), CC BY 4.0",
    ),
}

TABLE = "bronze.bronze_data_center_hearing_tracker_lead"
DDL = f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        tracker      text NOT NULL,
        record_id    text NOT NULL,
        feed_url     text NOT NULL,
        attribution  text NOT NULL,
        fetched_at   timestamptz NOT NULL,
        record       jsonb NOT NULL,
        PRIMARY KEY (tracker, record_id)
    )
"""
UPSERT = f"""
    INSERT INTO {TABLE} (tracker, record_id, feed_url, attribution, fetched_at, record)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (tracker, record_id) DO UPDATE SET
        feed_url = EXCLUDED.feed_url, attribution = EXCLUDED.attribution,
        fetched_at = EXCLUDED.fetched_at, record = EXCLUDED.record
"""


def parse_datacenterfights(body: bytes) -> list[tuple[str, dict[str, Any]]]:
    """``(record_id, record)`` for each entry of the ``meetings`` list of data.json."""
    meetings = json.loads(body).get("meetings") or []
    return [(str(m["id"]), m) for m in meetings if isinstance(m, dict) and m.get("id")]


def parse_sitingradar(body: bytes) -> list[tuple[str, dict[str, Any]]]:
    """``(record_id, record)`` for each CSV row, keyed by its ``item_id``."""
    text = body.decode("utf-8-sig", errors="replace")
    return [
        (row["item_id"], dict(row))
        for row in csv.DictReader(io.StringIO(text))
        if row.get("item_id")
    ]


PARSERS = {"datacenterfights": parse_datacenterfights, "sitingradar": parse_sitingradar}


def fetch_tracker(
    fetcher: PoliteFetcher, tracker: Tracker
) -> list[tuple[str, dict[str, Any]]]:
    """Fetch and parse one tracker's file. Raises on a refused or failed fetch."""
    resp = fetcher.get(
        tracker.feed_url
    )  # PermissionError when robots.txt / never-fetch says no
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return PARSERS[tracker.key](resp.content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tracker",
        action="append",
        choices=sorted(TRACKERS),
        help="Only this tracker.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and report, but don't write."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("NEON_DATABASE_URL_DEV"),
        help="Local / dev warehouse (default NEON_DATABASE_URL_DEV). Never production.",
    )
    args = parser.parse_args(argv)
    if not args.dry_run and not args.database_url:
        logger.error(
            "Set NEON_DATABASE_URL_DEV or pass --database-url (the local / dev warehouse)"
        )
        return 2

    fetcher = PoliteFetcher(min_interval=3.0)
    fetched_at = datetime.now(UTC)
    loaded: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    failed = 0
    for key in args.tracker or sorted(TRACKERS):
        tracker = TRACKERS[key]
        try:
            loaded[key] = fetch_tracker(fetcher, tracker)
        except Exception as err:  # noqa: BLE001 - one tracker failing must not stop the other
            failed += 1
            logger.error("{}: not loaded: {}: {}", key, type(err).__name__, err)
            continue
        logger.info("{}: {:,} record(s)", key, len(loaded[key]))

    if args.dry_run:
        logger.info("dry run: nothing written")
        return 1 if failed else 0
    with psycopg2.connect(args.database_url) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        for key, records in loaded.items():
            tracker = TRACKERS[key]
            for record_id, record in records:
                cur.execute(
                    UPSERT,
                    (
                        key,
                        record_id,
                        tracker.feed_url,
                        tracker.attribution,
                        fetched_at,
                        Json(record),
                    ),
                )
        conn.commit()
    total = sum(len(r) for r in loaded.values())
    logger.success(
        "Stored {:,} tracker record(s) in {} ({} tracker(s) failed)",
        total,
        TABLE,
        failed,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
