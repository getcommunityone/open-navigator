"""Postgres batch job persistence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.datasources.youtube.batch_job_status import (
    BatchJobStore,
    new_batch_id,
)


@pytest.fixture
def jobs_root(tmp_path):
    return tmp_path / "batch_jobs"


def test_sync_batch_job_to_db_roundtrip(jobs_root):
    url = (os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("NEON_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("No Postgres URL configured")

    bid = new_batch_id("test-db")
    store = BatchJobStore(bid, jobs_root=jobs_root)
    store.start_batch(step="captions", config={"total_jurisdictions": 1, "n": 10})
    store.jurisdiction_start(
        state_code="GA",
        jurisdiction_id="appling_13001",
        jurisdiction_name="Appling",
        pending_videos=2,
    )

    from scripts.datasources.youtube.batch_job_db import (
        list_batch_jobs_from_db,
        load_batch_job_from_db,
    )

    loaded = load_batch_job_from_db(bid)
    assert loaded is not None
    assert loaded.batch_id == bid
    assert any(j.jurisdiction_id == "appling_13001" for j in loaded.jurisdictions)

    recent = list_batch_jobs_from_db(limit=5)
    assert any(j.batch_id == bid for j in recent)


def test_build_dashboard_prefers_database(jobs_root):
    url = (os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("NEON_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("No Postgres URL configured")

    from scripts.datasources.youtube.batch_job_dashboard import build_dashboard_data

    with patch.dict(os.environ, {"BATCH_JOBS_USE_DB": "1"}):
        payload = build_dashboard_data(refresh_files=False, enrich_bronze=False)
    assert payload.get("source") in ("database", "files")
