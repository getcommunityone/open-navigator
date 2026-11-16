"""Batch job full jurisdiction plan (pending rows)."""

from __future__ import annotations

import pytest

from api.batch_jobs import batch_job_status
from api.batch_jobs.batch_job_status import (
    BatchJob,
    JurisdictionRun,
    expand_batch_job_plan,
    fetch_batch_plan_jurisdictions,
)


@pytest.fixture(autouse=True)
def _fresh_plan_cache():
    # expand_batch_job_plan reads the plan through an lru_cache keyed by the states: without this, a test sees the plan
    # the previous test cached and gets that test's rows.
    batch_job_status._fetch_batch_plan_cached.cache_clear()
    yield
    batch_job_status._fetch_batch_plan_cached.cache_clear()


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
        "api.batch_jobs.batch_job_status.fetch_batch_plan_jurisdictions",
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
        "api.batch_jobs.batch_job_status.fetch_batch_plan_jurisdictions",
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
        "api.batch_jobs.batch_job_status.fetch_batch_plan_jurisdictions",
        fake_plan,
    )
    monkeypatch.setattr(
        "api.batch_jobs.batch_job_status.fetch_batch_plan_jurisdictions_cached",
        fake_plan,
    )
    monkeypatch.setattr(
        "api.batch_jobs.batch_job_status._lookup_jurisdiction_name_from_db",
        lambda *_a, **_k: "Chilton County",
    )
    from api.batch_jobs import batch_job_status as mod

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
        "api.batch_jobs.batch_job_status._batch_database_url",
        lambda: "postgresql://fake",
    )

    runs = fetch_batch_plan_jurisdictions(["AL"], round_robin=False)
    ids = {r.jurisdiction_id for r in runs}
    assert "c-AL-01021" not in ids
    assert "chilton_01021" in ids


def test_batch_plan_sql_has_no_stray_percent_signs():
    """A bare % in the SQL (e.g. LIKE '%_x') breaks psycopg2's %s parameters; the
    error was swallowed and every plan silently came from the fallback query."""
    import ast
    import inspect
    import textwrap

    from api.batch_jobs import batch_job_status as b

    tree = ast.parse(textwrap.dedent(inspect.getsource(b.fetch_batch_plan_jurisdictions)))
    sql = next(
        n.args[0].value
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "execute"
    )
    # psycopg2 formats like Python's % operator: four parameters, nothing else.
    rendered = sql % ("'S'", "'S'", "true", "false")
    assert "%" not in rendered.replace("%%", "")
    assert "include_homepage_channels" in inspect.signature(b.fetch_batch_plan_jurisdictions).parameters
