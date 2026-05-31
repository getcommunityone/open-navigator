#!/usr/bin/env python3
"""
Build static HTML for batch job status (optional; primary UI is React).

React app: Data explorer → Batch jobs (`/data-explorer/batch-jobs`) via `GET /api/batch-jobs`.

Usage (repo root):
  .venv/bin/python packages/scrapers/src/scrapers/youtube/batch_job_dashboard.py --build
  .venv/bin/python packages/scrapers/src/scrapers/youtube/batch_job_dashboard.py --build --open
  .venv/bin/python packages/scrapers/src/scrapers/youtube/batch_job_dashboard.py --serve
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Literal

VideoPayloadMode = Literal["none", "failed_only", "running", "all"]

_FAILED_VIDEO_STATUSES = frozenset(
    {
        "fail",
        "failed",
        "tombstoned",
        "empty",
        "rate_limit",
        "error",
    }
)


def _is_failed_video_status(status: str) -> bool:
    s = (status or "").strip().lower()
    if not s or s in ("ok", "pending", "skipped", "noop"):
        return False
    if s in _FAILED_VIDEO_STATUSES:
        return True
    return s != "ok"


def slim_jurisdiction_videos(
    j: Dict[str, Any],
    *,
    video_mode: VideoPayloadMode,
) -> Dict[str, Any]:
    """Drop per-video rows when counts in ``stats`` are enough for the table."""
    if video_mode == "all":
        return j
    out = dict(j)
    status = (out.get("status") or "").strip().lower()
    if video_mode == "running" and (
        status == "running" or (out.get("current_video_id") or "").strip()
    ):
        return out
    videos = list(out.get("videos") or [])
    if video_mode == "failed_only":
        out["videos"] = [v for v in videos if _is_failed_video_status(v.get("status", ""))]
    else:
        out["videos"] = []
    return out


def slim_batch_dict(
    batch: Dict[str, Any],
    *,
    video_mode: VideoPayloadMode,
) -> Dict[str, Any]:
    out = dict(batch)
    jurs = batch.get("jurisdictions") or []
    if not jurs:
        return out
    batch_running = (batch.get("status") or "").lower() == "running"
    mode: VideoPayloadMode = video_mode
    if video_mode == "running" and not batch_running:
        mode = "failed_only"
    out["jurisdictions"] = [
        slim_jurisdiction_videos(j, video_mode=mode) if isinstance(j, dict) else j
        for j in jurs
    ]
    return out


def _totals_from_batch_summaries(batches: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {
        "batches": 0,
        "running": 0,
        "states": 0,
        "states_planned": 0,
        "states_started": 0,
        "states_completed": 0,
        "processed_jurisdictions": 0,
        "failed_jurisdictions": 0,
        "remaining_jurisdictions": 0,
        "videos_ok": 0,
        "videos_fail": 0,
        "videos_attempted": 0,
        "files_transcripts": 0,
        "files_transcripts_disk": 0,
        "transcript_hours": 0.0,
        "bronze_download_rows": 0,
        "files_analysis": 0,
        "files_reports": 0,
        "files_analysis_recent": 0,
        "files_reports_recent": 0,
    }
    planned_states: set[str] = set()
    started_states: set[str] = set()
    completed_states: set[str] = set()
    transcript_seconds = 0.0

    from api.batch_jobs.batch_job_status import config_state_codes

    for d in batches:
        totals["batches"] += 1
        if d.get("status") == "running":
            totals["running"] += 1
        s = d.get("summary") or {}
        for st in config_state_codes(d.get("config") or {}):
            planned_states.add(st)
        for st in s.get("states_started_codes") or []:
            started_states.add(str(st).upper())
        for st in s.get("states_completed_codes") or []:
            completed_states.add(str(st).upper())
        totals["processed_jurisdictions"] += int(s.get("processed_jurisdictions") or 0)
        totals["failed_jurisdictions"] += int(s.get("failed_jurisdictions") or 0)
        totals["remaining_jurisdictions"] += int(s.get("remaining_jurisdictions") or 0)
        totals["videos_ok"] += int(s.get("videos_ok") or 0)
        totals["videos_fail"] += int(s.get("videos_fail") or 0)
        attempted = int(s.get("videos_attempted") or s.get("files_processed") or 0)
        if not attempted:
            attempted = (
                int(s.get("videos_ok") or 0)
                + int(s.get("videos_fail") or 0)
                + int(s.get("videos_tombstoned") or 0)
                + int(s.get("videos_empty") or 0)
                + int(s.get("videos_rate_limit") or 0)
            )
        totals["videos_attempted"] += attempted
        totals["files_transcripts"] += int(s.get("files_transcripts") or 0)
        totals["files_transcripts_disk"] += int(s.get("files_transcripts_disk") or 0)
        totals["bronze_download_rows"] += int(s.get("bronze_download_rows") or 0)
        totals["files_analysis"] += int(s.get("files_analysis") or 0)
        totals["files_reports"] += int(s.get("files_reports") or 0)
        totals["files_analysis_recent"] += int(s.get("files_analysis_recent") or 0)
        totals["files_reports_recent"] += int(s.get("files_reports_recent") or 0)
        transcript_seconds += float(s.get("transcript_seconds") or 0)

    totals["states_planned"] = len(planned_states)
    totals["states_started"] = len(started_states)
    totals["states_completed"] = len(completed_states)
    totals["states"] = totals["states_planned"]
    totals["transcript_hours"] = round(transcript_seconds / 3600.0, 2)
    return totals


def _max_iso_timestamp(best: str, candidate: str) -> str:
    raw = (candidate or "").strip()
    if raw and (not best or raw > best):
        return raw
    return best


def pipeline_activity_at_from_batches(batches: List[Dict[str, Any]]) -> str:
    """
    Latest jurisdiction/video progress timestamp (not batch ``updated_at`` sync metadata).

    Includes ``summary.current_video_started_at`` (same clock as the Current file card) when
    the slim running snapshot has no jurisdiction rows.
    """
    best = ""
    for b in batches:
        jurs = b.get("jurisdictions") or []
        for j in jurs:
            if not isinstance(j, dict):
                continue
            for key in (
                "updated_at",
                "current_video_started_at",
                "finished_at",
                "started_at",
            ):
                best = _max_iso_timestamp(best, j.get(key) or "")
            for v in j.get("videos") or []:
                if isinstance(v, dict):
                    best = _max_iso_timestamp(best, v.get("finished_at") or "")
        summary = b.get("summary") or {}
        if isinstance(summary, dict):
            for key in (
                "current_video_started_at",
                "current_jurisdiction_finished_at",
            ):
                best = _max_iso_timestamp(best, summary.get(key) or "")
        for key in ("finished_at", "started_at"):
            best = _max_iso_timestamp(best, b.get(key) or "")
    return best


def build_dashboard_summary(*, limit: int = 30) -> Dict[str, Any]:
    """Fast path: batch list + totals from ``summary`` JSON only (no payload parse)."""
    import datetime as _dt
    import os

    use_db = os.getenv("BATCH_JOBS_USE_DB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    batches: List[Dict[str, Any]] = []
    source = "files"
    sql_totals: Dict[str, Any] | None = None

    if use_db:
        try:
            from api.batch_jobs.batch_job_db import (
                aggregate_dashboard_totals_from_db,
                list_batch_job_meta_from_db,
                running_batch_activity_from_db,
            )

            # Totals first: it reaps stale ``running`` rows, so the meta read
            # below sees the corrected per-batch statuses in this same snapshot.
            reaped_totals = aggregate_dashboard_totals_from_db(limit=limit)
            batches = list_batch_job_meta_from_db(limit=limit)
            if batches:
                source = "database"
                sql_totals = reaped_totals
                running = running_batch_activity_from_db()
                if running:
                    for b in batches:
                        if b.get("batch_id") == running.get("batch_id"):
                            b["jurisdictions"] = running.get("jurisdictions") or []
                            break
        except Exception:
            batches = []

    if not batches:
        jobs = list_batches(limit=limit)
        batches = [
            {
                "batch_id": j.batch_id,
                "step": j.step,
                "status": j.status,
                "started_at": j.started_at,
                "updated_at": j.updated_at,
                "finished_at": j.finished_at,
                "config": dict(j.config or {}),
                "summary": dict(j.summary or {}),
                "jurisdictions": [],
            }
            for j in jobs
        ]
        source = "files"

    totals = _totals_from_batch_summaries(batches)
    if sql_totals:
        totals.update(
            {
                k: sql_totals[k]
                for k in (
                    "batches",
                    "running",
                    "processed_jurisdictions",
                    "failed_jurisdictions",
                    "remaining_jurisdictions",
                    "videos_ok",
                    "videos_fail",
                    "files_transcripts",
                    "files_transcripts_disk",
                    "bronze_download_rows",
                    "files_analysis",
                    "files_reports",
                    "files_analysis_recent",
                    "files_reports_recent",
                    "files_analysis_errors_recent",
                    "files_reports_errors_recent",
                    "last_transcript_at",
                    "last_analysis_at",
                    "last_report_at",
                    "transcript_hours",
                )
                if k in sql_totals
            }
        )
        last_activity = pipeline_activity_at_from_batches(batches)
        if not last_activity and sql_totals.get("last_activity_at"):
            last_activity = sql_totals["last_activity_at"]
    else:
        last_activity = pipeline_activity_at_from_batches(batches)
    stage_report: Dict[str, Any] = {"states": [], "rows": []}
    if use_db:
        from api.batch_jobs.batch_job_db import dashboard_stage_report

        stage_report = dashboard_stage_report()
    now = _dt.datetime.now(_dt.timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "last_activity_at": last_activity,
        "totals": totals,
        "batches": batches,
        "stage_report": stage_report,
        "source": source,
        "detail": "summary",
    }


def build_batch_state_jurisdictions(*, batch_id: str, state_code: str) -> List[Dict[str, Any]]:
    """
    Slim jurisdiction rows for one state (no per-video arrays).

    Uses JSONB extraction for finished batches; single-state plan merge for running.
    """
    from api.batch_jobs.batch_job_db import (
        list_jurisdiction_rows_from_db,
        load_batch_job_from_db,
    )
    from api.batch_jobs.batch_job_status import (
        apply_batch_lifecycle,
        expand_batch_job_plan,
        fetch_batch_plan_jurisdictions_cached,
        needs_plan_expand,
    )

    st = (state_code or "").strip().upper()
    if not st:
        return []

    job = load_batch_job_from_db(batch_id)
    if not job:
        return []

    status = (job.status or "").lower()
    if status == "running" and needs_plan_expand(job):
        rr = job.config.get("round_robin") if job.config else None
        if rr is None:
            rr = True
        plan = fetch_batch_plan_jurisdictions_cached([st], round_robin=bool(rr))
        expand_batch_job_plan(job, plan=plan)
        apply_batch_lifecycle(job)
        full = job.to_dict()
        return [
            slim_jurisdiction_videos(j, video_mode="none")
            for j in full.get("jurisdictions") or []
            if (j.get("state_code") or "").upper() == st
        ]

    rows = list_jurisdiction_rows_from_db(batch_id, st)
    if rows:
        return rows

    apply_batch_lifecycle(job)
    full = job.to_dict()
    return [
        slim_jurisdiction_videos(j, video_mode="none")
        for j in full.get("jurisdictions") or []
        if (j.get("state_code") or "").upper() == st
    ]

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.batch_jobs.batch_job_status import (
    _REPO_ROOT,
    BatchJob,
    _recompute_summary,
    apply_batch_lifecycle,
    count_policy_files_for_jurisdiction,
    expand_batch_job_plan,
    jobs_dir,
    latest_dashboard_activity_at,
    list_batches,
)

_DASHBOARD_NAME = "dashboard.html"
_POLICY_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def _fmt_duration(seconds: Any) -> str:
    if seconds is None:
        return "—"
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "—"
    if total < 60:
        return f"{total}s"
    m, s = divmod(total, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _enrich_file_counts(job: BatchJob) -> BatchJob:
    from api.batch_jobs.batch_job_status import policy_disk_file_counts

    for j in job.jurisdictions:
        scanned = count_policy_files_for_jurisdiction(
            _POLICY_CACHE,
            state_code=j.state_code,
            jurisdiction_id=j.jurisdiction_id,
        )
        j.file_counts = dict(j.file_counts or {})
        j.file_counts.update(policy_disk_file_counts(scanned))
    return job


def _aggregate_jobs(
    jobs: List[BatchJob],
    *,
    enrich_transcript_from_bronze: bool = False,
) -> Dict[str, Any]:
    batches: List[Dict[str, Any]] = []
    totals = {
        "batches": 0,
        "running": 0,
        "states": 0,
        "states_planned": 0,
        "states_started": 0,
        "states_completed": 0,
        "processed_jurisdictions": 0,
        "failed_jurisdictions": 0,
        "remaining_jurisdictions": 0,
        "videos_ok": 0,
        "videos_fail": 0,
        "videos_attempted": 0,
        "files_transcripts": 0,
        "files_transcripts_disk": 0,
        "transcript_hours": 0.0,
        "bronze_download_rows": 0,
        "files_analysis": 0,
        "files_reports": 0,
        "files_analysis_recent": 0,
        "files_reports_recent": 0,
    }
    planned_states: set[str] = set()
    started_states: set[str] = set()
    completed_states: set[str] = set()
    transcript_seconds = 0.0

    bronze_conn = None
    if enrich_transcript_from_bronze:
        try:
            from api.batch_jobs.batch_job_db import (
                enrich_transcript_seconds_from_bronze,
                get_db_connection,
            )

            bronze_conn = get_db_connection()
        except Exception:
            bronze_conn = None

    try:
        from api.batch_jobs.batch_job_status import (
            _batch_plan_cache_key,
            _recompute_summary,
            config_state_codes,
            expand_batch_job_plan,
            fetch_batch_plan_jurisdictions_cached,
            needs_plan_expand,
            normalize_batch_job_jurisdictions,
            persist_batch_job,
        )

        plan_by_states: Dict[str, list] = {}

        import logging

        _log = logging.getLogger(__name__)

        for job in jobs:
            try:
                status_before = job.status
                if needs_plan_expand(job):
                    states = config_state_codes(job.config or {})
                    rr = job.config.get("round_robin") if job.config else None
                    if rr is None:
                        rr = True
                    plan_key = _batch_plan_cache_key(states, round_robin=bool(rr))
                    if plan_key and plan_key not in plan_by_states:
                        plan_by_states[plan_key] = fetch_batch_plan_jurisdictions_cached(
                            states, round_robin=bool(rr)
                        )
                    expand_batch_job_plan(
                        job, plan=plan_by_states.get(plan_key) if plan_key else None
                    )
                    if (job.status or "").lower() == "running":
                        normalize_batch_job_jurisdictions(job)
                apply_batch_lifecycle(job)
                _recompute_summary(job)
                if status_before != job.status:
                    try:
                        persist_batch_job(job)
                    except Exception as exc:
                        _log.warning(
                            "persist batch %s failed: %s", job.batch_id, exc
                        )
                if bronze_conn is not None:
                    try:
                        enrich_transcript_seconds_from_bronze(bronze_conn, job)
                    except Exception:
                        pass
                d = job.to_dict()
            except Exception as exc:
                _log.exception("batch %s skipped in dashboard: %s", job.batch_id, exc)
                d = job.to_dict()
            batches.append(d)
            s = d.get("summary") or {}
            totals["batches"] += 1
            if d.get("status") == "running":
                totals["running"] += 1
            for st in config_state_codes(job.config or {}):
                planned_states.add(st)
            for st in s.get("states_started_codes") or []:
                started_states.add(str(st).upper())
            for st in s.get("states_completed_codes") or []:
                completed_states.add(str(st).upper())
            totals["processed_jurisdictions"] += int(s.get("processed_jurisdictions") or 0)
            totals["failed_jurisdictions"] += int(s.get("failed_jurisdictions") or 0)
            totals["remaining_jurisdictions"] += int(s.get("remaining_jurisdictions") or 0)
            totals["videos_ok"] += int(s.get("videos_ok") or 0)
            totals["videos_fail"] += int(s.get("videos_fail") or 0)
            attempted = int(s.get("videos_attempted") or s.get("files_processed") or 0)
            if not attempted:
                attempted = (
                    int(s.get("videos_ok") or 0)
                    + int(s.get("videos_fail") or 0)
                    + int(s.get("videos_tombstoned") or 0)
                    + int(s.get("videos_empty") or 0)
                    + int(s.get("videos_rate_limit") or 0)
                )
            totals["videos_attempted"] += attempted
            totals["files_transcripts"] += int(s.get("files_transcripts") or 0)
            totals["files_transcripts_disk"] += int(s.get("files_transcripts_disk") or 0)
            totals["bronze_download_rows"] += int(s.get("bronze_download_rows") or 0)
            totals["files_analysis"] += int(s.get("files_analysis") or 0)
            totals["files_reports"] += int(s.get("files_reports") or 0)
            totals["files_analysis_recent"] += int(s.get("files_analysis_recent") or 0)
            totals["files_reports_recent"] += int(s.get("files_reports_recent") or 0)
            transcript_seconds += float(s.get("transcript_seconds") or 0)
    finally:
        if bronze_conn is not None:
            try:
                bronze_conn.close()
            except Exception:
                pass

    totals["states_planned"] = len(planned_states)
    totals["states_started"] = len(started_states)
    totals["states_completed"] = len(completed_states)
    totals["states"] = totals["states_planned"]
    totals["transcript_hours"] = round(transcript_seconds / 3600.0, 2)

    import datetime as _dt

    from api.batch_jobs.batch_job_db import dashboard_stage_report

    now = _dt.datetime.now(_dt.timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "last_activity_at": latest_dashboard_activity_at(jobs),
        "totals": totals,
        "batches": batches,
        "stage_report": dashboard_stage_report(),
        "source": "database",
        "detail": "full",
    }


def _override_recent_counts_from_events(payload: Dict[str, Any]) -> None:
    """
    Replace the batch-scoped disk-scan counters with the live per-event bronze
    stamps (migration 083): the 24h throughput, the all-time pipeline totals (so
    progress % is de-duplicated and current), and the per-step "ago" timestamps.
    Best-effort: leaves the disk-scan values in place if the DB/columns are missing.
    """
    totals = payload.get("totals")
    if not isinstance(totals, dict):
        return
    try:
        from api.batch_jobs.batch_job_db import (
            get_db_connection,
            policy_event_counts_24h,
        )

        with get_db_connection() as conn:
            counts = policy_event_counts_24h(conn)
        totals["files_analysis_recent"] = int(counts.get("analysis") or 0)
        totals["files_reports_recent"] = int(counts.get("reports") or 0)
        totals["files_analysis_errors_recent"] = int(counts.get("analysis_errors") or 0)
        totals["files_reports_errors_recent"] = int(counts.get("reports_errors") or 0)
        transcripts_total = int(counts.get("transcripts_total") or 0)
        analysis_total = int(counts.get("analysis_total") or 0)
        reports_total = int(counts.get("reports_total") or 0)
        if transcripts_total > 0:
            totals["files_transcripts_disk"] = transcripts_total
        if analysis_total > 0:
            totals["files_analysis"] = analysis_total
        if reports_total > 0:
            totals["files_reports"] = reports_total
        totals["last_transcript_at"] = counts.get("last_transcript_at") or ""
        totals["last_analysis_at"] = counts.get("last_analysis_at") or ""
        totals["last_report_at"] = counts.get("last_report_at") or ""
    except Exception as exc:
        import logging

        logging.getLogger(__name__).debug(
            "recent-event count override skipped: %s", exc
        )


def build_dashboard_data(
    *,
    refresh_files: bool = False,
    enrich_bronze: bool = True,
    enrich_bronze_only_running: bool = False,
    batch_limit: int = 25,
    video_mode: VideoPayloadMode = "running",
) -> Dict[str, Any]:
    """
    Build dashboard payload. Prefer Postgres (``bronze.youtube_batch_job_runs``);
    fall back to JSON files under ``data/cache/batch_jobs/``.

    ``refresh_files`` scans the policy cache on disk (slow). By default transcript
  counts come from ``bronze.bronze_events_youtube`` when ``enrich_bronze`` is true.
    """
    import os

    use_db = os.getenv("BATCH_JOBS_USE_DB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    if use_db:
        try:
            from api.batch_jobs.batch_job_db import (
                enrich_jobs_from_bronze,
                list_batch_jobs_from_db,
                sync_json_batches_to_db,
            )

            jobs = list_batch_jobs_from_db(limit=batch_limit)
            if not jobs:
                sync_json_batches_to_db(limit=batch_limit)
                jobs = list_batch_jobs_from_db(limit=batch_limit)
            if jobs:
                if enrich_bronze:
                    enrich_jobs_from_bronze(
                        jobs,
                        only_running_jurisdictions=True,
                        enrich_disk=False,
                    )
                elif refresh_files:
                    for job in jobs:
                        _enrich_file_counts(job)
                payload = _aggregate_jobs(
                    jobs, enrich_transcript_from_bronze=enrich_bronze
                )
                _override_recent_counts_from_events(payload)
                if video_mode != "all":
                    payload["batches"] = [
                        slim_batch_dict(b, video_mode=video_mode)
                        for b in payload.get("batches") or []
                    ]
                payload["detail"] = "full"
                return payload
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "batch dashboard DB read failed, using JSON files: %s", exc
            )

    jobs = list_batches(limit=batch_limit)
    if refresh_files:
        for job in jobs:
            _enrich_file_counts(job)
    elif enrich_bronze:
        try:
            from api.batch_jobs.batch_job_db import enrich_jobs_from_bronze

            enrich_jobs_from_bronze(jobs)
        except Exception:
            pass
    payload = _aggregate_jobs(jobs, enrich_transcript_from_bronze=enrich_bronze)
    payload["source"] = "files"
    if video_mode != "all":
        payload["batches"] = [
            slim_batch_dict(b, video_mode=video_mode) for b in payload.get("batches") or []
        ]
    payload["detail"] = "full"
    return payload


def render_html(payload: Dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Batch job status</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --border: #2d3a4f;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --ok: #3dd68c;
      --fail: #f07178;
      --warn: #e7b86a;
      --run: #7eb6ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: baseline;
      justify-content: space-between;
    }}
    h1 {{ margin: 0; font-size: 1.35rem; font-weight: 600; }}
    .meta {{ color: var(--muted); font-size: 0.85rem; }}
    main {{ display: grid; grid-template-columns: 280px 1fr; min-height: calc(100vh - 72px); }}
    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; }}
    }}
    aside {{
      border-right: 1px solid var(--border);
      padding: 1rem;
      overflow: auto;
    }}
    section {{ padding: 1rem 1.25rem; overflow: auto; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 0.65rem;
      margin-bottom: 1.25rem;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem 0.85rem;
    }}
    .card .label {{ color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .card .value {{ font-size: 1.35rem; font-weight: 600; margin-top: 0.15rem; }}
    .batch-list {{ list-style: none; padding: 0; margin: 0; }}
    .batch-list li {{
      margin-bottom: 0.35rem;
    }}
    .batch-list button {{
      width: 100%;
      text-align: left;
      background: transparent;
      border: 1px solid transparent;
      color: var(--text);
      padding: 0.55rem 0.65rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.88rem;
    }}
    .batch-list button:hover {{ background: var(--panel); }}
    .batch-list button.active {{
      background: var(--panel);
      border-color: var(--accent);
    }}
    .badge {{
      display: inline-block;
      font-size: 0.68rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      margin-left: 0.35rem;
      vertical-align: middle;
    }}
    .badge.running {{ background: #1e3a5f; color: var(--run); }}
    .badge.completed {{ background: #1a3d2e; color: var(--ok); }}
    .badge.failed {{ background: #3d2226; color: var(--fail); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.86rem;
    }}
    th, td {{
      text-align: left;
      padding: 0.5rem 0.6rem;
      border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; }}
    tr.j-row {{ cursor: pointer; }}
    tr.j-row:hover {{ background: rgba(61, 139, 253, 0.08); }}
    tr.j-row.selected {{ background: rgba(61, 139, 253, 0.15); }}
    .status-ok {{ color: var(--ok); }}
    .status-fail {{ color: var(--fail); }}
    .status-running {{ color: var(--run); }}
    .detail-panel {{
      margin-top: 1rem;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
    }}
    .detail-panel h3 {{ margin: 0 0 0.75rem; font-size: 1rem; }}
    .empty {{ color: var(--muted); padding: 2rem; text-align: center; }}
    .bar-wrap {{
      height: 8px;
      background: var(--border);
      border-radius: 4px;
      overflow: hidden;
      margin-top: 0.5rem;
    }}
    .bar-fill {{ height: 100%; background: var(--accent); }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Batch job status</h1>
      <div class="meta" id="generated-meta"></div>
    </div>
    <div class="meta">Refresh: re-run <code>batch_job_dashboard.py --build</code></div>
  </header>
  <main>
    <aside>
      <div class="cards" id="global-cards"></div>
      <ul class="batch-list" id="batch-list"></ul>
    </aside>
    <section>
      <div id="batch-detail" class="empty">Select a batch</div>
      <div id="jurisdiction-detail"></div>
    </section>
  </main>
  <script>
    const DATA = {data_json};
    const fmtDur = (s) => {{
      if (s == null || s === '') return '—';
      const t = Math.max(0, Math.floor(Number(s)));
      if (t < 60) return t + 's';
      const m = Math.floor(t / 60);
      const r = t % 60;
      if (m < 60) return m + 'm ' + r + 's';
      const h = Math.floor(m / 60);
      return h + 'h ' + (m % 60) + 'm';
    }};
    let selectedBatchId = null;
    let selectedJurisdictionId = null;

    function renderGlobalCards() {{
      const t = DATA.totals;
      const cards = [
        ['Batches', t.batches],
        ['Running', t.running],
        ['Jurisdictions done', t.processed_jurisdictions],
        ['Jurisdictions failed', t.failed_jurisdictions],
        ['Remaining', t.remaining_jurisdictions],
        ['Videos OK', t.videos_ok],
        ['Videos failed', t.videos_fail],
        ['Videos attempted (batch)', t.videos_attempted],
        ['Transcripts on disk', t.files_transcripts_disk],
        ['Bronze download rows', t.bronze_download_rows],
        ['Analysis on disk', t.files_analysis],
        ['Reports on disk', t.files_reports],
        ['Analysis (24h)', t.files_analysis_recent],
        ['Reports (24h)', t.files_reports_recent],
      ];
      document.getElementById('global-cards').innerHTML = cards.map(([l,v]) =>
        `<div class="card"><div class="label">${{l}}</div><div class="value">${{v}}</div></div>`
      ).join('');
      document.getElementById('generated-meta').textContent =
        'Generated ' + (DATA.generated_at || '').replace('T', ' ').slice(0, 19) + ' UTC';
    }}

    function statusClass(st) {{
      if (st === 'completed') return 'status-ok';
      if (st === 'failed') return 'status-fail';
      if (st === 'running') return 'status-running';
      return '';
    }}

    function renderBatchList() {{
      const ul = document.getElementById('batch-list');
      ul.innerHTML = DATA.batches.map(b => {{
        const s = b.summary || {{}};
        const pct = s.total_jurisdictions
          ? Math.round(100 * (s.processed_jurisdictions || 0) / s.total_jurisdictions)
          : 0;
        return `<li>
          <button type="button" data-id="${{b.batch_id}}" class="${{selectedBatchId === b.batch_id ? 'active' : ''}}">
            <div><strong>${{b.step}}</strong>
              <span class="badge ${{b.status}}">${{b.status}}</span></div>
            <div class="meta">${{b.batch_id}}</div>
            <div class="meta">${{s.processed_jurisdictions || 0}}/${{s.total_jurisdictions || '?'}} jurisdictions · ${{pct}}%</div>
          </button>
        </li>`;
      }}).join('');
      ul.querySelectorAll('button').forEach(btn => {{
        btn.addEventListener('click', () => selectBatch(btn.dataset.id));
      }});
      if (!selectedBatchId && DATA.batches.length) selectBatch(DATA.batches[0].batch_id);
    }}

    function selectBatch(id) {{
      selectedBatchId = id;
      selectedJurisdictionId = null;
      renderBatchList();
      renderBatchDetail();
      document.getElementById('jurisdiction-detail').innerHTML = '';
    }}

    function renderBatchDetail() {{
      const el = document.getElementById('batch-detail');
      const b = DATA.batches.find(x => x.batch_id === selectedBatchId);
      if (!b) {{ el.innerHTML = '<div class="empty">No batch selected</div>'; return; }}
      const s = b.summary || {{}};
      const cfg = b.config || {{}};
      const pct = s.total_jurisdictions
        ? Math.round(100 * (s.processed_jurisdictions || 0) / s.total_jurisdictions)
        : 0;
      const jurs = b.jurisdictions || [];
      el.innerHTML = `
        <h2 style="margin:0 0 0.5rem;font-size:1.15rem">${{b.step}} <span class="badge ${{b.status}}">${{b.status}}</span></h2>
        <div class="meta">${{b.batch_id}} · started ${{b.started_at || '—'}}</div>
        <div class="cards" style="margin-top:1rem">
          <div class="card"><div class="label">Processed</div><div class="value">${{s.processed_jurisdictions || 0}} / ${{s.total_jurisdictions || '?'}}</div></div>
          <div class="card"><div class="label">Success</div><div class="value status-ok">${{s.success_jurisdictions || 0}}</div></div>
          <div class="card"><div class="label">Failed</div><div class="value status-fail">${{s.failed_jurisdictions || 0}}</div></div>
          <div class="card"><div class="label">Remaining</div><div class="value">${{s.remaining_jurisdictions || 0}}</div></div>
          <div class="card"><div class="label">Elapsed</div><div class="value">${{fmtDur(s.elapsed_seconds)}}</div></div>
          <div class="card"><div class="label">ETA</div><div class="value">${{fmtDur(s.eta_seconds)}}</div></div>
          <div class="card"><div class="label">Videos OK</div><div class="value">${{s.videos_ok || 0}}</div></div>
          <div class="card"><div class="label">Videos fail</div><div class="value">${{s.videos_fail || 0}}</div></div>
        </div>
        <div class="bar-wrap"><div class="bar-fill" style="width:${{pct}}%"></div></div>
        <p class="meta" style="margin-top:0.75rem">States: ${{(cfg.states || []).join(', ') || '—'}} · N=${{cfg.n || '—'}} · delay=${{cfg.delay || '—'}}s · source=${{cfg.transcript_source || '—'}}</p>
        <h3 style="margin:1.25rem 0 0.5rem;font-size:0.95rem">Jurisdictions (${{jurs.length}})</h3>
        <table>
          <thead><tr>
            <th>State</th><th>Jurisdiction</th><th>Status</th><th>Videos</th><th>Files</th><th>Time</th>
          </tr></thead>
          <tbody id="juris-table-body"></tbody>
        </table>
      `;
      const tbody = document.getElementById('juris-table-body');
      tbody.innerHTML = jurs.map(j => {{
        const st = j.stats || {{}};
        const fc = j.file_counts || {{}};
        const vids = (st.ok || 0) + (st.fail || 0) + (st.tombstoned || 0);
        return `<tr class="j-row ${{selectedJurisdictionId === j.jurisdiction_id ? 'selected' : ''}}" data-jid="${{j.jurisdiction_id}}">
          <td>${{j.state_code}}</td>
          <td><strong>${{j.jurisdiction_name || j.jurisdiction_id}}</strong><br><span class="meta">${{j.jurisdiction_id}}</span></td>
          <td class="${{statusClass(j.status)}}">${{j.status}}${{j.exit_code ? ' (' + j.exit_code + ')' : ''}}</td>
          <td>ok ${{st.ok || 0}} · fail ${{st.fail || 0}} · tomb ${{st.tombstoned || 0}}${{vids ? '' : ''}}</td>
          <td>T ${{fc.transcripts || 0}} · A ${{fc.analysis || 0}} · R ${{fc.reports || 0}}</td>
          <td>${{fmtDur(j.elapsed_seconds)}}</td>
        </tr>`;
      }}).join('');
      tbody.querySelectorAll('.j-row').forEach(row => {{
        row.addEventListener('click', () => selectJurisdiction(b, row.dataset.jid));
      }});
    }}

    function selectJurisdiction(batch, jid) {{
      selectedJurisdictionId = jid;
      renderBatchDetail();
      const j = (batch.jurisdictions || []).find(x => x.jurisdiction_id === jid);
      const panel = document.getElementById('jurisdiction-detail');
      if (!j) {{ panel.innerHTML = ''; return; }}
      const videos = j.videos || [];
      panel.innerHTML = `
        <div class="detail-panel">
          <h3>${{j.jurisdiction_name || j.jurisdiction_id}} — videos (${{videos.length}})</h3>
          <table>
            <thead><tr><th>Video</th><th>Title</th><th>Status</th><th>Source</th><th>Error</th></tr></thead>
            <tbody>
              ${{videos.length ? videos.map(v => `
                <tr>
                  <td><a href="https://www.youtube.com/watch?v=${{v.video_id}}" target="_blank" rel="noopener">${{v.video_id}}</a></td>
                  <td>${{escapeHtml(v.title || '')}}</td>
                  <td class="${{v.status === 'ok' ? 'status-ok' : 'status-fail'}}">${{v.status}}</td>
                  <td>${{v.transcript_source || '—'}}</td>
                  <td class="meta">${{escapeHtml(v.error || '')}}</td>
                </tr>`).join('') : '<tr><td colspan="5" class="meta">No per-video log (re-run with --batch-id)</td></tr>'}}
            </tbody>
          </table>
          <p class="meta" style="margin-top:0.75rem">Stats: ${{JSON.stringify(j.stats || {{}})}}</p>
        </div>
      `;
    }}

    function escapeHtml(s) {{
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }}

    renderGlobalCards();
    renderBatchList();
  </script>
</body>
</html>
"""


