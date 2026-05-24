#!/usr/bin/env python3
"""
Promote rows from ``bronze.bronze_events_meetings_{counties,municipalities}_scraped``
into the OCD-aligned ``public.c1_event`` table, and attach their PDFs / YouTube /
HTML resources as ``c1_eventdocument`` and ``c1_eventmedia`` rows.

Pipeline:
  1. Scan every bronze resource row for a meeting date (URL, anchor text, filename).
  2. Group by (jurisdiction_id, ISO date) — each unique (jur, date) becomes one
     c1_event row. The event ``name`` is derived from the first anchor/title token
     in that group, falling back to "<jurisdiction> meeting <date>".
  3. UPSERT c1_event keyed by ``dedupe_key = jurisdiction_id|YYYY-MM-DD``.
  4. For each resource row:
        - PDF (doc_type agenda/minutes/other) -> c1_eventdocument with classification
          = agenda/minutes/other; links jsonb = [{url, media_type, text, local_path}]
        - YouTube link -> c1_eventmedia with classification = "recording"
        - HTML calendar/list pages -> skipped (no meeting-specific attachment)

Idempotent: re-running on the same bronze data produces the same dedupe_key, so
c1_event is upserted. c1_eventdocument / c1_eventmedia rows use a deterministic
``id`` (UUID v5 over event_id + url) so re-runs DO NOT duplicate.

Run::

    .venv/bin/python -m scripts.discovery.promote_bronze_meetings_to_c1_event --dry-run
    .venv/bin/python -m scripts.discovery.promote_bronze_meetings_to_c1_event
    .venv/bin/python -m scripts.discovery.promote_bronze_meetings_to_c1_event --states AL,GA
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

logger = logging.getLogger("promote_bronze_meetings")

# Stable UUID namespace for v5 ids (any random UUID works — keep this constant).
_UUID_NS_EVENT_RESOURCE = uuid.UUID("9c8a5d2b-1f4e-4a6b-a8c1-3e7f9b2c4d5a")

# Date patterns, ordered most specific first. Mirror the renamer's logic.
_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?P<y>20\d{2})[-_/.](?P<m>0?[1-9]|1[0-2])[-_/.](?P<d>0?[1-9]|[12]\d|3[01])"),
    re.compile(r"(?P<m>0?[1-9]|1[0-2])[-_/.](?P<d>0?[1-9]|[12]\d|3[01])[-_/.](?P<y>20\d{2})"),
    re.compile(
        r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+"
        r"(?P<d>0?[1-9]|[12]\d|3[01]),?\s+(?P<y>20\d{2})",
        re.IGNORECASE,
    ),
    re.compile(r"(?<!\d)(?P<y>20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)"),
)
_MONTH_NAME_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def derive_date(*sources: str) -> str | None:
    """Return ISO YYYY-MM-DD or None if no date confidently extracted."""
    blob = " ".join(s or "" for s in sources)
    for pat in _DATE_PATTERNS:
        m = pat.search(blob)
        if not m:
            continue
        gd = m.groupdict()
        if "mon" in gd:
            mm = _MONTH_NAME_TO_NUM.get((gd.get("mon") or "").lower()[:4]) \
                or _MONTH_NAME_TO_NUM.get((gd.get("mon") or "").lower()[:3])
            if not mm:
                continue
            try:
                return f"{int(gd['y']):04d}-{mm:02d}-{int(gd['d']):02d}"
            except (KeyError, ValueError):
                continue
        try:
            return f"{int(gd['y']):04d}-{int(gd['m']):02d}-{int(gd['d']):02d}"
        except (KeyError, ValueError):
            continue
    return None


def event_name_from_anchor(anchor: str | None, jurisdiction_id: str, date_iso: str) -> str:
    """Use the anchor text if it's reasonable; otherwise synthesize."""
    if anchor:
        cleaned = re.sub(r"\s+", " ", anchor).strip()
        # Drop date noise so name doesn't repeat the date
        cleaned = re.sub(
            r"\b(?:20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\b[\s_/.-]*",
            "", cleaned, flags=re.IGNORECASE,
        ).strip(" -_:")
        if 3 <= len(cleaned) <= 200:
            return cleaned
    return f"Meeting {date_iso}"


def classify_pdf(doc_type: str | None, anchor: str | None, url: str | None) -> str:
    """Return 'agenda' | 'minutes' | 'other' based on bronze hints + text."""
    if doc_type and doc_type in ("agenda", "minutes"):
        return doc_type
    blob = " ".join(s or "" for s in (doc_type, anchor, url)).lower()
    if "agenda" in blob:
        return "agenda"
    if "minutes" in blob:
        return "minutes"
    return "other"


# --------------------------------------------------------------------------------------


