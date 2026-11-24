"""
Production deployment jobs for the Data explorer React UI.

A second *kind* of batch job alongside the YouTube pipeline (``/api/batch-jobs``):
a multi-step **prod deployment** — database (Neon prod) then web (HuggingFace).

The actual work runs in a detached orchestrator
(``packages/hosting/src/hosting/deploy/run_deployment.py``) launched here; it
writes per-step status + logs under ``data/cache/batch_jobs/deployments/`` which
these endpoints read back. The orchestrator is launched **by file path** (not
``-m``) so it works even though the hosting package isn't installed in the API
venv.

Safety: real (non-dry-run) deploys are gated behind ``DEPLOYMENTS_ALLOW_LAUNCH``
(default off). Dry-run launches — which never execute a command — are always
allowed so the dashboard can be exercised without touching prod.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from api.auth import require_admin

# Every deployment endpoint (list/status/log/launch/stop) is admin-only. Unlike
# batch_jobs there is no SSE endpoint here, so gating the whole router is safe —
# all callers are token-bearing fetch()es.
router = APIRouter(
    prefix="/deployments",
    tags=["deployments"],
    dependencies=[Depends(require_admin)],
)

# Step metadata is duplicated (lightly) from hosting.deploy.run_deployment so the
# API need not import the hosting package (not installed in the API venv). The
# orchestrator remains the source of truth for the argv that actually runs.
# Keep in sync with hosting.deploy.run_deployment.STEP_DEFS (source of truth for
# the argv). A prod deployment is just a DATA COPY of local public serving objects
# into Neon prod public (runtime/auth tables excluded). ``web`` (HuggingFace) is a
# separate, optional step — selectable in the panel but not run by default.
_STEP_DEFS: List[Dict[str, str]] = [
    {
        "key": "load-analysis",
        "group": "load",
        "label": "Load analyses — files → bronze",
        "description": (
            "Read the saved analysis files (data/cache/gemini_transcript_policy) and load them into "
            "bronze.bronze_events_analysis_ai. Reads files only; never moves or deletes one."
        ),
        "target": "local-warehouse",
    },
    {
        "key": "dbt-gold",
        "group": "load",
        "label": "Rebuild gold — dbt",
        "description": (
            "dbt run for the analysis models and everything downstream (decisions, meetings, topics, "
            "places), then refresh the public serving views."
        ),
        "target": "local-warehouse",
    },
    {
        "key": "database",
        "group": "deploy",
        "label": "Database — serving copy (Neon prod)",
        "description": "Copy local public serving objects → Neon prod public (excludes runtime/auth tables).",
        "target": "neon-prod",
    },
    {
        "key": "web",
        "group": "deploy",
        "label": "Web (HuggingFace)",
        "description": "Build & deploy the web app + docs to HuggingFace Spaces.",
        "target": "huggingface",
    },
]
_STEP_KEYS = [d["key"] for d in _STEP_DEFS]
_STEP_GROUP = {d["key"]: d["group"] for d in _STEP_DEFS}
_DEFAULT_STEPS = ["database"]
# Default steps per group (keep in sync with hosting.deploy.run_deployment.DEFAULT_STEPS_BY_GROUP).
_DEFAULT_STEPS_BY_GROUP: Dict[str, List[str]] = {
    "load": ["load-analysis", "dbt-gold"],
    "deploy": ["database"],
}
# Steps that publish outside this machine. Only these need DEPLOYMENTS_ALLOW_LAUNCH; the load
# group writes the local warehouse only (dry run is still offered).
_OUTWARD_TARGETS = {"neon-prod", "huggingface"}
_STEP_TARGET = {d["key"]: d["target"] for d in _STEP_DEFS}


def _group_of(steps: List[str]) -> str:
    """``load`` when every step is a load step, else ``deploy``."""
    return "load" if steps and all(_STEP_GROUP.get(k) == "load" for k in steps) else "deploy"


def _repo_root() -> Path:
    # api/routes/deployments.py -> repo root
    return Path(__file__).resolve().parents[2]


def _status_dir() -> Path:
    return _repo_root() / "data" / "cache" / "batch_jobs" / "deployments"


def _orchestrator_path() -> Path:
    return (
        _repo_root()
        / "packages"
        / "hosting"
        / "src"
        / "hosting"
        / "deploy"
        / "run_deployment.py"
    )


def _deploy_enabled() -> bool:
    # Opt-IN switch for real deploys — prod is destructive/outward-facing.
    return os.getenv("DEPLOYMENTS_ALLOW_LAUNCH", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _pid_alive(pid: Any) -> bool:
    try:
        p = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        os.kill(p, 0)
    except OSError:
        return False
    try:
        with open(f"/proc/{p}/stat") as fh:
            state = fh.read().split(") ", 1)[1][:1]
        if state in ("Z", "X"):
            try:
                os.waitpid(p, os.WNOHANG)
            except (ChildProcessError, OSError):
                pass
            return False
    except (FileNotFoundError, IndexError):
        pass
    return True


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class DeploymentStepModel(BaseModel):
    key: str
    label: str = ""
    description: str = ""
    target: str = ""
    status: str = "pending"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    note: Optional[str] = None
    log: str = ""
    cmd: str = ""
    # Counts for the Load tab (#823); None when the step left no result file (older runs, dry runs).
    counts: Optional[Dict[str, int]] = None
    result: Optional[str] = None


class DeploymentJobModel(BaseModel):
    job_id: str
    job_type: str = "deployment"
    # ``load`` or ``deploy``; older status files lack it, so it is derived from the steps.
    group: str = "deploy"
    label: str = ""
    dry_run: bool = False
    pid: Optional[int] = None
    status: str = "running"
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None
    steps: List[DeploymentStepModel] = Field(default_factory=list)
    # ``True`` while the orchestrator process is still alive (computed, not stored).
    live: bool = False


class StepDefModel(BaseModel):
    key: str
    label: str
    description: str
    target: str
    group: str = "deploy"


class DeploymentsListResponse(BaseModel):
    jobs: List[DeploymentJobModel] = Field(default_factory=list)
    available_steps: List[StepDefModel] = Field(default_factory=list)
    enabled: bool = False


class LaunchDeploymentRequest(BaseModel):
    # With no steps, the group's defaults run (``deploy`` when no group is given).
    steps: List[str] = Field(default_factory=list)
    group: str = "deploy"
    # Default to a dry run — a real prod deploy must be opted into explicitly.
    dry_run: bool = True


class LaunchDeploymentResponse(BaseModel):
    launched: bool
    job_id: str = ""
    pid: Optional[int] = None
    dry_run: bool = True
    steps: List[str] = Field(default_factory=list)
    detail: str = ""


class StopDeploymentResponse(BaseModel):
    stopped: bool = False
    detail: str = ""


class DeploymentLogResponse(BaseModel):
    job_id: str
    step: str
    path: str = ""
    lines: List[str] = Field(default_factory=list)


class StepResultReason(BaseModel):
    reason: str
    outcome: str
    label: str
    advice: str = ""
    count: int


class StepResultItem(BaseModel):
    file: str = ""
    video_id: Optional[str] = None
    tier: Optional[str] = None
    outcome: str = ""
    reason: str = ""
    detail: Optional[str] = None


class StepResultResponse(BaseModel):
    job_id: str
    step: str
    # False when the step left no result file: the UI says so instead of showing zeros.
    available: bool = False
    kind: str = ""
    dry_run: bool = False
    counts: Dict[str, int] = Field(default_factory=dict)
    reasons: List[StepResultReason] = Field(default_factory=list)
    total: int = 0
    rows: List[StepResultItem] = Field(default_factory=list)


# What each reason means and what to do about it. Unknown reasons are shown under their own name.
_REASON_INFO: Dict[str, tuple] = {
    "unreadable": ("File could not be read", "The analysis file is empty or not valid JSON. Re-run the analysis for that meeting."),
    "upsert_failed": ("Database write failed", "Read the error text; a foreign-key error usually means the meeting's event row is missing."),
    "no_event": ("No event row yet", "Run ingestion.youtube.promote_to_c1_event so the video has a civic_event row, then load again."),
    "no_meta": ("No run metadata", "The file has no metadata file of its own in 04_runs, so its model and video are unknown."),
    "meta_mismatch": ("Metadata is for the other tier", "A full run overwrote the light run's metadata before #796. Re-run the light analysis to get its own record."),
    "tier_mismatch": ("Tier does not match", "The metadata's analysis_tier disagrees with the file name."),
    "no_video": ("No video id", "The metadata names no video, so the analysis cannot be tied to a meeting."),
    "policy_excluded": ("Excluded at analysis time", "The transcript was marked as a promo, news item or non-meeting. Expected."),
    "junk_channel": ("Junk channel", "The channel is classified as not a government channel. Expected."),
    "non_meeting_type": ("Not a meeting", "meeting_type is OTHER, UNKNOWN or blank. Review it on the Meeting kinds tab if that is wrong."),
    "low_keep_score": ("Low meeting score", "The Jev keep-score is below the floor. Override the meeting kind if it is a real meeting."),
    "cache_missing": ("Analysis cache not found", "The cache folder the loader reads does not exist on this machine. Check the path and the mount."),
    "error": ("dbt model failed", "Read the dbt message; fix the model or its upstream data and run the step again."),
    "fail": ("dbt test failed", "Read the dbt message."),
    "skipped": ("dbt model skipped", "An upstream model failed, so this one did not run."),
}


# Job ids are "<group>_<YYYYMMDD>_<HHMMSS>"; the id becomes part of a file name.
_JOB_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,80}")


def _load_step_result(job_id: str, step: str) -> Optional[Dict[str, Any]]:
    path = _status_dir() / f"{job_id}_{step}.result.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _int_counts(raw: Any) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            out[str(k)] = int(v)
    return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_job(path: Path) -> Optional[DeploymentJobModel]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("job_id"):
        return None
    pid = data.get("pid")
    live = _pid_alive(pid)
    # A job whose orchestrator died without finishing is stale — surface it as
    # failed so the dashboard doesn't pin it at "running" forever.
    status = str(data.get("status") or "")
    if status == "running" and not live:
        status = "failed"
        data["status"] = status
    try:
        job = DeploymentJobModel(**data)
    except Exception:
        return None
    job.live = live
    job.group = _group_of([st.key for st in job.steps])
    return job


def _list_jobs() -> List[DeploymentJobModel]:
    d = _status_dir()
    if not d.is_dir():
        return []
    jobs: List[DeploymentJobModel] = []
    for path in d.glob("*.json"):
        job = _read_job(path)
        if job is not None:
            jobs.append(job)
    jobs.sort(key=lambda j: j.started_at or "", reverse=True)
    return jobs


def _job_path(job_id: str) -> Path:
    return _status_dir() / f"{job_id}.json"


def _write_initial_status(
    status_dir: Path, job_id: str, steps: List[str], dry_run: bool, pid: int
) -> None:
    """Seed a ``running`` status file so the job is visible before the detached
    orchestrator boots and writes its own (which then takes over)."""
    by_key = {d["key"]: d for d in _STEP_DEFS}
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "job_id": job_id,
        "job_type": "deployment",
        "label": "Prod deployment" + (" (dry run)" if dry_run else ""),
        "dry_run": dry_run,
        "pid": pid,
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "steps": [
            {
                "key": k,
                "label": by_key.get(k, {}).get("label", k),
                "description": by_key.get(k, {}).get("description", ""),
                "target": by_key.get(k, {}).get("target", ""),
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "exit_code": None,
                "log": f"data/cache/batch_jobs/deployments/{job_id}_{k}.log",
                "cmd": "",
            }
            for k in steps
        ],
    }
    try:
        dest = status_dir / f"{job_id}.json"
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, dest)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/", response_model=DeploymentsListResponse)
async def list_deployments(
    limit: int = Query(25, ge=1, le=200),
    group: Optional[str] = Query(None, description="load or deploy; omit for everything"),
) -> DeploymentsListResponse:
    g = (group or "").strip().lower() or None
    if g is not None and g not in ("load", "deploy"):
        raise HTTPException(status_code=400, detail="group must be 'load' or 'deploy'")
    jobs = [j for j in _list_jobs() if g is None or j.group == g][:limit]
    steps = [d for d in _STEP_DEFS if g is None or d["group"] == g]
    return DeploymentsListResponse(
        jobs=jobs,
        available_steps=[StepDefModel(**d) for d in steps],
        # Real launches: deploy needs DEPLOYMENTS_ALLOW_LAUNCH; load writes the local warehouse only.
        enabled=True if g == "load" else _deploy_enabled(),
    )


@router.get("/{job_id}", response_model=DeploymentJobModel)
async def get_deployment(job_id: str) -> DeploymentJobModel:
    job = _read_job(_job_path(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail=f"deployment job not found: {job_id}")
    return job


@router.post("/launch", response_model=LaunchDeploymentResponse)
async def launch_deployment(req: LaunchDeploymentRequest) -> LaunchDeploymentResponse:
    group_req = (req.group or "deploy").strip().lower()
    if group_req not in _DEFAULT_STEPS_BY_GROUP:
        raise HTTPException(status_code=400, detail="group must be 'load' or 'deploy'")
    steps = [s.strip().lower() for s in (req.steps or []) if s and s.strip()]
    if not steps:
        steps = list(_DEFAULT_STEPS_BY_GROUP[group_req])
    bad = [s for s in steps if s not in _STEP_KEYS]
    if bad:
        raise HTTPException(status_code=400, detail=f"unknown step(s): {bad}; known: {_STEP_KEYS}")
    if len({_STEP_GROUP[s] for s in steps}) > 1:
        raise HTTPException(
            status_code=400,
            detail="load steps and deploy steps cannot run in the same job",
        )
    group = _STEP_GROUP[steps[0]]

    dry_run = bool(req.dry_run)
    outward = any(_STEP_TARGET.get(s) in _OUTWARD_TARGETS for s in steps)
    if not dry_run and outward and not _deploy_enabled():
        raise HTTPException(
            status_code=403,
            detail="Real deploys are disabled. Set DEPLOYMENTS_ALLOW_LAUNCH=1 to enable, "
            "or run with dry_run=true.",
        )

    # Refuse to start while another job of the same kind is still live.
    for j in _list_jobs():
        if j.live and j.status == "running" and j.group == group:
            raise HTTPException(
                status_code=409,
                detail=f"A {group} job is already running ({j.job_id}). Stop it first.",
            )

    script = _orchestrator_path()
    if not script.is_file():
        raise HTTPException(status_code=500, detail=f"orchestrator missing: {script}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = f"{group}_{stamp}"  # load_… or deploy_…
    status_dir = _status_dir()
    status_dir.mkdir(parents=True, exist_ok=True)

    argv = [
        sys.executable,
        str(script),
        "--job-id",
        job_id,
        "--steps",
        ",".join(steps),
        "--status-dir",
        str(status_dir),
    ]
    if dry_run:
        argv.append("--dry-run")

    # The orchestrator owns its own per-step logs; capture its own stdout/stderr
    # (launch/argparse errors) to a bootstrap log next to the status file.
    boot_log = status_dir / f"{job_id}_orchestrator.log"
    try:
        logf = open(boot_log, "ab")
        proc = subprocess.Popen(
            argv,
            cwd=str(_repo_root()),
            env=dict(os.environ),
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # detach so it outlives the request
        )
    except Exception as exc:
        logger.exception("deployment launch failed")
        raise HTTPException(status_code=500, detail=f"launch failed: {exc}") from exc

    # Write an initial status file so the job appears immediately (the
    # orchestrator atomically overwrites it once it boots — last writer wins).
    _write_initial_status(status_dir, job_id, steps, dry_run, proc.pid)

    logger.info(
        f"launched deployment job_id={job_id} steps={steps} dry_run={dry_run} pid={proc.pid}"
    )
    kind = "load" if group == "load" else "deployment"
    detail = (
        f"Started dry-run {kind} '{job_id}' (pid {proc.pid}). No commands were executed."
        if dry_run
        else (
            f"Started {kind} '{job_id}' (pid {proc.pid}). The dashboard updates as it runs."
            if group == "load"
            else f"Started PROD deployment '{job_id}' (pid {proc.pid}). The dashboard updates as it runs."
        )
    )
    return LaunchDeploymentResponse(
        launched=True,
        job_id=job_id,
        pid=proc.pid,
        dry_run=dry_run,
        steps=steps,
        detail=detail,
    )


@router.post("/{job_id}/stop", response_model=StopDeploymentResponse)
async def stop_deployment(job_id: str, force: bool = Query(False)) -> StopDeploymentResponse:
    job = _read_job(_job_path(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail=f"deployment job not found: {job_id}")
    if not job.live or job.pid is None:
        return StopDeploymentResponse(detail=f"Deployment '{job_id}' is not running.")
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(os.getpgid(int(job.pid)), sig)
    except Exception:
        try:
            os.kill(int(job.pid), sig)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"stop failed: {exc}") from exc
    how = "SIGKILL" if force else "SIGTERM"
    logger.info(f"stopped deployment {job_id} via {how} (pid {job.pid})")
    return StopDeploymentResponse(
        stopped=True,
        detail=f"Stopped deployment '{job_id}'. The dashboard will update as it exits.",
    )


@router.get("/{job_id}/log", response_model=DeploymentLogResponse)
async def deployment_log(
    job_id: str,
    step: str = Query(..., description="Step key whose log to tail."),
    lines: int = Query(200, ge=1, le=2000),
) -> DeploymentLogResponse:
    step = (step or "").strip().lower()
    if step not in _STEP_KEYS:
        raise HTTPException(status_code=400, detail=f"step must be one of {_STEP_KEYS}")
    path = _status_dir() / f"{job_id}_{step}.log"
    if not path.is_file():
        return DeploymentLogResponse(job_id=job_id, step=step)
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > 262144:
                fh.seek(-262144, 2)
            data = fh.read()
        tail = data.decode("utf-8", "replace").splitlines()[-lines:]
    except Exception:
        tail = []
    return DeploymentLogResponse(
        job_id=job_id,
        step=step,
        path=str(path.relative_to(_repo_root())),
        lines=tail,
    )


@router.get("/{job_id}/result", response_model=StepResultResponse)
async def deployment_step_result(
    job_id: str,
    step: str = Query(..., description="Step key whose counts and items to read."),
    outcome: Optional[str] = Query(None, description="Only items with this outcome: skipped or error."),
    reason: Optional[str] = Query(None, description="Only items with this reason."),
    q: Optional[str] = Query(None, description="Case-insensitive text found in the file, video id or detail."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StepResultResponse:
    """Counts and the items that were not loaded for one step of a run (#823).

    Reads the step's ``<job_id>_<step>.result.json``. ``reasons`` and their counts always cover the
    whole run; ``total`` and ``rows`` reflect the filters."""
    step = (step or "").strip().lower()
    if step not in _STEP_KEYS:
        raise HTTPException(status_code=400, detail=f"step must be one of {_STEP_KEYS}")
    if not _JOB_ID_RE.fullmatch(job_id or ""):
        raise HTTPException(status_code=400, detail="invalid job id")
    data = _load_step_result(job_id, step)
    if data is None:
        return StepResultResponse(job_id=job_id, step=step, available=False)

    items = [i for i in (data.get("items") or []) if isinstance(i, dict)]
    by_reason: Dict[tuple, int] = {}
    for item in items:
        key = (str(item.get("reason") or "unknown"), str(item.get("outcome") or ""))
        by_reason[key] = by_reason.get(key, 0) + 1
    reasons = [
        StepResultReason(
            reason=r, outcome=o, count=n,
            label=_REASON_INFO.get(r, (r.replace("_", " "), ""))[0],
            advice=_REASON_INFO.get(r, (r, ""))[1],
        )
        # errors first, then the biggest groups
        for (r, o), n in sorted(by_reason.items(), key=lambda kv: (kv[0][1] != "error", -kv[1], kv[0][0]))
    ]

    needle = (q or "").strip().lower()
    want_outcome = (outcome or "").strip().lower()
    want_reason = (reason or "").strip().lower()

    def keep(item: Dict[str, Any]) -> bool:
        if want_outcome and str(item.get("outcome") or "").lower() != want_outcome:
            return False
        if want_reason and str(item.get("reason") or "").lower() != want_reason:
            return False
        if needle:
            hay = " ".join(str(item.get(k) or "") for k in ("file", "video_id", "detail")).lower()
            return needle in hay
        return True

    # Errors first, otherwise the order the step wrote them (sorted() is stable).
    matched = sorted((i for i in items if keep(i)), key=lambda i: str(i.get("outcome") or "") != "error")
    rows = [
        StepResultItem(
            file=str(i.get("file") or ""),
            video_id=str(i["video_id"]) if i.get("video_id") else None,
            tier=str(i["tier"]) if i.get("tier") else None,
            outcome=str(i.get("outcome") or ""),
            reason=str(i.get("reason") or "unknown"),
            detail=str(i["detail"]) if i.get("detail") else None,
        )
        for i in matched[offset : offset + limit]
    ]
    return StepResultResponse(
        job_id=job_id, step=step, available=True,
        kind=str(data.get("kind") or ""), dry_run=bool(data.get("dry_run")),
        counts=_int_counts(data.get("counts")), reasons=reasons, total=len(matched), rows=rows,
    )
