"""Offline tests for hosting.neon.regenerate_bills_map."""
from __future__ import annotations

import re

import pytest

from hosting.neon import regenerate_bills_map as mod


def test_aggregate_query_uses_array_slice_not_limit_inside_array_agg():
    assert "LIMIT 3" not in mod._AGGREGATE_QUERY
    assert re.search(r"\(ARRAY_AGG\s*\(.*?\)\)\[1:3\]", mod._AGGREGATE_QUERY, re.DOTALL)


_NAV_VARS = (
    "OPEN_NAVIGATOR_DATABASE_URL",
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "DATABASE_URL",
)


def test_resolve_open_navigator_db_url_priority_and_normalization(monkeypatch):
    for var in _NAV_VARS:
        monkeypatch.delenv(var, raising=False)

    assert mod._resolve_open_navigator_db_url() == "postgresql://postgres:password@localhost:5433/open_navigator"

    monkeypatch.setenv("DATABASE_URL", "  postgres://u:p@db.example/nav?sslmode=require  ")
    assert mod._resolve_open_navigator_db_url() == "postgresql://u:p@db.example/nav?sslmode=require"

    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://dev@localhost/nav")
    assert mod._resolve_open_navigator_db_url() == "postgresql://dev@localhost/nav"

    monkeypatch.setenv("OPEN_NAVIGATOR_DATABASE_URL", "postgres://primary@neon.example/nav")
    assert mod._resolve_open_navigator_db_url() == "postgresql://primary@neon.example/nav"


def test_default_target_never_falls_back_to_production(monkeypatch):
    for var in _NAV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://u:p@prod.neon.example/nav")

    assert mod._resolve_open_navigator_db_url() == "postgresql://postgres:password@localhost:5433/open_navigator"

    # A SQLite DATABASE_URL (legacy user DB) is skipped, not handed to asyncpg.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/users.db")
    assert mod._resolve_open_navigator_db_url() == "postgresql://postgres:password@localhost:5433/open_navigator"


def test_prod_target_requires_explicit_flag_and_variable(monkeypatch):
    for var in _NAV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://dev@localhost/nav")

    with pytest.raises(RuntimeError, match="NEON_DATABASE_URL"):
        mod._resolve_open_navigator_db_url("prod")

    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://u:p@prod.neon.example/nav")
    assert mod._resolve_open_navigator_db_url("prod") == "postgresql://u:p@prod.neon.example/nav"

    with pytest.raises(ValueError):
        mod._resolve_open_navigator_db_url("production")


def test_main_defaults_to_dev_target(monkeypatch):
    seen: dict[str, str] = {}

    async def _fake_regen(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(mod, "regenerate_map_aggregates", _fake_regen)
    mod.main([])
    assert seen == {"target": "dev"}
    mod.main(["--target", "prod"])
    assert seen == {"target": "prod"}


def test_dsn_host_strips_credentials():
    assert mod._dsn_host("postgresql://u:secret@prod.neon.example:5432/nav") == "prod.neon.example:5432"
    assert mod._dsn_host("postgresql://u:p@db.example/nav") == "db.example"


def test_resolve_openstates_db_url_normalization(monkeypatch):
    monkeypatch.setenv("OPENSTATES_DATABASE_URL", "postgres://u:p@host/openstates")
    assert mod._resolve_openstates_db_url() == "postgresql://u:p@host/openstates"

    monkeypatch.delenv("OPENSTATES_DATABASE_URL", raising=False)
    assert mod._resolve_openstates_db_url() == "postgresql://postgres:password@localhost:5433/openstates"


class _FakeConn:
    def __init__(self, rows=None, close_error: Exception | None = None):
        self.rows = rows or []
        self.closed = False
        self.executed: list[tuple[str, tuple]] = []
        self._close_error = close_error

    async def fetch(self, _sql: str):
        return self.rows

    async def execute(self, sql: str, *args):
        self.executed.append((sql, args))

    async def close(self):
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


@pytest.mark.asyncio
async def test_openstates_conn_closed_when_navigator_connect_fails(monkeypatch):
    openstates_conn = _FakeConn()
    calls = {"n": 0}

    async def _fake_connect(_dsn: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return openstates_conn
        raise OSError("navigator unreachable")

    monkeypatch.setattr(mod.asyncpg, "connect", _fake_connect)

    with pytest.raises(OSError, match="navigator unreachable"):
        await mod.regenerate_map_aggregates(
            openstates_db_url="postgresql://localhost/os",
            navigator_db_url="postgresql://localhost/nav",
        )

    assert openstates_conn.closed is True


@pytest.mark.asyncio
async def test_regenerate_map_aggregates_inserts_rows_and_closes_both(monkeypatch):
    rows = [
        {"state": "ca", "total_bills": 60000, "sample_bills": [{"bill_number": "AB 1"}]},
        {"state": "tx", "total_bills": 25000, "sample_bills": []},
        {"state": "ny", "total_bills": 15000, "sample_bills": []},
        {"state": "wy", "total_bills": 500, "sample_bills": []},
    ]
    openstates_conn = _FakeConn(rows=rows)
    navigator_conn = _FakeConn()
    dsns: list[str] = []

    async def _fake_connect(dsn: str):
        dsns.append(dsn)
        return openstates_conn if len(dsns) == 1 else navigator_conn

    monkeypatch.setattr(mod.asyncpg, "connect", _fake_connect)

    await mod.regenerate_map_aggregates(
        openstates_db_url="postgres://os-host/os",
        navigator_db_url="postgres://nav-host/nav",
    )

    assert dsns == ["postgresql://os-host/os", "postgresql://nav-host/nav"]
    assert openstates_conn.closed is True
    assert navigator_conn.closed is True
    assert "TRUNCATE TABLE rpt_bill_map_aggregate" in navigator_conn.executed[0][0]
    inserts = navigator_conn.executed[1:]
    assert [args[0] for _sql, args in inserts] == ["CA", "TX", "NY", "WY"]
    assert [args[13] for _sql, args in inserts] == ["very_high", "high", "medium", "low"]