@dataclass
class BronzeRow:
    bronze_id: int
    bronze_table: str               # 'counties' | 'municipalities'
    jurisdiction_id: str
    state_code: str | None
    resource_category: str          # 'document' | 'link'
    resource_kind: str | None       # 'pdf' | 'html_page' | 'youtube' | …
    url: str | None
    local_path: str | None
    doc_type: str | None
    anchor: str | None
    homepage_url: str | None

    @property
    def is_pdf(self) -> bool:
        return self.resource_category == "document" and (self.resource_kind or "") == "pdf"

    @property
    def is_youtube(self) -> bool:
        return self.resource_kind == "youtube"

    @property
    def is_other_stream(self) -> bool:
        return self.resource_kind == "other_stream"


def load_bronze_rows(conn, states: tuple[str, ...] | None) -> list[BronzeRow]:
    state_filter = ""
    args: tuple = ()
    if states:
        state_filter = "AND state_code = ANY(%s)"
        args = (list(states),)
    sql = f"""
        SELECT id, jurisdiction_id, state_code, resource_category, resource_kind,
               url, local_path, doc_type, anchor_or_link_text, homepage_url
        FROM bronze.bronze_events_meetings_counties_scraped
        WHERE TRUE {state_filter}
        UNION ALL
        SELECT id, jurisdiction_id, state_code, resource_category, resource_kind,
               url, local_path, doc_type, anchor_or_link_text, homepage_url
        FROM bronze.bronze_events_meetings_municipalities_scraped
        WHERE TRUE {state_filter}
    """
    rows: list[BronzeRow] = []
    with conn.cursor() as cur:
        cur.execute(sql, args + args if states else ())
        for r in cur.fetchall():
            rows.append(BronzeRow(
                bronze_id=r[0], bronze_table="counties_or_muni",
                jurisdiction_id=r[1], state_code=r[2],
                resource_category=r[3], resource_kind=r[4],
                url=r[5], local_path=r[6], doc_type=r[7],
                anchor=r[8], homepage_url=r[9],
            ))
    return rows


# --------------------------------------------------------------------------------------


@dataclass
class GroupKey:
    jurisdiction_id: str
    date_iso: str


@dataclass
class EventGroup:
    key: GroupKey
    state_code: str | None
    homepage_url: str | None
    rows: list[BronzeRow] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        return f"{self.key.jurisdiction_id}|{self.key.date_iso}"

    @property
    def event_id(self) -> str:
        # Deterministic: same dedupe_key -> same UUID; safe re-run.
        u = uuid.uuid5(_UUID_NS_EVENT_RESOURCE, self.dedupe_key)
        return f"ocd-event/{u}"

    def derive_name(self) -> str:
        # Prefer the most informative anchor text in the group
        for r in self.rows:
            if r.anchor and len(r.anchor.strip()) >= 5:
                return event_name_from_anchor(r.anchor, self.key.jurisdiction_id, self.key.date_iso)
        return event_name_from_anchor(None, self.key.jurisdiction_id, self.key.date_iso)


def group_rows(bronze: list[BronzeRow]) -> tuple[list[EventGroup], int, int]:
    """Return (groups, datable_resources, undatable_resources)."""
    by_key: dict[tuple[str, str], EventGroup] = {}
    datable = undatable = 0
    for r in bronze:
        # Only datable resources contribute to event creation.
        date = derive_date(r.anchor or "", r.url or "", r.local_path or "")
        if not date:
            undatable += 1
            continue
        datable += 1
        key = (r.jurisdiction_id, date)
        if key not in by_key:
            by_key[key] = EventGroup(
                key=GroupKey(jurisdiction_id=r.jurisdiction_id, date_iso=date),
                state_code=r.state_code,
                homepage_url=r.homepage_url,
            )
        by_key[key].rows.append(r)
    return list(by_key.values()), datable, undatable


# --------------------------------------------------------------------------------------


def upsert_events(conn, groups: list[EventGroup], *, dry_run: bool) -> int:
    if dry_run:
        return len(groups)
    inserted = 0
    with conn.cursor() as cur:
        for g in groups:
            cur.execute("""
                INSERT INTO public.c1_event (
                    id, name, start_date, jurisdiction_id, dedupe_key,
                    classification, status, source,
                    state, created_at, updated_at,
                    extras, links, sources
                ) VALUES (
                    %s, %s, %s::date, %s, %s,
                    'committee-meeting', 'confirmed', 'bronze_meetings_promotion',
                    %s, now(), now(),
                    '{}'::jsonb, '[]'::jsonb, '[]'::jsonb
                )
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL
                DO UPDATE SET
                    -- preserve existing id; refresh metadata
                    name = EXCLUDED.name,
                    start_date = EXCLUDED.start_date,
                    updated_at = now()
                RETURNING id
            """, (g.event_id, g.derive_name(), g.key.date_iso,
                  g.key.jurisdiction_id, g.dedupe_key, g.state_code))
            inserted += 1 if cur.rowcount else 0
    conn.commit()
    return inserted


