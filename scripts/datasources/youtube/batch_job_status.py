#!/usr/bin/env python3
"""
Persist batch job progress for priority-state pipelines (captions, analyze, catalog).

Writes JSON under ``data/cache/batch_jobs/`` and syncs to
``bronze.youtube_batch_job_runs`` (migration 073) for the live API dashboard.

Used by ``run_priority_states_last_n.sh`` and ``backfill_jurisdiction_transcripts.py``.
View in React: ``/data-explorer/batch-jobs`` (``GET /api/batch-jobs/stream`` SSE).
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
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_DEFAULT_JOBS_DIR = _REPO_ROOT / "data" / "cache" / "batch_jobs"
_INDEX_NAME = "index.json"
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def batch_inactivity_seconds() -> float:
    """Mark ``running`` batches cancelled after this many seconds without activity."""
    raw = os.getenv("BATCH_JOB_INACTIVITY_SECONDS", "3600")
    try:
        return max(60.0, float(raw))
    except (TypeError, ValueError):
        return 3600.0


def config_state_codes(cfg: Optional[Dict[str, Any]]) -> List[str]:
    raw = (cfg or {}).get("states") or []
    if isinstance(raw, str):
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    if isinstance(raw, list):
        return [str(s).strip().upper() for s in raw if str(s).strip()]
    return []


def _parse_utc_iso(iso: str) -> Optional[datetime]:
    text = (iso or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def last_batch_activity_at(job: BatchJob) -> datetime:
    """
    Latest timestamp that indicates real pipeline work (jurisdiction / video progress).

    Does not use ``job.updated_at`` (dashboard sync metadata). When nothing is recorded,
    falls back to ``started_at`` so idle ``running`` rows can stale-cancel instead of
    looking falsely active.
    """
    best: Optional[datetime] = None
    for j in job.jurisdictions:
        for iso in (
            j.updated_at,
            j.current_video_started_at,
            j.finished_at,
            j.started_at,
        ):
            dt = _parse_utc_iso(iso or "")
            if dt and (best is None or dt > best):
                best = dt
        for v in j.videos or []:
            dt = _parse_utc_iso(v.finished_at or "")
            if dt and (best is None or dt > best):
                best = dt
    if best is not None:
        return best
    dt = _parse_utc_iso(job.started_at or "")
    if dt:
        return dt
    return datetime.fromtimestamp(0, tz=timezone.utc)


def latest_dashboard_activity_at(jobs: List[BatchJob]) -> str:
    """Latest jurisdiction/video progress across batches (not API ``generated_at``)."""
    best: Optional[datetime] = None
    for job in jobs:
        try:
            dt = last_batch_activity_at(job)
            if dt.year > 1971 and (best is None or dt > best):
                best = dt
        except Exception:
            pass
    return best.isoformat() if best is not None and best.year > 1971 else ""


def state_progress_for_job(job: BatchJob) -> Dict[str, Any]:
    """
    Per-batch state coverage from jurisdiction rows.

    * started — at least one jurisdiction in that state is running or finished
    * completed — every jurisdiction row for that state is finished (none pending/running)
    """
    planned = config_state_codes(job.config)
    by_state: Dict[str, Dict[str, int]] = {}
    for j in job.jurisdictions:
        st = (j.state_code or "").strip().upper()
        if not st:
            continue
        bucket = by_state.setdefault(st, {"pending": 0, "running": 0, "done": 0})
        if j.status == "pending":
            bucket["pending"] += 1
        elif j.status == "running":
            bucket["running"] += 1
        else:
            bucket["done"] += 1

    universe = sorted(set(planned) | set(by_state))
    started_codes = [
        st
        for st in universe
        if by_state.get(st, {}).get("running", 0) + by_state.get(st, {}).get("done", 0) > 0
    ]
    completed_codes = [
        st
        for st in universe
        if by_state.get(st)
        and by_state[st].get("pending", 0) == 0
        and by_state[st].get("running", 0) == 0
        and by_state[st].get("done", 0) > 0
    ]
    return {
        "states_planned": len(universe),
        "states_started": len(started_codes),
        "states_completed": len(completed_codes),
        "states_started_codes": started_codes,
        "states_completed_codes": completed_codes,
    }


def _maybe_stale_cancel_batch(job: BatchJob) -> bool:
    """Cancel ``running`` batches with no activity for ``batch_inactivity_seconds()``."""
    if (job.status or "").lower() != "running":
        return False
    inactive = batch_inactivity_seconds()
    now = datetime.now(timezone.utc)
    if (now - last_batch_activity_at(job)).total_seconds() <= inactive:
        return False
    finished = _utc_now_iso()
    job.status = "cancelled"
    job.finished_at = finished
    cfg = dict(job.config or {})
    cfg["stale_cancel_reason"] = f"no activity for {int(inactive)}s"
    job.config = cfg
    for j in job.jurisdictions:
        if j.status == "running":
            j.status = "failed"
            j.exit_code = -1
            j.finished_at = finished
            j.updated_at = finished
            j.current_video_id = ""
            j.current_video_title = ""
            j.current_video_started_at = ""
    return True


def persist_batch_job(job: BatchJob) -> None:
    """Write lifecycle changes to Postgres and the JSON cache file when present."""
    job.updated_at = _utc_now_iso()
    _recompute_summary(job)
    try:
        from scripts.datasources.youtube.batch_job_db import sync_batch_job_to_db

        sync_batch_job_to_db(job)
    except Exception:
        pass
    try:
        store = BatchJobStore(job.batch_id)
        if store.path.is_file():
            tmp = store.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(job.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(store.path)
            _update_index(store.root, job)
    except Exception:
        pass


def duration_seconds_from_catalog_minutes(duration_minutes: object) -> Optional[float]:
    """Convert ``bronze_events_youtube.duration_minutes`` to seconds for batch UI."""
    if duration_minutes is None:
        return None
    try:
        sec = float(duration_minutes) * 60.0
    except (TypeError, ValueError):
        return None
    if sec <= 0 or sec > 86400 * 48:  # cap absurd values (~48h)
        return None
    return round(sec, 1)


def _slug(s: str, max_len: int = 48) -> str:
    out = _SLUG_RE.sub("-", (s or "").strip()).strip("-")
    return (out[:max_len] if out else "batch")


def new_batch_id(step: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_slug(step, 24)}-{ts}"


def jobs_dir() -> Path:
    raw = (os.getenv("BATCH_JOBS_DIR") or "").strip()
    return Path(raw).resolve() if raw else _DEFAULT_JOBS_DIR


def _batch_database_url() -> str:
    return (
        os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("NEON_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )


def fetch_batch_plan_jurisdictions(
    states: List[str],
    *,
    round_robin: bool = True,
    database_url: Optional[str] = None,
) -> List[JurisdictionRun]:
    """
    Canonical jurisdictions for the batch plan (``pending``), aligned with
    ``intermediate.int_jurisdictions`` — not legacy ``c-AL-*`` ids on bronze video rows.
    """
    from scripts.jurisdictions.jurisdiction_id import (
        _PREFIXED_USPS_GEOID_RE,
        _SLUG_GEOID_RE,
        _TYPED_JURISDICTION_ID_RE,
        ensure_canonical_jurisdiction_id,
    )

    st_list = [s.strip().upper() for s in states if (s or "").strip()]
    if not st_list:
        return []
    url = (database_url or "").strip() or _batch_database_url()
    if not url:
        return []
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return []

    rows: list = []
    try:
        with psycopg2.connect(url) as conn, conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:
            cur.execute(
                """
                SELECT
                    j.state_code,
                    j.jurisdiction_id,
                    j.name AS jurisdiction_name,
                    j.jurisdiction_type::text AS jurisdiction_type
                FROM intermediate.int_jurisdictions j
                WHERE j.state_code = ANY(%s)
                  AND j.jurisdiction_id IS NOT NULL
                  AND BTRIM(j.jurisdiction_id) <> ''
                  AND EXISTS (
                      SELECT 1
                      FROM bronze.bronze_events_youtube y
                      WHERE y.state_code = j.state_code
                        AND (
                          y.jurisdiction_id = j.jurisdiction_id
                          OR y.jurisdiction_id = 'c-' || j.state_code || '-' || j.geoid
                          OR y.jurisdiction_id = 'municipality_' || j.geoid
                          OR y.jurisdiction_id LIKE '%\\_' || j.geoid ESCAPE '\\'
                        )
                  )
                ORDER BY j.state_code, j.name, j.jurisdiction_id
                """,
                (st_list,),
            )
            rows = list(cur.fetchall())
    except Exception:
        rows = []

    if not rows:
        try:
            with psycopg2.connect(url) as conn, conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (state_code, jurisdiction_id)
                           state_code,
                           jurisdiction_id,
                           jurisdiction_name,
                           NULL::text AS jurisdiction_type
                    FROM bronze.bronze_events_youtube
                    WHERE state_code = ANY(%s)
                      AND jurisdiction_id IS NOT NULL
                      AND BTRIM(jurisdiction_id) <> ''
                    ORDER BY state_code, jurisdiction_id, jurisdiction_name
                    """,
                    (st_list,),
                )
                rows = list(cur.fetchall())
        except Exception:
            return []

    if round_robin:
        from collections import defaultdict

        buckets: Dict[str, list] = defaultdict(list)
        for r in rows:
            buckets[str(r["state_code"]).upper()].append(r)
        active = [s for s in st_list if buckets.get(s)]
        max_len = max((len(buckets[s]) for s in active), default=0)
        ordered: list = []
        for i in range(max_len):
            for s in active:
                if i < len(buckets[s]):
                    ordered.append(buckets[s][i])
        rows = ordered

    out: List[JurisdictionRun] = []
    seen_keys: set[str] = set()
    for r in rows:
        raw_id = str(r["jurisdiction_id"]).strip()
        name = str(r.get("jurisdiction_name") or "").strip()
        if not name or name == raw_id or _looks_like_jurisdiction_id_label(name):
            name = ""
        jtype = str(r.get("jurisdiction_type") or "").strip()
        jid = ensure_canonical_jurisdiction_id(
            raw_id,
            name=name or None,
            jurisdiction_type=jtype or None,
            database_url=url,
        ) or raw_id
        if _PREFIXED_USPS_GEOID_RE.match(jid):
            continue
        if not (
            (_SLUG_GEOID_RE.match(jid) and not _TYPED_JURISDICTION_ID_RE.match(jid))
            or _TYPED_JURISDICTION_ID_RE.match(jid)
        ):
            continue
        key = _plan_jurisdiction_key(jid)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        row = JurisdictionRun(
            state_code=str(r["state_code"]).upper(),
            jurisdiction_id=jid,
            jurisdiction_name=name,
            jurisdiction_type=jtype,
            status="pending",
        )
        normalize_jurisdiction_run(row, database_url=url)
        out.append(row)

    return out


