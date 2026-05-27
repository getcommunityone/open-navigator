"""Unit tests for core_lib.db.session commit / rollback semantics."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from core_lib.db.engine import get_async_engine, get_sync_engine
from core_lib.db.session import async_session, sync_session


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    db_path = tmp_path / "session_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    get_sync_engine.cache_clear()
    get_async_engine.cache_clear()
    import core_lib.db.session as s
    s._sync_factory = None
    s._async_factory = None

    with sync_session() as ses:
        ses.execute(text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"))

    yield

    get_sync_engine.cache_clear()
    get_async_engine.cache_clear()
    s._sync_factory = None
    s._async_factory = None


def _count_sync() -> int:
    with sync_session() as ses:
        return ses.execute(text("SELECT COUNT(*) FROM t")).scalar_one()


def test_sync_session_commits_on_success():
    with sync_session() as ses:
        ses.execute(text("INSERT INTO t (v) VALUES ('a')"))
        ses.execute(text("INSERT INTO t (v) VALUES ('b')"))
    assert _count_sync() == 2


def test_sync_session_rolls_back_on_exception():
    with pytest.raises(RuntimeError):
        with sync_session() as ses:
            ses.execute(text("INSERT INTO t (v) VALUES ('x')"))
            raise RuntimeError("boom")
    assert _count_sync() == 0


def test_async_session_commits_on_success():
    async def go():
        async with async_session() as ses:
            await ses.execute(text("INSERT INTO t (v) VALUES ('a1')"))
            await ses.execute(text("INSERT INTO t (v) VALUES ('a2')"))

    asyncio.run(go())
    assert _count_sync() == 2


def test_async_session_rolls_back_on_exception():
    async def go():
        async with async_session() as ses:
            await ses.execute(text("INSERT INTO t (v) VALUES ('z')"))
            raise RuntimeError("boom-async")

    with pytest.raises(RuntimeError, match="boom-async"):
        asyncio.run(go())
    assert _count_sync() == 0
