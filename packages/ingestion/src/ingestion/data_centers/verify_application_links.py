"""Check the job-application links that are due and record the results (DC-1.3, #248).

    python -m ingestion.data_centers.verify_application_links --limit 50
    python -m ingestion.data_centers.verify_application_links --dry-run

Reads ``public.job_application_link`` (the admin-kept table) in the database the API
uses (``NEON_DATABASE_URL_DEV``, else ``NEON_DATABASE_URL``, else ``DATABASE_URL``). A link is due when it has never been checked or was last
checked more than a day ago. A ``live`` answer sets ``last_verified_at``; every
answer sets ``last_checked_at``, ``last_check_status`` and ``last_http_status``.
"""

from __future__ import annotations

import argparse
import os

import httpx
import psycopg2
from loguru import logger

from ingestion.data_centers.application_links import (
    TIMEOUT_SECONDS,
    USER_AGENT,
    check_link,
)

DUE_SQL = """
    SELECT job_application_link_id, url
    FROM public.job_application_link
    WHERE last_checked_at IS NULL OR last_checked_at < now() - interval '1 day'
    ORDER BY last_checked_at NULLS FIRST, job_application_link_id
    LIMIT %s
"""

UPDATE_SQL = """
    UPDATE public.job_application_link
    SET last_checked_at = %(checked_at)s,
        last_check_status = %(status)s,
        last_http_status = %(http_status)s,
        last_verified_at = CASE WHEN %(verified)s THEN %(checked_at)s ELSE last_verified_at END,
        updated_at = now()
    WHERE job_application_link_id = %(id)s
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=100, help="Most links to check (default 100).")
    parser.add_argument("--dry-run", action="store_true", help="Check, but don't write results.")
    args = parser.parse_args(argv)

    # Same order as api/database.py, so the CLI writes where the API reads.
    dsn = next(
        (os.environ[k] for k in ("NEON_DATABASE_URL_DEV", "NEON_DATABASE_URL", "DATABASE_URL") if os.environ.get(k)),
        None,
    )
    if not dsn:
        logger.error("Set NEON_DATABASE_URL_DEV, NEON_DATABASE_URL or DATABASE_URL")
        return 2

    counts = {"live": 0, "dead": 0, "error": 0}
    with psycopg2.connect(dsn) as conn, httpx.Client(
        follow_redirects=True, timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        with conn.cursor() as cur:
            cur.execute(DUE_SQL, (args.limit,))
            due = cur.fetchall()
        logger.info("Checking {} application links", len(due))
        for link_id, url in due:
            result = check_link(url, client=client)
            counts[result.status] += 1
            logger.info("{} {} -> {} ({})", link_id, url, result.status, result.http_status)
            if args.dry_run:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    UPDATE_SQL,
                    {
                        "id": link_id,
                        "checked_at": result.checked_at,
                        "status": result.status,
                        "http_status": result.http_status,
                        "verified": result.verified,
                    },
                )
            conn.commit()
    logger.success(
        "Checked {} links: {} live, {} dead, {} error{}",
        sum(counts.values()),
        counts["live"],
        counts["dead"],
        counts["error"],
        " (dry run, nothing written)" if args.dry_run else "",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
