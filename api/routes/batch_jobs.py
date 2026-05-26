"""
YouTube / policy pipeline batch job status for the Data explorer React UI.

Reads from ``bronze.youtube_batch_job_runs`` (real-time). JSON files under
``data/cache/batch_jobs/`` are synced on read when the DB is empty.

Live updates: ``GET /api/batch-jobs/stream`` (Server-Sent Events).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

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


class BatchJobsDashboardResponse(BaseModel):
    generated_at: str
    last_activity_at: str = ""
    totals: BatchJobsTotals
    batches: List[BatchJobModel]
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
        from scripts.datasources.youtube.batch_job_db import latest_dashboard_revision

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
    from scripts.datasources.youtube.batch_job_dashboard import (
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
    from scripts.datasources.youtube.batch_job_db import list_failed_videos_from_db

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
    from scripts.datasources.youtube.batch_job_dashboard import (
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
        from scripts.datasources.youtube.batch_job_db import load_batch_job_from_db

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
        from scripts.datasources.youtube.batch_job_db import (
            enrich_jobs_from_bronze,
            load_batch_job_from_db,
        )
        from scripts.datasources.youtube.batch_job_status import (
            BatchJobStore,
            _recompute_summary,
            apply_batch_lifecycle,
            count_policy_files_for_jurisdiction,
            expand_batch_job_plan,
        )
        from scripts.datasources.youtube.batch_job_dashboard import _POLICY_CACHE

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
            from scripts.datasources.youtube.batch_job_dashboard import slim_batch_dict

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
