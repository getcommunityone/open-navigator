"""Land the open (CC BY 4.0) data center inventories in bronze (#958).

    python -m ingestion.data_centers.facility_inventories                       # all three
    python -m ingestion.data_centers.facility_inventories --source registry     # one
    python -m ingestion.data_centers.facility_inventories --dry-run             # fetch, don't write

Which inventories we may import, and why, is recorded in
web_docs/docs/development/data-center-source-review.md (#956). Three publish a free file
under CC BY 4.0:

* ``registry``: US Data Center Registry, suedatacenters.org (Theory Road LLC). One row per
  facility. Credit Compute Atlas for the base data and SueDataCenters.org for joins,
  corrections and additions.
* ``public_evidence``: Public Evidence Project, publicevidence.org. One row per public record
  (permit, docket, filing), each with the government ``source_url``. Credit it and Compute
  Atlas upstream.
* ``greencalculus``: github.com/greencalculus/us-data-centers-by-state. State aggregates, each
  credited to its original publisher.

Each record lands as raw JSONB keyed by the source's own id, one row per record, with
``first_seen_at`` (kept) and ``last_seen_at`` (moved to this run). A record missing from a
newer file keeps its old ``last_seen_at``, so dbt can tell it is no longer listed instead of
dropping it. dbt does all the typing and matching (``stg_data_center_facility_registry``,
``stg_data_center_public_record``, ``stg_data_center_state_count``, ``data_center_site``).

Politeness: one request per file through ``community_events.PoliteFetcher`` (descriptive
User-Agent, robots.txt, the never-fetch list). Run it at most daily.

Writes only to the local / dev warehouse: ``--database-url``, else ``NEON_DATABASE_URL_DEV``.
It never falls back to the production database.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg2
from loguru import logger
from psycopg2.extras import Json

from ingestion.data_centers.community_events import PoliteFetcher


@dataclass(frozen=True)
class Inventory:
    key: str
    feed_url: str
    table: str
    id_header: str
    required: tuple[str, ...]
    attribution: str


INVENTORIES: dict[str, Inventory] = {
    "registry": Inventory(
        "registry",
        "https://suedatacenters.org/data-centers.csv",
        "bronze.bronze_data_center_facility_registry",
        "id",
        ("id", "name", "status", "state", "latitude", "longitude", "profile_url"),
        "US Data Center Registry, SueDataCenters.org (Theory Road LLC), base data from Compute Atlas. CC BY 4.0.",
    ),
    "public_evidence": Inventory(
        "public_evidence",
        "https://publicevidence.org/data/national-data-center-public-records.csv",
        "bronze.bronze_data_center_facility_public_evidence",
        "id",
        ("id", "state_code", "title", "source_url", "public_evidence_record_url"),
        "Public Evidence Project (publicevidence.org), with Compute Atlas upstream. CC BY 4.0.",
    ),
    "greencalculus": Inventory(
        "greencalculus",
        "https://raw.githubusercontent.com/greencalculus/us-data-centers-by-state/main/us-data-centers.csv",
        "bronze.bronze_data_center_state_count_greencalculus",
        "id",
        ("id", "state", "metric", "value", "source", "source_url"),
        "US Data Centers by State (github.com/greencalculus/us-data-centers-by-state), CC BY 4.0; "
        "each figure credited to its original publisher.",
    ),
}


class HeaderMismatch(ValueError):
    """The file no longer has a header this loader relies on."""


def parse_csv(body: bytes, inv: Inventory) -> list[tuple[str, dict[str, str]]]:
    """``(record_id, row)`` per CSV row with an id. Raises HeaderMismatch on a missing header."""
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig", errors="replace")))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [h for h in inv.required if h not in headers]
    if missing:
        raise HeaderMismatch(f"{inv.key}: missing {missing}; found {headers}")
    rows: list[tuple[str, dict[str, str]]] = []
    for raw in reader:
        row = {
            (k or "").strip(): (v or "").strip()
            for k, v in raw.items()
            if k is not None
        }
        if row.get(inv.id_header):
            rows.append((row[inv.id_header], row))
    return rows


def create_sql(inv: Inventory) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {inv.table} (
            record_id      text PRIMARY KEY,
            feed_url       text NOT NULL,
            attribution    text NOT NULL,
            record         jsonb NOT NULL,
            first_seen_at  timestamptz NOT NULL,
            last_seen_at   timestamptz NOT NULL
        )
    """


def upsert_sql(inv: Inventory) -> str:
    return f"""
        INSERT INTO {inv.table} (record_id, feed_url, attribution, record, first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (record_id) DO UPDATE SET
            feed_url = EXCLUDED.feed_url, attribution = EXCLUDED.attribution,
            record = EXCLUDED.record, last_seen_at = EXCLUDED.last_seen_at
    """


def fetch_inventory(
    fetcher: PoliteFetcher, inv: Inventory
) -> list[tuple[str, dict[str, str]]]:
    """Fetch and parse one inventory file. Raises on a refused or failed fetch."""
    resp = fetcher.get(
        inv.feed_url
    )  # PermissionError when robots.txt / never-fetch says no
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return parse_csv(resp.content, inv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(INVENTORIES),
        help="Only this inventory.",
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
    seen_at = datetime.now(UTC)
    loaded: dict[str, list[tuple[str, dict[str, str]]]] = {}
    failed = 0
    for key in args.source or sorted(INVENTORIES):
        inv = INVENTORIES[key]
        try:
            loaded[key] = fetch_inventory(fetcher, inv)
        except Exception as err:  # noqa: BLE001 - one source failing must not stop the others
            failed += 1
            logger.error("{}: not loaded: {}: {}", key, type(err).__name__, err)
            continue
        logger.info("{}: {:,} record(s)", key, len(loaded[key]))

    if args.dry_run:
        logger.info("dry run: nothing written")
        return 1 if failed else 0
    with psycopg2.connect(args.database_url) as conn, conn.cursor() as cur:
        for key, rows in loaded.items():
            inv = INVENTORIES[key]
            cur.execute(create_sql(inv))
            sql = upsert_sql(inv)
            for record_id, row in rows:
                cur.execute(
                    sql,
                    (
                        record_id,
                        inv.feed_url,
                        inv.attribution,
                        Json(row),
                        seen_at,
                        seen_at,
                    ),
                )
            logger.success("{}: {:,} record(s) in {}", key, len(rows), inv.table)
        conn.commit()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
