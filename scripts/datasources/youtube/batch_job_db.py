"""
Postgres persistence for YouTube pipeline batch jobs (real-time dashboard).

Table: ``bronze.youtube_batch_job_runs`` (migration 073).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json, RealDictCursor

from scripts.datasources.youtube.batch_job_status import BatchJob, BatchJobStore, list_batches

logger = logging.getLogger(__name__)

_ENSURED = False


def _use_db() -> bool:
    return os.getenv("BATCH_JOBS_USE_DB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def get_db_connection():
    import psycopg2

    from scripts.database.target_database_url import resolve_target_database_url

    url = resolve_target_database_url()
    for bad in ("&channel_binding=require", "channel_binding=require&", "channel_binding=require"):
        url = url.replace(bad, "")
    url = url.replace("&&", "&").rstrip("?&")
    return psycopg2.connect(url)


def ensure_batch_job_tables(conn: Any) -> None:
    global _ENSURED
    if _ENSURED:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bronze.youtube_batch_job_runs (
                batch_id    VARCHAR(128) PRIMARY KEY,
                step        VARCHAR(32)  NOT NULL,
                status      VARCHAR(32)  NOT NULL,
                started_at  TIMESTAMPTZ,
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMPTZ,
                config      JSONB        NOT NULL DEFAULT '{}',
                summary     JSONB        NOT NULL DEFAULT '{}',
                payload     JSONB        NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_youtube_batch_job_runs_updated
                ON bronze.youtube_batch_job_runs (updated_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_youtube_batch_job_runs_running
                ON bronze.youtube_batch_job_runs (status)
                WHERE status = 'running'
            """
        )
    finally:
        cur.close()
    conn.commit()
    _ENSURED = True


def upsert_batch_job(conn: Any, job: BatchJob) -> None:
    ensure_batch_job_tables(conn)
    payload = job.to_dict()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO bronze.youtube_batch_job_runs (
                batch_id, step, status, started_at, updated_at, finished_at,
                config, summary, payload
            ) VALUES (
                %(batch_id)s, %(step)s, %(status)s,
                %(started_at)s::timestamptz, %(updated_at)s::timestamptz,
                NULLIF(%(finished_at)s, '')::timestamptz,
                %(config)s, %(summary)s, %(payload)s
            )
            ON CONFLICT (batch_id) DO UPDATE SET
                step = EXCLUDED.step,
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                updated_at = EXCLUDED.updated_at,
                finished_at = EXCLUDED.finished_at,
                config = EXCLUDED.config,
                summary = EXCLUDED.summary,
                payload = EXCLUDED.payload
            """,
            {
                "batch_id": job.batch_id,
                "step": job.step,
                "status": job.status,
                "started_at": job.started_at or None,
                "updated_at": job.updated_at,
                "finished_at": job.finished_at or "",
                "config": Json(job.config or {}),
                "summary": Json(job.summary or {}),
                "payload": Json(payload),
            },
        )
    finally:
        cur.close()
    conn.commit()


def sync_batch_job_to_db(job: BatchJob) -> None:
    if not _use_db():
        return
    try:
        with get_db_connection() as conn:
            upsert_batch_job(conn, job)
    except Exception as exc:
        logger.warning("batch job DB sync failed for %s: %s", job.batch_id, exc)


def list_batch_jobs_from_db(*, limit: int = 100) -> List[BatchJob]:
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT payload
                FROM bronze.youtube_batch_job_runs
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    jobs: List[BatchJob] = []
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        jobs.append(BatchJob.from_dict(payload))
    return jobs


def sync_json_batches_to_db(*, limit: int = 100) -> int:
    """Import recent JSON batch files into Postgres (one-time / backfill)."""
    if not _use_db():
        return 0
    jobs = list_batches(limit=limit)
    if not jobs:
        return 0
    with get_db_connection() as conn:
        for job in jobs:
            upsert_batch_job(conn, job)
    return len(jobs)


def enrich_transcript_counts_from_bronze(conn: Any, job: BatchJob) -> None:
    """Set jurisdiction ``bronze_download_rows`` from bronze_events_youtube."""
    jids = [j.jurisdiction_id for j in job.jurisdictions if j.jurisdiction_id]
    if not jids:
        return
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT
                jurisdiction_id,
                COUNT(*) FILTER (WHERE transcript_download_at IS NOT NULL)::int AS transcripts,
                COUNT(*) FILTER (
                    WHERE transcript_file_error IS NOT NULL
                      AND BTRIM(transcript_file_error) <> ''
                )::int AS transcript_errors
            FROM bronze.bronze_events_youtube
            WHERE jurisdiction_id = ANY(%s)
            GROUP BY jurisdiction_id
            """,
            (jids,),
        )
        by_jid = {r["jurisdiction_id"]: r for r in cur.fetchall()}
    finally:
        cur.close()

    for j in job.jurisdictions:
        row = by_jid.get(j.jurisdiction_id) or {}
        tx = int(row.get("transcripts") or 0)
        j.file_counts = dict(j.file_counts or {})
        j.file_counts["bronze_download_rows"] = tx
        j.file_counts["bronze_transcript_errors"] = int(
            row.get("transcript_errors") or 0
        )


