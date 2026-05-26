"""Tests for batch job status store and dashboard payload."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.datasources.youtube.batch_job_status import (
    BatchJobStore,
    _recompute_summary,
    new_batch_id,
)
from scripts.datasources.youtube.batch_job_dashboard import build_dashboard_data


def test_batch_lifecycle_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bid = new_batch_id("captions")
        store = BatchJobStore(bid, jobs_root=root)
        store.start_batch(
            step="captions",
            config={"n": 10, "total_jurisdictions": 2, "seed_plan": False},
        )
        store.jurisdiction_start(
            state_code="GA",
            jurisdiction_id="appling_13001",
            jurisdiction_name="Appling County",
            pending_videos=3,
        )
        store.record_video(
            jurisdiction_id="appling_13001",
            video_id="abc123",
            status="ok",
            title="Meeting",
            transcript_source="yt-dlp",
        )
        mid = store.load()
        _recompute_summary(mid)
        assert mid.summary["videos_ok"] == 1
        assert mid.summary["videos_fail"] == 0
        store.record_video(
            jurisdiction_id="appling_13001",
            video_id="def456",
            status="fail",
            error="no captions",
        )
        store.jurisdiction_finish(
            jurisdiction_id="appling_13001",
            exit_code=0,
            stats={"ok": 1, "fail": 1},
            file_counts={
                "transcripts_disk": 5,
                "analysis_disk": 2,
                "reports_disk": 0,
                "bronze_download_rows": 99,
            },
        )
        store.finish_batch(status="completed")

        job = store.load()
        assert job.status == "completed"
        assert job.summary["processed_jurisdictions"] == 1
        assert job.summary["remaining_jurisdictions"] == 1
        assert job.summary["videos_ok"] == 1
        assert job.summary["videos_fail"] == 1
        assert job.summary["files_transcripts"] == 1
        assert job.summary["files_processed"] == 2
        assert job.summary["videos_attempted"] == 2
        assert job.summary["files_transcripts_disk"] == 5
        assert job.summary["files_analysis"] == 2
        assert job.summary["bronze_download_rows"] == 99
        assert len(job.jurisdictions) == 1
        assert len(job.jurisdictions[0].videos) == 2

        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
        assert index[0]["batch_id"] == bid


def test_dashboard_build_no_refresh():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bid = new_batch_id("test")
        store = BatchJobStore(bid, jobs_root=root)
        store.start_batch(step="captions", config={"total_jurisdictions": 1})
        store.jurisdiction_start(
            state_code="IN",
            jurisdiction_id="adams_18001",
            jurisdiction_name="Adams",
        )
        store.jurisdiction_finish(
            jurisdiction_id="adams_18001",
            exit_code=0,
            stats={"ok": 2},
        )

        import scripts.datasources.youtube.batch_job_status as mod

        old = mod.jobs_dir
        mod.jobs_dir = lambda: root  # type: ignore[assignment]
        try:
            payload = build_dashboard_data(refresh_files=False)
        finally:
            mod.jobs_dir = old  # type: ignore[assignment]

        assert payload["totals"]["batches"] >= 1
        assert payload["batches"][0]["batch_id"] == bid
        assert store.load().status == "completed"


def test_auto_finish_when_all_target_jurisdictions_done():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bid = new_batch_id("captions")
        store = BatchJobStore(bid, jobs_root=root)
        store.start_batch(
            step="captions",
            config={"total_jurisdictions": 1, "seed_plan": False},
        )
        store.jurisdiction_start(
            state_code="AL",
            jurisdiction_id="bullock_01011",
            jurisdiction_name="Bullock",
        )
        store.jurisdiction_finish(
            jurisdiction_id="bullock_01011",
            exit_code=0,
            stats={"ok": 2},
        )
        job = store.load()
        assert job.status == "completed"
        assert job.finished_at
        assert job.summary["remaining_jurisdictions"] == 0


def test_last_batch_activity_not_now_when_jurisdiction_timestamps_missing():
    from scripts.datasources.youtube.batch_job_status import (
        BatchJob,
        JurisdictionRun,
        batch_inactivity_seconds,
        last_batch_activity_at,
    )

    stale_start = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        - __import__("datetime").timedelta(seconds=batch_inactivity_seconds() + 120)
    ).isoformat()
    job = BatchJob(
        batch_id="x",
        step="captions",
        started_at=stale_start,
        updated_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        jurisdictions=[
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="a_1",
                status="running",
            ),
        ],
    )
    idle = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        - last_batch_activity_at(job)
    ).total_seconds()
    assert idle > batch_inactivity_seconds()


def test_stale_cancel_after_inactivity():
    from datetime import datetime, timedelta, timezone

    from scripts.datasources.youtube.batch_job_status import (
        JurisdictionRun,
        _recompute_summary,
        batch_inactivity_seconds,
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bid = new_batch_id("captions")
        store = BatchJobStore(bid, jobs_root=root)
        stale = (
            datetime.now(timezone.utc) - timedelta(seconds=batch_inactivity_seconds() + 60)
        ).isoformat()
        store.start_batch(
            step="captions",
            config={"states": ["AL", "GA"], "total_jurisdictions": 2, "seed_plan": False},
        )
        job = store.load()
        job.status = "running"
        job.updated_at = stale
        job.jurisdictions = [
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="a_1",
                status="running",
                updated_at=stale,
            ),
        ]
        _recompute_summary(job)
        assert job.status == "cancelled"
        assert job.jurisdictions[0].status == "failed"


def test_state_progress_started_and_completed():
    from scripts.datasources.youtube.batch_job_status import (
        BatchJob,
        JurisdictionRun,
        _recompute_summary,
    )

    job = BatchJob(
        batch_id="test",
        step="captions",
        config={"states": ["AL", "GA", "IN"]},
        jurisdictions=[
            JurisdictionRun(state_code="AL", jurisdiction_id="a_1", status="completed"),
            JurisdictionRun(state_code="AL", jurisdiction_id="a_2", status="pending"),
            JurisdictionRun(state_code="GA", jurisdiction_id="g_1", status="running"),
            JurisdictionRun(state_code="IN", jurisdiction_id="i_1", status="pending"),
        ],
    )
    _recompute_summary(job)
    assert job.summary["states_planned"] == 3
    assert job.summary["states_started"] == 2
    assert set(job.summary["states_started_codes"]) == {"AL", "GA"}
    assert job.summary["states_completed"] == 0
