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

from api.batch_jobs.batch_job_status import BatchJob, BatchJobStore, list_batches

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

    from core_lib.db import resolve_target_database_url

    url = resolve_target_database_url()
    for bad in ("&channel_binding=require", "channel_binding=require&", "channel_binding=require"):
        url = url.replace(bad, "")
    url = url.replace("&&", "&").rstrip("?&")
    return psycopg2.connect(
        url,
        connect_timeout=int(os.getenv("PGCONNECT_TIMEOUT", "10")),
        options=os.getenv("PGOPTIONS", "-c statement_timeout=60000"),
    )


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


def reap_stale_running_batches(*, limit: int = 30) -> int:
    """Cancel ``running`` batch rows whose recorded activity has gone stale.

    The dashboard counts ``status = 'running'`` rows, but a row stays ``running``
    after its worker dies or starts skipping already-done work — the per-job
    stale-cancel (``apply_batch_lifecycle`` → ``_maybe_stale_cancel_batch``,
    BATCH_JOB_INACTIVITY_SECONDS, default 3600s) only fires when a job is
    otherwise touched, which never happens for an abandoned run. Sweeping it here,
    on the dashboard read path, keeps ``totals.running`` honest instead of pinning
    it at a phantom count. Returns the number of rows whose status changed.
    """
    if not _use_db():
        return 0
    # Lazy import: batch_job_status imports this module, so import its lifecycle
    # helpers at call time to avoid a circular import at module load.
    from api.batch_jobs.batch_job_status import apply_batch_lifecycle, persist_batch_job

    reaped = 0
    try:
        with get_db_connection() as conn:
            ensure_batch_job_tables(conn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT payload
                    FROM bronze.youtube_batch_job_runs
                    WHERE status = 'running'
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            job = BatchJob.from_dict(payload)
            if apply_batch_lifecycle(job):
                persist_batch_job(job)  # writes cancelled/completed status back
                reaped += 1
    except Exception as exc:
        logger.warning("stale batch reap failed: %s", exc)
    return reaped


def policy_event_counts_24h(conn: Any) -> Dict[str, Any]:
    """
    Pipeline counts from the per-event bronze stamps (migration 083):

    - ``analysis`` / ``reports`` / ``*_errors`` — events in the last 24h.
    - ``*_total`` — all-time count of transcripts/analyses/reports (one live,
      de-duplicated source for the "on disk" cards and progress %, instead of
      summing per-batch disk scans, which double-counts transcripts across
      overlapping batches and goes stale for analysis/reports).
    - ``last_*_at`` — most recent stamp per step; drives the "ago" cards and,
      unlike the batch ``updated_at`` clock, reflects standalone analyze runs.

    Returns zeros/empty strings if the columns do not exist yet (migration not
    applied), so the dashboard falls back to the batch-summary counters.
    """
    out: Dict[str, Any] = {
        "analysis": 0,
        "reports": 0,
        "analysis_errors": 0,
        "reports_errors": 0,
        "transcripts_total": 0,
        "analysis_total": 0,
        "reports_total": 0,
        "last_transcript_at": "",
        "last_analysis_at": "",
        "last_report_at": "",
    }
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE policy_analysis_at >= now() - interval '24 hours'
                    )::int AS analysis,
                    COUNT(*) FILTER (
                        WHERE policy_report_at >= now() - interval '24 hours'
                    )::int AS reports,
                    COUNT(*) FILTER (
                        WHERE policy_analysis_error IS NOT NULL
                          AND last_updated >= now() - interval '24 hours'
                    )::int AS analysis_errors,
                    COUNT(*) FILTER (
                        WHERE policy_report_error IS NOT NULL
                          AND last_updated >= now() - interval '24 hours'
                    )::int AS reports_errors,
                    COUNT(*) FILTER (WHERE transcript_download_at IS NOT NULL)::int
                        AS transcripts_total,
                    COUNT(*) FILTER (WHERE policy_analysis_at IS NOT NULL)::int
                        AS analysis_total,
                    COUNT(*) FILTER (WHERE policy_report_at IS NOT NULL)::int
                        AS reports_total,
                    MAX(transcript_download_at) AS last_transcript_at,
                    MAX(policy_analysis_at) AS last_analysis_at,
                    MAX(policy_report_at) AS last_report_at
                FROM bronze.bronze_events_youtube
                """
            )
            row = cur.fetchone()
        if row:
            out["analysis"] = int(row[0] or 0)
            out["reports"] = int(row[1] or 0)
            out["analysis_errors"] = int(row[2] or 0)
            out["reports_errors"] = int(row[3] or 0)
            out["transcripts_total"] = int(row[4] or 0)
            out["analysis_total"] = int(row[5] or 0)
            out["reports_total"] = int(row[6] or 0)
            out["last_transcript_at"] = row[7].isoformat() if row[7] is not None else ""
            out["last_analysis_at"] = row[8].isoformat() if row[8] is not None else ""
            out["last_report_at"] = row[9].isoformat() if row[9] is not None else ""
    except Exception as exc:
        # Columns missing (pre-083) or transient DB error — degrade to zeros so the
        # dashboard falls back to the disk-scan counters.
        conn.rollback()
        logger.debug("policy_event_counts_24h unavailable: %s", exc)
    return out


# Pipeline stages, in funnel order. Each (scope, stage) pair is one report row,
# so adding a metric is a field and adding a dimension (state, later jurisdiction)
# is more rows — not more columns.
PIPELINE_STAGES = ("discover", "videos", "transcripts", "analyses", "reports")


def _stage_timing(conn: Any) -> Dict[str, Any]:
    """Per-stage cadence: median seconds between recent completions (~throughput
    per file) and the most recent output file path. Column names are fixed (not
    user input), so the f-string is safe. Empty on pre-083 DBs.

    ``avg_seconds`` is the median gap between *completed* rows, so it freezes
    during a stall — no new row means no new gap, and gaps >= 1h are filtered
    out anyway. To keep ``/hr`` and ETA honest, we also return:

    - ``stale_seconds``: the open trailing gap (``now() - last_at``), i.e. how
      long we have already been waiting for the next completion.
    - ``effective_seconds``: ``max(avg_seconds, stale_seconds)`` — once the next
      file is overdue, the best estimate of the current per-file pace is at
      least how long we have waited. It degrades while stalled and snaps back to
      ``avg_seconds`` the moment a file lands. Consumers showing a live rate for
      an idle (not-running) stage should ignore ``stale_seconds``.
    """

    def _one(ts_col: str, path_col: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "avg_seconds": None,
            "last_path": "",
            "last_at": "",
            "stale_seconds": None,
            "effective_seconds": None,
        }
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH recent AS (
                        SELECT {ts_col} AS ts, {path_col} AS path
                        FROM bronze.bronze_events_youtube
                        WHERE {ts_col} IS NOT NULL
                        ORDER BY {ts_col} DESC LIMIT 150
                    ),
                    gaps AS (
                        SELECT EXTRACT(EPOCH FROM (ts - LAG(ts) OVER (ORDER BY ts))) AS gap
                        FROM recent
                    ),
                    latest AS (
                        SELECT ts, path FROM recent ORDER BY ts DESC LIMIT 1
                    )
                    SELECT
                        (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY gap)
                           FROM gaps WHERE gap > 0 AND gap < 3600) AS med_gap,
                        (SELECT path FROM latest) AS last_path,
                        (SELECT ts FROM latest) AS last_at,
                        EXTRACT(EPOCH FROM (now() - (SELECT ts FROM latest))) AS stale_seconds
                    """
                )
                row = cur.fetchone()
            if row:
                out["avg_seconds"] = round(float(row[0]), 1) if row[0] is not None else None
                out["last_path"] = str(row[1] or "")
                out["last_at"] = row[2].isoformat() if row[2] is not None else ""
                out["stale_seconds"] = (
                    round(float(row[3]), 1) if row[3] is not None else None
                )
                avg = out["avg_seconds"]
                stale = out["stale_seconds"]
                if avg is not None:
                    out["effective_seconds"] = (
                        round(max(avg, stale), 1) if stale is not None else avg
                    )
        except Exception:
            conn.rollback()
        return out

    vids = _one("transcript_download_at", "transcript_file_path")
    return {
        "videos": vids,
        "transcripts": vids,
        "analyses": _one("policy_analysis_at", "policy_analysis_path"),
        "reports": _one("policy_report_at", "policy_report_path"),
    }