def _det_uuid(event_id: str, url: str, kind: str) -> str:
    """Deterministic UUID for child rows so re-runs don't duplicate."""
    return str(uuid.uuid5(_UUID_NS_EVENT_RESOURCE, f"{kind}|{event_id}|{url or ''}"))


def insert_resources(conn, groups: list[EventGroup], *, dry_run: bool) -> dict[str, int]:
    """Insert c1_eventdocument and c1_eventmedia rows for each group."""
    if dry_run:
        n_pdf = n_yt = n_other = 0
        for g in groups:
            for r in g.rows:
                if r.is_pdf:
                    n_pdf += 1
                elif r.is_youtube:
                    n_yt += 1
                elif r.is_other_stream:
                    n_other += 1
        return {"documents": n_pdf, "media_youtube": n_yt, "media_other_stream": n_other}

    counts = {"documents": 0, "media_youtube": 0, "media_other_stream": 0}
    with conn.cursor() as cur:
        for g in groups:
            for r in g.rows:
                if r.is_pdf and r.url:
                    classification = classify_pdf(r.doc_type, r.anchor, r.url)
                    doc_id = _det_uuid(g.event_id, r.url, "document")
                    links = (
                        '[{"url":' + _q(r.url) + ',"media_type":"application/pdf"'
                        + (',"text":' + _q(r.anchor) if r.anchor else "")
                        + (',"local_path":' + _q(r.local_path) if r.local_path else "")
                        + "}]"
                    )
                    cur.execute("""
                        INSERT INTO public.c1_eventdocument
                            (id, note, date, event_id, classification, links)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (id) DO NOTHING
                    """, (doc_id, (r.anchor or "")[:8000], g.key.date_iso,
                          g.event_id, classification, links))
                    if cur.rowcount:
                        counts["documents"] += 1
                elif r.is_youtube and r.url:
                    media_id = _det_uuid(g.event_id, r.url, "media_youtube")
                    links = '[{"url":' + _q(r.url) + ',"media_type":"video/youtube"}]'
                    cur.execute("""
                        INSERT INTO public.c1_eventmedia
                            (id, note, date, event_id, classification, links)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (id) DO NOTHING
                    """, (media_id, (r.anchor or "YouTube recording")[:300],
                          g.key.date_iso, g.event_id, "recording", links))
                    if cur.rowcount:
                        counts["media_youtube"] += 1
                elif r.is_other_stream and r.url:
                    media_id = _det_uuid(g.event_id, r.url, "media_other_stream")
                    links = '[{"url":' + _q(r.url) + '}]'
                    cur.execute("""
                        INSERT INTO public.c1_eventmedia
                            (id, note, date, event_id, classification, links)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (id) DO NOTHING
                    """, (media_id, (r.anchor or "Video stream")[:300],
                          g.key.date_iso, g.event_id, "recording", links))
                    if cur.rowcount:
                        counts["media_other_stream"] += 1
    conn.commit()
    return counts


def _q(s: str | None) -> str:
    """Inline JSON string-escaping for simple values inside jsonb literals."""
    if s is None:
        return "null"
    import json
    return json.dumps(s)


# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default="", help="Comma-separated state codes; empty = all")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    load_dotenv(_ROOT / ".env")
    db_url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not db_url:
        raise SystemExit("NEON_DATABASE_URL_DEV not set in .env")

    import psycopg2
    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip()) or None

    conn = psycopg2.connect(db_url)
    try:
        bronze = load_bronze_rows(conn, states)
        logger.info("Loaded %d bronze resource rows%s", len(bronze),
                    f" for {states}" if states else "")
        groups, datable, undatable = group_rows(bronze)
        logger.info("Datable rows: %d ; undatable (skipped): %d", datable, undatable)
        logger.info("Distinct (jurisdiction, date) meetings: %d", len(groups))

        if args.dry_run:
            print("\nDRY RUN — no DB writes. Sample of first 5 groups:")
            for g in groups[:5]:
                print(f"  {g.key.jurisdiction_id} {g.key.date_iso} \"{g.derive_name()[:60]}\" "
                      f"({len(g.rows)} resources)")
            counts = insert_resources(conn, groups, dry_run=True)
            print(f"\nWould upsert {len(groups)} c1_event rows")
            print(f"Would attach {counts['documents']} c1_eventdocument rows")
            print(f"Would attach {counts['media_youtube']} c1_eventmedia (youtube) rows")
            print(f"Would attach {counts['media_other_stream']} c1_eventmedia (other_stream) rows")
            return 0

        upserted = upsert_events(conn, groups, dry_run=False)
        logger.info("Upserted %d c1_event rows", upserted)
        counts = insert_resources(conn, groups, dry_run=False)
        print()
        print(f"c1_event rows upserted:                {upserted}")
        print(f"c1_eventdocument rows inserted:        {counts['documents']}")
        print(f"c1_eventmedia (YouTube) inserted:      {counts['media_youtube']}")
        print(f"c1_eventmedia (other-stream) inserted: {counts['media_other_stream']}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
