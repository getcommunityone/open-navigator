"""Batch job full jurisdiction plan (pending rows)."""

from __future__ import annotations

from scripts.datasources.youtube.batch_job_status import (
    BatchJob,
    JurisdictionRun,
    expand_batch_job_plan,
    fetch_batch_plan_jurisdictions,
)


def test_expand_batch_job_plan_merges_pending(monkeypatch):
    def fake_plan(states, *, round_robin=True, database_url=None):
        return [
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="a_1",
                jurisdiction_name="Alpha",
                status="pending",
            ),
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="b_2",
                jurisdiction_name="Beta",
                status="pending",
            ),
        ]

    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status.fetch_batch_plan_jurisdictions",
        fake_plan,
    )
    job = BatchJob(
        batch_id="test",
        step="captions",
        config={"states": ["AL"], "total_jurisdictions": 2},
        jurisdictions=[
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="a_1",
                jurisdiction_name="Alpha",
                status="completed",
                stats={"ok": 3},
            ),
        ],
    )
    expand_batch_job_plan(job)
    assert len(job.jurisdictions) == 2
    assert job.jurisdictions[0].status == "completed"
    assert job.jurisdictions[1].status == "pending"
    assert job.jurisdictions[1].jurisdiction_id == "b_2"


def test_expand_preserves_completed_when_ids_differ_by_type(monkeypatch):
    def fake_plan(states, *, round_robin=True, database_url=None):
        return [
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="anniston_0101852",
                jurisdiction_name="Anniston",
                status="pending",
            ),
        ]

    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status.fetch_batch_plan_jurisdictions",
        fake_plan,
    )
    job = BatchJob(
        batch_id="test",
        step="captions",
        config={"states": ["AL"], "total_jurisdictions": 1},
        jurisdictions=[
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="municipality_0101852",
                jurisdiction_name="Anniston",
                status="completed",
                stats={"ok": 6},
            ),
        ],
    )
    expand_batch_job_plan(job)
    assert len(job.jurisdictions) == 1
    assert job.jurisdictions[0].status == "completed"
    assert job.jurisdictions[0].stats.get("ok") == 6


def test_expand_upgrades_legacy_prefixed_row_from_plan(monkeypatch):
    def fake_plan(states, *, round_robin=True, database_url=None):
        return [
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="chilton_01021",
                jurisdiction_name="Chilton County",
                jurisdiction_type="county",
                status="pending",
            ),
        ]

    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status.fetch_batch_plan_jurisdictions",
        fake_plan,
    )
    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status.fetch_batch_plan_jurisdictions_cached",
        fake_plan,
    )
    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status._lookup_jurisdiction_name_from_db",
        lambda *_a, **_k: "Chilton County",
    )
    from scripts.datasources.youtube import batch_job_status as mod

    mod._fetch_batch_plan_cached.cache_clear()
    job = BatchJob(
        batch_id="test",
        step="captions",
        config={"states": ["AL"], "total_jurisdictions": 1},
        jurisdictions=[
            JurisdictionRun(
                state_code="AL",
                jurisdiction_id="c-AL-01021",
                jurisdiction_name="c-AL-01021",
                status="pending",
            ),
        ],
    )
    expand_batch_job_plan(job)
    assert len(job.jurisdictions) == 1
    assert job.jurisdictions[0].jurisdiction_id == "chilton_01021"
    assert job.jurisdictions[0].jurisdiction_name == "Chilton County"


def test_fetch_batch_plan_drops_legacy_prefixed_ids(monkeypatch):
    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, *_args, **_kwargs):
            return None

        def fetchall(self):
            return self._rows

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class FakeConn:
        def __init__(self, rows):
            self._rows = rows

        def cursor(self, cursor_factory=None):
            return FakeCursor(self._rows)

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    rows = [
        {
            "state_code": "AL",
            "jurisdiction_id": "chilton_01021",
            "jurisdiction_name": "Chilton County",
            "jurisdiction_type": "county",
        },
        {
            "state_code": "AL",
            "jurisdiction_id": "c-AL-01021",
            "jurisdiction_name": "Chilton County",
            "jurisdiction_type": "county",
        },
    ]

    def fake_connect(_url):
        return FakeConn(rows)

    import psycopg2

    monkeypatch.setattr(psycopg2, "connect", fake_connect)
    monkeypatch.setattr(
        "scripts.datasources.youtube.batch_job_status._batch_database_url",
        lambda: "postgresql://fake",
    )

    runs = fetch_batch_plan_jurisdictions(["AL"], round_robin=False)
    ids = {r.jurisdiction_id for r in runs}
    assert "c-AL-01021" not in ids
    assert "chilton_01021" in ids