_STATUS_RANK = {
    "completed": 5,
    "failed": 4,
    "running": 3,
    "cancelled": 2,
    "pending": 1,
}


def _plan_jurisdiction_key(jurisdiction_id: str) -> str:
    """Match plan rows to batch rows even when id format differs (``municipality_*`` vs ``slug_geoid``)."""
    from scripts.jurisdictions.jurisdiction_id import (
        parse_jurisdiction_id,
        resolve_canonical_jurisdiction_id,
    )

    jid = (jurisdiction_id or "").strip()
    if not jid:
        return ""
    canonical = resolve_canonical_jurisdiction_id(jid).strip().lower()
    _jt, geoid, _slug = parse_jurisdiction_id(canonical or jid)
    if geoid:
        return f"geoid:{geoid}"
    return canonical or jid.lower()


def _looks_like_jurisdiction_id_label(text: str) -> bool:
    """True when ``text`` is an id string, not a place name (e.g. ``c-AL-01021``)."""
    from scripts.jurisdictions.jurisdiction_id import (
        _PREFIXED_USPS_GEOID_RE,
        _SLUG_GEOID_RE,
        _TYPED_JURISDICTION_ID_RE,
    )

    t = (text or "").strip()
    if not t:
        return False
    if _PREFIXED_USPS_GEOID_RE.match(t):
        return True
    if _TYPED_JURISDICTION_ID_RE.match(t):
        return True
    if _SLUG_GEOID_RE.match(t) and "_" in t and not re.search(r"\s", t):
        return True
    return False


