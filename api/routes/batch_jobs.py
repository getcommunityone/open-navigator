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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/batch-jobs", tags=["batch-jobs"])


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


class StageReportRow(BaseModel):
    # One (scope, stage) row. scope is a 2-letter state code or "ALL" (rollup).
    scope: str
    stage: str
    done: int = 0
    total: int = 0
    failed: int = 0
    last_at: str = ""


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
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _load_dashboard,
        refresh_files=refresh_files,
        enrich_bronze=enrich_bronze,
        enrich_bronze_only_running=enrich_bronze_only_running,
        detail=detail,
        batch_limit=batch_limit,
    )


def _load_dashboard(
    *,
    refresh_files: bool,
    enrich_bronze: bool,
    enrich_bronze_only_running: bool = False,
    detail: str = "full",
    batch_limit: int = 25,
) -> Dict[str, Any]:
    from api.batch_jobs.batch_job_dashboard import (
        VideoPayloadMode,
        build_dashboard_data,
        build_dashboard_summary,
    )

    if detail == "summary":
        payload = build_dashboard_summary(limit=batch_limit)
    else:
        video_mode: VideoPayloadMode = "all" if detail == "full" else "running"
        payload = build_dashboard_data(
            refresh_files=refresh_files,
            enrich_bronze=enrich_bronze,
            enrich_bronze_only_running=enrich_bronze_only_running,
            batch_limit=batch_limit,
            video_mode=video_mode,
        )
    return _sanitize_dashboard_payload(payload)


