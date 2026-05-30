#!/usr/bin/env python3
"""
Persist Part 1 policy analysis legislation links to bronze Postgres tables.

Requires migration 018_policy_legislation_linkage.sql applied on the target DB.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger


def database_url(explicit: Optional[str] = None) -> str:
    load_dotenv()
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def ensure_legislation_tables(conn) -> None:
    """Apply 018 migration SQL if tables missing (idempotent)."""
    migration = (
        Path(__file__).resolve().parents[5]
        / "packages/hosting/scripts/neon/migrations/018_policy_legislation_linkage.sql"
    )
    if migration.is_file():
        sql = migration.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        return
    logger.warning("Migration file not found: {}", migration)


def _collect_primary_leg_ids(analysis: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    seen: set[str] = set()
    for leg in analysis.get("legislation") or []:
        if isinstance(leg, dict) and leg.get("leg_id"):
            lid = str(leg["leg_id"])
            if lid not in seen:
                seen.add(lid)
                ids.append(lid)
    for bucket in ("decisions", "uncontested_items"):
        for row in analysis.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            for lid in row.get("legislation_refs") or []:
                s = str(lid).strip()
                if s and s not in seen:
                    seen.add(s)
                    ids.append(s)
    return ids


def persist_policy_analysis_bronze(
    analysis: Dict[str, Any],
    *,
    video_id: str,
    source_event_id: int,
    source_ai_model: str,
    database_url_override: Optional[str] = None,
    analysis_cache_path: Optional[str] = None,
) -> Dict[str, int]:
    """
    Upsert bronze.bronze_bills, bronze_meeting_item_legislation, bronze_policy_decisions;
    set bronze_events_youtube.primary_leg_ids for the video.
    """
    import psycopg2
    from psycopg2.extras import Json

    stats = {"bills": 0, "item_links": 0, "decisions": 0, "youtube_updated": 0}
    vid = (video_id or "").strip()
    if not vid or not source_event_id:
        logger.warning("persist skipped: missing video_id or source_event_id")
        return stats

    url = database_url(database_url_override)
    now = datetime.now(timezone.utc)
    primary_leg_ids = _collect_primary_leg_ids(analysis)

    conn = psycopg2.connect(url)
    try:
        ensure_legislation_tables(conn)
        with conn.cursor() as cur:
            for leg in analysis.get("legislation") or []:
                if not isinstance(leg, dict) or not leg.get("leg_id"):
                    continue
                leg_id = str(leg["leg_id"])
                key = f"{source_event_id}_{leg_id}"
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_bills (
                        source_event_id_leg_id, source_event_id, video_id,
                        source_ai_model, leg_id, leg_type, official_number,
                        title, jurisdiction, year, status, relevance, url,
                        agenda_labels, analysis_cache_path, extracted_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (source_event_id, leg_id, source_ai_model) DO UPDATE SET
                        video_id = EXCLUDED.video_id,
                        leg_type = EXCLUDED.leg_type,
                        official_number = EXCLUDED.official_number,
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        relevance = EXCLUDED.relevance,
                        analysis_cache_path = EXCLUDED.analysis_cache_path,
                        extracted_at = EXCLUDED.extracted_at
                    """,
                    (
                        key,
                        source_event_id,
                        vid,
                        source_ai_model,
                        leg_id,
                        leg.get("leg_type"),
                        leg.get("official_number"),
                        leg.get("title"),
                        (analysis.get("meeting") or {}).get("jurisdiction"),
                        leg.get("year"),
                        leg.get("status"),
                        leg.get("relevance"),
                        leg.get("url"),
                        Json([]),
                        analysis_cache_path,
                        now,
                    ),
                )
                stats["bills"] += 1

            for entry in analysis.get("agenda_legislation_map") or []:
                if not isinstance(entry, dict):
                    continue
                item_id = str(entry.get("item_id") or "").strip()
                if not item_id:
                    continue
                kind = str(entry.get("item_kind") or "uncontested")
                if kind not in ("uncontested", "decision"):
                    kind = "uncontested"
                for leg_id in entry.get("leg_ids") or []:
                    lid = str(leg_id).strip()
                    if not lid:
                        continue
                    cur.execute(
                        """
                        INSERT INTO bronze.bronze_meeting_item_legislation (
                            source_event_id, video_id, source_ai_model,
                            item_id, item_kind, leg_id, agenda_labels, headline, extracted_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, item_id, leg_id, source_ai_model)
                        DO UPDATE SET
                            agenda_labels = EXCLUDED.agenda_labels,
                            headline = EXCLUDED.headline,
                            extracted_at = EXCLUDED.extracted_at
                        """,
                        (
                            source_event_id,
                            vid,
                            source_ai_model,
                            item_id,
                            kind,
                            lid,
                            Json(entry.get("agenda_labels") or []),
                            entry.get("headline"),
                            now,
                        ),
                    )
                    stats["item_links"] += 1

            for row in analysis.get("decisions") or []:
                if not isinstance(row, dict):
                    continue
                did = str(row.get("decision_id") or "").strip()
                if not did:
                    continue
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_policy_decisions (
                        source_event_id, video_id, source_ai_model, decision_id,
                        subject_id, headline, outcome, legislation_refs, vote_tally, extracted_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_event_id, decision_id, source_ai_model) DO UPDATE SET
                        subject_id = EXCLUDED.subject_id,
                        headline = EXCLUDED.headline,
                        outcome = EXCLUDED.outcome,
                        legislation_refs = EXCLUDED.legislation_refs,
                        vote_tally = EXCLUDED.vote_tally,
                        extracted_at = EXCLUDED.extracted_at
                    """,
                    (
                        source_event_id,
                        vid,
                        source_ai_model,
                        did,
                        row.get("subject_id"),
                        row.get("headline"),
                        row.get("outcome"),
                        Json(row.get("legislation_refs") or []),
                        Json(row.get("vote_tally")),
                        now,
                    ),
                )
                stats["decisions"] += 1

            cur.execute(
                """
                UPDATE bronze.bronze_events_youtube
                SET primary_leg_ids = %s::jsonb,
                    legislation_validated_at = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE video_id = %s
                """,
                (json.dumps(primary_leg_ids), now, vid),
            )
            if cur.rowcount:
                stats["youtube_updated"] = 1

        conn.commit()
    finally:
        conn.close()

    logger.info("Persisted legislation bronze for {}: {}", vid, stats)
    return stats


_POLICY_EVENT_STAGES = {"analysis", "report"}


def record_policy_event(
    video_id: str,
    *,
    stage: str,
    ok: bool,
    path: Optional[str] = None,
    error: Optional[str] = None,
    database_url_override: Optional[str] = None,
) -> bool:
    """
    Best-effort: stamp a policy ``analysis``/``report`` outcome onto the bronze event row.

    On success sets ``policy_<stage>_at = now()`` (+ path) and clears the error; on
    failure sets ``policy_<stage>_error`` and leaves the success timestamp untouched.
    Keyed by ``video_id`` (same as ``persist_policy_analysis_bronze``). Swallows all
    errors so it never breaks the pipeline. Returns True when a row was updated.
    """
    import psycopg2

    vid = (video_id or "").strip()
    if not vid:
        return False
    if stage not in _POLICY_EVENT_STAGES:
        logger.warning("record_policy_event: unknown stage {!r}", stage)
        return False

    if ok:
        set_clause = (
            f"policy_{stage}_at = %s, "
            f"policy_{stage}_path = %s, "
            f"policy_{stage}_error = NULL, "
            "last_updated = CURRENT_TIMESTAMP"
        )
        params = [datetime.now(timezone.utc), path, vid]
    else:
        set_clause = (
            f"policy_{stage}_error = %s, last_updated = CURRENT_TIMESTAMP"
        )
        params = [(error or "unknown error")[:2000], vid]

    try:
        conn = psycopg2.connect(database_url(database_url_override))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE bronze.bronze_events_youtube SET {set_clause} WHERE video_id = %s",
                    params,
                )
                updated = bool(cur.rowcount)
            conn.commit()
        finally:
            conn.close()
        if not updated:
            logger.debug(
                "record_policy_event: no bronze row for video_id={} (stage={})", vid, stage
            )
        return updated
    except Exception as exc:  # never break the pipeline on a tracking write
        logger.warning("record_policy_event failed for {} ({}): {}", vid, stage, exc)
        return False


def resolve_event_id_for_video(database_url_str: str, video_id: str) -> Optional[int]:
    import psycopg2

    conn = psycopg2.connect(database_url_str)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_id FROM bronze.bronze_events_youtube WHERE video_id = %s LIMIT 1",
                (video_id.strip(),),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
    finally:
        conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_json", type=Path, help="Path to 02_analysis/*.json")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--event-id", type=int, default=0)
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--database-url", default="")
    args = parser.parse_args()

    data = json.loads(args.analysis_json.read_text(encoding="utf-8"))
    eid = args.event_id or resolve_event_id_for_video(
        database_url(args.database_url), args.video_id
    )
    if not eid:
        raise SystemExit(f"No event_id for video {args.video_id}")

    persist_policy_analysis_bronze(
        data,
        video_id=args.video_id,
        source_event_id=eid,
        source_ai_model=args.model,
        database_url_override=args.database_url or None,
        analysis_cache_path=str(args.analysis_json.resolve()),
    )


if __name__ == "__main__":
    main()
