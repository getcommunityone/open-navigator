"""Unit tests for api/routes/trending.py database resolution, caching, and fallback logic."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, List
import pytest
import psycopg2

from api.routes import trending


@pytest.fixture(autouse=True)
def _reset_trending_cache():
    trending.clear_trending_cache()
    yield
    trending.clear_trending_cache()


class _FakeConnection:
    def __init__(self) -> None:
        self.rollbacks = 0
        self.closed = False

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class _FakeCursor:
    def __init__(self, handler, conn: _FakeConnection) -> None:
        self._handler = handler
        self.connection = conn
        self._rows: List[Any] = []
        self.queries: List[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.queries.append((sql, params))
        self._rows = self._handler(sql, params)

    def fetchall(self) -> List[Any]:
        return list(self._rows)

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_resolve_db_url_priority_and_postgres_scheme(monkeypatch: pytest.MonkeyPatch):
    for key in trending._DB_ENV_PRIORITY:
        monkeypatch.delenv(key, raising=False)

    assert trending.resolve_db_url() == trending._DEFAULT_LOCAL_DB_URL

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db.example.com:5432/prod")
    assert trending.resolve_db_url() == "postgresql://user:pass@db.example.com:5432/prod"

    monkeypatch.setenv("OPEN_NAVIGATOR_DATABASE_URL", "postgresql://nav:pass@nav.example.com:5432/nav")
    assert trending.resolve_db_url() == "postgresql://nav:pass@nav.example.com:5432/nav"

    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://neon:pass@neon.example.com:5432/neon")
    assert trending.resolve_db_url() == "postgresql://neon:pass@neon.example.com:5432/neon"

    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://dev:pass@localhost:5433/dev")
    assert trending.resolve_db_url() == "postgresql://dev:pass@localhost:5433/dev"


def test_everyorg_causes_linkage_mart_fallback_rolls_back_same_connection(
    monkeypatch: pytest.MonkeyPatch,
):
    conn = _FakeConnection()
    connect_calls = 0

    def handler(sql: str, params: Any):
        if "gold.meeting_cause_link" in sql:
            raise psycopg2.errors.UndefinedTable("relation gold.meeting_cause_link does not exist")
        return [
            ("education", "Education", "Schools and learning", "📚", "human_services", 1, 0),
            ("housing", "Housing", "Affordable housing", "🏠", "community", 2, 0),
        ]

    @contextmanager
    def fake_cursor():
        nonlocal connect_calls
        connect_calls += 1
        yield _FakeCursor(handler, conn)

    monkeypatch.setattr(trending, "_cursor", fake_cursor)

    items = trending.get_everyorg_causes(limit=5, state="Alabama", city="Tuscaloosa")
    assert connect_calls == 1
    assert conn.rollbacks == 1
    assert len(items) == 2
    assert items[0].cause_id == "education"
    assert items[0].meeting_count == 0
    assert items[0].image_url == "/images/causes/everyorg_education_square.png"


def test_ntee_causes_populates_cause_id_and_uses_single_connection_on_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    conn = _FakeConnection()
    connect_calls = 0

    def handler(sql: str, params: Any):
        if "bronze.bronze_ntee_codes" in sql:
            raise psycopg2.errors.UndefinedTable("bronze.bronze_ntee_codes missing")
        assert "FROM public.tag" in sql
        return [
            ("A", "Arts, Culture & Humanities", "Cultural organizations", "ntee"),
            ("B", "Education", "Educational institutions", "ntee"),
        ]

    @contextmanager
    def fake_cursor():
        nonlocal connect_calls
        connect_calls += 1
        yield _FakeCursor(handler, conn)

    monkeypatch.setattr(trending, "_cursor", fake_cursor)

    items = trending.get_ntee_causes(limit=5, level=1)
    assert connect_calls == 1
    assert conn.rollbacks == 1
    assert len(items) == 2
    assert items[0].cause_id == "A"
    assert items[0].icon == "🎨"
    assert items[1].cause_id == "B"
    assert items[1].icon == "📚"


@pytest.mark.asyncio
async def test_get_trending_causes_mixed_handles_limit_one_and_odd_limits(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        trending,
        "get_everyorg_causes",
        lambda limit=20, state=None, city=None: [
            trending.CauseItem(
                cause_id=f"eo-{i}",
                name=f"EveryOrg {i}",
                icon="📌",
                category="general",
            )
            for i in range(limit)
        ],
    )
    monkeypatch.setattr(
        trending,
        "get_ntee_causes",
        lambda limit=20, level=None: [
            trending.CauseItem(
                cause_id=f"ntee-{i}",
                name=f"NTEE {i}",
                icon="📚",
                category="ntee",
            )
            for i in range(limit)
        ],
    )

    res_one = await trending.get_trending_causes(source="mixed", limit=1, level=None, state=None, city=None)
    assert res_one.total == 1
    assert len(res_one.causes) == 1
    assert res_one.causes[0].cause_id == "eo-0"

    res_three = await trending.get_trending_causes(source="mixed", limit=3, level=1, state=None, city=None)
    assert res_three.total == 3
    assert [c.cause_id for c in res_three.causes] == ["eo-0", "ntee-0", "eo-1"]


@pytest.mark.asyncio
async def test_get_trending_causes_inflight_deduplication_and_cache(
    monkeypatch: pytest.MonkeyPatch,
):
    call_count = 0

    def slow_everyorg(limit=20, state=None, city=None):
        nonlocal call_count
        call_count += 1
        return [
            trending.CauseItem(
                cause_id="environment",
                name="Environment",
                icon="🌍",
                category="environment",
                meeting_count=7,
            )
        ]

    monkeypatch.setattr(trending, "get_everyorg_causes", slow_everyorg)

    results = await asyncio.gather(
        *[
            trending.get_trending_causes(
                source="everyorg", limit=6, level=None, state="Georgia", city="Atlanta"
            )
            for _ in range(5)
        ]
    )

    assert call_count == 1
    for res in results:
        assert res.total == 1
        assert res.causes[0].cause_id == "environment"
        assert res.causes[0].meeting_count == 7


@pytest.mark.asyncio
async def test_get_trending_topics_state_and_missing_table_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    conn = _FakeConnection()
    should_fail = False

    def handler(sql: str, params: Any):
        if should_fail:
            raise psycopg2.errors.UndefinedTable("public.rpt_bill_map_aggregate missing")
        assert params == ("AL", 5)
        return [("Education", 42, 9, "AL"), ("Health", 18, 4, "AL")]

    @contextmanager
    def fake_cursor():
        yield _FakeCursor(handler, conn)

    monkeypatch.setattr(trending, "_cursor", fake_cursor)

    should_fail = True
    empty_res = await trending.get_trending_topics(state="Alabama", limit=5)
    assert empty_res.total == 0
    assert empty_res.topics == []

    # Empty fallback should not poison the cache; subsequent call after table creation succeeds.
    should_fail = False
    ok_res = await trending.get_trending_topics(state="Alabama", limit=5)
    assert ok_res.total == 2
    assert ok_res.topics[0].name == "Education"
    assert ok_res.topics[0].recent_bill_count == 9
    assert ok_res.topics[0].state_code == "AL"


@pytest.mark.asyncio
async def test_get_trending_stats_reuses_single_connection_with_tag_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    conn = _FakeConnection()
    connect_calls = 0

    def handler(sql: str, params: Any):
        if "bronze.bronze_everyorg_causes" in sql:
            return [(38,)]
        if "bronze.bronze_ntee_codes" in sql:
            raise psycopg2.errors.UndefinedTable("bronze.bronze_ntee_codes not found")
        if "public.tag" in sql:
            return [(26,)]
        raise AssertionError(f"Unexpected SQL: {sql}")

    @contextmanager
    def fake_cursor():
        nonlocal connect_calls
        connect_calls += 1
        yield _FakeCursor(handler, conn)

    monkeypatch.setattr(trending, "_cursor", fake_cursor)

    stats = await trending.get_trending_stats()
    assert connect_calls == 1
    assert conn.rollbacks == 1
    assert stats["everyorg_causes"] == 38
    assert stats["ntee_causes"] == 26
    assert stats["total_causes"] == 64


def test_bounded_cache_evicts_oldest_when_full(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(trending, "_MAX_CACHE_ENTRIES", 3)
    trending._set_cached("k1", "v1")
    trending._set_cached("k2", "v2")
    trending._set_cached("k3", "v3")
    trending._set_cached("k4", "v4")

    assert len(trending._trending_cache) == 3
    assert trending._get_cached("k1") is None
    assert trending._get_cached("k2") == "v2"
    assert trending._get_cached("k4") == "v4"