def write_dashboard(*, refresh_files: bool = True) -> Path:
    out_dir = jobs_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_dashboard_data(refresh_files=refresh_files)
    out_path = out_dir / _DASHBOARD_NAME
    out_path.write_text(render_html(payload), encoding="utf-8")
    return out_path


def serve_dashboard(port: int = 8765) -> None:
    root = jobs_dir()
    root.mkdir(parents=True, exist_ok=True)
    handler = SimpleHTTPRequestHandler
    original = handler.directory

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}/{_DASHBOARD_NAME}"
    print(f"Serving {root} at {url}")
    print("Ctrl+C to stop")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Write dashboard.html")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser after build")
    parser.add_argument("--serve", action="store_true", help="Serve jobs dir and open dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-refresh-files",
        action="store_true",
        help="Skip scanning policy cache for file counts (faster)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print dashboard JSON to stdout (for Vite dev fallback / debugging)",
    )
    args = parser.parse_args()

    if args.json:
        payload = build_dashboard_data(refresh_files=not args.no_refresh_files)
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.serve:
        write_dashboard(refresh_files=not args.no_refresh_files)
        serve_dashboard(port=args.port)
        return 0

    if args.build or not (args.build or args.serve):
        path = write_dashboard(refresh_files=not args.no_refresh_files)
        print(path)
        if args.open:
            webbrowser.open(path.as_uri())
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
