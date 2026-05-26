"""Fast dashboard payload helpers."""

from __future__ import annotations

from scripts.datasources.youtube.batch_job_dashboard import (
    _totals_from_batch_summaries,
    slim_batch_dict,
    slim_jurisdiction_videos,
)


def test_slim_jurisdiction_strips_ok_videos():
    j = {
        "jurisdiction_id": "x_13001",
        "status": "completed",
        "stats": {"ok": 3, "fail": 1},
        "videos": [
            {"video_id": "a", "status": "ok"},
            {"video_id": "b", "status": "fail"},
        ],
    }
    out = slim_jurisdiction_videos(j, video_mode="failed_only")
    assert len(out["videos"]) == 1
    assert out["videos"][0]["video_id"] == "b"


def test_slim_batch_keeps_running_jurisdiction_videos():
    batch = {
        "batch_id": "captions-test",
        "status": "running",
        "jurisdictions": [
            {
                "jurisdiction_id": "x_13001",
                "status": "running",
                "current_video_id": "vid1",
                "videos": [{"video_id": "vid1", "status": "pending"}],
            },
            {
                "jurisdiction_id": "y_13002",
                "status": "completed",
                "videos": [{"video_id": "z", "status": "ok"}],
            },
        ],
    }
    out = slim_batch_dict(batch, video_mode="running")
    running = out["jurisdictions"][0]
    done = out["jurisdictions"][1]
    assert len(running["videos"]) == 1
    assert done["videos"] == []


def test_totals_from_summaries_only():
    batches = [
        {
            "status": "running",
            "config": {"states": ["GA", "AL"]},
            "summary": {
                "processed_jurisdictions": 2,
                "videos_ok": 10,
                "videos_fail": 1,
                "states_started_codes": ["GA"],
                "states_completed_codes": [],
            },
        }
    ]
    totals = _totals_from_batch_summaries(batches)
    assert totals["batches"] == 1
    assert totals["running"] == 1
    assert totals["videos_ok"] == 10
    assert totals["states_planned"] == 2
    assert totals["states_started"] == 1
