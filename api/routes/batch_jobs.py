"""
YouTube / policy pipeline batch job status for the Data explorer React UI.

Reads from ``bronze.youtube_batch_job_runs`` (real-time). JSON files under
``data/cache/batch_jobs/`` are synced on read when the DB is empty.

Live updates: ``GET /api/batch-jobs/stream`` (Server-Sent Events).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

# A "running" launch that has produced no pipeline activity for this long is
# treated as stalled/timed-out, so the dashboard re-enables launching.
_LAUNCH_STALL_SECONDS = 3600
# Softer signal: warn on the dashboard well before the stall reap (#750).
_LAUNCH_WARN_SECONDS_DEFAULT = 900

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from api.auth import require_admin

router = APIRouter(prefix="/batch-jobs", tags=["batch-jobs"])


def _launch_warn_seconds() -> float:
    raw = os.getenv("BATCH_JOB_LAUNCH_WARN_SECONDS", str(_LAUNCH_WARN_SECONDS_DEFAULT))
    try:
        return max(60.0, float(raw))
    except (TypeError, ValueError):
        return float(_LAUNCH_WARN_SECONDS_DEFAULT)


# Launch-log lines that mean YouTube traffic cannot leave through the VPN (#488 / #750).
_VPN_DOWN_RE = re.compile(
    r"Surfshark is off|VpnRequiredError|no VPN tunnel route",
    re.IGNORECASE,
)


class BatchJobsTotals(BaseModel):
    batches: int = 0
    running: int = 0
    states: int = 0
    states_planned: int = 0
    states_started: int = 0
    states_completed: int = 0
    processed_jurisdictions: int = 0
    failed_jurisdictions: int = 0
    remaining_jurisdictions: int = 0
    videos_ok: int = 0
    videos_fail: int = 0
    videos_attempted: int = 0
    files_transcripts: int = 0
    files_transcripts_disk: int = 0
    transcript_hours: float = 0.0
    bronze_download_rows: int = 0
    files_analysis: int = 0
    files_reports: int = 0
    # Rolling 24h throughput from per-event bronze stamps (migration 083).
    files_analysis_recent: int = 0
    files_reports_recent: int = 0
    files_analysis_errors_recent: int = 0
    files_reports_errors_recent: int = 0
    # Most recent stamp per step (all time) for the "ago" cards.
    last_transcript_at: str = ""
    last_analysis_at: str = ""
    last_report_at: str = ""


class VideoResultModel(BaseModel):
    video_id: str
    title: str = ""
    status: str = "pending"
    error: str = ""
    transcript_source: str = ""
    finished_at: str = ""
    duration_seconds: float | None = None


class JurisdictionRunModel(BaseModel):
    state_code: str
    jurisdiction_id: str
    jurisdiction_name: str = ""
    status: str = "pending"
    started_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float = 0
    exit_code: int = 0
    stats: Dict[str, int] = Field(default_factory=dict)
    videos: List[VideoResultModel] = Field(default_factory=list)
    file_counts: Dict[str, int] = Field(default_factory=dict)
    current_video_id: str = ""
    current_video_title: str = ""
    current_video_started_at: str = ""


class BatchJobModel(BaseModel):
    batch_id: str
    step: str
    status: str
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    jurisdictions: List[JurisdictionRunModel] = Field(default_factory=list)


class StageBreakdownEntry(BaseModel):
    # Per-entity split of a stage's coverage (e.g. discover: counties vs
    # municipalities). Entries sum back to the parent row's done/total.
    entity: str
    done: int = 0
    total: int = 0
    failed: int = 0


class StageReportRow(BaseModel):
    # One (scope, stage) row. scope is a 2-letter state code or "ALL" (rollup).
    scope: str
    stage: str
    done: int = 0
    total: int = 0
    failed: int = 0
    last_at: str = ""
    # Optional per-entity split (only populated for the discover stage today).
    breakdown: List[StageBreakdownEntry] = Field(default_factory=list)


class StageReport(BaseModel):
    states: List[str] = Field(default_factory=list)
    rows: List[StageReportRow] = Field(default_factory=list)
    # Per-stage cadence/last-file:
    # {stage: {avg_seconds, last_path, last_at, stale_seconds, effective_seconds}}.
    # effective_seconds = max(avg_seconds, stale_seconds) so /hr and ETA reflect a
    # stall in progress, not just the historical pace between completions.
    timing: Dict[str, Any] = Field(default_factory=dict)


class BatchJobsDashboardResponse(BaseModel):
    generated_at: str
    last_activity_at: str = ""
    totals: BatchJobsTotals
    batches: List[BatchJobModel]
    stage_report: StageReport = Field(default_factory=StageReport)
    source: str = "database"
    detail: str = "full"


def _sanitize_dashboard_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce DB payloads so Pydantic response validation does not 500."""
    import math

    totals = payload.get("totals")
    if isinstance(totals, dict):
        th = totals.get("transcript_hours")
        if isinstance(th, float) and (math.isnan(th) or math.isinf(th)):
            totals["transcript_hours"] = 0.0

    for batch in payload.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        for j in batch.get("jurisdictions") or []:
            if not isinstance(j, dict):
                continue
            raw_stats = j.get("stats")
            if isinstance(raw_stats, dict):
                clean: Dict[str, int] = {}
                for key, val in raw_stats.items():
                    try:
                        clean[str(key)] = int(val)
                    except (TypeError, ValueError):
                        continue
                j["stats"] = clean
            for field in ("elapsed_seconds",):
                try:
                    j[field] = float(j.get(field) or 0)
                except (TypeError, ValueError):
                    j[field] = 0.0
    return payload


def _parse_dashboard_cohort(cohort: Optional[str] = None) -> Optional[str]:
    """Normalize optional dashboard ``?cohort=`` (priority / data_centers scope stage_report)."""
    if cohort is None or not str(cohort).strip():
        return None
    c = str(cohort).strip().lower()
    if c not in ("priority", "data_centers", "all"):
        raise HTTPException(
            status_code=400,
            detail="cohort must be one of priority, data_centers, all",
        )
    return c


async def _latest_dashboard_revision_async() -> Optional[str]:
    try:
        from api.batch_jobs.batch_job_db import latest_dashboard_revision

        return await asyncio.to_thread(latest_dashboard_revision)
    except Exception:
        return None


