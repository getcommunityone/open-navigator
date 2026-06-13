#!/usr/bin/env python3
"""Download-only: OpenStates bill version & document PDFs into the local cache.

The OpenStates source database (``openstates`` on localhost:5433) keeps every
bill's *version* links (Introduced / Engrossed / Enrolled / amendments) and
*document* links (fiscal notes, committee reports, analyses) in
``opencivicdata_billversionlink`` / ``opencivicdata_billdocumentlink`` — each
row a URL + ``media_type``. ~2.2M version + ~0.48M document links are PDFs.

This module reads those URLs (filtered by state / session) and fetches each PDF
into the standard cache hierarchy, named by bill with a date prefix so the tree
is self-describing and easy to index downstream (e.g. Databricks Auto Loader):

  data/cache/bills/<STATE>/<session>/<bill>/<date>_<bill>_<kind>_<note>__<h8>.pdf
  data/cache/bills/<STATE>/<session>/<bill>/<...>.pdf.json   (per-file metadata)

The sidecar ``.pdf.json`` carries the source url, sha256, bytes, content-type,
bill identifier, kind, note and date — the manifest a Spark/Databricks job globs
to build its index without re-reading the binaries.

This module is download-only: it never writes to the warehouse. Loading the
fetched PDFs (parse / extract / classify) is a separate job.

Usage:
    python -m ingestion.openstates.bill_documents --state AL --limit 50 --dry-run
    python -m ingestion.openstates.bill_documents --state CA --session 20232024
    python -m ingestion.openstates.bill_documents --state AL --kind document
    python -m ingestion.openstates.bill_documents --state AL TX GA --rate 4
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg2
import psycopg2.extras
from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging
from loguru import logger

CACHE_DIR = Path("data/cache/bills")

# OpenStates source DB (read-only here). Mirrors export_committee_reports.py.
DEFAULT_OPENSTATES_DSN = "postgresql://postgres:postgres@localhost:5433/openstates"

USER_AGENT = (
    "OpenNavigatorBillDocs/1.0 (+https://github.com/getcommunityone/open-navigator; "
    "legislative bill version/document PDF archive for civic analysis)"
)

VALID_KINDS = ("version", "document")


def resolve_openstates_dsn() -> str:
    """Source DSN for the OpenStates Postgres (env override, else local default)."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return os.getenv("OPENSTATES_DATABASE_URL", DEFAULT_OPENSTATES_DSN)


def normalize_states(states: list[str] | None) -> list[str] | None:
    """Upper-case, de-dupe USPS codes; None/[] means *all states*."""
    if not states:
        return None
    seen: list[str] = []
    for s in states:
        code = s.strip().upper()
        if code and code not in seen:
            seen.append(code)
    return seen or None


def _division_ids(states: list[str] | None) -> list[str] | None:
    """USPS codes -> OCD division ids used to filter by jurisdiction (index-friendly)."""
    if not states:
        return None
    return [f"ocd-division/country:us/state:{s.lower()}" for s in states]