@router.get("/stream")
async def stream_batch_jobs(
    refresh_files: bool = Query(False),
    enrich_bronze: bool = Query(
        False,
        description="When true, refresh transcript counts from bronze each tick (heavier)",
    ),
) -> StreamingResponse:
    """SSE stream of dashboard JSON; pushes when DB revision changes."""

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
) -> BatchJobsDashboardResponse:
    if detail not in ("summary", "standard", "full"):
        raise HTTPException(
            status_code=400,
            detail="detail must be summary, standard, or full",
        )
    try:
        payload = await _load_dashboard_async(
            refresh_files=refresh_files,
            enrich_bronze=enrich_bronze,
            detail=detail,
            batch_limit=batch_limit,
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
_LAUNCH_STEPS = ("discover", "catalog", "captions", "backfill", "analyze", "each", "all")
_STATE_RE = re.compile(r"^[A-Z]{2}$")


def _repo_root() -> Path:
    # api/routes/batch_jobs.py -> repo root
    return Path(__file__).resolve().parents[2]


def _launch_enabled() -> bool:
    # Opt-out kill switch — set BATCH_JOBS_ALLOW_LAUNCH=0 on any exposed deploy.
    return os.getenv("BATCH_JOBS_ALLOW_LAUNCH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
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
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _launch_stalled(live: Dict[str, Any], freshest: str) -> bool:
    """A live launch with no activity (or none since it started) for over the
    stall window — i.e. stuck. ``freshest`` and ``started_at`` are UTC ISO."""
    last_seen = max(freshest or "", str(live.get("started_at") or ""))
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


class LaunchStatusResponse(BaseModel):
    enabled: bool
    busy: bool = False
    running: int = 0
    # Per-step concurrency: different steps may run at once; the same step may not.
    running_steps: List[str] = Field(default_factory=list)
    stalled_steps: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=lambda: list(_LAUNCH_STEPS))


class LaunchResponse(BaseModel):
    launched: bool
    pid: Optional[int] = None
    step: str = ""
    states: List[str] = Field(default_factory=list)
    log: str = ""
    detail: str = ""


@router.get("/launch", response_model=LaunchStatusResponse)
async def launch_status() -> LaunchStatusResponse:
    """Per-step running/stalled state for the dashboard's Run buttons."""
    running_rows, freshest = await asyncio.to_thread(_dashboard_runtime)
    running, stalled = _classify_launches(freshest)
    running_steps = sorted({str(m.get("step") or "") for m in running} - {""})
    stalled_steps = sorted({str(m.get("step") or "") for m in stalled} - {""})
    return LaunchStatusResponse(
        enabled=_launch_enabled(),
        running=running_rows,
        running_steps=running_steps,
        stalled_steps=stalled_steps,
        busy=running_rows > 0 or bool(running_steps),
    )


@router.post("/launch", response_model=LaunchResponse)
async def launch_pipeline(req: LaunchRequest) -> LaunchResponse:
    """(Re)launch a pipeline step. Refuses if a run is already active."""
    if not _launch_enabled():
        raise HTTPException(
            status_code=403, detail="Job launch disabled (set BATCH_JOBS_ALLOW_LAUNCH=1)."
        )
    step = (req.step or "").strip().lower()
    if step not in _LAUNCH_STEPS:
        raise HTTPException(status_code=400, detail=f"step must be one of {list(_LAUNCH_STEPS)}")
    states = [s.strip().upper() for s in (req.states or []) if s and s.strip()]
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

    root = _repo_root()
    env = dict(os.environ)
    if step == "discover":
        # Stage 0 runs the channel-discovery script. It accepts one state or a
        # comma list (--states A,B,C); we always pass --states so the ALL-scope
        # launcher can sweep the whole selected set (priority or 50 + DC) in one
        # detached run.
        if not states:
            raise HTTPException(
                status_code=400, detail="discover requires at least one state."
            )
        target = root / _DISCOVER_SCRIPT
        if not target.is_file():
            raise HTTPException(status_code=500, detail=f"discover script missing: {target}")
        import sys as _sys

        argv = [_sys.executable, str(target), "--states", ",".join(states)]
    elif step == "backfill":
        # Global transcript backfill over the int_events_union mart. Unlike the
        # per-jurisdiction `captions` step (which reads bronze_events_youtube
        # WHERE jurisdiction_id = …), this is a flat sweep that also reaches the
        # LocalView/union videos that have no bronze_events_youtube row. Runs the
        # standalone script directly (fixed argv, no shell), like `discover`, so
        # it has no per-jurisdiction batch tracking. States optional.
        #
        # Backfill batch size is independent of the wrapper-step N clamp above:
        # the UI size picker sends `n` = 100/500/2000/4000, or 0 for "All". 0 (or
        # negative) means sweep every missing transcript (omit --limit); a run is
        # resumable (re-queries what's still missing), so a bounded size still
        # makes progress across clicks. Cap to a sane ceiling so a stray value
        # can't launch an absurd run.
        target = root / _BACKFILL_SCRIPT
        if not target.is_file():
            raise HTTPException(status_code=500, detail=f"backfill script missing: {target}")
        import sys as _sys

        backfill_limit = int(req.n or 0)
        argv = [_sys.executable, str(target)]
        if backfill_limit > 0:
            argv += ["--limit", str(min(backfill_limit, 100000))]
        if states:
            argv += ["--states", ",".join(states)]
        # The mart-wide sweep can touch thousands of videos in a single run, so
        # route captions through the Webshare rotating residential pool to spread
        # the per-IP 429 ceiling — the bare cookies+direct egress (.env default,
        # used by the per-jurisdiction `captions` step) hits YouTube's rate limit
        # after ~20 fetches. Falls back to cookies+direct automatically if
        # PROXY_USER_NAME / PROXY_PASSWORD are unset (webshare_enabled() == False).
        env["YOUTUBE_USE_WEBSHARE"] = "1"
    else:
        script = root / _LAUNCH_SCRIPT
        if not script.is_file():
            raise HTTPException(status_code=500, detail=f"launch script missing: {script}")
        env["BATCH_STATUS"] = "1"
        env["N"] = str(n)
        env["PARALLEL"] = str(parallel)
        if states:
            env["STATES"] = ",".join(states)
        argv = ["bash", str(script), step]  # fixed argv, no shell

    import datetime as _dt

    log_dir = root / "data" / "cache" / "batch_jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"launch_{step}_{stamp}.log"

    try:
        logf = open(log_path, "ab")
        proc = subprocess.Popen(
            argv,
            cwd=str(root),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # detach so it outlives the request
        )
    except Exception as exc:
        logger.exception("pipeline launch failed")
        raise HTTPException(status_code=500, detail=f"launch failed: {exc}") from exc

    try:
        _write_launches(
            kept
            + [
                {
                    "pid": proc.pid,
                    "step": step,
                    "states": states,
                    "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                }
            ]
        )
    except Exception:
        pass

    rel_log = str(log_path.relative_to(root))
    logger.info(
        f"launched pipeline step={step} states={states or 'default'} "
        f"n={n} parallel={parallel} pid={proc.pid} log={rel_log}"
    )
    return LaunchResponse(
        launched=True,
        pid=proc.pid,
        step=step,
        states=states,
        log=rel_log,
        detail=f"Started '{step}' (pid {proc.pid}). The dashboard will update as it runs.",
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


@router.post("/launch/stop", response_model=StopResponse)
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
            if alive and (not step or m_step == step):
                _kill_launch(m, sig=sig)
                stopped_steps.append(m_step)
                try:
                    stopped_pids.append(int(m["pid"]))
                except (KeyError, TypeError, ValueError):
                    pass
                continue  # drop from the tracked file — it's being stopped
            if alive:
                kept.append(m)  # alive but not targeted → keep tracking
            # dead launches are dropped (reaped) either way
        _write_launches(kept)
        return stopped_steps, stopped_pids

    stopped_steps, stopped_pids = await asyncio.to_thread(_do_stop)
    if not stopped_pids:
        scope = f"step '{step}'" if step else "any step"
        return StopResponse(detail=f"No running launch found for {scope}.")
    steps = sorted(set(s for s in stopped_steps if s))
    how = "SIGKILL" if req.force else "SIGTERM"
    logger.info(f"stopped pipeline launches via {how}: steps={steps} pids={stopped_pids}")
    return StopResponse(
        stopped=len(stopped_pids),
        steps=steps,
        pids=stopped_pids,
        detail=(
            f"Stopped {len(stopped_pids)} launch(es) ({', '.join(steps) or 'unknown'}). "
            "The dashboard will clear as the process exits."
        ),
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


@router.get("/launch/log", response_model=LaunchLogResponse)
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
