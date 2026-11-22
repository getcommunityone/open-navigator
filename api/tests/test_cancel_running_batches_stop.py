"""#742: Stop all force-cancels orphan running batch rows."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.batch_jobs.batch_job_status import BatchJob, JurisdictionRun


def test_cancel_running_batches_marks_job_cancelled() -> None:
    job = BatchJob(
        batch_id="captions-test",
        step="captions",
        status="running",
        jurisdictions=[
            JurisdictionRun(
                jurisdiction_id="j1",
                jurisdiction_name="Test",
                state_code="AL",
                status="running",
            )
        ],
    )
    row = {"payload": job.to_dict()}

    with (
        patch("api.batch_jobs.batch_job_db._use_db", return_value=True),
        patch("api.batch_jobs.batch_job_db.get_db_connection") as get_conn,
        patch("api.batch_jobs.batch_job_db.ensure_batch_job_tables"),
        patch("api.batch_jobs.batch_job_status.persist_batch_job") as persist,
    ):
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [row]
        conn.cursor.return_value.__enter__.return_value = cur
        get_conn.return_value.__enter__.return_value = conn

        from api.batch_jobs.batch_job_db import cancel_running_batches

        n = cancel_running_batches(reason="test stop")

    assert n == 1
    persist.assert_called_once()
    saved = persist.call_args[0][0]
    assert saved.status == "cancelled"
    assert saved.config.get("stop_all_reason") == "test stop"
    assert saved.jurisdictions[0].status == "failed"
