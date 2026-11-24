"""The meeting type a video title names (#831), and a command to re-type rows stored as ``Other``.

``detect_meeting_type`` used six substring checks and called everything else ``Other``, so committee
meetings, commissions, work sessions and briefings were all stored as ``Other``. The type is shown on
decision and meeting pages, and the analysis loader reads it, so the label should say what the title
says. Matching is on whole words: "special" inside "specialist" no longer makes a "Special Meeting".

The first matching rule wins. The first three rules keep the answers the old checks gave, so rows
that already had a type keep it.

Re-type the rows already stored as ``Other`` (new scrapes are typed on insert; a re-scrape does not
overwrite ``meeting_type``)::

    python -m scrapers.youtube.meeting_type                # dry run: what would change
    python -m scrapers.youtube.meeting_type --apply
    python -m scrapers.youtube.meeting_type --states AL,GA --apply

It writes to the local warehouse (``NEON_DATABASE_URL_DEV``, else ``localhost:5433``), never to
``NEON_DATABASE_URL``, and only touches rows whose type is blank, ``Other``, ``Unknown`` or the
loader's ``YouTube Video`` placeholder.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

from loguru import logger

OTHER = "Other"
# Stored values that say nothing about the meeting; only these are ever re-typed.
UNTYPED = ("", "other", "unknown", "youtube video")


def _rule(label: str, pattern: str) -> tuple[str, re.Pattern[str]]:
    return label, re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


# Order matters: the named body first (as before), then other bodies, then the form of the meeting.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    _rule("City Council", r"city\s+council|council\s+meeting"),
    _rule("Planning Commission", r"planning|zoning"),
    _rule("School Board", r"school\s+board|board\s+of\s+education"),
    _rule("Committee", r"committee|subcommittee"),
    _rule("Commission", r"commission|commissioners?"),
    _rule("Board", r"board(?!\s+games?)|trustees|aldermen|selectmen|supervisors"),
    _rule("Authority", r"authority"),
    _rule("Work Session", r"work\s*session|study\s+session"),
    _rule("Briefing", r"briefing"),
    _rule("Public Hearing", r"public\s+hearing|hearing"),
    _rule("Town Hall", r"town\s+hall"),
    _rule("Special Meeting", r"special(?:\s+called)?\s+(?:meeting|session)|special"),
    _rule("Workshop", r"workshop"),
    _rule("Council", r"council"),
)


def meeting_type_from_title(title: str | None) -> str:
    """The type a title names, or ``Other`` when it names none."""
    text = str(title or "")
    for label, pattern in _RULES:
        if pattern.search(text):
            return label
    return OTHER


def local_warehouse_url() -> str:
    """``NEON_DATABASE_URL_DEV``, else the local warehouse. Never ``NEON_DATABASE_URL`` (production)."""
    dev = (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
    if dev:
        return dev
    password = os.getenv("POSTGRES_PASSWORD", "password")
    return f"postgresql://postgres:{password}@localhost:5433/open_navigator"


def plan_retype(rows: list[tuple[str, str | None, str | None]]) -> list[tuple[str, str, str]]:
    """``(video_id, old_type, new_type)`` for each untyped row whose title names a type.

    ``rows`` are ``(video_id, meeting_type, title)``. A row that already has a real type is never
    changed, and neither is one whose title names nothing."""
    changes: list[tuple[str, str, str]] = []
    for video_id, old, title in rows:
        if str(old or "").strip().lower() not in UNTYPED:
            continue
        new = meeting_type_from_title(title)
        if new != OTHER:
            changes.append((video_id, str(old or ""), new))
    return changes


def run(*, database_url: str, states: tuple[str, ...] | None = None, apply: bool = False) -> dict[str, int]:
    """Re-type untyped rows of ``bronze.bronze_event_youtube`` from their titles. Dry run unless ``apply``."""
    import psycopg2  # imported here so the classifier can be used without a database driver

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT video_id, meeting_type, title FROM bronze.bronze_event_youtube "
                "WHERE lower(btrim(coalesce(meeting_type, ''))) = ANY(%s)"
            )
            params: list[object] = [list(UNTYPED)]
            if states:
                sql += " AND state_code = ANY(%s)"
                params.append(list(states))
            cur.execute(sql, params)
            rows = cur.fetchall()
            changes = plan_retype(rows)
            by_type = Counter(new for _vid, _old, new in changes)
            logger.info("{:,} untyped videos read; {:,} have a title that names a type", len(rows), len(changes))
            for label, n in by_type.most_common():
                logger.info("  {:<20} {:,}", label, n)
            if apply and changes:
                cur.executemany(
                    "UPDATE bronze.bronze_event_youtube SET meeting_type = %s "
                    "WHERE video_id = %s AND lower(btrim(coalesce(meeting_type, ''))) = ANY(%s)",
                    [(new, vid, list(UNTYPED)) for vid, _old, new in changes],
                )
                conn.commit()
                logger.success("Re-typed {:,} videos", len(changes))
            elif changes:
                logger.info("Dry run: nothing written. Pass --apply to re-type them.")
    finally:
        conn.close()
    return {"untyped": len(rows), "retyped": len(changes) if apply else 0, "would_retype": len(changes),
            "still_other": len(rows) - len(changes)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-type videos stored as Other from what their titles say (#831).")
    parser.add_argument("--states", default="", help="Comma-separated state codes; empty = all")
    parser.add_argument("--apply", action="store_true", help="Write the new types (default: dry run)")
    args = parser.parse_args(argv)
    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip()) or None
    run(database_url=local_warehouse_url(), states=states, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
