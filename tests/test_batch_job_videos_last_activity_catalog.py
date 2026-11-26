"""Videos stage Last activity follows catalog ``last_updated`` (#757)."""

from __future__ import annotations

import inspect

from api.batch_jobs import batch_job_db as bj


def test_stage_timing_videos_uses_catalog_clock() -> None:
    src = inspect.getsource(bj._stage_timing)
    assert "last_updated" in src
    assert "GREATEST(last_updated, transcript_download_at)" in src


def test_pipeline_stage_report_videos_last_uses_catalog_clock() -> None:
    src = inspect.getsource(bj.pipeline_stage_report)
    assert "last_updated" in src
    assert src.count("GREATEST(last_updated, transcript_download_at)") >= 1
