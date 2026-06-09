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
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/deployments", tags=["deployments"])

# Step metadata is duplicated (lightly) from hosting.deploy.run_deployment so the
# API need not import the hosting package (not installed in the API venv). The
# orchestrator remains the source of truth for the argv that actually runs.
# Keep in sync with hosting.deploy.run_deployment.STEP_DEFS (source of truth for
# the argv). A prod deployment is just a DATA COPY of local public serving objects
# into Neon prod public (runtime/auth tables excluded). ``web`` (HuggingFace) is a
# separate, optional step — selectable in the panel but not run by default.
_STEP_DEFS: List[Dict[str, str]] = [
    {
        "key": "database",
        "label": "Database — serving copy (Neon prod)",
        "description": "Copy local public serving objects → Neon prod public (excludes runtime/auth tables).",
        "target": "neon-prod",
    },
    {
        "key": "web",
        "label": "Web (HuggingFace)",
        "description": "Build & deploy the web app + docs to HuggingFace Spaces.",
        "target": "huggingface",
    },
]
_STEP_KEYS = [d["key"] for d in _STEP_DEFS]
_DEFAULT_STEPS = ["database"]


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


class DeploymentJobModel(BaseModel):
    job_id: str
    job_type: str = "deployment"
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


class DeploymentsListResponse(BaseModel):
    jobs: List[DeploymentJobModel] = Field(default_factory=list)
    available_steps: List[StepDefModel] = Field(default_factory=list)
    enabled: bool = False


class LaunchDeploymentRequest(BaseModel):
    steps: List[str] = Field(default_factory=lambda: list(_DEFAULT_STEPS))
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
async def list_deployments(limit: int = Query(25, ge=1, le=200)) -> DeploymentsListResponse:
    jobs = _list_jobs()[:limit]
    return DeploymentsListResponse(
        jobs=jobs,
        available_steps=[StepDefModel(**d) for d in _STEP_DEFS],
        enabled=_deploy_enabled(),
    )


@router.get("/{job_id}", response_model=DeploymentJobModel)
async def get_deployment(job_id: str) -> DeploymentJobModel:
    job = _read_job(_job_path(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail=f"deployment job not found: {job_id}")
    return job


@router.post("/launch", response_model=LaunchDeploymentResponse)
async def launch_deployment(req: LaunchDeploymentRequest) -> LaunchDeploymentResponse:
    steps = [s.strip().lower() for s in (req.steps or []) if s and s.strip()]
    if not steps:
        steps = list(_DEFAULT_STEPS)
    bad = [s for s in steps if s not in _STEP_KEYS]
    if bad:
        raise HTTPException(status_code=400, detail=f"unknown step(s): {bad}; known: {_STEP_KEYS}")

    dry_run = bool(req.dry_run)
    if not dry_run and not _deploy_enabled():
        raise HTTPException(
            status_code=403,
            detail="Real deploys are disabled. Set DEPLOYMENTS_ALLOW_LAUNCH=1 to enable, "
            "or run with dry_run=true.",
        )

    # Refuse to start while another deployment is still live.
    for j in _list_jobs():
        if j.live and j.status == "running":
            raise HTTPException(
                status_code=409,
                detail=f"A deployment is already running ({j.job_id}). Stop it first.",
            )

    script = _orchestrator_path()
    if not script.is_file():
        raise HTTPException(status_code=500, detail=f"orchestrator missing: {script}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = f"deploy_{stamp}"
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
    detail = (
        f"Started dry-run deployment '{job_id}' (pid {proc.pid}). No commands were executed."
        if dry_run
        else f"Started PROD deployment '{job_id}' (pid {proc.pid}). The dashboard updates as it runs."
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
