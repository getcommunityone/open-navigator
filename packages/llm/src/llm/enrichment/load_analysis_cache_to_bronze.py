#!/usr/bin/env python3
"""
Backfill bronze.bronze_events_analysis_ai from the on-disk Gemini analysis cache.

The analyze step (``load_meeting_transcripts``) writes each analysis both to the
database and to ``data/cache/gemini_transcript_policy/<STATE>/.../02_analysis/<meeting>.json``.
When the warehouse is rebuilt the cache survives but the table is empty, so the
dbt bronze extraction (``bronze_*_from_ai``) has nothing to read. This loader
re-ingests the cached analysis JSON into ``bronze.bronze_events_analysis_ai``
*without* re-calling Gemini, so the extraction step can run from cache.

Mapping a cache file → a table row:
  - The structured analysis is the ``02_analysis/<meeting_id>.json`` file itself.
  - Per-meeting metadata (video_id, video_url, gemini_model, generated_at) lives in
    the sibling ``04_runs/<meeting_id>.meta.json``.
  - ``event_id`` is resolved from ``bronze.bronze_event_youtube`` (which carries
    both ``video_id`` and ``event_id``, one row per scraped video) by matching the
    YouTube ``video_id``.

Rows are upserted on ``(event_id, analysis_type, ai_model)`` — the same conflict
target ``load_meeting_transcripts.save_analysis`` uses — so a backfill followed by
a live analyze run stay consistent.

Usage:
    python -m llm.enrichment.load_analysis_cache_to_bronze                 # all states
    python -m llm.enrichment.load_analysis_cache_to_bronze --states AL,GA  # specific states
    python -m llm.enrichment.load_analysis_cache_to_bronze --dry-run       # no DB writes
    python -m llm.enrichment.load_analysis_cache_to_bronze --limit 50      # cap files (debug)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
from loguru import logger

from llm.enrichment.analysis_load_gate import (
    DEFAULT_MIN_MEETING_P,
    SKIP_REASONS,
    decide_skip,
    fetch_video_info,
    meta_matches_file,
    tier_from_path,
)
from llm.prompt_version import prompt_version_from_meta

PROJECT_ROOT = Path(__file__).parents[5]
CACHE_ROOT = PROJECT_ROOT / "data" / "cache" / "gemini_transcript_policy"

DATABASE_URL = os.getenv(
    "NEON_DATABASE_URL_DEV",
    "postgresql://postgres:%s@localhost:5433/open_navigator"
    % os.getenv("POSTGRES_PASSWORD", "password"),
)

ANALYSIS_TYPE = "policy_frame_analysis"
DEFAULT_AI_MODEL = "gemini-2.5-flash-lite"

_VIDEO_ID_RE = re.compile(r"[?&]v=([^&]+)")


def extract_video_id(video_url: Optional[str]) -> Optional[str]:
    """Pull the 11-char YouTube id out of a watch URL (mirrors save_analysis)."""
    if not video_url:
        return None
    m = _VIDEO_ID_RE.search(video_url)
    if m:
        return m.group(1)
    # Bare id fallback
    return video_url if re.fullmatch(r"[\w-]{6,20}", video_url) else None


def discover_analysis_files(cache_root: Path, states: Optional[list[str]]) -> list[Path]:
    """All ``*/02_analysis/*.json`` files, optionally filtered to <STATE> top dirs."""
    files: list[Path] = []
    for path in sorted(cache_root.glob("*/*/*/*/02_analysis/*.json")):
        if path.name.startswith("_"):
            continue
        state_code = path.relative_to(cache_root).parts[0].upper()
        if states and state_code not in states:
            continue
        files.append(path)
    return files


def load_meta(analysis_path: Path) -> Optional[dict[str, Any]]:
    """Read the sibling ``04_runs/<stem>.meta.json`` for a given analysis file."""
    meta_path = analysis_path.parent.parent / "04_runs" / f"{analysis_path.stem}.meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Unreadable meta {}: {}", meta_path.name, exc)
        return None


def build_video_to_event_map(conn) -> dict[str, int]:
    """Map YouTube video_id → civic_event.legacy_id via the promoted civic_event rows.

    ``bronze.bronze_events_analysis_ai.event_id`` has a FK to
    ``public.civic_event(legacy_id)``, so the loaded event_id MUST be a legacy_id.
    A YouTube video is promoted into civic_event (see
    ``ingestion.youtube.promote_to_c1_event``) keyed on
    ``dedupe_key = 'youtube|<video_id>'``, which makes this an exact, parse-free
    reverse lookup. (An earlier version mapped via ``bronze_event_youtube.event_id``,
    but those synthetic ids are a different id space than ``legacy_id`` — zero
    overlap — so every FK insert was rejected and the table stayed empty.)
    """
    mapping: dict[str, int] = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT split_part(dedupe_key, '|', 2) AS video_id, legacy_id "
                "FROM gold.civic_event "
                "WHERE dedupe_key LIKE 'youtube|%' AND legacy_id IS NOT NULL"
            )
            for video_id, legacy_id in cur.fetchall():
                if video_id:
                    mapping[video_id] = legacy_id
    except psycopg2.Error as exc:
        conn.rollback()
        logger.error(
            "Could not read public.civic_event youtube rows ({}). Have you run "
            "`python -m ingestion.youtube.promote_to_c1_event` first? "
            "event_id resolution unavailable.", exc
        )
    return mapping


def _parse_generated_at(meta: Optional[dict[str, Any]]) -> Optional[datetime]:
    if not meta:
        return None
    raw = meta.get("generated_at")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None


def _timeline_from_analysis(analysis: dict[str, Any]) -> Optional[str]:
    decisions = analysis.get("decisions") or []
    if decisions and isinstance(decisions[0], dict):
        return decisions[0].get("diagram_timeline")
    return None


def upsert_row(conn, *, event_id: int, video_id: str, ai_model: str,
               prompt_version: Optional[str] = None,
               raw_response: str, analysis: dict[str, Any],
               summary_text: Optional[str], timeline_mermaid: Optional[str],
               created_at: Optional[datetime]) -> None:
    """Upsert one analysis into bronze_events_analysis_ai (mirrors save_analysis)."""
    insert_sql = """
    INSERT INTO bronze.bronze_events_analysis_ai (
        event_id, video_id, analysis_type, ai_model, prompt_version,
        raw_response, structured_analysis, summary_text, timeline_mermaid,
        processing_time_seconds, tokens_used, error_message, created_at, updated_at
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        NULL, NULL, NULL, COALESCE(%s, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP
    )
    ON CONFLICT (event_id, analysis_type, ai_model)
    DO UPDATE SET
        video_id = EXCLUDED.video_id,
        prompt_version = EXCLUDED.prompt_version,
        raw_response = EXCLUDED.raw_response,
        structured_analysis = EXCLUDED.structured_analysis,
        summary_text = EXCLUDED.summary_text,
        timeline_mermaid = EXCLUDED.timeline_mermaid,
        updated_at = CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(insert_sql, (
            event_id, video_id, ANALYSIS_TYPE, ai_model, prompt_version,
            raw_response, json.dumps(analysis), summary_text, timeline_mermaid,
            created_at,
        ))


def _empty_stats() -> dict[str, int]:
    stats = {
        "discovered": 0, "loaded": 0, "loaded_light": 0, "loaded_full": 0,
        "skipped_no_meta": 0, "skipped_meta_mismatch": 0, "skipped_tier_mismatch": 0,
        "skipped_no_video": 0, "skipped_no_event": 0, "skipped_other_tier": 0,
        "unchecked_no_bronze_row": 0, "errors": 0,
    }
    for reason in SKIP_REASONS:
        stats[f"skipped_{reason}"] = 0
    return stats


def run(cache_root: Path = CACHE_ROOT, database_url: str = DATABASE_URL,
        states: Optional[list[str]] = None, dry_run: bool = False,
        limit: Optional[int] = None, tier: str = "both",
        min_meeting_p: float = DEFAULT_MIN_MEETING_P, gate: bool = True) -> dict[str, int]:
    """Load saved analyses into ``bronze_events_analysis_ai``. Reads files only: never moves,
    renames or deletes one. ``gate=False`` turns the non-government skip rules off."""
    logger.info("=" * 70)
    logger.info("CACHE → bronze_events_analysis_ai backfill")
    logger.info("  cache root : {}", cache_root)
    logger.info("  states     : {}", ",".join(states) if states else "ALL")
    logger.info("  tier       : {}", tier)
    logger.info("  gate       : {}", f"on (keep-score floor {min_meeting_p})" if gate else "OFF")
    logger.info("  dry-run    : {}", dry_run)
    logger.info("=" * 70)

    stats = _empty_stats()
    if not cache_root.exists():
        logger.error("Cache root not found: {}", cache_root)
        return stats

    files = discover_analysis_files(cache_root, states)
    if limit:
        files = files[:limit]
    stats["discovered"] = len(files)
    logger.info("Discovered {:,} analysis files", len(files))

    # Pass 1: read each file's own metadata and decide which tier and video it is.
    entries: list[dict[str, Any]] = []
    for path in files:
        file_tier = tier_from_path(path)
        if tier != "both" and file_tier != tier:
            stats["skipped_other_tier"] += 1
            continue
        try:
            analysis = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Unreadable analysis {}: {}", path.name, exc)
            stats["errors"] += 1
            continue
        meta = load_meta(path)
        if meta is None:
            stats["skipped_no_meta"] += 1
            continue
        if not meta_matches_file(meta, path):
            # A shared, pre-#796 metadata file written for the other tier's analysis.
            stats["skipped_meta_mismatch"] += 1
            logger.warning("Metadata for {} belongs to a different analysis file; skipped", path.name)
            continue
        recorded_tier = meta.get("analysis_tier")
        if recorded_tier and recorded_tier != file_tier:
            stats["skipped_tier_mismatch"] += 1
            continue
        video_id = meta.get("video_id") or extract_video_id(meta.get("video_url"))
        if not video_id:
            stats["skipped_no_video"] += 1
            continue
        entries.append({"path": path, "tier": file_tier, "analysis": analysis, "meta": meta, "video_id": video_id})

    conn = psycopg2.connect(database_url)
    try:
        video_to_event = build_video_to_event_map(conn)
        logger.info("Resolved {:,} video_id → civic_event.legacy_id mappings from promoted civic_event rows", len(video_to_event))

        info: dict[str, dict[str, Any]] = {}
        low_keep: set[str] = set()
        if gate:
            info = fetch_video_info(conn, [e["video_id"] for e in entries])
            from llm.typesafe.screen_transcripts import jev_skip_meeting_video_ids

            low_keep = jev_skip_meeting_video_ids(database_url, min_meeting_p)

        # Pass 2: skip what the gate rejects, load the rest.
        for e in entries:
            path, video_id, meta, analysis = e["path"], e["video_id"], e["meta"], e["analysis"]
            if gate:
                row = info.get(video_id)
                if row is None:
                    stats["unchecked_no_bronze_row"] += 1
                reason = decide_skip(row, video_id in low_keep)
                if reason:
                    stats[f"skipped_{reason}"] += 1
                    logger.debug("Skip {} ({})", path.name, reason)
                    continue

            event_id = video_to_event.get(video_id)
            if event_id is None:
                stats["skipped_no_event"] += 1
                logger.debug("No civic_event for video_id={} ({})", video_id, path.name)
                continue

            ai_model = meta.get("gemini_model") or DEFAULT_AI_MODEL
            from llm.gemini.meeting_date_qa import qa_recorded_video_meeting_date

            analysis, date_warnings = qa_recorded_video_meeting_date(
                analysis,
                video_id=video_id,
                title=str(meta.get("title") or ""),
                published_at=meta.get("published_at"),
            )
            for w in date_warnings:
                logger.warning("{} ({})", w, path.name)
            summary_text = (analysis.get("meeting") or {}).get("meeting_summary")
            timeline_mermaid = _timeline_from_analysis(analysis)
            created_at = _parse_generated_at(meta)
            # raw_response is NOT NULL-cleaned downstream; the cache has no separate
            # raw text, so persist the structured JSON text as the faithful response.
            raw_response = path.read_text()

            if dry_run:
                stats["loaded"] += 1
                stats[f"loaded_{e['tier']}"] += 1
                continue

            try:
                upsert_row(
                    conn, event_id=event_id, video_id=video_id, ai_model=ai_model,
                    prompt_version=prompt_version_from_meta(meta),
                    raw_response=raw_response, analysis=analysis,
                    summary_text=summary_text, timeline_mermaid=timeline_mermaid,
                    created_at=created_at,
                )
                conn.commit()
                stats["loaded"] += 1
                stats[f"loaded_{e['tier']}"] += 1
            except psycopg2.Error as exc:
                conn.rollback()
                logger.error("Upsert failed for {} (event_id={}): {}", path.name, event_id, exc)
                stats["errors"] += 1
    finally:
        conn.close()

    skipped_gate = sum(stats[f"skipped_{r}"] for r in SKIP_REASONS)
    logger.success(
        "Backfill done: loaded={loaded:,} of {discovered:,} (light {loaded_light:,}, full {loaded_full:,}); "
        "skipped by gate={g:,} (excluded={ex:,}, junk={ju:,}, non-meeting={nm:,}, low keep-score={lk:,}); "
        "no_event={skipped_no_event:,}, no_meta={skipped_no_meta:,}, meta_mismatch={skipped_meta_mismatch:,}, "
        "no_video={skipped_no_video:,}, errors={errors:,}",
        g=skipped_gate, ex=stats["skipped_policy_excluded"], ju=stats["skipped_junk_channel"],
        nm=stats["skipped_non_meeting_type"], lk=stats["skipped_low_keep_score"], **stats,
    )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill bronze_events_analysis_ai from the analysis cache (no Gemini calls)",
    )
    parser.add_argument("--states", type=str, metavar="AL,GA",
                        help="Comma-separated state codes to load (default: all)")
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT,
                        help="Override the gemini_transcript_policy cache root")
    parser.add_argument("--database-url", type=str, default=DATABASE_URL)
    parser.add_argument("--dry-run", action="store_true",
                        help="Discover and resolve, but do not write to the DB")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap the number of files processed (debug)")
    parser.add_argument("--tier", choices=("light", "full", "both"), default="both",
                        help="Which analyses to load (default: both; full files end in _full.json)")
    parser.add_argument("--min-meeting-p", type=float, default=DEFAULT_MIN_MEETING_P,
                        help="Skip videos whose Jev keep-score P(government_meeting)+P(town_hall) is below this")
    parser.add_argument("--no-gate", action="store_true",
                        help="Load everything: turn off the non-government skip rules")
    args = parser.parse_args()

    states = [s.strip().upper() for s in args.states.split(",")] if args.states else None

    stats = run(
        cache_root=args.cache_root, database_url=args.database_url,
        states=states, dry_run=args.dry_run, limit=args.limit,
        tier=args.tier, min_meeting_p=args.min_meeting_p, gate=not args.no_gate,
    )
    # Non-zero exit only on hard errors; unmatched events are expected/benign.
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