async def _load_dashboard_async(
    *,
    refresh_files: bool,
    enrich_bronze: bool,
    enrich_bronze_only_running: bool = False,
    detail: str = "full",
    batch_limit: int = 25,
    cohort: Optional[str] = None,
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _load_dashboard,
        refresh_files=refresh_files,
        enrich_bronze=enrich_bronze,
        enrich_bronze_only_running=enrich_bronze_only_running,
        detail=detail,
        batch_limit=batch_limit,
        cohort=cohort,
    )


def _load_dashboard(
    *,
    refresh_files: bool,
    enrich_bronze: bool,
    enrich_bronze_only_running: bool = False,
    detail: str = "full",
    batch_limit: int = 25,
    cohort: Optional[str] = None,
) -> Dict[str, Any]:
    from api.batch_jobs.batch_job_dashboard import (
        VideoPayloadMode,
        build_dashboard_data,
        build_dashboard_summary,
    )

    if detail == "summary":
        payload = build_dashboard_summary(limit=batch_limit, cohort=cohort)
    else:
        video_mode: VideoPayloadMode = "all" if detail == "full" else "running"
        payload = build_dashboard_data(
            refresh_files=refresh_files,
            enrich_bronze=enrich_bronze,
            enrich_bronze_only_running=enrich_bronze_only_running,
            batch_limit=batch_limit,
            video_mode=video_mode,
            cohort=cohort,
        )
    return _sanitize_dashboard_payload(payload)


