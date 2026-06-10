#!/usr/bin/env python3
"""
Repair ``youtube_channel_*`` on ``bronze_jurisdictions_{counties,municipalities}_scraped``.

Problem: bulk ``pattern_match`` handle guessing (@CalhounCounty, etc.) filled ~2k county
rows with wrong channels. This script:

1. **Clears** primary columns when selection is ``pattern_match`` (optional: only when no
   verified replacement exists).
2. **Restores** from verified sources (priority order):
   - ``data/cache/gemini_transcript_policy/{state}/{type}/{jurisdiction_id}/{UC…}/`` (had transcripts)
   - ``bronze.bronze_event_youtube`` (channel with most videos for that jurisdiction)
   - ``payload.youtube_channels`` entries whose ``discovery_method`` is not ``pattern_match``
3. Optionally **scrubs** ``pattern_match`` entries out of ``payload.youtube_channels``.

Dry-run by default.

Usage (repo root):

  .venv/bin/python packages/scrapers/src/scrapers/youtube/repair_scraped_youtube_channels.py --dry-run
  .venv/bin/python packages/scrapers/src/scrapers/youtube/repair_scraped_youtube_channels.py --apply
  .venv/bin/python packages/scrapers/src/scrapers/youtube/repair_scraped_youtube_channels.py --apply --states AL,GA
  .venv/bin/python packages/scrapers/src/scrapers/youtube/repair_scraped_youtube_channels.py --apply --clear-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
load_dotenv(_REPO / ".env")

_DEFAULT_GEMINI_CACHE = _REPO / "data" / "cache" / "gemini_transcript_policy"
_UC_RE = re.compile(r"^UC[\w-]{11,}$")
_GENERIC_HANDLE_RE = re.compile(
    r"youtube\.com/@([A-Za-z0-9_]+)$",
    re.I,
)


@dataclass
class VerifiedChannel:
    channel_id: str
    source: str
    transcript_count: int = 0
    event_count: int = 0

    @property
    def channel_url(self) -> str:
        return f"https://www.youtube.com/channel/{self.channel_id}"

    def score(self) -> tuple[int, int, int]:
        """Higher = prefer for primary."""
        source_rank = {
            "gemini_transcript_policy": 4,
            "bronze_event_youtube": 3,
            "payload_non_pattern_match": 2,
        }.get(self.source, 0)
        return (source_rank, self.transcript_count, self.event_count)


@dataclass
class RepairStats:
    scanned: int = 0
    cleared_pattern_match: int = 0
    restored: int = 0
    payload_scrubbed: int = 0
    skipped_has_verified: int = 0
    by_source: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _connect():
    import psycopg2

    url = os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("Set NEON_DATABASE_URL_DEV or DATABASE_URL in .env")
    return psycopg2.connect(url)


def _is_pattern_match(method: str | None) -> bool:
    return (method or "").strip().lower().startswith("pattern_match")


def _looks_generic_handle(url: str | None) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return False
    m = _GENERIC_HANDLE_RE.search(u.split("?")[0])
    if not m:
        return False
    handle = m.group(1).lower()
    # @{Name}County / @{Name}City without state suffix — common collision handles
    return handle.endswith("county") or handle.endswith("city") or handle.endswith("co")


def collect_verified_from_gemini_cache(
    cache_root: Path,
    *,
    min_transcripts: int = 1,
) -> dict[str, VerifiedChannel]:
    """Map ``jurisdiction_id`` → best UC folder under gemini cache."""
    by_jid: dict[str, list[VerifiedChannel]] = defaultdict(list)
    if not cache_root.is_dir():
        return {}

    for channel_dir in cache_root.glob("*/*/*/UC*/"):
        parts = channel_dir.relative_to(cache_root).parts
        if len(parts) < 4:
            continue
        jid, uc = parts[2], parts[3]
        if not _UC_RE.match(uc):
            continue
        n_tx = len(list((channel_dir / "01_transcripts").glob("*.json")))
        if n_tx < min_transcripts:
            continue
        by_jid[jid].append(
            VerifiedChannel(
                channel_id=uc,
                source="gemini_transcript_policy",
                transcript_count=n_tx,
            )
        )

    out: dict[str, VerifiedChannel] = {}
    for jid, rows in by_jid.items():
        out[jid] = max(rows, key=lambda r: r.score())
    return out


def collect_verified_from_bronze_events(conn) -> dict[str, VerifiedChannel]:
    """Map canonical ``jurisdiction_id`` → channel with most cataloged videos."""
    from core_lib.jurisdictions.jurisdiction_id import resolve_canonical_jurisdiction_id
    from scripts.discovery.youtube_channel_verification import (
        qualifies_for_bronze_jurisdiction_youtube,
    )

    sql = """
        SELECT
            y.jurisdiction_id,
            y.channel_id,
            COUNT(*) AS n,
            MAX(y.jurisdiction_name) AS jurisdiction_name,
            MAX(y.state_code) AS state_code,
            MAX(y.jurisdiction_type) AS jurisdiction_type,
            MAX(bc.channel_title) AS channel_title,
            MAX(bc.channel_description) AS channel_description
        FROM bronze.bronze_event_youtube y
        LEFT JOIN bronze.bronze_events_channels bc ON bc.channel_id = y.channel_id
        WHERE y.channel_id IS NOT NULL AND y.channel_id LIKE 'UC%%'
        GROUP BY y.jurisdiction_id, y.channel_id
        ORDER BY y.jurisdiction_id, n DESC
    """
    by_jid: dict[str, list[VerifiedChannel]] = defaultdict(list)
    with conn.cursor() as cur:
        cur.execute(sql)
        for jid_raw, cid, n, jname, state, jtype, title, desc in cur.fetchall():
            canon = resolve_canonical_jurisdiction_id(str(jid_raw)) or str(jid_raw)
            row = {
                "youtube_channel_url": f"https://www.youtube.com/channel/{cid}",
                "youtube_channel_id": str(cid).strip(),
                "channel_title": title,
                "channel_description": desc,
                "discovery_method": "verified_bronze_event_youtube",
                "official_meeting_confidence": 0.55,
                "back_links_to_jurisdiction_website": False,
            }
            if not qualifies_for_bronze_jurisdiction_youtube(
                row,
                jurisdiction_type=str(jtype or "county"),
                jurisdiction_name=str(jname or canon),
                jurisdiction_state_code=str(state or ""),
                jurisdiction_homepage="",
            ):
                continue
            by_jid[canon].append(
                VerifiedChannel(
                    channel_id=str(cid).strip(),
                    source="bronze_event_youtube",
                    event_count=int(n),
                )
            )
    return {jid: max(rows, key=lambda r: r.score()) for jid, rows in by_jid.items()}


def _best_non_pattern_from_payload(payload: dict | None) -> VerifiedChannel | None:
    from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel

    channels = []
    for ch in (payload or {}).get("youtube_channels") or []:
        if not isinstance(ch, dict):
            continue
        method = str(ch.get("discovery_method") or "")
        if _is_pattern_match(method):
            continue
        url = (ch.get("channel_url") or ch.get("youtube_channel_url") or "").strip()
        cid = (ch.get("channel_id") or ch.get("youtube_channel_id") or "").strip()
        if not cid.startswith("UC") and "/channel/UC" in url:
            m = re.search(r"(UC[\w-]{11,})", url)
            cid = m.group(1) if m else ""
        if cid.startswith("UC"):
            channels.append(ch)
    if not channels:
        return None
    url, method, conf = pick_primary_youtube_channel(channels)
    if not url:
        return None
    for ch in channels:
        u = (ch.get("channel_url") or ch.get("youtube_channel_url") or "").strip()
        if u == url:
            cid = (ch.get("channel_id") or "").strip()
            if not cid.startswith("UC"):
                m = re.search(r"(UC[\w-]{11,})", url)
                cid = m.group(1) if m else ""
            if cid.startswith("UC"):
                return VerifiedChannel(
                    channel_id=cid,
                    source="payload_non_pattern_match",
                )
    m = re.search(r"(UC[\w-]{11,})", url)
    if m:
        return VerifiedChannel(channel_id=m.group(1), source="payload_non_pattern_match")
    return None


def merge_verified(
    *maps: dict[str, VerifiedChannel],
) -> dict[str, VerifiedChannel]:
    """Later maps override earlier only if higher score."""
    merged: dict[str, VerifiedChannel] = {}
    for m in maps:
        for jid, row in m.items():
            prev = merged.get(jid)
            if prev is None or row.score() > prev.score():
                merged[jid] = row
    return merged


def scrub_payload_pattern_match(payload: dict | None) -> tuple[dict, bool]:
    if not payload:
        return {}, False
    out = dict(payload)
    raw = out.get("youtube_channels") or []
    if not isinstance(raw, list):
        return out, False
    kept = [
        ch
        for ch in raw
        if isinstance(ch, dict)
        and not _is_pattern_match(str(ch.get("discovery_method") or ""))
    ]
    changed = len(kept) != len(raw)
    if changed:
        out["youtube_channels"] = kept
        out["pattern_match_channels_removed"] = len(raw) - len(kept)
    return out, changed


def load_scraped_rows(
    conn,
    *,
    table: str,
    states: list[str] | None,
) -> list[dict[str, Any]]:
    state_clause = ""
    params: list[Any] = []
    if states:
        state_clause = " AND upper(btrim(usps::text)) = ANY(%s)"
        params.append([s.upper() for s in states])

    sql = f"""
        SELECT geoid, usps, jurisdiction_id,
               youtube_channel_url, youtube_channel_id,
               youtube_channel_selection_method,
               youtube_channel_selection_confidence,
               payload
        FROM {table}
        WHERE TRUE {state_clause}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def repair_table(
    conn,
    *,
    table: str,
    jurisdiction_type: str,
    verified_by_jid: dict[str, VerifiedChannel],
    verified_by_geoid: dict[str, VerifiedChannel],
    states: list[str] | None,
    apply: bool,
    clear_only: bool,
    scrub_payload: bool,
    clear_without_replacement: bool,
    stats: RepairStats,
) -> None:
    import psycopg2.extras

    rows = load_scraped_rows(conn, table=table, states=states)
    updates: list[tuple] = []

    for row in rows:
        stats.scanned += 1
        geoid = str(row["geoid"] or "").strip()
        jid = str(row["jurisdiction_id"] or "").strip()
        method = str(row["youtube_channel_selection_method"] or "")
        url = str(row["youtube_channel_url"] or "").strip()
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload = payload if isinstance(payload, dict) else {}

        verified = verified_by_jid.get(jid) or verified_by_geoid.get(geoid)
        if not verified:
            payload_best = _best_non_pattern_from_payload(payload)
            if payload_best:
                verified = payload_best

        is_bad_primary = _is_pattern_match(method)
        if not is_bad_primary and url and _looks_generic_handle(url):
            is_bad_primary = True

        new_url = None
        new_cid = None
        new_method = None
        new_conf = None
        new_payload = payload

        if scrub_payload:
            new_payload, payload_changed = scrub_payload_pattern_match(payload)
            if payload_changed:
                stats.payload_scrubbed += 1

        if is_bad_primary or clear_only:
            if verified and not clear_only:
                new_url = verified.channel_url
                new_cid = verified.channel_id
                new_method = f"verified_{verified.source}"
                new_conf = 0.95 if verified.source == "gemini_transcript_policy" else 0.55
                stats.restored += 1
                stats.by_source[verified.source] += 1
            elif clear_without_replacement or clear_only or not verified:
                if url or row.get("youtube_channel_id"):
                    stats.cleared_pattern_match += 1
                new_url = None
                new_cid = None
                new_method = None
                new_conf = None
            else:
                stats.skipped_has_verified += 1
        elif verified and not url:
            # empty primary but we have verified cache/events
            new_url = verified.channel_url
            new_cid = verified.channel_id
            new_method = f"verified_{verified.source}"
            new_conf = 0.95 if verified.source == "gemini_transcript_policy" else 0.55
            stats.restored += 1
            stats.by_source[verified.source] += 1

        if not apply:
            continue

        updates.append(
            (
                new_url,
                new_cid,
                new_method,
                new_conf,
                psycopg2.extras.Json(new_payload),
                geoid,
            )
        )

    if apply and updates:
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                UPDATE {table}
                SET youtube_channel_url = %s,
                    youtube_channel_id = %s,
                    youtube_channel_selection_method = %s,
                    youtube_channel_selection_confidence = %s,
                    payload = %s,
                    discovered_at = NOW()
                WHERE geoid = %s
                """,
                updates,
            )
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry-run (default)")
    parser.add_argument("--states", default="", help="Comma-separated USPS filter")
    parser.add_argument("--clear-only", action="store_true", help="Null pattern_match primaries; do not restore")
    parser.add_argument(
        "--no-scrub-payload",
        action="store_true",
        help="Leave payload.youtube_channels unchanged",
    )
    parser.add_argument(
        "--gemini-cache",
        default=str(_DEFAULT_GEMINI_CACHE),
        help="gemini_transcript_policy root",
    )
    parser.add_argument(
        "--min-gemini-transcripts",
        type=int,
        default=1,
        help="Minimum 01_transcripts JSON files to trust a gemini UC folder",
    )
    parser.add_argument(
        "--counties-only",
        action="store_true",
        help="Only repair bronze_jurisdictions_counties_scraped",
    )
    parser.add_argument(
        "--municipalities-only",
        action="store_true",
        help="Only repair bronze_jurisdictions_municipalities_scraped",
    )
    args = parser.parse_args()
    apply = bool(args.apply)
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] or None

    gemini = collect_verified_from_gemini_cache(
        Path(args.gemini_cache),
        min_transcripts=args.min_gemini_transcripts,
    )
    print(f"Verified channels from gemini cache: {len(gemini)}")

    conn = _connect()
    try:
        bronze = collect_verified_from_bronze_events(conn)
        print(f"Verified channels from bronze_event_youtube: {len(bronze)}")

        verified_jid = merge_verified(gemini, bronze)
        # Also index by geoid via int_jurisdictions
        verified_geoid: dict[str, VerifiedChannel] = {}
        with conn.cursor() as cur:
            if states:
                cur.execute(
                    """
                    SELECT jurisdiction_id, geoid
                    FROM intermediate.int_jurisdictions
                    WHERE state_code = ANY(%s)
                    """,
                    ([s.upper() for s in states],),
                )
            else:
                cur.execute(
                    "SELECT jurisdiction_id, geoid FROM intermediate.int_jurisdictions"
                )
            for jid, geoid in cur.fetchall():
                v = verified_jid.get(str(jid))
                if v and geoid:
                    verified_geoid[str(geoid)] = v

        stats = RepairStats()
        tables: list[tuple[str, str]] = []
        if not args.municipalities_only:
            tables.append(
                ("bronze.bronze_jurisdictions_counties_scraped", "county")
            )
        if not args.counties_only:
            tables.append(
                ("bronze.bronze_jurisdictions_municipalities_scraped", "municipality")
            )

        for tbl, _jtype in tables:
            print(f"\n=== {tbl} ({'APPLY' if apply else 'DRY-RUN'}) ===")
            repair_table(
                conn,
                table=tbl,
                jurisdiction_type=_jtype,
                verified_by_jid=verified_jid,
                verified_by_geoid=verified_geoid,
                states=states,
                apply=apply,
                clear_only=args.clear_only,
                scrub_payload=not args.no_scrub_payload,
                clear_without_replacement=True,
                stats=stats,
            )

        print("\n--- Summary ---")
        print(f"Rows scanned:              {stats.scanned}")
        print(f"Cleared pattern_match:     {stats.cleared_pattern_match}")
        print(f"Restored from verified:    {stats.restored}")
        for src, n in sorted(stats.by_source.items()):
            print(f"  via {src}: {n}")
        print(f"Payload arrays scrubbed:   {stats.payload_scrubbed}")
        if not apply:
            print("\nRe-run with --apply to write changes.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