def pipeline_stage_report(conn: Any) -> Dict[str, Any]:
    """
    Long-format per-state pipeline coverage from the bronze per-event stamps.

    Returns ``{"states": [...], "rows": [{scope, stage, done, total, failed,
    last_at}, ...]}`` where ``scope`` is a 2-letter state code or ``"ALL"`` (the
    national rollup). All four stages are derived from one ``GROUP BY state_code``
    over ``bronze_events_youtube`` so per-state and overall numbers are consistent
    and live (covering standalone/parallel analyze runs). Empty on pre-083 DBs.
    """
    out: Dict[str, Any] = {"states": [], "rows": []}

    def _iso(v: Any) -> str:
        return v.isoformat() if v is not None else ""

    def _max_iso(a: str, b: str) -> str:
        return a if a >= b else b

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(NULLIF(state_code, ''), '??')                     AS st,
                    COUNT(*) FILTER (WHERE transcript_download_at IS NOT NULL)::int AS vids_ok,
                    COUNT(*) FILTER (WHERE transcript_file_error IS NOT NULL)::int  AS vids_fail,
                    COUNT(*) FILTER (WHERE policy_analysis_at IS NOT NULL)::int     AS analyses,
                    COUNT(*) FILTER (WHERE policy_analysis_error IS NOT NULL)::int  AS analysis_err,
                    COUNT(*) FILTER (WHERE policy_report_at IS NOT NULL)::int       AS reports,
                    COUNT(*) FILTER (WHERE policy_report_error IS NOT NULL)::int    AS report_err,
                    MAX(transcript_download_at)                                 AS last_video,
                    MAX(policy_analysis_at)                                     AS last_analysis,
                    MAX(policy_report_at)                                       AS last_report
                FROM bronze.bronze_events_youtube
                GROUP BY 1
                """
            )
            db_rows = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        logger.debug("pipeline_stage_report unavailable: %s", exc)
        return out

    # Stage 0 (channel discovery) lives in the scraped-jurisdiction tables, not in
    # bronze_events_youtube: per state, how many jurisdictions have a YouTube channel
    # found (done) out of all scraped (total); failed = still missing a channel.
    discover_by_state: Dict[str, Dict[str, Any]] = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT usps AS st,
                    COUNT(*)::int AS total,
                    COUNT(*) FILTER (
                        WHERE COALESCE(NULLIF(youtube_channel_id, ''),
                                       NULLIF(youtube_channel_url, '')) IS NOT NULL
                    )::int AS done,
                    MAX(discovered_at) AS last_at
                FROM (
                    SELECT usps, youtube_channel_id, youtube_channel_url, discovered_at
                      FROM bronze.bronze_jurisdictions_counties_scraped
                    UNION ALL
                    SELECT usps, youtube_channel_id, youtube_channel_url, discovered_at
                      FROM bronze.bronze_jurisdictions_municipalities_scraped
                ) j
                WHERE COALESCE(usps, '') <> ''
                GROUP BY usps
                """
            )
            for st, total, done, last_at in cur.fetchall():
                discover_by_state[str(st)] = {
                    "total": int(total), "done": int(done), "last_at": _iso(last_at)
                }
    except Exception:
        conn.rollback()  # scraped tables absent — discover stage degrades to zeros

    def _discover_row(scope: str, disc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        d = disc or {"total": 0, "done": 0, "last_at": ""}
        return {
            "scope": scope, "stage": "discover", "done": d["done"], "total": d["total"],
            "failed": max(0, d["total"] - d["done"]), "last_at": d["last_at"],
        }

    def _stage_rows(
        scope: str, rec: Dict[str, Any], disc: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        ok = int(rec["vids_ok"])
        fail = int(rec["vids_fail"])
        attempted = ok + fail
        lv, la, lr = rec["last_video"], rec["last_analysis"], rec["last_report"]
        # done / total / failed / last_at per stage. Transcripts/analyses/reports
        # are denominated by the videos that got a transcript (the funnel input).
        return [
            _discover_row(scope, disc),
            {"scope": scope, "stage": "videos", "done": ok, "total": attempted,
             "failed": fail, "last_at": lv},
            {"scope": scope, "stage": "transcripts", "done": ok, "total": ok,
             "failed": fail, "last_at": lv},
            {"scope": scope, "stage": "analyses", "done": int(rec["analyses"]), "total": ok,
             "failed": int(rec["analysis_err"]), "last_at": la},
            {"scope": scope, "stage": "reports", "done": int(rec["reports"]), "total": ok,
             "failed": int(rec["report_err"]), "last_at": lr},
        ]

    cols = ("st", "vids_ok", "vids_fail", "analyses", "analysis_err", "reports",
            "report_err", "last_video", "last_analysis", "last_report")
    per_state = [dict(zip(cols, r)) for r in db_rows]

    rows: List[Dict[str, Any]] = []
    states: List[str] = []
    totals = {k: 0 for k in ("vids_ok", "vids_fail", "analyses", "analysis_err",
                             "reports", "report_err")}
    last = {"last_video": "", "last_analysis": "", "last_report": ""}
    for rec in per_state:
        st = str(rec["st"])
        for tk in ("last_video", "last_analysis", "last_report"):
            rec[tk] = _iso(rec[tk])
        for nk in totals:
            totals[nk] += int(rec[nk])
        for tk in last:
            last[tk] = _max_iso(last[tk], rec[tk])
        # Only surface states that have entered the pipeline (any attempted video).
        if int(rec["vids_ok"]) + int(rec["vids_fail"]) > 0 and st != "??":
            states.append(st)
            rows.extend(_stage_rows(st, rec, discover_by_state.get(st)))

    disc_all = {"total": 0, "done": 0, "last_at": ""}
    for st in states:
        d = discover_by_state.get(st)
        if d:
            disc_all["total"] += d["total"]
            disc_all["done"] += d["done"]
            disc_all["last_at"] = _max_iso(disc_all["last_at"], d["last_at"])
    rows = _stage_rows("ALL", {**totals, **last}, disc_all) + rows
    out["states"] = sorted(states)
    out["rows"] = rows
    out["timing"] = _stage_timing(conn)
    return out


def dashboard_stage_report() -> Dict[str, Any]:
    """Open a connection and return the per-state pipeline report (empty on error)."""
    try:
        with get_db_connection() as conn:
            ensure_batch_job_tables(conn)
            return pipeline_stage_report(conn)
    except Exception as exc:
        logger.debug("dashboard_stage_report unavailable: %s", exc)
        return {"states": [], "rows": []}


def aggregate_dashboard_totals_from_db(*, limit: int = 30) -> Dict[str, Any]:
    """Sum numeric fields from ``summary`` JSONB across recent batches (no payload)."""
    # Reap abandoned ``running`` rows first so the ``running`` count below (and any
    # per-batch meta read for the same dashboard tick) reflects real liveness.
    reap_stale_running_batches(limit=limit)
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH recent AS (
                    SELECT status, config, summary, updated_at
                    FROM bronze.youtube_batch_job_runs
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT %s
                )
                SELECT
                    COUNT(*)::int AS batches,
                    COUNT(*) FILTER (WHERE status = 'running')::int AS running,
                    COALESCE(SUM((summary->>'processed_jurisdictions')::int), 0)
                        AS processed_jurisdictions,
                    COALESCE(SUM((summary->>'failed_jurisdictions')::int), 0)
                        AS failed_jurisdictions,
                    COALESCE(SUM((summary->>'remaining_jurisdictions')::int), 0)
                        AS remaining_jurisdictions,
                    COALESCE(SUM((summary->>'videos_ok')::int), 0) AS videos_ok,
                    COALESCE(SUM((summary->>'videos_fail')::int), 0) AS videos_fail,
                    COALESCE(SUM((summary->>'files_transcripts')::int), 0)
                        AS files_transcripts,
                    COALESCE(SUM((summary->>'files_transcripts_disk')::int), 0)
                        AS files_transcripts_disk,
                    COALESCE(SUM((summary->>'bronze_download_rows')::int), 0)
                        AS bronze_download_rows,
                    COALESCE(SUM((summary->>'files_analysis')::int), 0) AS files_analysis,
                    COALESCE(SUM((summary->>'files_reports')::int), 0) AS files_reports,
                    COALESCE(SUM((summary->>'transcript_seconds')::float), 0)
                        AS transcript_seconds,
                    MAX(updated_at) AS last_updated
                FROM recent
                """,
                (limit,),
            )
            row = cur.fetchone() or {}
            recent_events = policy_event_counts_24h(conn)
    totals = {
        "batches": int(row.get("batches") or 0),
        "running": int(row.get("running") or 0),
        "states": 0,
        "states_planned": 0,
        "states_started": 0,
        "states_completed": 0,
        "processed_jurisdictions": int(row.get("processed_jurisdictions") or 0),
        "failed_jurisdictions": int(row.get("failed_jurisdictions") or 0),
        "remaining_jurisdictions": int(row.get("remaining_jurisdictions") or 0),
        "videos_ok": int(row.get("videos_ok") or 0),
        "videos_fail": int(row.get("videos_fail") or 0),
        "videos_attempted": 0,
        "files_transcripts": int(row.get("files_transcripts") or 0),
        "files_transcripts_disk": int(row.get("files_transcripts_disk") or 0),
        "transcript_hours": round(float(row.get("transcript_seconds") or 0) / 3600.0, 2),
        "bronze_download_rows": int(row.get("bronze_download_rows") or 0),
        "files_analysis": int(row.get("files_analysis") or 0),
        "files_reports": int(row.get("files_reports") or 0),
        # Rolling 24h throughput from per-event bronze stamps (migration 083); covers
        # both batch and standalone runs, unlike the batch-scoped disk-scan counters.
        "files_analysis_recent": int(recent_events.get("analysis") or 0),
        "files_reports_recent": int(recent_events.get("reports") or 0),
        "files_analysis_errors_recent": int(recent_events.get("analysis_errors") or 0),
        "files_reports_errors_recent": int(recent_events.get("reports_errors") or 0),
        # Most recent stamp per step (all time) for the dashboard "ago" cards.
        "last_transcript_at": recent_events.get("last_transcript_at") or "",
        "last_analysis_at": recent_events.get("last_analysis_at") or "",
        "last_report_at": recent_events.get("last_report_at") or "",
    }
    # Prefer the live, de-duplicated bronze-stamp totals for the pipeline cards and
    # progress %: summing per-batch disk scans inflates transcripts (overlapping
    # batches) and goes stale for analysis/reports. Only override when the stamps
    # have data, so a pre-083 DB still shows the batch-summary fallback.
    transcripts_total = int(recent_events.get("transcripts_total") or 0)
    analysis_total = int(recent_events.get("analysis_total") or 0)
    reports_total = int(recent_events.get("reports_total") or 0)
    if transcripts_total > 0:
        totals["files_transcripts_disk"] = transcripts_total
    if analysis_total > 0:
        totals["files_analysis"] = analysis_total
    if reports_total > 0:
        totals["files_reports"] = reports_total
    last_updated = row.get("last_updated")
    totals["last_activity_at"] = (
        last_updated.isoformat() if last_updated is not None else ""
    )
    return totals


def list_jurisdiction_rows_from_db(
    batch_id: str,
    state_code: str,
) -> List[Dict[str, Any]]:
    """
    Extract slim jurisdiction rows for one state via JSONB (no per-video arrays).
    """
    st = (state_code or "").strip().upper()
    if not st:
        return []
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT COALESCE(
                    jsonb_agg(sub.row ORDER BY sub.sort_name),
                    '[]'::jsonb
                ) AS jurisdictions
                FROM (
                    SELECT
                        jsonb_build_object(
                            'state_code', elem->>'state_code',
                            'jurisdiction_id', elem->>'jurisdiction_id',
                            'jurisdiction_name', elem->>'jurisdiction_name',
                            'status', COALESCE(NULLIF(elem->>'status', ''), 'pending'),
                            'started_at', COALESCE(elem->>'started_at', ''),
                            'updated_at', COALESCE(elem->>'updated_at', ''),
                            'finished_at', COALESCE(elem->>'finished_at', ''),
                            'elapsed_seconds',
                                COALESCE((elem->>'elapsed_seconds')::float, 0),
                            'exit_code', COALESCE((elem->>'exit_code')::int, 0),
                            'stats', COALESCE(elem->'stats', '{}'::jsonb),
                            'file_counts', COALESCE(elem->'file_counts', '{}'::jsonb),
                            'current_video_id', COALESCE(elem->>'current_video_id', ''),
                            'current_video_title', COALESCE(elem->>'current_video_title', ''),
                            'current_video_started_at',
                                COALESCE(elem->>'current_video_started_at', ''),
                            'videos', '[]'::jsonb
                        ) AS row,
                        lower(
                            COALESCE(
                                elem->>'jurisdiction_name',
                                elem->>'jurisdiction_id',
                                ''
                            )
                        ) AS sort_name
                    FROM bronze.youtube_batch_job_runs b,
                         jsonb_array_elements(
                             CASE
                                 WHEN jsonb_typeof(b.payload->'jurisdictions') = 'array'
                                 THEN b.payload->'jurisdictions'
                                 ELSE '[]'::jsonb
                             END
                         ) elem
                    WHERE b.batch_id = %s
                      AND UPPER(COALESCE(elem->>'state_code', '')) = %s
                ) sub
                """,
                (batch_id, st),
            )
            row = cur.fetchone()
    raw = row.get("jurisdictions") if row else []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []
    return [dict(x) for x in raw if isinstance(x, dict)]


def running_batch_activity_from_db() -> Optional[Dict[str, Any]]:
    """Active in-flight rows for the running batch (JSONB projection; no full payload parse)."""
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    b.batch_id,
                    COALESCE(
                        jsonb_agg(sub.row ORDER BY sub.sort_key),
                        '[]'::jsonb
                    ) AS jurisdictions
                FROM bronze.youtube_batch_job_runs b
                LEFT JOIN LATERAL (
                    SELECT
                        jsonb_build_object(
                            'state_code', elem->>'state_code',
                            'jurisdiction_id', elem->>'jurisdiction_id',
                            'jurisdiction_name', elem->>'jurisdiction_name',
                            'status', COALESCE(elem->>'status', 'running'),
                            'updated_at', COALESCE(elem->>'updated_at', ''),
                            'current_video_id', COALESCE(elem->>'current_video_id', ''),
                            'current_video_title', COALESCE(elem->>'current_video_title', ''),
                            'current_video_started_at',
                                COALESCE(elem->>'current_video_started_at', ''),
                            'videos', '[]'::jsonb
                        ) AS row,
                        COALESCE(elem->>'current_video_started_at', elem->>'started_at', '')
                            AS sort_key
                    FROM jsonb_array_elements(
                        CASE
                            WHEN jsonb_typeof(b.payload->'jurisdictions') = 'array'
                            THEN b.payload->'jurisdictions'
                            ELSE '[]'::jsonb
                        END
                    ) elem
                    WHERE LOWER(COALESCE(elem->>'status', '')) = 'running'
                       OR COALESCE(elem->>'current_video_id', '') <> ''
                ) sub ON TRUE
                WHERE b.status = 'running'
                GROUP BY b.batch_id
                ORDER BY MAX(b.updated_at) DESC NULLS LAST
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if not row:
        return None
    jurs = row.get("jurisdictions") or []
    if isinstance(jurs, str):
        jurs = json.loads(jurs)
    if not isinstance(jurs, list) or not jurs:
        return None
    return {"batch_id": row["batch_id"], "jurisdictions": [dict(x) for x in jurs if isinstance(x, dict)]}


_FAILED_VIDEO_STATUSES = frozenset(
    {"fail", "failed", "tombstoned", "empty", "rate_limit", "error"}
)


def list_failed_videos_from_db(
    *,
    batch_id: Optional[str] = None,
    limit: int = 500,
    batch_limit: int = 25,
) -> Dict[str, Any]:
    """
    Extract per-video failure rows from stored batch payloads (JSONB).

    Returns ``rows`` plus ``total_fail_in_summaries`` (sum of ``summary.videos_fail``)
    which may exceed ``len(rows)`` when failures were counted in stats but not logged
    per video, or when ``limit`` truncates.
    """
    bid = (batch_id or "").strip() or None
    lim = max(1, min(int(limit), 2000))
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if bid:
                cur.execute(
                    """
                    SELECT COALESCE((summary->>'videos_fail')::int, 0) AS n
                    FROM bronze.youtube_batch_job_runs
                    WHERE batch_id = %s
                    """,
                    (bid,),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM((summary->>'videos_fail')::int), 0)::int AS n
                    FROM (
                        SELECT summary
                        FROM bronze.youtube_batch_job_runs
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT %s
                    ) recent
                    """,
                    (batch_limit,),
                )
            summary_row = cur.fetchone() or {}
            total_fail = int(summary_row.get("n") or 0)

            cur.execute(
                """
                SELECT
                    b.batch_id,
                    b.step AS batch_step,
                    j.elem->>'state_code' AS state_code,
                    j.elem->>'jurisdiction_id' AS jurisdiction_id,
                    j.elem->>'jurisdiction_name' AS jurisdiction_name,
                    v.elem->>'video_id' AS video_id,
                    v.elem->>'title' AS title,
                    v.elem->>'status' AS status,
                    v.elem->>'error' AS error,
                    v.elem->>'transcript_source' AS transcript_source,
                    v.elem->>'finished_at' AS finished_at,
                    v.elem->>'duration_seconds' AS duration_seconds
                FROM bronze.youtube_batch_job_runs b
                CROSS JOIN LATERAL jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof(b.payload->'jurisdictions') = 'array'
                        THEN b.payload->'jurisdictions'
                        ELSE '[]'::jsonb
                    END
                ) AS j(elem)
                CROSS JOIN LATERAL jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof(j.elem->'videos') = 'array'
                        THEN j.elem->'videos'
                        ELSE '[]'::jsonb
                    END
                ) AS v(elem)
                WHERE (%s::text IS NULL OR b.batch_id = %s)
                  AND COALESCE(v.elem->>'video_id', '') <> ''
                  AND (
                    LOWER(COALESCE(v.elem->>'status', '')) = ANY(%s)
                    OR (
                      LOWER(COALESCE(v.elem->>'status', '')) NOT IN (
                        'ok', 'pending', 'skipped', 'noop', ''
                      )
                    )
                  )
                ORDER BY b.updated_at DESC NULLS LAST,
                         v.elem->>'finished_at' DESC NULLS LAST
                LIMIT %s
                """,
                (
                    bid,
                    bid,
                    list(_FAILED_VIDEO_STATUSES),
                    lim + 1,
                ),
            )
            raw_rows = cur.fetchall()
    truncated = len(raw_rows) > lim
    rows_out: List[Dict[str, Any]] = []
    for row in raw_rows[:lim]:
        dur = row.get("duration_seconds")
        try:
            dur_f = float(dur) if dur not in (None, "") else None
        except (TypeError, ValueError):
            dur_f = None
        rows_out.append(
            {
                "batch_id": row["batch_id"],
                "batch_step": row.get("batch_step") or "",
                "state_code": row.get("state_code") or "",
                "jurisdiction_id": row.get("jurisdiction_id") or "",
                "jurisdiction_name": row.get("jurisdiction_name") or "",
                "video": {
                    "video_id": row.get("video_id") or "",
                    "title": row.get("title") or "",
                    "status": row.get("status") or "",
                    "error": row.get("error") or "",
                    "transcript_source": row.get("transcript_source") or "",
                    "finished_at": row.get("finished_at") or "",
                    "duration_seconds": dur_f,
                },
            }
        )
    return {
        "rows": rows_out,
        "total_fail_in_summaries": total_fail,
        "truncated": truncated,
    }


def list_batch_job_meta_from_db(*, limit: int = 30) -> List[Dict[str, Any]]:
    """Lightweight batch rows (no ``payload``) for fast dashboard summary."""
    with get_db_connection() as conn:
        ensure_batch_job_tables(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    batch_id,
                    step,
                    status,
                    started_at,
                    updated_at,
                    finished_at,
                    config,
                    summary
                FROM bronze.youtube_batch_job_runs
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        started = row.get("started_at")
        updated = row.get("updated_at")
        finished = row.get("finished_at")
        out.append(
            {
                "batch_id": row["batch_id"],
                "step": row["step"],
                "status": row["status"],
                "started_at": started.isoformat() if started else "",
                "updated_at": updated.isoformat() if updated else "",
                "finished_at": finished.isoformat() if finished else "",
                "config": row.get("config") or {},
                "summary": row.get("summary") or {},
                "jurisdictions": [],
            }
        )
    return out


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


def enrich_transcript_seconds_from_bronze(conn: Any, job: BatchJob) -> None:
    """
    Set ``job.summary['transcript_seconds']`` from ``bronze_events_youtube.duration_minutes``.

    Batch payloads often have per-video stats without ``duration_seconds`` (older runs or
    DB copies). Prefer catalog duration for ok video ids in ``j.videos``; if none, sum
    transcripts downloaded in processed jurisdictions since ``job.started_at``.
    """
    from api.batch_jobs.batch_job_status import (
        transcript_seconds_from_job_videos,
    )

    ok_ids = [
        v.video_id
        for j in job.jurisdictions
        for v in j.videos or []
        if (v.status or "").strip().lower() == "ok" and (v.video_id or "").strip()
    ]
    cur = conn.cursor()
    try:
        if ok_ids:
            cur.execute(
                """
                SELECT COALESCE(SUM(duration_minutes), 0) * 60.0
                FROM bronze.bronze_events_youtube
                WHERE video_id = ANY(%s)
                  AND duration_minutes IS NOT NULL
                  AND duration_minutes > 0
                """,
                (ok_ids,),
            )
            row = cur.fetchone()
            secs = float(row[0] or 0) if row else 0.0
        else:
            active_jids = [
                j.jurisdiction_id
                for j in job.jurisdictions
                if j.jurisdiction_id
                and j.status in ("completed", "failed", "running")
                and (
                    int((j.stats or {}).get("ok") or 0) > 0
                    or any(
                        (v.status or "").strip().lower() == "ok" for v in j.videos or []
                    )
                )
            ]
            if not active_jids:
                secs = transcript_seconds_from_job_videos(job)
            elif job.started_at:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(duration_minutes), 0) * 60.0
                    FROM bronze.bronze_events_youtube
                    WHERE jurisdiction_id = ANY(%s)
                      AND transcript_download_at IS NOT NULL
                      AND transcript_download_at >= %s::timestamptz
                      AND duration_minutes IS NOT NULL
                      AND duration_minutes > 0
                    """,
                    (active_jids, job.started_at),
                )
                row = cur.fetchone()
                secs = float(row[0] or 0) if row else 0.0
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(duration_minutes), 0) * 60.0
                    FROM bronze.bronze_events_youtube
                    WHERE jurisdiction_id = ANY(%s)
                      AND transcript_download_at IS NOT NULL
                      AND duration_minutes IS NOT NULL
                      AND duration_minutes > 0
                    """,
                    (active_jids,),
                )
                row = cur.fetchone()
                secs = float(row[0] or 0) if row else 0.0
    finally:
        cur.close()

    job.summary = dict(job.summary or {})
    job.summary["transcript_seconds"] = round(secs, 1)


def enrich_disk_file_counts(job: BatchJob, *, cache_root: Path | None = None) -> None:
    """Merge on-disk policy cache file counts into each jurisdiction's ``file_counts``."""
    from api.batch_jobs.batch_job_status import (
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
                    enrich_transcript_seconds_from_bronze(conn, stub)
                    if enrich_disk:
                        enrich_disk_file_counts(stub)
                    by_jid = {j.jurisdiction_id: j for j in pending}
                    for j in job.jurisdictions:
                        if j.jurisdiction_id in by_jid:
                            j.file_counts = dict(j.file_counts or {})
                            j.file_counts.update(by_jid[j.jurisdiction_id].file_counts)
                else:
                    enrich_transcript_counts_from_bronze(conn, job)
                    enrich_transcript_seconds_from_bronze(conn, job)
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
