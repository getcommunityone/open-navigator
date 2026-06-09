"""Production deployment orchestrator.

Runs an ordered set of deployment steps (e.g. ``database`` → Neon prod,
``web`` → HuggingFace Spaces) as a single detached job. Each step is a child
subprocess; stdout/stderr stream to a per-step log file and the overall job
status (per-step state, exit codes, timestamps) is written to a JSON file the
``/api/deployments`` dashboard polls.

Design notes
------------
* **Stdlib only** — so it stays importable (``python -m hosting.deploy``)
  *and* runnable by file path (the API launches it that way to dodge the
  hosting-not-installed-in-the-API-venv gotcha).
* **Dry-run is orchestrator-level**: in ``--dry-run`` no child command runs at
  all — each step logs the command it *would* run and is marked completed. This
  is the safe default so the dashboard can be exercised without touching prod.
* **Sequential, fail-fast**: a failing step stops the job; the remaining steps
  are marked ``skipped`` and the job status becomes ``failed``.

Run::

    python -m hosting.deploy.run_deployment --job-id <id> --steps database,web [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Step registry
# ---------------------------------------------------------------------------
# ``{python}`` is replaced with the running interpreter. ``cwd`` is relative to
# the repo root. Add a new deployment target by adding an entry here — the API
# and UI discover steps from :func:`available_steps`, so no other change needed.
STEP_DEFS: Dict[str, Dict[str, Any]] = {
    "database": {
        "label": "Database (Neon prod)",
        "description": "Sync serving data to the Neon production Postgres.",
        "target": "neon-prod",
        "argv": ["{python}", "-m", "hosting.neon.sync_event_documents_to_neon"],
    },
    "web": {
        "label": "Web (HuggingFace)",
        "description": "Build & deploy the web app + docs to HuggingFace Spaces.",
        "target": "huggingface",
        "argv": ["bash", "packages/hosting/scripts/huggingface/deploy-huggingface.sh", "--skip-test"],
    },
}
# Default ordered pipeline: stand up the database, then ship the web app.
DEFAULT_STEPS: List[str] = ["database", "web"]


def available_steps() -> List[Dict[str, str]]:
    """Step metadata for the API/UI (no argv — that's an orchestrator detail)."""
    return [
        {
            "key": key,
            "label": str(defn["label"]),
            "description": str(defn["description"]),
            "target": str(defn["target"]),
        }
        for key, defn in STEP_DEFS.items()
    ]


def _repo_root() -> Path:
    # packages/hosting/src/hosting/deploy/run_deployment.py -> repo root
    return Path(__file__).resolve().parents[5]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Job state file
# ---------------------------------------------------------------------------
class DeploymentJob:
    """In-memory job state mirrored to ``<status_dir>/<job_id>.json``."""

    def __init__(
        self,
        *,
        job_id: str,
        steps: List[str],
        dry_run: bool,
        status_dir: Path,
        log_dir: Path,
    ) -> None:
        self.job_id = job_id
        self.dry_run = dry_run
        self.status_dir = status_dir
        self.log_dir = log_dir
        self.status_path = status_dir / f"{job_id}.json"
        self.started_at = _now_iso()
        self.finished_at: Optional[str] = None
        self.status = "running"
        self.steps: List[Dict[str, Any]] = []
        for key in steps:
            defn = STEP_DEFS[key]
            self.steps.append(
                {
                    "key": key,
                    "label": defn["label"],
                    "description": defn["description"],
                    "target": defn["target"],
                    "status": "pending",
                    "started_at": None,
                    "finished_at": None,
                    "exit_code": None,
                    "log": str((log_dir / f"{job_id}_{key}.log").relative_to(_repo_root())),
                    "cmd": "",
                }
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": "deployment",
            "label": "Prod deployment" + (" (dry run)" if self.dry_run else ""),
            "dry_run": self.dry_run,
            "pid": os.getpid(),
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": _now_iso(),
            "finished_at": self.finished_at,
            "steps": self.steps,
        }

    def flush(self) -> None:
        """Atomically write the status JSON (tmp + rename) so readers never see
        a half-written file."""
        self.status_dir.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self.to_dict(), indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(self.status_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(data)
            os.replace(tmp, self.status_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def _step_argv(key: str) -> List[str]:
    raw = STEP_DEFS[key]["argv"]
    return [sys.executable if tok == "{python}" else tok for tok in raw]


def _child_env() -> Dict[str, str]:
    """Child env with ``packages/hosting/src`` on PYTHONPATH so ``-m hosting.*``
    step commands resolve even when hosting isn't installed in this venv."""
    env = dict(os.environ)
    hosting_src = str(_repo_root() / "packages" / "hosting" / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{hosting_src}{os.pathsep}{existing}" if existing else hosting_src
    return env


class _Orchestrator:
    def __init__(self, job: DeploymentJob) -> None:
        self.job = job
        self._current: Optional[subprocess.Popen] = None
        self._cancelled = False

    def _on_signal(self, signum, _frame) -> None:  # noqa: ANN001
        self._cancelled = True
        if self._current and self._current.poll() is None:
            try:
                self._current.terminate()
            except Exception:
                pass

    def run(self) -> int:
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        root = _repo_root()
        self.job.flush()
        failed = False

        for step in self.job.steps:
            if self._cancelled:
                step["status"] = "skipped"
                continue
            if failed:
                step["status"] = "skipped"
                self.job.flush()
                continue

            argv = _step_argv(step["key"])
            step["cmd"] = " ".join(argv)
            step["status"] = "running"
            step["started_at"] = _now_iso()
            self.job.flush()

            log_path = root / step["log"]
            log_path.parent.mkdir(parents=True, exist_ok=True)

            if self.job.dry_run:
                with open(log_path, "w") as fh:
                    fh.write(f"[{_now_iso()}] [dry-run] would run: {step['cmd']}\n")
                    fh.write("[dry-run] no command executed.\n")
                step["exit_code"] = 0
                step["status"] = "completed"
                step["finished_at"] = _now_iso()
                self.job.flush()
                continue

            try:
                with open(log_path, "w") as logf:
                    logf.write(f"[{_now_iso()}] $ {step['cmd']}\n")
                    logf.flush()
                    self._current = subprocess.Popen(
                        argv,
                        cwd=str(root),
                        env=_child_env(),
                        stdout=logf,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                    )
                    rc = self._current.wait()
                self._current = None
            except Exception as exc:  # launch itself failed
                with open(log_path, "a") as fh:
                    fh.write(f"\n[{_now_iso()}] launch failed: {exc}\n")
                rc = 127

            step["exit_code"] = rc
            if self._cancelled:
                step["status"] = "cancelled"
                self.job.flush()
                break
            if rc == 0:
                step["status"] = "completed"
            else:
                step["status"] = "failed"
                failed = True
            step["finished_at"] = _now_iso()
            self.job.flush()

        if self._cancelled:
            self.job.status = "cancelled"
        elif failed:
            self.job.status = "failed"
        else:
            self.job.status = "completed"
        self.job.finished_at = _now_iso()
        self.job.flush()
        return 0 if self.job.status == "completed" else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a production deployment job.")
    parser.add_argument("--job-id", required=True, help="Unique job id (used for status/log filenames).")
    parser.add_argument(
        "--steps",
        default=",".join(DEFAULT_STEPS),
        help=f"Comma-separated ordered steps. Known: {','.join(STEP_DEFS)}",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log commands without executing them.")
    parser.add_argument(
        "--status-dir",
        default=str(_repo_root() / "data" / "cache" / "batch_jobs" / "deployments"),
        help="Directory for the job status JSON + per-step logs.",
    )
    args = parser.parse_args(argv)

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEP_DEFS]
    if unknown:
        parser.error(f"unknown step(s): {unknown}; known: {list(STEP_DEFS)}")
    if not steps:
        parser.error("no steps given")

    status_dir = Path(args.status_dir)
    job = DeploymentJob(
        job_id=args.job_id,
        steps=steps,
        dry_run=args.dry_run,
        status_dir=status_dir,
        log_dir=status_dir,
    )
    return _Orchestrator(job).run()


if __name__ == "__main__":
    raise SystemExit(main())
