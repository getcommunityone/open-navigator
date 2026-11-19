"""Clear contact-form senders' emails 180 days after they wrote (#456).

``contact_submission`` lives in the API's own database next to ``user`` (see ``api.models.ContactSubmission``). The
retention rule in ``web_docs/docs/development/contact-form-privacy.md`` is: set ``sender_email`` to NULL once
``created_at`` is more than 180 days old, and keep the rest of the row so the GitHub issue link still works.

Run it::

    python -m hosting.retention.contact_submission --dry-run      # count only
    python -m hosting.retention.contact_submission                # clear
    python -m hosting.retention.contact_submission --days 90

The database is ``--database-url``, else the first set of ``NEON_DATABASE_URL_DEV``, ``NEON_DATABASE_URL``,
``DATABASE_URL`` (the order ``api.database`` uses), so it reaches the same database the API does. It prints how many
rows it cleared and which host and database it ran against, and never prints an email.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from loguru import logger

DEFAULT_DAYS = 180
URL_ENV_NAMES = ("NEON_DATABASE_URL_DEV", "NEON_DATABASE_URL", "DATABASE_URL")

_WHERE = "created_at < {p} AND sender_email IS NOT NULL"


def cutoff_for(days: int, now: datetime | None = None) -> str:
    """The instant before which a row is expired, as a UTC timestamp string the database compares directly."""
    if days < 1:
        raise ValueError(f"--days must be at least 1, got {days}")
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return (moment - timedelta(days=days)).replace(microsecond=0).isoformat(sep=" ")


def clear_expired_emails(conn: Any, *, days: int = DEFAULT_DAYS, now: datetime | None = None,
                         dry_run: bool = False, param: str = "%s") -> int:
    """Set ``sender_email`` to NULL on every row older than ``days`` days; return how many rows that is.

    ``dry_run`` only counts. ``param`` is the DB-API placeholder (``%s`` for psycopg2, ``?`` for sqlite3). The rule
    is plain SQL, so it behaves the same on PostgreSQL and in the unit tests' SQLite.
    """
    cutoff = cutoff_for(days, now)
    where = _WHERE.format(p=param)
    cur = conn.cursor()
    try:
        if dry_run:
            cur.execute(f"SELECT count(*) FROM contact_submission WHERE {where}", (cutoff,))
            return int(cur.fetchone()[0])
        cur.execute(f"UPDATE contact_submission SET sender_email = NULL WHERE {where}", (cutoff,))
        cleared = int(cur.rowcount)
        conn.commit()
        return cleared
    finally:
        cur.close()


def resolve_database_url(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    for name in URL_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    return None


def describe_target(url: str) -> str:
    """``host/database`` of a URL, with no user or password, for the log."""
    parsed = urlparse(url)
    return f"{parsed.hostname or '?'}{':' + str(parsed.port) if parsed.port else ''}{parsed.path or ''}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m hosting.retention.contact_submission",
                                description="Clear contact-form senders' emails after the retention period (#456).")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"retention in days (default {DEFAULT_DAYS})")
    p.add_argument("--dry-run", action="store_true", help="count the rows that would be cleared; change nothing")
    p.add_argument("--database-url", default=None,
                   help="PostgreSQL URL of the API's database (default: NEON_DATABASE_URL_DEV, NEON_DATABASE_URL, "
                        "DATABASE_URL, first one set)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    url = resolve_database_url(args.database_url)
    if not url:
        logger.error("No database: pass --database-url or set one of {}", ", ".join(URL_ENV_NAMES))
        return 2
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql"):
        logger.error("This job runs against the API's PostgreSQL database; got {}", urlparse(url).scheme or "no scheme")
        return 2
    import psycopg2

    target = describe_target(url)
    logger.info("contact_submission retention: {} days, {} on {}", args.days,
                "dry run" if args.dry_run else "clearing", target)
    conn = psycopg2.connect(url)
    try:
        cleared = clear_expired_emails(conn, days=args.days, dry_run=args.dry_run)
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        logger.error("No contact_submission table on {}: is this the API's database?", target)
        return 1
    finally:
        conn.close()
    verb = "would clear" if args.dry_run else "cleared"
    print(f"{verb} sender_email on {cleared} contact_submission row(s) older than {args.days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