def enrich_disk_file_counts(job: BatchJob, *, cache_root: Path | None = None) -> None:
    """Merge on-disk policy cache file counts into each jurisdiction's ``file_counts``."""
    from scripts.datasources.youtube.batch_job_status import (
        count_policy_files_for_jurisdiction,
        policy_disk_file_counts,
    )

    root = cache_root or (
        Path(__file__).resolve().parents[3] / "data" / "cache" / "gemini_transcript_policy"
    )
    for j in job.jurisdictions:
        if not j.jurisdiction_id:
            continue
        scanned = count_policy_files_for_jurisdiction(
            root,
            state_code=j.state_code,
            jurisdiction_id=j.jurisdiction_id,
        )
        j.file_counts = dict(j.file_counts or {})
        j.file_counts.update(policy_disk_file_counts(scanned))


def enrich_jobs_from_bronze(
    jobs: List[BatchJob],
    *,
    only_running_jurisdictions: bool = False,
    enrich_disk: bool = True,
) -> None:
    if not jobs:
        return
    try:
        with get_db_connection() as conn:
            for job in jobs:
                if only_running_jurisdictions:
                    pending = [
                        j
                        for j in job.jurisdictions
                        if j.status in ("running", "pending")
                    ]
                    if not pending:
                        continue
                    stub = BatchJob(
                        batch_id=job.batch_id,
                        step=job.step,
                        jurisdictions=pending,
                    )
                    enrich_transcript_counts_from_bronze(conn, stub)
                    if enrich_disk:
                        enrich_disk_file_counts(stub)
                    by_jid = {j.jurisdiction_id: j for j in pending}
                    for j in job.jurisdictions:
                        if j.jurisdiction_id in by_jid:
                            j.file_counts = dict(j.file_counts or {})
                            j.file_counts.update(by_jid[j.jurisdiction_id].file_counts)
                else:
                    enrich_transcript_counts_from_bronze(conn, job)
                    if enrich_disk:
                        enrich_disk_file_counts(job)
    except Exception as exc:
        logger.warning("bronze transcript count enrich failed: %s", exc)


def load_batch_job_from_db(batch_id: str) -> Optional[BatchJob]:
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT payload FROM bronze.youtube_batch_job_runs
                WHERE batch_id = %s
                """,
                (batch_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return BatchJob.from_dict(payload)


def latest_dashboard_revision() -> Optional[str]:
    """Cheap change detector for SSE (max updated_at + running count)."""
    try:
        with get_db_connection() as conn:
            ensure_batch_job_tables(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(MAX(updated_at)::text, ''),
                        COUNT(*) FILTER (WHERE status = 'running')::int
                    FROM bronze.youtube_batch_job_runs
                    """
                )
                updated_at, running = cur.fetchone()
        return f"{updated_at}|{running}"
    except Exception:
        return None