@router.get("/stream")
async def stream_batch_jobs(
    refresh_files: bool = Query(False),
    enrich_bronze: bool = Query(
        False,
        description="When true, refresh transcript counts from bronze each tick (heavier)",
    ),
    cohort: Optional[str] = Query(
        None,
        description="Launch cohort; data_centers scopes stage_report to DC jurisdictions",
    ),
) -> StreamingResponse:
    """SSE stream of dashboard JSON; pushes when DB revision changes."""
    cohort_norm = _parse_dashboard_cohort(cohort)

    async def event_generator() -> AsyncIterator[str]:
        last_rev: Optional[str] = None
        running_batches = 0
        while True:
            rev = await _latest_dashboard_revision_async()

            if last_rev is None or rev != last_rev:
                summary = await _load_dashboard_async(
                    refresh_files=False,
                    enrich_bronze=False,
                    detail="summary",
                    cohort=cohort_norm,
                )
                yield (
                    "event: summary\n"
                    f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"
                )
                totals = summary.get("totals") or {}
                running_batches = int(totals.get("running") or 0)
                last_rev = rev

            await asyncio.sleep(1.0 if running_batches > 0 else 3.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Dashboard response cache -------------------------------------------------
# The dashboard aggregates (especially the int_events_union transcript-coverage
# view) take ~30s, and the UI polls frequently — so without caching every poll
# re-runs the whole thing and competes with the analyze backfill's writes, the
# endpoint exceeds the client timeout, and the UI shows "empty response". Cache
# the assembled payload per param-set with a short TTL: single-flight (concurrent
# polls share one computation), stale-while-revalidate (serve the last result
# instantly and refresh in the background once stale), and shielded so a client
# disconnect still lets the in-flight computation finish and populate the cache —
# so the next "Retry load" hits it warm. Tune via BATCH_JOBS_DASHBOARD_TTL_SECONDS
# (default 20); set to 0 to disable caching.
_DASH_CACHE: Dict[tuple, tuple] = {}
_DASH_INFLIGHT: Dict[tuple, Any] = {}


def _dash_ttl() -> float:
    try:
        return max(0.0, float(os.environ.get("BATCH_JOBS_DASHBOARD_TTL_SECONDS", "20")))
    except ValueError:
        return 20.0


async def _load_dashboard_cached(**kwargs: Any) -> Dict[str, Any]:
    ttl = _dash_ttl()
    if ttl <= 0:
        return await _load_dashboard_async(**kwargs)

    key = tuple(sorted(kwargs.items()))
    loop = asyncio.get_running_loop()
    hit = _DASH_CACHE.get(key)
    if hit is not None and loop.time() - hit[0] < ttl:
        return hit[1]  # fresh

    async def _compute() -> Dict[str, Any]:
        try:
            payload = await _load_dashboard_async(**kwargs)
            _DASH_CACHE[key] = (loop.time(), payload)
            return payload
        finally:
            _DASH_INFLIGHT.pop(key, None)

    task = _DASH_INFLIGHT.get(key)
    if task is None or task.done():
        task = loop.create_task(_compute())
        _DASH_INFLIGHT[key] = task

    if hit is not None:
        return hit[1]  # stale-while-revalidate: serve stale, refresh in background
    # Cold cache: must wait for the first computation. Shield it so a client
    # timeout/disconnect doesn't cancel the work — it still caches for the retry.
    return await asyncio.shield(task)


@router.get("/", response_model=BatchJobsDashboardResponse)
@router.get("", response_model=BatchJobsDashboardResponse, include_in_schema=False)
async def list_batch_jobs(
    refresh_files: bool = Query(
        False,
        description="Scan policy cache on disk for analysis/report counts (slow)",
    ),
    enrich_bronze: bool = Query(
        False,
        description="Refresh transcript metrics from bronze (slow; stream uses lighter enrich)",
    ),
    detail: str = Query(
        "summary",
        description="summary = aggregates + batch list (default); standard/full load jurisdiction payloads (slow)",
    ),
    batch_limit: int = Query(25, ge=1, le=100),
    cohort: Optional[str] = Query(
        None,
        description="Launch cohort; data_centers scopes stage_report to DC jurisdictions",
    ),
) -> BatchJobsDashboardResponse:
    if detail not in ("summary", "standard", "full"):
        raise HTTPException(
            status_code=400,
            detail="detail must be summary, standard, or full",
        )
    cohort_norm = _parse_dashboard_cohort(cohort)
    try:
        payload = await _load_dashboard_cached(
            refresh_files=refresh_files,
            enrich_bronze=enrich_bronze,
            detail=detail,
            batch_limit=batch_limit,
            cohort=cohort_norm,
        )
        return BatchJobsDashboardResponse(**payload)
    except Exception as exc:
        logger.exception("batch-jobs dashboard failed")
        raise HTTPException(
            status_code=500,
            detail=f"Batch jobs dashboard failed: {exc}",
        ) from exc


# --- Re-kick: (re)launch a stopped pipeline run from the dashboard --------------
# Spawns the existing wrapper script as a detached subprocess. Hardened against
# misuse: a fixed argv (no shell), an allowlisted step, validated state codes, a
# single-run guard (won't double-launch), and an opt-out kill switch.
_LAUNCH_SCRIPT = "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
# Stage 0 (discover) runs a different, per-state script; the rest run the wrapper.
_DISCOVER_SCRIPT = "packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py"
# `backfill` runs the flat, mart-wide transcript sweep (reaches LocalView/union
# videos with no jurisdiction the per-jurisdiction `captions` loop never visits).
_BACKFILL_SCRIPT = "packages/scrapers/src/scrapers/youtube/backfill_transcripts.py"
# analyze / analyze-light are aliases (light Part 1). reports-* = Part 2 only.
# analyze-full / reports-full are opt-in and require full_filters (#755).
_LAUNCH_STEPS = (
    "discover",
    "catalog",
    "captions",
    "backfill",
    "analyze",
    "analyze-light",
    "reports-light",
    "analyze-full",
    "reports-full",
    "each",
    "all",
)
_FULL_FILTER_STEPS = frozenset({"analyze-full", "reports-full"})
_FULL_FILTER_KEYS = frozenset({"has_decisions", "interestingness", "data_center"})
# Steps that talk to YouTube and must wait for the VPN tunnel before auto-resume (#752).
_LAUNCH_STEPS_NEED_VPN = frozenset(_LAUNCH_STEPS)
_STATE_RE = re.compile(r"^[A-Z]{2}$")
_VPN_EXIT_CODE = 5


def _auto_resume_enabled() -> bool:
    if not _launch_enabled():
        return False
    v = (os.getenv("BATCH_JOBS_AUTO_RESUME") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _auto_resume_max() -> int:
    raw = os.getenv("BATCH_JOBS_AUTO_RESUME_MAX", "5")
    try:
        return max(0, min(20, int(raw)))
    except (TypeError, ValueError):
        return 5


def _vpn_tunnel_up_for_resume() -> bool:
    """Route-table only (no public-IP lookups) so the watchdog cannot hang (#752)."""
    try:
        from scrapers.youtube.vpn_guard import read_routes, vpn_required

        if not vpn_required():
            return True
        return bool(read_routes().tunnel_interface)
    except Exception as exc:
        logger.debug("vpn tunnel check for resume failed: {!r}", exc)
        return False


def _read_exit_code(meta: Dict[str, Any]) -> Optional[int]:
    path = Path(str(meta.get("exit_path") or ""))
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        return int(text)
    except (OSError, ValueError, IndexError):
        return None


def _repo_root() -> Path:
    # api/routes/batch_jobs.py -> repo root
    return Path(__file__).resolve().parents[2]


def _launch_enabled() -> bool:
    # Opt-in: disabled unless BATCH_JOBS_ALLOW_LAUNCH is explicitly truthy on this
    # deploy (defaults off, matching deployments.py). The mutating endpoints are
    # additionally gated by require_admin.
    return os.getenv("BATCH_JOBS_ALLOW_LAUNCH", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _launch_meta_path() -> Path:
    return _repo_root() / "data" / "cache" / "batch_jobs" / "launch.json"


def _read_launches() -> List[Dict[str, Any]]:
    """All tracked launches: list of {pid, step, states, started_at}."""
    try:
        data = json.loads(_launch_meta_path().read_text())
    except (OSError, ValueError, FileNotFoundError):
        return []
    if isinstance(data, dict):  # legacy single-launch file
        return [data]
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def _write_launches(launches: List[Dict[str, Any]]) -> None:
    try:
        _launch_meta_path().write_text(json.dumps(launches))
    except Exception:
        pass


def _pid_alive(pid: Any) -> bool:
    try:
        p = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        os.kill(p, 0)  # signal 0 = exists (but zombies pass this too)
    except OSError:
        return False
    # A finished-but-unreaped child shows as a zombie ("Z"/"X"); treat it as dead
    # so a completed launch doesn't pin the dashboard at "running" forever.
    try:
        with open(f"/proc/{p}/stat") as fh:
            state = fh.read().split(") ", 1)[1][:1]
        if state in ("Z", "X"):
            try:
                os.waitpid(p, os.WNOHANG)  # reap if it's our child
            except (ChildProcessError, OSError):
                pass
            return False
    except (FileNotFoundError, IndexError):
        pass
    return True


def _dashboard_runtime() -> "tuple[int, str]":
    """(# running batch rows, freshest pipeline-activity ISO) in one DB hit."""
    try:
        from api.batch_jobs.batch_job_db import aggregate_dashboard_totals_from_db

        t = aggregate_dashboard_totals_from_db(limit=10) or {}
        running = int(t.get("running") or 0)
        freshest = max(
            str(t.get(k) or "")
            for k in (
                "last_activity_at",
                "last_transcript_at",
                "last_analysis_at",
                "last_report_at",
            )
        )
        return running, freshest
    except Exception:
        return 0, ""


def _iso_age_seconds(iso: str) -> Optional[float]:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _latest_launch_log(step: str) -> Optional[Path]:
    log_dir = _repo_root() / "data" / "cache" / "batch_jobs"
    candidates = sorted(log_dir.glob(f"launch_{step}_*.log"), reverse=True)
    return candidates[0] if candidates else None


def _launch_log_signals(step: str, *, lines: int = 80) -> Dict[str, Any]:
    """Last activity timestamp + VPN-down hint from the newest launch log for ``step``."""
    path = _latest_launch_log(step)
    if path is None:
        return {"last_at": "", "vpn_down": False, "path": ""}
    tail = _tail_lines(path, lines)
    _current, since = _parse_current(tail)
    if not since:
        try:
            since = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            since = ""
    vpn_down = any(_VPN_DOWN_RE.search(ln or "") for ln in tail[-40:])
    return {"last_at": since, "vpn_down": vpn_down, "path": str(path)}


def _launch_activity_iso(live: Dict[str, Any], freshest: str) -> str:
    """Best-effort 'last progress' for a live launch.

    Discover/backfill do not stamp ``youtube_batch_job_runs`` the way catalog/
    captions do, so unrelated analyze/transcript freshest must not hide a hung
    discover log (#750).
    """
    step = str(live.get("step") or "")
    started = str(live.get("started_at") or "")
    log_at = str(_launch_log_signals(step).get("last_at") or "")
    if step in ("discover", "backfill"):
        return max(started, log_at)
    return max(freshest or "", started, log_at)


def _launch_stalled(live: Dict[str, Any], freshest: str) -> bool:
    """A live launch with no activity (or none since it started) for over the
    stall window — i.e. stuck. ``freshest`` and ``started_at`` are UTC ISO."""
    last_seen = _launch_activity_iso(live, freshest)
    age = _iso_age_seconds(last_seen) if last_seen else None
    return age is not None and age > _LAUNCH_STALL_SECONDS


def _kill_launch(meta: Dict[str, Any], *, sig: int = signal.SIGTERM) -> None:
    """Best-effort signal to a launch's process group (SIGTERM by default).

    Launches start with ``start_new_session=True`` so the pid is its own process
    group leader; signalling the group reaches the whole pipeline subtree.
    """
    try:
        os.killpg(os.getpgid(int(meta["pid"])), sig)
    except Exception:
        # Fall back to signalling just the pid if the group lookup fails.
        try:
            os.kill(int(meta["pid"]), sig)
        except Exception:
            pass


def _classify_launches(freshest: str) -> "tuple[List[Dict[str, Any]], List[Dict[str, Any]]]":
    """(running, stalled) metas among live launches; dead ones are ignored."""
    running: List[Dict[str, Any]] = []
    stalled: List[Dict[str, Any]] = []
    for m in _read_launches():
        if not _pid_alive(m.get("pid")):
            continue
        (stalled if _launch_stalled(m, freshest) else running).append(m)
    return running, stalled


class LaunchRequest(BaseModel):
    step: str = "analyze"
    states: List[str] = Field(default_factory=list)
    n: int = 10
    parallel: int = 4
    cohort: str = "priority"
    # Multi-select eligibility for analyze-full / reports-full (#755). OR semantics.
    full_filters: List[str] = Field(default_factory=list)


class LaunchStatusResponse(BaseModel):
    enabled: bool
    busy: bool = False
    running: int = 0
    # Per-step concurrency: different steps may run at once; the same step may not.
    running_steps: List[str] = Field(default_factory=list)
    stalled_steps: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=lambda: list(_LAUNCH_STEPS))
    # Operator-facing stall / VPN signals (#750). ``warning`` is empty when idle.
    warning: str = ""
    vpn_down: bool = False
    inactive_seconds: Optional[float] = None
    # Steps the watchdog re-spawned on this status poll (#752).
    resumed_steps: List[str] = Field(default_factory=list)
    auto_resume_note: str = ""


class LaunchResponse(BaseModel):
    launched: bool
    pid: Optional[int] = None
    step: str = ""
    states: List[str] = Field(default_factory=list)
    log: str = ""
    detail: str = ""


def _recent_log_vpn_down(*, max_age_seconds: float = 7200.0) -> bool:
    """True when a recent launch log (even after the PID exited) mentions VPN down."""
    for step in _LAUNCH_STEPS:
        signals = _launch_log_signals(step)
        if not signals.get("vpn_down"):
            continue
        age = _iso_age_seconds(str(signals.get("last_at") or ""))
        if age is not None and age <= max_age_seconds:
            return True
    return False


def _launch_operator_signals(
    freshest: str,
    running: List[Dict[str, Any]],
    stalled: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build warning / vpn_down / inactive_seconds for the dashboard header."""
    warn_after = _launch_warn_seconds()
    warning = ""
    vpn_down = False
    inactive_seconds: Optional[float] = None
    for m in (*running, *stalled):
        step = str(m.get("step") or "") or "pipeline"
        signals = _launch_log_signals(step)
        if signals.get("vpn_down"):
            vpn_down = True
        last_seen = _launch_activity_iso(m, freshest)
        age = _iso_age_seconds(last_seen) if last_seen else None
        if age is None:
            continue
        inactive_seconds = age if inactive_seconds is None else max(inactive_seconds, age)
        if age >= warn_after and not warning:
            mins = max(1, int(age // 60))
            warning = (
                f"{step}: no launch-log activity for {mins}m — "
                "job may be stuck (check VPN / Surfshark)."
            )
    # Process already exited after VpnRequiredError — still show the error for a while.
    if not vpn_down and _recent_log_vpn_down():
        vpn_down = True
    if vpn_down:
        warning = (
            "VPN appears down (Surfshark off in launch log). "
            "Connect Surfshark and re-run."
            + (f" {warning}" if warning and "Surfshark off" not in warning else "")
        )
    elif stalled and not warning:
        steps = ", ".join(sorted({str(m.get("step") or "") for m in stalled} - {""})) or "pipeline"
        warning = f"{steps}: timed out (no activity >1h) — re-launch after fixing VPN/blockers."
    return {
        "warning": warning,
        "vpn_down": vpn_down,
        "inactive_seconds": inactive_seconds,
    }


def _discover_argv(states: List[str], cohort: str) -> List[str]:
    """Argv for the Discover CLI (channel candidates). Raises ValueError if missing."""
    if not states:
        raise ValueError("discover requires at least one state.")
    target = _repo_root() / _DISCOVER_SCRIPT
    if not target.is_file():
        raise ValueError(f"discover script missing: {target}")
    import sys as _sys

    # --load: after each state CSV, catalog candidates so scraped bronze
    # youtube_channel_* / discovered_at update as loads land (#740).
    argv = [
        _sys.executable,
        str(target),
        "--states",
        ",".join(states),
        "--load",
    ]
    if cohort == "data_centers":
        argv += ["--cohort", "data_centers"]
    return argv


def _normalize_full_filters(raw: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in raw or []:
        key = str(item or "").strip().lower()
        if key not in _FULL_FILTER_KEYS or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _shell_step_for_launch(step: str) -> str:
    """Map API launch step → shell wrapper argument."""
    if step in ("analyze", "analyze-light"):
        return "analyze-light"
    return step


def _build_launch_argv(
    step: str,
    *,
    states: List[str],
    cohort: str,
    n: int,
    parallel: int,
    full_filters: Optional[List[str]] = None,
) -> "tuple[List[str], Dict[str, str]]":
    """Return (argv, env updates) for a pipeline step. Raises ValueError on bad paths."""
    import shlex

    root = _repo_root()
    # Drop exported bash completion functions. A broken BASH_FUNC_* (e.g.
    # _xinetd_services with an extglob pattern) is reimported by every child
    # `bash` and aborts the pipeline before the script runs — Run all then
    # looks like a no-op (#687).
    env = {k: v for k, v in os.environ.items() if not k.startswith("BASH_FUNC_")}
    env["COHORT"] = cohort
    env["STATES"] = ",".join(states)
    if step == "discover":
        return _discover_argv(states, cohort), env
    if step == "backfill":
        target = root / _BACKFILL_SCRIPT
        if not target.is_file():
            raise ValueError(f"backfill script missing: {target}")
        import sys as _sys

        backfill_limit = int(n or 0)
        argv = [_sys.executable, str(target)]
        if backfill_limit > 0:
            argv += ["--limit", str(min(backfill_limit, 100000))]
        if states:
            argv += ["--states", ",".join(states)]
        if cohort == "data_centers":
            argv += ["--cohort", "data_centers"]
        return argv, env
    script = root / _LAUNCH_SCRIPT
    if not script.is_file():
        raise ValueError(f"launch script missing: {script}")
    env["BATCH_STATUS"] = "1"
    env["N"] = str(n)
    env["PARALLEL"] = str(parallel)
    filters = _normalize_full_filters(full_filters)
    if filters:
        env["FULL_FILTERS"] = ",".join(filters)
    analyze_like = {
        "analyze",
        "analyze-light",
        "reports-light",
        "analyze-full",
        "reports-full",
        "each",
        "all",
    }
    if cohort == "data_centers" and step in analyze_like:
        env.setdefault("SKIP_JEV_MEETING_BELOW", "0.6")
    # Run all = Discover → catalog → captions → analyze-light → reports-light (#755).
    # Discover is a separate Python CLI; the shell wrapper never ran it.
    if step == "all":
        disc = _discover_argv(states, cohort)
        disc_cmd = " ".join(shlex.quote(a) for a in disc)
        # --noprofile/--norc: don't load operator rc files; BASH_FUNC_* already stripped (#687).
        pipe_cmd = " ".join(
            shlex.quote(a)
            for a in ["bash", "--noprofile", "--norc", str(script), "all"]
        )
        chain = (
            f'echo "=== Discover (channel candidates) ==="; {disc_cmd}; '
            f'disc_ec=$?; '
            f'if [ "$disc_ec" -eq {_VPN_EXIT_CODE} ]; then '
            f'echo "Discover stopped: VPN required (exit {_VPN_EXIT_CODE})"; exit {_VPN_EXIT_CODE}; '
            f'fi; '
            f'if [ "$disc_ec" -ne 0 ]; then '
            f'echo "WARN: Discover exited $disc_ec — continuing to catalog"; '
            f'fi; '
            f'echo "=== Catalog → captions → analyze-light → reports-light ==="; '
            f'{pipe_cmd}; exit $?'
        )
        return ["bash", "--noprofile", "--norc", "-c", chain], env
    shell_step = _shell_step_for_launch(step)
    return ["bash", "--noprofile", "--norc", str(script), shell_step], env


def _spawn_launch(
    step: str,
    *,
    states: List[str],
    cohort: str,
    n: int,
    parallel: int,
    resume_count: int = 0,
    auto_resume: bool = True,
    full_filters: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Start a detached launch and return its tracking meta (includes exit_path)."""
    import datetime as _dt
    import shlex

    filters = _normalize_full_filters(full_filters)
    argv, env = _build_launch_argv(
        step,
        states=states,
        cohort=cohort,
        n=n,
        parallel=parallel,
        full_filters=filters,
    )
    root = _repo_root()
    log_dir = root / "data" / "cache" / "batch_jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"launch_{step}_{stamp}.log"
    exit_path = log_dir / f"launch_{step}_{stamp}.exit"
    # Record exit code so auto-resume can tell clean finish (0) from VPN (5) / crash.
    inner = " ".join(shlex.quote(a) for a in argv)
    wrapper = (
        f"{inner}; ec=$?; echo \"$ec\" > {shlex.quote(str(exit_path))}; exit \"$ec\""
    )
    logf = open(log_path, "ab")
    proc = subprocess.Popen(
        ["bash", "--noprofile", "--norc", "-c", wrapper],
        cwd=str(root),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "pid": proc.pid,
        "step": step,
        "states": list(states),
        "cohort": cohort,
        "n": int(n),
        "parallel": int(parallel),
        "full_filters": list(filters),
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "log": str(log_path.relative_to(root)),
        "exit_path": str(exit_path),
        "auto_resume": bool(auto_resume),
        "resume_count": int(resume_count),
        "stopped": False,
        "awaiting_vpn": False,
    }


def _maybe_auto_resume_launches(freshest: str) -> "tuple[List[str], str]":
    """Re-spawn dead/stalled auto-resume launches. Returns (resumed_steps, note)."""
    if not _auto_resume_enabled():
        return [], ""
    max_resumes = _auto_resume_max()
    vpn_up = _vpn_tunnel_up_for_resume()
    resumed: List[str] = []
    notes: List[str] = []
    kept: List[Dict[str, Any]] = []
    live_steps = {
        str(m.get("step") or "")
        for m in _read_launches()
        if _pid_alive(m.get("pid")) and not _launch_stalled(m, freshest)
    }

    for m in _read_launches():
        step = str(m.get("step") or "")
        if m.get("stopped") or m.get("auto_resume") is False:
            # Drop operator-stopped / capped tombstones once the PID is gone.
            if _pid_alive(m.get("pid")):
                kept.append(m)
            continue

        alive = _pid_alive(m.get("pid"))
        stalled = alive and _launch_stalled(m, freshest)
        exit_code = _read_exit_code(m)

        if alive and not stalled:
            kept.append(m)
            continue

        if stalled:
            _kill_launch(m)
            alive = False

        # Clean successful finish — do not relaunch.
        if not alive and exit_code == 0:
            logger.info("launch finished ok step={} pid={} — not resuming", step, m.get("pid"))
            continue

        count = int(m.get("resume_count") or 0)
        if count >= max_resumes:
            notes.append(f"{step}: auto-resume cap ({max_resumes}) reached")
            kept.append({**m, "pid": None, "auto_resume": False, "awaiting_vpn": False})
            continue

        needs_vpn = step in _LAUNCH_STEPS_NEED_VPN
        vpn_exit = exit_code == _VPN_EXIT_CODE
        log_vpn = bool(_launch_log_signals(step).get("vpn_down"))
        if needs_vpn and (vpn_exit or log_vpn or m.get("awaiting_vpn")) and not vpn_up:
            kept.append({**m, "pid": None, "awaiting_vpn": True})
            notes.append(f"{step}: waiting for VPN before auto-resume")
            continue

        if step in live_steps or step in resumed:
            kept.append({**m, "pid": None})
            continue

        try:
            new_meta = _spawn_launch(
                step,
                states=[str(s) for s in (m.get("states") or []) if str(s).strip()],
                cohort=str(m.get("cohort") or "priority"),
                n=int(m.get("n") or 10),
                parallel=int(m.get("parallel") or 1),
                resume_count=count + 1,
                auto_resume=True,
                full_filters=[
                    str(f) for f in (m.get("full_filters") or []) if str(f).strip()
                ],
            )
        except Exception as exc:
            logger.warning("auto-resume spawn failed step={}: {!r}", step, exc)
            kept.append({**m, "pid": None, "awaiting_vpn": bool(needs_vpn and not vpn_up)})
            notes.append(f"{step}: auto-resume failed ({exc})")
            continue

        logger.info(
            "auto-resumed launch step={} resume_count={} pid={}",
            step,
            new_meta.get("resume_count"),
            new_meta.get("pid"),
        )
        kept.append(new_meta)
        resumed.append(step)
        live_steps.add(step)

    _write_launches(kept)
    note = "; ".join(notes)
    if resumed:
        note = (
            f"Auto-resumed: {', '.join(resumed)}"
            + (f". {note}" if note else "")
        )
    return resumed, note


@router.get("/launch", response_model=LaunchStatusResponse)
async def launch_status() -> LaunchStatusResponse:
    """Per-step running/stalled state for the dashboard's Run buttons."""
    running_rows, freshest = await asyncio.to_thread(_dashboard_runtime)
    resumed_steps, resume_note = await asyncio.to_thread(
        _maybe_auto_resume_launches, freshest
    )
    running, stalled = _classify_launches(freshest)
    running_steps = sorted({str(m.get("step") or "") for m in running} - {""})
    stalled_steps = sorted({str(m.get("step") or "") for m in stalled} - {""})
    signals = _launch_operator_signals(freshest, running, stalled)
    warning = str(signals.get("warning") or "")
    if resume_note and "waiting for VPN" in resume_note and not warning:
        warning = resume_note
    elif resume_note and resumed_steps:
        warning = (warning + " · " if warning else "") + resume_note
    return LaunchStatusResponse(
        enabled=_launch_enabled(),
        running=running_rows,
        running_steps=running_steps,
        stalled_steps=stalled_steps,
        busy=running_rows > 0 or bool(running_steps),
        warning=warning,
        vpn_down=bool(signals.get("vpn_down")),
        inactive_seconds=signals.get("inactive_seconds"),
        resumed_steps=resumed_steps,
        auto_resume_note=resume_note,
    )


@router.post(
    "/launch",
    response_model=LaunchResponse,
    dependencies=[Depends(require_admin)],
)
async def launch_pipeline(req: LaunchRequest) -> LaunchResponse:
    """(Re)launch a pipeline step. Refuses if a run is already active."""
    if not _launch_enabled():
        raise HTTPException(
            status_code=403, detail="Job launch disabled (set BATCH_JOBS_ALLOW_LAUNCH=1)."
        )
    step = (req.step or "").strip().lower()
    if step not in _LAUNCH_STEPS:
        raise HTTPException(status_code=400, detail=f"step must be one of {list(_LAUNCH_STEPS)}")
    full_filters = _normalize_full_filters(req.full_filters)
    if step in _FULL_FILTER_STEPS and not full_filters:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{step} requires a non-empty full_filters list "
                f"(one of {sorted(_FULL_FILTER_KEYS)})"
            ),
        )
    cohort = (req.cohort or "priority").strip().lower()
    if cohort not in ("priority", "data_centers", "all"):
        raise HTTPException(
            status_code=400,
            detail="cohort must be one of priority, data_centers, all",
        )
    from api.batch_jobs.batch_job_db import get_db_connection
    from api.batch_jobs.cohorts import resolve_launch_states

    conn = None
    try:
        if cohort == "data_centers":
            conn = get_db_connection()
        states = resolve_launch_states(cohort, req.states or [], conn=conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
    bad = [s for s in states if not _STATE_RE.match(s)]
    if bad:
        raise HTTPException(status_code=400, detail=f"invalid state code(s): {bad}")
    if len(states) > 60:
        raise HTTPException(status_code=400, detail="too many states")
    n = max(1, min(2000, int(req.n or 10)))
    parallel = max(1, min(8, int(req.parallel or 1)))

    # Per-step guard: different steps may run concurrently; the same step (or a
    # full-pipeline run) may not overlap. Reap dead/stalled launches first.
    _, freshest = await asyncio.to_thread(_dashboard_runtime)
    kept: List[Dict[str, Any]] = []
    for m in _read_launches():
        if not _pid_alive(m.get("pid")):
            continue
        if _launch_stalled(m, freshest):
            _kill_launch(m)  # reap the stalled run, free the slot
            continue
        kept.append(m)
    running_steps = {str(m.get("step")) for m in kept}
    if (
        step in running_steps
        or (step in ("all", "each") and running_steps)
        or (running_steps & {"all", "each"})
    ):
        raise HTTPException(
            status_code=409,
            detail=f"A conflicting run is already active ({', '.join(sorted(running_steps))}).",
        )

    # Backfill: UI size picker sends n = 100/500/2000/4000, or 0 for "All".
    # Discover / wrapper steps still use the clamped n above.
    launch_n = int(req.n or 0) if step == "backfill" else n

    try:
        meta = _spawn_launch(
            step,
            states=states,
            cohort=cohort,
            n=launch_n,
            parallel=parallel,
            resume_count=0,
            auto_resume=True,
            full_filters=full_filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("pipeline launch failed")
        raise HTTPException(status_code=500, detail=f"launch failed: {exc}") from exc

    try:
        # Drop prior tombstones for this step so a fresh Run replaces them.
        others = [
            m
            for m in kept
            if str(m.get("step") or "") != step
        ]
        _write_launches(others + [meta])
    except Exception:
        pass

    rel_log = str(meta.get("log") or "")
    logger.info(
        f"launched pipeline step={step} states={states or 'default'} "
        f"n={launch_n} parallel={parallel} pid={meta.get('pid')} log={rel_log} "
        f"auto_resume=1"
    )
    return LaunchResponse(
        launched=True,
        pid=int(meta["pid"]) if meta.get("pid") is not None else None,
        step=step,
        states=states,
        log=rel_log,
        detail=(
            f"Started '{step}' (pid {meta.get('pid')}). "
            "Auto-resume is on if it dies or stalls (Stop all disables it)."
        ),
    )


class StopRequest(BaseModel):
    # Stop only this step's launch(es); omit/empty to stop every running launch.
    step: Optional[str] = None
    # SIGTERM by default (lets the pipeline exit cleanly); force = SIGKILL.
    force: bool = False


class StopResponse(BaseModel):
    stopped: int = 0
    steps: List[str] = Field(default_factory=list)
    pids: List[int] = Field(default_factory=list)
    detail: str = ""


@router.post(
    "/launch/stop",
    response_model=StopResponse,
    dependencies=[Depends(require_admin)],
)
async def stop_pipeline(req: StopRequest) -> StopResponse:
    """Stop running pipeline launch(es). Signals the detached process group so the
    whole subtree exits. ``step`` targets one step; omit it to stop everything."""
    if not _launch_enabled():
        raise HTTPException(
            status_code=403, detail="Job control disabled (set BATCH_JOBS_ALLOW_LAUNCH=1)."
        )
    step = (req.step or "").strip().lower()
    if step and step not in _LAUNCH_STEPS:
        raise HTTPException(status_code=400, detail=f"step must be one of {list(_LAUNCH_STEPS)}")
    sig = signal.SIGKILL if req.force else signal.SIGTERM

    def _do_stop() -> "tuple[List[str], List[int]]":
        kept: List[Dict[str, Any]] = []
        stopped_steps: List[str] = []
        stopped_pids: List[int] = []
        for m in _read_launches():
            alive = _pid_alive(m.get("pid"))
            m_step = str(m.get("step") or "")
            if (alive or m.get("awaiting_vpn")) and (not step or m_step == step):
                if alive:
                    _kill_launch(m, sig=sig)
                    try:
                        stopped_pids.append(int(m["pid"]))
                    except (KeyError, TypeError, ValueError):
                        pass
                stopped_steps.append(m_step)
                # Tombstone: auto-resume must not revive an operator Stop (#752).
                kept.append(
                    {
                        **m,
                        "pid": None,
                        "auto_resume": False,
                        "stopped": True,
                        "awaiting_vpn": False,
                    }
                )
                continue
            if alive or m.get("awaiting_vpn"):
                kept.append(m)  # not targeted → keep tracking
            # finished (exit 0) / unreaped dead without awaiting_vpn → drop
        _write_launches(kept)
        return stopped_steps, stopped_pids

    stopped_steps, stopped_pids = await asyncio.to_thread(_do_stop)
    steps = sorted(set(s for s in stopped_steps if s))

    # Also clear orphan ``running`` batch rows so Run all re-enables (#742).
    # Stop may find no live PIDs (launch.json already empty) while
    # youtube_batch_job_runs still shows status=running.
    from api.batch_jobs.batch_job_db import cancel_running_batches

    cancelled_rows = await asyncio.to_thread(
        cancel_running_batches,
        reason="operator Stop all (#742)",
        step=step or None,
    )

    if not stopped_pids and cancelled_rows == 0:
        scope = f"step '{step}'" if step else "any step"
        return StopResponse(detail=f"No running launch found for {scope}.")
    how = "SIGKILL" if req.force else "SIGTERM"
    logger.info(
        f"stopped pipeline launches via {how}: steps={steps} pids={stopped_pids} "
        f"cancelled_rows={cancelled_rows}"
    )
    parts: List[str] = []
    if stopped_pids:
        parts.append(
            f"Stopped {len(stopped_pids)} launch(es) ({', '.join(steps) or 'unknown'}). "
            "Auto-resume disabled for those steps"
        )
    if cancelled_rows:
        parts.append(f"cancelled {cancelled_rows} running batch row(s)")
    return StopResponse(
        stopped=len(steps),
        steps=steps,
        pids=stopped_pids,
        detail="; ".join(parts) + ". The dashboard will clear shortly.",
    )


# Lines worth showing as "current item" in a launch log (most recent wins).
_LOG_ITEM_RE = re.compile(
    r"(=== .*===|\[\d+/\d+\]|Calling gemini|Wrote |Analyz|Discover|Caption|catalog)",
    re.IGNORECASE,
)
_LOG_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)")


def _tail_lines(path: Path, n: int) -> List[str]:
    try:
        # Read at most the last ~256 KiB so huge logs stay cheap.
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > 262144:
                fh.seek(-262144, 2)
            data = fh.read()
        text = data.decode("utf-8", "replace")
        return text.splitlines()[-n:]
    except Exception:
        return []


def _parse_current(lines: List[str]) -> "tuple[str, str]":
    """(current item line, ISO timestamp of latest activity) from a log tail."""
    current = ""
    for ln in reversed(lines):
        if ln.strip() and _LOG_ITEM_RE.search(ln):
            current = ln.strip()
            break
    since = ""
    for ln in reversed(lines):
        m = _LOG_TS_RE.search(ln)
        if m:
            since = m.group(1).replace(" ", "T")
            break
    return current[:300], since


class LaunchLogResponse(BaseModel):
    step: str
    path: str = ""
    lines: List[str] = Field(default_factory=list)
    current: str = ""
    current_since: str = ""


@router.get(
    "/launch/log",
    response_model=LaunchLogResponse,
    dependencies=[Depends(require_admin)],
)
async def launch_log(
    step: str = Query(..., description="Pipeline step whose latest log to tail"),
    lines: int = Query(120, ge=1, le=1000),
) -> LaunchLogResponse:
    step = (step or "").strip().lower()
    if step not in _LAUNCH_STEPS:
        raise HTTPException(status_code=400, detail=f"step must be one of {list(_LAUNCH_STEPS)}")
    log_dir = _repo_root() / "data" / "cache" / "batch_jobs"
    candidates = sorted(log_dir.glob(f"launch_{step}_*.log"), reverse=True)
    if not candidates:
        return LaunchLogResponse(step=step)
    path = candidates[0]
    tail = await asyncio.to_thread(_tail_lines, path, lines)
    current, since = _parse_current(tail)
    return LaunchLogResponse(
        step=step,
        path=str(path.relative_to(_repo_root())),
        lines=tail,
        current=current,
        current_since=since,
    )


class BatchJurisdictionsResponse(BaseModel):
    batch_id: str
    state_code: str
    jurisdictions: List[JurisdictionRunModel] = Field(default_factory=list)


class FailedVideoRowModel(BaseModel):
    batch_id: str
    batch_step: str = ""
    state_code: str = ""
    jurisdiction_id: str = ""
    jurisdiction_name: str = ""
    video: VideoResultModel


class FailedVideosListResponse(BaseModel):
    rows: List[FailedVideoRowModel] = Field(default_factory=list)
    total_fail_in_summaries: int = 0
    truncated: bool = False


class CohortsResponse(BaseModel):
    priority: List[str]
    data_centers: List[str]
    all: List[str]


@router.get("/cohorts", response_model=CohortsResponse)
async def list_cohorts() -> CohortsResponse:
    """State-code lists for priority, data-center, and full-US launch cohorts."""
    from api.batch_jobs.batch_job_db import get_db_connection
    from api.batch_jobs.cohorts import cohort_state_codes

    def _load() -> CohortsResponse:
        conn = get_db_connection()
        try:
            return CohortsResponse(
                priority=cohort_state_codes("priority"),
                data_centers=cohort_state_codes("data_centers", conn=conn),
                all=cohort_state_codes("all"),
            )
        finally:
            conn.close()

    try:
        return await asyncio.to_thread(_load)
    except Exception as exc:
        logger.exception("batch-jobs cohorts failed")
        raise HTTPException(
            status_code=500,
            detail=f"Batch jobs cohorts failed: {exc}",
        ) from exc


@router.get("/failed-videos", response_model=FailedVideosListResponse)
async def list_failed_videos(
    batch_id: Optional[str] = Query(
        None, description="Limit to one batch; omit for recent batches combined"
    ),
    limit: int = Query(500, ge=1, le=2000),
    batch_limit: int = Query(25, ge=1, le=100),
) -> FailedVideosListResponse:
    """Per-video failure log extracted from batch payloads (not summary counts only)."""
    from api.batch_jobs.batch_job_db import list_failed_videos_from_db

    try:
        payload = await asyncio.to_thread(
            list_failed_videos_from_db,
            batch_id=batch_id,
            limit=limit,
            batch_limit=batch_limit,
        )
    except Exception as exc:
        logger.exception("list failed videos failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed videos list failed: {exc}",
        ) from exc
    rows = payload.get("rows") or []
    return FailedVideosListResponse(
        rows=[FailedVideoRowModel(**r) for r in rows],
        total_fail_in_summaries=int(payload.get("total_fail_in_summaries") or 0),
        truncated=bool(payload.get("truncated")),
    )


@router.get("/{batch_id}/jurisdictions", response_model=BatchJurisdictionsResponse)
async def list_batch_jurisdictions(
    batch_id: str,
    state: str = Query(..., min_length=2, max_length=2, description="USPS state code"),
) -> BatchJurisdictionsResponse:
    """Slim jurisdiction rows for one state (loaded on demand; no per-video arrays)."""
    from api.batch_jobs.batch_job_dashboard import (
        build_batch_state_jurisdictions,
    )

    st = state.strip().upper()
    try:
        rows = await asyncio.to_thread(
            build_batch_state_jurisdictions,
            batch_id=batch_id,
            state_code=st,
        )
    except Exception as exc:
        logger.exception("batch jurisdictions failed for %s %s", batch_id, st)
        raise HTTPException(
            status_code=500,
            detail=f"Batch jurisdictions failed: {exc}",
        ) from exc
    if not rows:
        from api.batch_jobs.batch_job_db import load_batch_job_from_db

        if await asyncio.to_thread(load_batch_job_from_db, batch_id) is None:
            raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")
    payload = _sanitize_dashboard_payload({"batches": [{"jurisdictions": rows}]})
    jurs = payload.get("batches", [{}])[0].get("jurisdictions") or []
    return BatchJurisdictionsResponse(
        batch_id=batch_id,
        state_code=st,
        jurisdictions=[JurisdictionRunModel(**j) for j in jurs],
    )


@router.get("/{batch_id}", response_model=BatchJobModel)
async def get_batch_job(
    batch_id: str,
    refresh_files: bool = Query(False),
    enrich_bronze: bool = Query(False),
    include_videos: str = Query(
        "all",
        description="all | failed_only | none — per-video rows for drill-down",
    ),
) -> BatchJobModel:
    def _build_job() -> Dict[str, Any]:
        from api.batch_jobs.batch_job_db import (
            enrich_jobs_from_bronze,
            load_batch_job_from_db,
        )
        from api.batch_jobs.batch_job_status import (
            BatchJobStore,
            _recompute_summary,
            apply_batch_lifecycle,
            count_policy_files_for_jurisdiction,
            expand_batch_job_plan,
        )
        from api.batch_jobs.batch_job_dashboard import _POLICY_CACHE

        job = load_batch_job_from_db(batch_id)
        if job is None:
            try:
                job = BatchJobStore(batch_id).load()
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail=f"Batch not found: {batch_id}"
                ) from exc

        apply_batch_lifecycle(job)
        _recompute_summary(job)
        if enrich_bronze:
            enrich_jobs_from_bronze([job])
            expand_batch_job_plan(job)
            _recompute_summary(job)
        elif refresh_files:
            for j in job.jurisdictions:
                j.file_counts = count_policy_files_for_jurisdiction(
                    _POLICY_CACHE,
                    state_code=j.state_code,
                    jurisdiction_id=j.jurisdiction_id,
                )
        d = job.to_dict()
        if include_videos in ("none", "failed_only", "running"):
            from api.batch_jobs.batch_job_dashboard import slim_batch_dict

            mode = include_videos if include_videos != "running" else "running"
            d = slim_batch_dict(d, video_mode=mode)  # type: ignore[arg-type]
        elif include_videos != "all":
            raise HTTPException(
                status_code=400,
                detail="include_videos must be all, failed_only, none, or running",
            )
        return d

    try:
        d = await asyncio.to_thread(_build_job)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("batch job detail failed for %s", batch_id)
        raise HTTPException(
            status_code=500, detail=f"Batch job load failed: {exc}"
        ) from exc
    return BatchJobModel(**d)