def build_links_sql(
    *,
    kinds: tuple[str, ...],
    states: list[str] | None,
    session: str | None,
    pdf_only: bool,
    limit: int | None,
    min_year: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build the UNION-ALL link query + params. Pure (no DB access).

    Ordering is **most-recent-year-first with breadth across states**: rows are
    sorted by session year descending, then round-robined across states (every
    state's 1st bill, then every state's 2nd, ...) so a budget-capped run spreads
    coverage over many states' newest sessions rather than draining one state.
    """
    division_ids = _division_ids(states)

    def leg(kind: str) -> str:
        if kind == "version":
            link, child, child_fk = (
                "opencivicdata_billversionlink",
                "opencivicdata_billversion",
                "version_id",
            )
            classification = "c.classification::text"
        else:
            link, child, child_fk = (
                "opencivicdata_billdocumentlink",
                "opencivicdata_billdocument",
                "document_id",
            )
            classification = "NULL::text"
        where = []
        if pdf_only:
            where.append("l.media_type = 'application/pdf'")
        if division_ids is not None:
            where.append("j.division_id = ANY(%(division_ids)s)")
        if session is not None:
            where.append("s.identifier = %(session)s")
        if min_year is not None:
            # start_date is varchar 'YYYY-MM-DD'; 4-char year compares lexically.
            where.append("LEFT(s.start_date, 4) >= %(min_year)s")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        return f"""
            SELECT
                '{kind}'::text AS kind,
                b.identifier   AS bill_identifier,
                s.identifier   AS session,
                LEFT(s.start_date, 4) AS session_year,
                UPPER(SUBSTRING(j.division_id FROM 'state:([a-z]{{2}})')) AS state,
                c.note         AS note,
                c.date::text   AS doc_date,
                {classification} AS classification,
                l.url          AS url,
                l.media_type   AS media_type
            FROM {link} l
            JOIN {child} c ON l.{child_fk} = c.id
            JOIN opencivicdata_bill b ON c.bill_id = b.id
            JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
            JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
            {where_sql}
        """

    legs = [leg(k) for k in kinds]
    union = "\nUNION ALL\n".join(legs)
    # Round-robin across states within each year (breadth), newest year first.
    sql = f"""
        SELECT q.*,
               ROW_NUMBER() OVER (
                   PARTITION BY q.session_year, q.state
                   ORDER BY q.bill_identifier, q.url
               ) AS state_rn
        FROM (
        {union}
        ) q
        ORDER BY q.session_year DESC NULLS LAST, state_rn, q.state
    """
    if limit is not None:
        sql += "\nLIMIT %(limit)s"

    params: dict[str, Any] = {}
    if division_ids is not None:
        params["division_ids"] = division_ids
    if session is not None:
        params["session"] = session
    if min_year is not None:
        params["min_year"] = str(min_year)
    if limit is not None:
        params["limit"] = limit
    return sql, params


def iter_links(conn, sql: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Stream link rows via a server-side cursor (never materialize millions)."""
    with conn.cursor(name="bill_doc_links", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.itersize = 2000
        cur.execute(sql, params)
        for row in cur:
            yield dict(row)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str | None, *, maxlen: int = 40, default: str = "na") -> str:
    """Lower-case, hyphenate, trim to ``maxlen``. Empty -> ``default``."""
    if not value:
        return default
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return (slug[:maxlen].rstrip("-") or default)


def _date_prefix(doc_date: str | None) -> str:
    """First 10 chars of an ISO date (YYYY-MM-DD), else 'nodate'."""
    if doc_date and len(doc_date) >= 10:
        return doc_date[:10]
    return "nodate"


def target_path(row: dict[str, Any], *, cache_dir: Path = CACHE_DIR) -> Path:
    """Cache path for a link row: <state>/<session>/<bill>/<date>_<bill>_<kind>_<note>__<h8>.pdf.

    A short URL hash guarantees uniqueness when several links share the same
    date/note, and makes cache hits deterministic across runs.
    """
    state = (row.get("state") or "us").upper()
    session = slugify(row.get("session"), maxlen=24, default="nosession")
    bill = slugify(row.get("bill_identifier"), maxlen=24, default="nobill")
    note = slugify(row.get("note"), maxlen=32, default="doc")
    kind = row["kind"]
    prefix = _date_prefix(row.get("doc_date"))
    h8 = hashlib.sha1((row["url"] or "").encode("utf-8")).hexdigest()[:8]
    fname = f"{prefix}_{bill}_{kind}_{note}__{h8}.pdf"
    return cache_dir / state / session / bill / fname


def _is_done(pdf: Path) -> bool:
    """A link is already fetched when both the PDF and its sidecar exist non-empty."""
    sidecar = pdf.with_suffix(pdf.suffix + ".json")
    return pdf.is_file() and pdf.stat().st_size > 0 and sidecar.is_file()


def _write_sidecar(pdf: Path, row: dict[str, Any], resp_meta: dict[str, Any]) -> None:
    meta = {
        "url": row["url"],
        "media_type": row.get("media_type"),
        "kind": row["kind"],
        "state": row.get("state"),
        "session": row.get("session"),
        "bill_identifier": row.get("bill_identifier"),
        "note": row.get("note"),
        "doc_date": row.get("doc_date"),
        "classification": row.get("classification"),
        "local_path": str(pdf),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        **resp_meta,
    }
    pdf.with_suffix(pdf.suffix + ".json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


async def download(
    *,
    states: list[str] | None = None,
    session: str | None = None,
    kinds: tuple[str, ...] = VALID_KINDS,
    pdf_only: bool = True,
    limit: int | None = None,
    min_year: int | None = None,
    rate_limit_per_sec: float = 4.0,
    force: bool = False,
    dry_run: bool = False,
    cache_dir: Path = CACHE_DIR,
    dsn: str | None = None,
    max_gb: float | None = None,
    min_free_gb: float | None = 2.0,
) -> dict[str, int]:
    """Fetch bill PDFs from the OpenStates DB into ``cache_dir``.

    Disk budget (important on a space-constrained volume): the run stops cleanly
    once it has written ``max_gb`` this session, or once free space on the target
    drive would fall below ``min_free_gb``. Both are checked before each fetch, so
    a budget-capped run is safe to leave unattended. Cached files already on disk
    don't count against ``max_gb``.

    Returns a counts dict: candidates / skipped (cache) / fetched / failed / stopped.
    """
    states = normalize_states(states)
    dsn = dsn or resolve_openstates_dsn()
    sql, params = build_links_sql(
        kinds=kinds, states=states, session=session, pdf_only=pdf_only,
        limit=limit, min_year=min_year,
    )

    logger.info(
        "Querying OpenStates links: states={} session={} min_year={} kinds={} pdf_only={} limit={}",
        states or "ALL", session or "ALL", min_year or "ANY", kinds, pdf_only, limit,
    )
    max_bytes = int(max_gb * 1024**3) if max_gb else None
    min_free_bytes = int(min_free_gb * 1024**3) if min_free_gb else None
    if max_bytes or min_free_bytes:
        logger.info(
            "Disk budget: max_gb={} min_free_gb={}", max_gb or "∞", min_free_gb or 0,
        )

    counts = {"candidates": 0, "skipped": 0, "fetched": 0, "failed": 0, "stopped": 0}
    bytes_written = 0

    config = HttpClientConfig(
        base_url="",
        source="openstates_bill_docs",
        timeout_s=60.0,
        rate_limit_per_sec=rate_limit_per_sec,
        default_headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )

    conn = psycopg2.connect(dsn)
    try:
        rows = iter_links(conn, sql, params)
        if dry_run:
            for row in rows:
                counts["candidates"] += 1
                if counts["candidates"] <= 20:
                    logger.info("[dry-run] {} -> {}", row["url"], target_path(row, cache_dir=cache_dir))
            logger.info("[dry-run] {} candidate link(s); nothing downloaded", counts["candidates"])
            return counts

        async with BaseAsyncClient(config) as client:
            for row in rows:
                counts["candidates"] += 1
                url = row.get("url")
                if not url:
                    continue
                pdf = target_path(row, cache_dir=cache_dir)

                if not force and _is_done(pdf):
                    counts["skipped"] += 1
                    continue

                # Disk budget: stop cleanly before we overrun the volume.
                if max_bytes is not None and bytes_written >= max_bytes:
                    logger.warning(
                        "max_gb budget reached ({:.2f} GB written); stopping.",
                        bytes_written / 1024**3,
                    )
                    counts["stopped"] = 1
                    break
                if min_free_bytes is not None:
                    free = shutil.disk_usage(".").free
                    if free < min_free_bytes:
                        logger.warning(
                            "free space {:.2f} GB below floor {:.2f} GB; stopping.",
                            free / 1024**3, min_free_bytes / 1024**3,
                        )
                        counts["stopped"] = 1
                        break

                try:
                    resp = await client.get(url)
                except Exception as exc:  # noqa: BLE001 - one bad link shouldn't abort the run
                    counts["failed"] += 1
                    logger.warning("fetch failed {}: {}", url, exc)
                    continue

                body = resp.content
                if not body:
                    counts["failed"] += 1
                    logger.warning("empty body from {}", url)
                    continue

                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower() or None
                pdf.parent.mkdir(parents=True, exist_ok=True)
                pdf.write_bytes(body)
                _write_sidecar(
                    pdf,
                    row,
                    {
                        "http_status": resp.status_code,
                        "content_type": ctype,
                        "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                    },
                )
                counts["fetched"] += 1
                bytes_written += len(body)
                if counts["fetched"] % 100 == 0:
                    logger.info(
                        "progress: fetched={} ({:.2f} GB) skipped={} failed={} (seen {})",
                        counts["fetched"], bytes_written / 1024**3,
                        counts["skipped"], counts["failed"], counts["candidates"],
                    )
    finally:
        conn.close()

    logger.success(
        "done: candidates={} fetched={} ({:.2f} GB) skipped(cache)={} failed={} stopped_on_budget={}",
        counts["candidates"], counts["fetched"], bytes_written / 1024**3,
        counts["skipped"], counts["failed"], counts["stopped"],
    )
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download OpenStates bill version/document PDFs into data/cache/bills.",
    )
    parser.add_argument(
        "--state",
        nargs="*",
        dest="states",
        help="USPS code(s) to fetch, e.g. AL TX GA. Default: all states.",
    )
    parser.add_argument(
        "--session",
        help="Legislative session identifier filter (e.g. 20232024). Default: all sessions.",
    )
    parser.add_argument(
        "--kind",
        choices=(*VALID_KINDS, "both"),
        default="both",
        help="version links, document links, or both (default).",
    )
    parser.add_argument(
        "--all-media",
        action="store_true",
        help="Include non-PDF links too (default: PDFs only).",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Only sessions starting in this year or later (e.g. 2025). "
        "Rows are always ordered newest-year-first, breadth across states.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max links to consider (for testing)."
    )
    parser.add_argument(
        "--max-gb",
        type=float,
        default=None,
        help="Stop after writing this many GB this run (disk budget).",
    )
    parser.add_argument(
        "--min-free-gb",
        type=float,
        default=2.0,
        help="Stop if free space on the target drive falls below this (default 2).",
    )
    parser.add_argument(
        "--rate", type=float, default=4.0, help="Max requests/sec (default 4)."
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-download even if cached."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidate URLs + target paths without downloading.",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    kinds = VALID_KINDS if args.kind == "both" else (args.kind,)
    asyncio.run(
        download(
            states=args.states,
            session=args.session,
            kinds=kinds,
            pdf_only=not args.all_media,
            limit=args.limit,
            min_year=args.min_year,
            rate_limit_per_sec=args.rate,
            force=args.force,
            dry_run=args.dry_run,
            max_gb=args.max_gb,
            min_free_gb=args.min_free_gb,
        )
    )


if __name__ == "__main__":
    main()