def _lookup_jurisdiction_name_from_db(
    jurisdiction_id: str,
    *,
    database_url: Optional[str] = None,
) -> str:
    """Place name from ``int_jurisdictions`` for a canonical or legacy id."""
    from scripts.jurisdictions.jurisdiction_id import parse_jurisdiction_id

    jid = (jurisdiction_id or "").strip()
    if not jid:
        return ""
    url = (database_url or "").strip() or _batch_database_url()
    if not url:
        return ""
    _jt, geoid, _slug = parse_jurisdiction_id(jid)
    try:
        import psycopg2
    except ImportError:
        return ""
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT name FROM intermediate.int_jurisdictions
                WHERE jurisdiction_id = %s
                LIMIT 1
                """,
                (jid,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0]).strip()
            if geoid:
                cur.execute(
                    """
                    SELECT name FROM intermediate.int_jurisdictions
                    WHERE geoid = %s
                    ORDER BY jurisdiction_id
                    LIMIT 1
                    """,
                    (geoid,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0]).strip()
    except Exception:
        return ""
    return ""


def normalize_jurisdiction_run(
    j: JurisdictionRun,
    *,
    database_url: Optional[str] = None,
) -> JurisdictionRun:
    """Canonical ``jurisdiction_id`` and human ``jurisdiction_name`` for dashboard rows."""
    from scripts.jurisdictions.jurisdiction_id import (
        _PREFIXED_USPS_GEOID_RE,
        ensure_canonical_jurisdiction_id,
    )

    raw_id = (j.jurisdiction_id or "").strip()
    if not raw_id:
        return j
    name = (j.jurisdiction_name or "").strip()
    if not name or name == raw_id or _looks_like_jurisdiction_id_label(name):
        name = ""

    jid = ensure_canonical_jurisdiction_id(
        raw_id,
        name=name or None,
        jurisdiction_type=(j.jurisdiction_type or None),
        database_url=database_url,
    ) or raw_id
    if _PREFIXED_USPS_GEOID_RE.match(jid):
        jid = ensure_canonical_jurisdiction_id(
            raw_id,
            name=None,
            jurisdiction_type=(j.jurisdiction_type or "county"),
            database_url=database_url,
        ) or jid

    j.jurisdiction_id = jid
    if not name or _looks_like_jurisdiction_id_label(name):
        name = _lookup_jurisdiction_name_from_db(jid, database_url=database_url)
    if name and not _looks_like_jurisdiction_id_label(name):
        j.jurisdiction_name = name
    return j


def _upgrade_jurisdiction_from_plan(
    existing: JurisdictionRun, placeholder: JurisdictionRun
) -> None:
    """Apply canonical id and display name from the fresh plan row."""
    from scripts.jurisdictions.jurisdiction_id import (
        _SLUG_GEOID_RE,
        _TYPED_JURISDICTION_ID_RE,
    )

    def _is_canonical_slug(jid: str) -> bool:
        return bool(_SLUG_GEOID_RE.match(jid) and not _TYPED_JURISDICTION_ID_RE.match(jid))

    pid = (placeholder.jurisdiction_id or "").strip()
    eid = (existing.jurisdiction_id or "").strip()
    if pid and (_is_canonical_slug(pid) or not _is_canonical_slug(eid)):
        existing.jurisdiction_id = pid
    pname = (placeholder.jurisdiction_name or "").strip()
    if pname and not _looks_like_jurisdiction_id_label(pname):
        existing.jurisdiction_name = pname
    if placeholder.jurisdiction_type and not (existing.jurisdiction_type or "").strip():
        existing.jurisdiction_type = placeholder.jurisdiction_type


def normalize_batch_job_jurisdictions(
    job: BatchJob,
    *,
    database_url: Optional[str] = None,
) -> bool:
    """Normalize all jurisdiction rows in place. Returns True if anything changed."""
    changed = False
    url = database_url
    for j in job.jurisdictions:
        before = (j.jurisdiction_id, j.jurisdiction_name)
        normalize_jurisdiction_run(j, database_url=url)
        if (j.jurisdiction_id, j.jurisdiction_name) != before:
            changed = True
    return changed


def _prefer_jurisdiction_run(
    current: JurisdictionRun, other: JurisdictionRun
) -> JurisdictionRun:
    """Keep the row with the most advanced status (never downgrade completed → pending)."""
    cur_rank = _STATUS_RANK.get((current.status or "").lower(), 0)
    other_rank = _STATUS_RANK.get((other.status or "").lower(), 0)
    if other_rank > cur_rank:
        return other
    if other_rank < cur_rank:
        return current
    if (other.videos or other.stats) and not (current.videos or current.stats):
        return other
    return current


def expand_batch_job_plan(job: BatchJob) -> None:
    """Fill in ``pending`` rows for jurisdictions not started yet in this batch."""
    cfg = job.config or {}
    if cfg.get("seed_plan") is False:
        return
    states = cfg.get("states") or []
    if not states:
        return
    rr = cfg.get("round_robin")
    if rr is None:
        rr = True
    plan = fetch_batch_plan_jurisdictions(states, round_robin=bool(rr))
    if not plan:
        return

    by_key: Dict[str, JurisdictionRun] = {}
    for j in job.jurisdictions:
        key = _plan_jurisdiction_key(j.jurisdiction_id)
        if not key:
            continue
        if key in by_key:
            by_key[key] = _prefer_jurisdiction_run(by_key[key], j)
        else:
            by_key[key] = j

    merged: List[JurisdictionRun] = []
    matched: set[str] = set()
    for placeholder in plan:
        key = _plan_jurisdiction_key(placeholder.jurisdiction_id)
        existing = by_key.get(key) if key else None
        if existing is not None:
            _upgrade_jurisdiction_from_plan(existing, placeholder)
            normalize_jurisdiction_run(existing)
            merged.append(existing)
            matched.add(key)
        else:
            normalize_jurisdiction_run(placeholder)
            merged.append(placeholder)
            if key:
                matched.add(key)

    for key, j in by_key.items():
        if key in matched:
            continue
        from scripts.jurisdictions.jurisdiction_id import _PREFIXED_USPS_GEOID_RE

        if _PREFIXED_USPS_GEOID_RE.match((j.jurisdiction_id or "").strip()):
            continue
        normalize_jurisdiction_run(j)
        merged.append(j)

    job.jurisdictions = merged
    if not int(cfg.get("total_jurisdictions") or 0):
        job.config["total_jurisdictions"] = len(merged)


@dataclass
class VideoResult:
    video_id: str
    title: str = ""
    status: str = "pending"  # ok | fail | tombstoned | empty | rate_limit | skipped
    error: str = ""
    transcript_source: str = ""
    finished_at: str = ""
    duration_seconds: Optional[float] = None


@dataclass
class JurisdictionRun:
    state_code: str
    jurisdiction_id: str
    jurisdiction_name: str = ""
    jurisdiction_type: str = ""
    status: str = "pending"  # pending | running | completed | failed
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float = 0.0
    exit_code: int = 0
    stats: Dict[str, int] = field(default_factory=dict)
    videos: List[VideoResult] = field(default_factory=list)
    file_counts: Dict[str, int] = field(
        default_factory=lambda: {"transcripts": 0, "analysis": 0, "reports": 0}
    )
    current_video_id: str = ""
    current_video_title: str = ""
    current_video_started_at: str = ""


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
            videos = []
            for v in j.get("videos") or []:
                vd = dict(v)
                if "duration_seconds" not in vd:
                    vd["duration_seconds"] = None
                elif vd["duration_seconds"] is not None:
                    try:
                        vd["duration_seconds"] = float(vd["duration_seconds"])
                    except (TypeError, ValueError):
                        vd["duration_seconds"] = None
                videos.append(VideoResult(**vd))
            jurs.append(
                JurisdictionRun(
                    state_code=j.get("state_code", ""),
                    jurisdiction_id=j.get("jurisdiction_id", ""),
                    jurisdiction_name=j.get("jurisdiction_name", ""),
                    jurisdiction_type=str(j.get("jurisdiction_type") or ""),
                    status=j.get("status", "pending"),
                    started_at=j.get("started_at", ""),
                    updated_at=j.get("updated_at", ""),
                    finished_at=j.get("finished_at", ""),
                    elapsed_seconds=float(j.get("elapsed_seconds") or 0),
                    exit_code=int(j.get("exit_code") or 0),
                    stats=dict(j.get("stats") or {}),
                    videos=videos,
                    file_counts=dict(
                        j.get("file_counts")
                        or {"transcripts": 0, "analysis": 0, "reports": 0}
                    ),
                    current_video_id=j.get("current_video_id", ""),
                    current_video_title=j.get("current_video_title", ""),
                    current_video_started_at=j.get("current_video_started_at", ""),
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


_VIDEO_COUNT_KEYS = ("ok", "fail", "tombstoned", "empty", "rate_limit")

_STATUS_TO_STAT_KEY: Dict[str, str] = {
    "ok": "ok",
    "fail": "fail",
    "tombstoned": "tombstoned",
    "empty": "empty",
    "rate_limit": "rate_limit",
}


def _disk_file_count(fc: Dict[str, int], disk_key: str, legacy_key: str) -> int:
    """Prefer explicit ``*_disk`` keys; fall back to legacy ``transcripts`` / ``analysis`` keys."""
    if disk_key in fc:
        return int(fc.get(disk_key) or 0)
    return int(fc.get(legacy_key) or 0)


def transcript_seconds_from_job_videos(job: BatchJob) -> float:
    """Sum ``duration_seconds`` for batch video rows with status ``ok``."""
    total = 0.0
    for j in job.jurisdictions:
        for v in j.videos or []:
            if (v.status or "").strip().lower() != "ok":
                continue
            if v.duration_seconds is None:
                continue
            total += float(v.duration_seconds)
    return total


def _jurisdiction_video_counts(j: JurisdictionRun) -> Dict[str, int]:
    """Count finished videos for summary totals.

    While a jurisdiction is running, ``record_video`` appends to ``j.videos`` but
    ``jurisdiction_finish`` has not written final ``j.stats`` yet — prefer the video
    list so the dashboard does not lag behind jurisdiction success counts.
    """
    if j.videos:
        counts = {k: 0 for k in _VIDEO_COUNT_KEYS}
        for v in j.videos:
            key = _STATUS_TO_STAT_KEY.get((v.status or "").strip().lower())
            if key:
                counts[key] += 1
        return counts
    return {k: int((j.stats or {}).get(k) or 0) for k in _VIDEO_COUNT_KEYS}


def _running_file_clock(
    j: JurisdictionRun, now: datetime
) -> tuple[Optional[float], str, str, str]:
    """
  Seconds on the in-flight video for a running jurisdiction.

  Uses explicit ``current_video_started_at`` when set; otherwise time since the
  last completed video in this run, or since the jurisdiction started.
    """
    if j.status != "running":
        return None, "", "", ""

    if j.current_video_started_at:
        try:
            start = datetime.fromisoformat(
                j.current_video_started_at.replace("Z", "+00:00")
            )
            secs = max(0.0, (now - start).total_seconds())
            return (
                secs,
                j.current_video_id or "",
                (j.current_video_title or "")[:120],
                j.current_video_started_at,
            )
        except ValueError:
            pass

    start_iso = ""
    video_id = ""
    title = ""
    if j.videos:
        last = j.videos[-1]
        if last.finished_at:
            start_iso = last.finished_at
            video_id = last.video_id
            title = (last.title or "")[:120]
    if not start_iso and j.started_at:
        start_iso = j.started_at
    if not start_iso:
        return None, video_id, title, ""

    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        secs = max(0.0, (now - start).total_seconds())
        return secs, video_id, title, start_iso
    except ValueError:
        return None, video_id, title, start_iso


def apply_batch_lifecycle(job: BatchJob) -> bool:
    """Stale-cancel inactive runs, then auto-finish when the plan is done. Returns True if status changed."""
    before = (job.status or "").lower()
    _maybe_stale_cancel_batch(job)
    _maybe_auto_finish_batch(job)
    return before != (job.status or "").lower()


def _maybe_auto_finish_batch(job: BatchJob) -> None:
    """
    Mark the batch completed when every target jurisdiction is done.

    Progress cards use jurisdiction counts; ``job.status`` only flipped on ``finish_batch``
    before. Single-jurisdiction tests (or a killed shell after the last backfill) left
    ``running`` at 100%.
    """
    if job.status != "running":
        return
    total_j = int(job.config.get("total_jurisdictions") or 0) or len(job.jurisdictions)
    if total_j <= 0:
        return
    if any(j.status == "running" for j in job.jurisdictions):
        return
    processed = sum(1 for j in job.jurisdictions if j.status in ("completed", "failed"))
    if processed < total_j:
        return
    job.status = "completed"
    if not job.finished_at:
        job.finished_at = _utc_now_iso()


def _recompute_summary(job: BatchJob) -> None:
    if (job.status or "").lower() == "running":
        _maybe_stale_cancel_batch(job)
    total_j = int(job.config.get("total_jurisdictions") or 0) or len(job.jurisdictions)
    processed = sum(1 for j in job.jurisdictions if j.status in ("completed", "failed"))
    success = sum(1 for j in job.jurisdictions if j.status == "completed" and j.exit_code == 0)
    failed = sum(1 for j in job.jurisdictions if j.status == "failed" or j.exit_code != 0)
    remaining = max(0, total_j - processed)

    v_ok = v_fail = v_tomb = v_empty = v_rl = 0
    for j in job.jurisdictions:
        counts = _jurisdiction_video_counts(j)
        v_ok += counts["ok"]
        v_fail += counts["fail"]
        v_tomb += counts["tombstoned"]
        v_empty += counts["empty"]
        v_rl += counts["rate_limit"]

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

    disk = {"transcripts": 0, "analysis": 0, "reports": 0}
    bronze_download_rows = 0
    for j in job.jurisdictions:
        fc = j.file_counts or {}
        disk["transcripts"] += _disk_file_count(
            fc, "transcripts_disk", "transcripts"
        )
        disk["analysis"] += _disk_file_count(fc, "analysis_disk", "analysis")
        disk["reports"] += _disk_file_count(fc, "reports_disk", "reports")
        bronze_download_rows += int(fc.get("bronze_download_rows") or 0)

    files_processed = v_ok + v_fail + v_tomb + v_empty + v_rl
    videos_attempted = files_processed
    avg_seconds_per_file: Optional[float] = None
    if files_processed > 0 and elapsed > 0:
        avg_seconds_per_file = round(elapsed / files_processed, 1)

    current_file_seconds: Optional[float] = None
    current_video_id = ""
    current_video_title = ""
    current_jurisdiction_id = ""
    current_video_started_at = ""
    now = datetime.now(timezone.utc)
    for j in job.jurisdictions:
        secs, vid, title, started_iso = _running_file_clock(j, now)
        if secs is None:
            continue
        if current_file_seconds is None or secs >= current_file_seconds:
            current_file_seconds = secs
            current_video_id = vid
            current_video_title = title
            current_jurisdiction_id = j.jurisdiction_id
            current_video_started_at = started_iso

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
        # Batch-scoped caption outcomes (same source as Videos OK / fail cards).
        "files_transcripts": v_ok,
        "files_processed": files_processed,
        "videos_attempted": videos_attempted,
        # Policy cache on disk (all JSON under each jurisdiction folder, not this run only).
        "files_transcripts_disk": disk["transcripts"],
        "files_analysis": disk["analysis"],
        "files_reports": disk["reports"],
        # Bronze rows with transcript_download_at (lifetime per jurisdiction).
        "bronze_download_rows": bronze_download_rows,
        "transcript_seconds": round(transcript_seconds_from_job_videos(job), 1),
        "avg_seconds_per_file": avg_seconds_per_file,
        "current_file_seconds": (
            round(current_file_seconds, 1)
            if current_file_seconds is not None
            else None
        ),
        "current_video_id": current_video_id,
        "current_video_title": current_video_title,
        "current_jurisdiction_id": current_jurisdiction_id,
        "current_video_started_at": current_video_started_at,
        **state_progress_for_job(job),
    }
    _maybe_auto_finish_batch(job)


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
        try:
            from scripts.datasources.youtube.batch_job_db import sync_batch_job_to_db

            sync_batch_job_to_db(job)
        except Exception:
            pass

    def start_batch(
        self,
        *,
        step: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> BatchJob:
        now = _utc_now_iso()
        cfg = dict(config or {})
        job = BatchJob(
            batch_id=self.batch_id,
            step=step,
            status="running",
            started_at=now,
            updated_at=now,
            config=cfg,
        )
        states = cfg.get("states") or []
        if states and cfg.get("seed_plan") is not False:
            plan = fetch_batch_plan_jurisdictions(
                states,
                round_robin=bool(cfg.get("round_robin", True)),
            )
            if plan:
                job.jurisdictions = plan
                if not int(cfg.get("total_jurisdictions") or 0):
                    cfg["total_jurisdictions"] = len(plan)
                    job.config = cfg
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
        from scripts.jurisdictions.jurisdiction_id import resolve_canonical_jurisdiction_id

        jurisdiction_id = resolve_canonical_jurisdiction_id(
            jurisdiction_id.strip(),
            name=(jurisdiction_name or "").strip() or None,
        )
        job = self.load()
        now = _utc_now_iso()
        run = JurisdictionRun(
            state_code=state_code.upper(),
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            status="running",
            started_at=now,
            updated_at=now,
        )
        if pending_videos:
            run.stats["pending"] = pending_videos
        start_key = _plan_jurisdiction_key(jurisdiction_id)
        job.jurisdictions = [
            j
            for j in job.jurisdictions
            if _plan_jurisdiction_key(j.jurisdiction_id) != start_key
        ]
        job.jurisdictions.append(run)
        self.save(job)
        return run

    def _find_jurisdiction(self, job: BatchJob, jurisdiction_id: str) -> JurisdictionRun:
        from scripts.jurisdictions.jurisdiction_id import resolve_canonical_jurisdiction_id

        jid = resolve_canonical_jurisdiction_id((jurisdiction_id or "").strip()) or (
            jurisdiction_id or ""
        ).strip()
        key = _plan_jurisdiction_key(jid)
        for j in job.jurisdictions:
            if j.jurisdiction_id == jid:
                return j
            if key and _plan_jurisdiction_key(j.jurisdiction_id) == key:
                return j
        raise KeyError(jurisdiction_id)

    def video_start(
        self,
        *,
        jurisdiction_id: str,
        video_id: str,
        title: str = "",
    ) -> None:
        job = self.load()
        j = self._find_jurisdiction(job, jurisdiction_id)
        j.current_video_id = video_id
        j.current_video_title = (title or "")[:200]
        j.current_video_started_at = _utc_now_iso()
        j.updated_at = j.current_video_started_at
        self.save(job)

    def record_video(
        self,
        *,
        jurisdiction_id: str,
        video_id: str,
        status: str,
        title: str = "",
        error: str = "",
        transcript_source: str = "",
        duration_seconds: Optional[float] = None,
    ) -> None:
        job = self.load()
        j = self._find_jurisdiction(job, jurisdiction_id)
        if j.current_video_id == video_id:
            j.current_video_id = ""
            j.current_video_title = ""
            j.current_video_started_at = ""
        prior_status = ""
        for v in j.videos:
            if v.video_id == video_id:
                prior_status = (v.status or "").strip().lower()
                break
        j.videos = [v for v in j.videos if v.video_id != video_id]
        if prior_status:
            old_key = _STATUS_TO_STAT_KEY.get(prior_status)
            if old_key:
                j.stats[old_key] = max(0, int(j.stats.get(old_key) or 0) - 1)
        now = _utc_now_iso()
        j.videos.append(
            VideoResult(
                video_id=video_id,
                title=title[:200],
                status=status,
                error=(error or "")[:500],
                transcript_source=transcript_source,
                finished_at=now,
                duration_seconds=duration_seconds,
            )
        )
        new_key = _STATUS_TO_STAT_KEY.get((status or "").strip().lower())
        if new_key:
            j.stats[new_key] = int(j.stats.get(new_key) or 0) + 1
        j.updated_at = now
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
        j.updated_at = j.finished_at
        j.current_video_id = ""
        j.current_video_title = ""
        j.current_video_started_at = ""
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


def policy_disk_file_counts(scanned: Dict[str, int]) -> Dict[str, int]:
    """Map ``count_policy_files_for_jurisdiction`` keys to explicit on-disk counters."""
    return {
        "transcripts_disk": int(scanned.get("transcripts") or 0),
        "analysis_disk": int(scanned.get("analysis") or 0),
        "reports_disk": int(scanned.get("reports") or 0),
    }


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
        "round_robin": bool(getattr(args, "round_robin", 1)),
        "seed_plan": not getattr(args, "no_seed_plan", False),
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
    p_start.add_argument(
        "--round-robin",
        type=int,
        default=1,
        help="1 = interleave states in plan order (default), 0 = state-by-state",
    )
    p_start.add_argument(
        "--no-seed-plan",
        action="store_true",
        help="Do not pre-load all jurisdictions as pending rows",
    )
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
