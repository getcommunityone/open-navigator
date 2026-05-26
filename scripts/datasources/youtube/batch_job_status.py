#!/usr/bin/env python3
"""
Persist batch job progress for priority-state pipelines (captions, analyze, catalog).

Status files: ``data/cache/batch_jobs/<batch_id>.json`` and ``index.json``.

Used by ``run_priority_states_last_n.sh`` and ``backfill_jurisdiction_transcripts.py``.
View: ``.venv/bin/python scripts/datasources/youtube/batch_job_dashboard.py --open``
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_JOBS_DIR = _REPO_ROOT / "data" / "cache" / "batch_jobs"
_INDEX_NAME = "index.json"
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, max_len: int = 48) -> str:
    out = _SLUG_RE.sub("-", (s or "").strip()).strip("-")
    return (out[:max_len] if out else "batch")


def new_batch_id(step: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_slug(step, 24)}-{ts}"


def jobs_dir() -> Path:
    raw = (os.getenv("BATCH_JOBS_DIR") or "").strip()
    return Path(raw).resolve() if raw else _DEFAULT_JOBS_DIR


@dataclass
class VideoResult:
    video_id: str
    title: str = ""
    status: str = "pending"  # ok | fail | tombstoned | empty | rate_limit | skipped
    error: str = ""
    transcript_source: str = ""
    finished_at: str = ""


@dataclass
class JurisdictionRun:
    state_code: str
    jurisdiction_id: str
    jurisdiction_name: str = ""
    status: str = "pending"  # pending | running | completed | failed
    started_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float = 0.0
    exit_code: int = 0
    stats: Dict[str, int] = field(default_factory=dict)
    videos: List[VideoResult] = field(default_factory=list)
    file_counts: Dict[str, int] = field(
        default_factory=lambda: {"transcripts": 0, "analysis": 0, "reports": 0}
    )


@dataclass
class BatchJob:
    batch_id: str
    step: str
    status: str = "running"  # running | completed | failed | cancelled
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    jurisdictions: List[JurisdictionRun] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BatchJob:
        jurs = []
        for j in data.get("jurisdictions") or []:
            videos = [VideoResult(**v) for v in j.get("videos") or []]
            jurs.append(
                JurisdictionRun(
                    state_code=j.get("state_code", ""),
                    jurisdiction_id=j.get("jurisdiction_id", ""),
                    jurisdiction_name=j.get("jurisdiction_name", ""),
                    status=j.get("status", "pending"),
                    started_at=j.get("started_at", ""),
                    finished_at=j.get("finished_at", ""),
                    elapsed_seconds=float(j.get("elapsed_seconds") or 0),
                    exit_code=int(j.get("exit_code") or 0),
                    stats=dict(j.get("stats") or {}),
                    videos=videos,
                    file_counts=dict(
                        j.get("file_counts")
                        or {"transcripts": 0, "analysis": 0, "reports": 0}
                    ),
                )
            )
        return cls(
            batch_id=data["batch_id"],
            step=data.get("step", ""),
            status=data.get("status", "running"),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
            finished_at=data.get("finished_at", ""),
            config=dict(data.get("config") or {}),
            summary=dict(data.get("summary") or {}),
            jurisdictions=jurs,
        )


def _recompute_summary(job: BatchJob) -> None:
    total_j = int(job.config.get("total_jurisdictions") or 0) or len(job.jurisdictions)
    processed = sum(1 for j in job.jurisdictions if j.status in ("completed", "failed"))
    success = sum(1 for j in job.jurisdictions if j.status == "completed" and j.exit_code == 0)
    failed = sum(1 for j in job.jurisdictions if j.status == "failed" or j.exit_code != 0)
    remaining = max(0, total_j - processed)

    v_ok = v_fail = v_tomb = v_empty = v_rl = 0
    for j in job.jurisdictions:
        for st in (j.stats or {}).values():
            pass
        v_ok += int((j.stats or {}).get("ok") or 0)
        v_fail += int((j.stats or {}).get("fail") or 0)
        v_tomb += int((j.stats or {}).get("tombstoned") or 0)
        v_empty += int((j.stats or {}).get("empty") or 0)
        v_rl += int((j.stats or {}).get("rate_limit") or 0)

    elapsed = 0.0
    if job.started_at:
        try:
            start = datetime.fromisoformat(job.started_at.replace("Z", "+00:00"))
            end = (
                datetime.fromisoformat(job.finished_at.replace("Z", "+00:00"))
                if job.finished_at
                else datetime.now(timezone.utc)
            )
            elapsed = max(0.0, (end - start).total_seconds())
        except ValueError:
            elapsed = 0.0

    eta_seconds: Optional[float] = None
    if processed > 0 and remaining > 0 and elapsed > 0:
        eta_seconds = (elapsed / processed) * remaining

    files = {"transcripts": 0, "analysis": 0, "reports": 0}
    for j in job.jurisdictions:
        for k in files:
            files[k] += int((j.file_counts or {}).get(k) or 0)

    job.summary = {
        "total_jurisdictions": total_j,
        "processed_jurisdictions": processed,
        "success_jurisdictions": success,
        "failed_jurisdictions": failed,
        "remaining_jurisdictions": remaining,
        "elapsed_seconds": round(elapsed, 1),
        "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
        "videos_ok": v_ok,
        "videos_fail": v_fail,
        "videos_tombstoned": v_tomb,
        "videos_empty": v_empty,
        "videos_rate_limit": v_rl,
        "files_transcripts": files["transcripts"],
        "files_analysis": files["analysis"],
        "files_reports": files["reports"],
    }


class BatchJobStore:
    def __init__(self, batch_id: str, *, jobs_root: Optional[Path] = None) -> None:
        self.batch_id = batch_id
        self.root = jobs_root or jobs_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{batch_id}.json"

    def load(self) -> BatchJob:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return BatchJob.from_dict(data)

    def save(self, job: BatchJob) -> None:
        job.updated_at = _utc_now_iso()
        _recompute_summary(job)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(job.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)
        _update_index(self.root, job)

    def start_batch(
        self,
        *,
        step: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> BatchJob:
        now = _utc_now_iso()
        job = BatchJob(
            batch_id=self.batch_id,
            step=step,
            status="running",
            started_at=now,
            updated_at=now,
            config=dict(config or {}),
        )
        self.save(job)
        return job

    def finish_batch(self, *, status: str = "completed") -> BatchJob:
        job = self.load()
        job.status = status
        job.finished_at = _utc_now_iso()
        self.save(job)
        return job

    def jurisdiction_start(
        self,
        *,
        state_code: str,
        jurisdiction_id: str,
        jurisdiction_name: str = "",
        pending_videos: int = 0,
    ) -> JurisdictionRun:
        job = self.load()
        run = JurisdictionRun(
            state_code=state_code.upper(),
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            status="running",
            started_at=_utc_now_iso(),
        )
        if pending_videos:
            run.stats["pending"] = pending_videos
        job.jurisdictions = [
            j for j in job.jurisdictions if j.jurisdiction_id != jurisdiction_id
        ]
        job.jurisdictions.append(run)
        self.save(job)
        return run

    def _find_jurisdiction(self, job: BatchJob, jurisdiction_id: str) -> JurisdictionRun:
        for j in job.jurisdictions:
            if j.jurisdiction_id == jurisdiction_id:
                return j
        raise KeyError(jurisdiction_id)

    def record_video(
        self,
        *,
        jurisdiction_id: str,
        video_id: str,
        status: str,
        title: str = "",
        error: str = "",
        transcript_source: str = "",
    ) -> None:
        job = self.load()
        j = self._find_jurisdiction(job, jurisdiction_id)
        j.videos = [v for v in j.videos if v.video_id != video_id]
        j.videos.append(
            VideoResult(
                video_id=video_id,
                title=title[:200],
                status=status,
                error=(error or "")[:500],
                transcript_source=transcript_source,
                finished_at=_utc_now_iso(),
            )
        )
        self.save(job)

    def jurisdiction_finish(
        self,
        *,
        jurisdiction_id: str,
        exit_code: int,
        stats: Optional[Dict[str, int]] = None,
        file_counts: Optional[Dict[str, int]] = None,
    ) -> None:
        job = self.load()
        j = self._find_jurisdiction(job, jurisdiction_id)
        j.status = "completed" if exit_code == 0 else "failed"
        j.exit_code = exit_code
        j.finished_at = _utc_now_iso()
        if stats:
            j.stats = {k: int(v) for k, v in stats.items()}
        if file_counts:
            j.file_counts = {k: int(v) for k, v in file_counts.items()}
        if j.started_at:
            try:
                start = datetime.fromisoformat(j.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(j.finished_at.replace("Z", "+00:00"))
                j.elapsed_seconds = max(0.0, (end - start).total_seconds())
            except ValueError:
                j.elapsed_seconds = 0.0
        self.save(job)

    def shell_jurisdiction_done(
        self,
        *,
        state_code: str,
        jurisdiction_id: str,
        jurisdiction_name: str,
        exit_code: int,
    ) -> None:
        """Mark jurisdiction when backfill did not write status (crash / missing --batch-id)."""
        try:
            job = self.load()
            self._find_jurisdiction(job, jurisdiction_id)
        except (FileNotFoundError, KeyError):
            self.jurisdiction_start(
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=jurisdiction_name,
            )
        self.jurisdiction_finish(
            jurisdiction_id=jurisdiction_id,
            exit_code=exit_code,
            stats={"shell_exit": exit_code},
        )


def _update_index(root: Path, job: BatchJob) -> None:
    index_path = root / _INDEX_NAME
    entries: List[Dict[str, Any]] = []
    if index_path.is_file():
        try:
            entries = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries = [e for e in entries if e.get("batch_id") != job.batch_id]
    entries.insert(
        0,
        {
            "batch_id": job.batch_id,
            "step": job.step,
            "status": job.status,
            "started_at": job.started_at,
            "updated_at": job.updated_at,
            "summary": job.summary,
        },
    )
    entries = entries[:200]
    index_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def count_policy_files_for_jurisdiction(
    cache_root: Path,
    *,
    state_code: str,
    jurisdiction_id: str,
) -> Dict[str, int]:
    """Count transcript/analysis/report files under policy cache for one jurisdiction."""
    from scripts.gemini.policy_processing_status_report import (
        _DIR_ANALYSIS,
        _DIR_REPORTS,
        _DIR_TRANSCRIPTS,
        scan_jurisdiction_cache,
    )

    counts = {"transcripts": 0, "analysis": 0, "reports": 0}
    if not cache_root.is_dir():
        return counts
    by_jid = scan_jurisdiction_cache(cache_root)
    st = by_jid.get(jurisdiction_id)
    if st:
        counts["transcripts"] = st.transcripts
        counts["analysis"] = st.analysis_json
        counts["reports"] = st.reports_md
        return counts

    state = (state_code or "").upper()
    jid = jurisdiction_id.lower()
    for state_dir in cache_root.iterdir():
        if not state_dir.is_dir() or state_dir.name.upper() != state:
            continue
        for type_dir in state_dir.iterdir():
            if not type_dir.is_dir():
                continue
            for jdir in type_dir.iterdir():
                if jdir.name.lower() != jid and jid not in jdir.name.lower():
                    continue
                for ch in jdir.iterdir():
                    if not ch.is_dir():
                        continue
                    tx = ch / _DIR_TRANSCRIPTS
                    if tx.is_dir():
                        counts["transcripts"] += sum(
                            1 for p in tx.glob("*.json") if p.is_file()
                        )
                    an = ch / _DIR_ANALYSIS
                    if an.is_dir():
                        counts["analysis"] += sum(
                            1
                            for p in an.glob("*.json")
                            if p.is_file() and not p.name.startswith("_")
                        )
                    rp = ch / _DIR_REPORTS
                    if rp.is_dir():
                        counts["reports"] += sum(
                            1 for p in rp.glob("*.md") if p.is_file()
                        )
    return counts


def list_batches(*, limit: int = 50) -> List[BatchJob]:
    root = jobs_dir()
    jobs: List[BatchJob] = []
    index_path = root / _INDEX_NAME
    ids: List[str] = []
    if index_path.is_file():
        try:
            for row in json.loads(index_path.read_text(encoding="utf-8")):
                bid = row.get("batch_id")
                if bid:
                    ids.append(bid)
        except json.JSONDecodeError:
            pass
    if not ids:
        ids = sorted(
            (p.stem for p in root.glob("*.json") if p.name != _INDEX_NAME),
            reverse=True,
        )
    for bid in ids[:limit]:
        path = root / f"{bid}.json"
        if path.is_file():
            try:
                jobs.append(BatchJob.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError):
                continue
    return jobs


def _cli_start(args: argparse.Namespace) -> int:
    batch_id = (args.batch_id or "").strip() or new_batch_id(args.step)
    store = BatchJobStore(batch_id)
    config = {
        "states": [s.strip().upper() for s in (args.states or "").split(",") if s.strip()],
        "n": args.n,
        "delay": args.delay,
        "total_jurisdictions": args.total_jurisdictions,
        "transcript_source": args.transcript_source or "",
        "max_jurisdictions": args.max_jurisdictions or 0,
    }
    store.start_batch(step=args.step, config=config)
    print(batch_id)
    return 0


def _cli_jurisdiction_start(args: argparse.Namespace) -> int:
    store = BatchJobStore(args.batch_id)
    store.jurisdiction_start(
        state_code=args.state,
        jurisdiction_id=args.jurisdiction_id,
        jurisdiction_name=args.jurisdiction_name or "",
        pending_videos=args.pending_videos,
    )
    return 0


def _cli_jurisdiction_finish(args: argparse.Namespace) -> int:
    store = BatchJobStore(args.batch_id)
    stats = json.loads(args.stats) if args.stats else {}
    store.jurisdiction_finish(
        jurisdiction_id=args.jurisdiction_id,
        exit_code=args.exit_code,
        stats=stats,
    )
    return 0


def _cli_finish(args: argparse.Namespace) -> int:
    store = BatchJobStore(args.batch_id)
    store.finish_batch(status=args.status)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Create a new batch job file")
    p_start.add_argument("--step", required=True)
    p_start.add_argument("--batch-id", default="")
    p_start.add_argument("--states", default="")
    p_start.add_argument("--n", type=int, default=0)
    p_start.add_argument("--delay", type=float, default=0)
    p_start.add_argument("--total-jurisdictions", type=int, default=0)
    p_start.add_argument("--transcript-source", default="")
    p_start.add_argument("--max-jurisdictions", type=int, default=0)
    p_start.set_defaults(func=_cli_start)

    p_js = sub.add_parser("jurisdiction-start")
    p_js.add_argument("--batch-id", required=True)
    p_js.add_argument("--state", required=True)
    p_js.add_argument("--jurisdiction-id", required=True)
    p_js.add_argument("--jurisdiction-name", default="")
    p_js.add_argument("--pending-videos", type=int, default=0)
    p_js.set_defaults(func=_cli_jurisdiction_start)

    p_jf = sub.add_parser("jurisdiction-finish")
    p_jf.add_argument("--batch-id", required=True)
    p_jf.add_argument("--jurisdiction-id", required=True)
    p_jf.add_argument("--exit-code", type=int, default=0)
    p_jf.add_argument("--stats", default="")
    p_jf.set_defaults(func=_cli_jurisdiction_finish)

    p_fin = sub.add_parser("finish")
    p_fin.add_argument("--batch-id", required=True)
    p_fin.add_argument("--status", default="completed")
    p_fin.set_defaults(func=_cli_finish)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
