"""Unit tests for api/routes/cpi.py validation, bounded caching, and DB resolution."""
from __future__ import annotations

import asyncio
import time
import psycopg2
import pytest
from fastapi import HTTPException

from api.routes import cpi


@pytest.fixture(autouse=True)
def _reset_cpi_cache():
    cpi.clear_cpi_cache()
    yield
    cpi.clear_cpi_cache()


def test_resolve_db_url_priority_and_scheme_normalization(monkeypatch: pytest.MonkeyPatch):
    for key in cpi._DB_ENV_PRIORITY:
        monkeypatch.delenv(key, raising=False)

    assert cpi.resolve_db_url() == cpi._DEFAULT_LOCAL_DB_URL

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    assert cpi.resolve_db_url() == "postgresql://user:pass@host:5432/db"

    monkeypatch.setenv("OPEN_NAVIGATOR_DATABASE_URL", "postgresql://nav:pass@host:5432/nav")
    assert cpi.resolve_db_url() == "postgresql://nav:pass@host:5432/nav"

    monkeypatch.setenv("NEON_DATABASE_URL", "postgres://neon:pass@neon:5432/neon")
    assert cpi.resolve_db_url() == "postgresql://neon:pass@neon:5432/neon"

    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://dev:pass@localhost:5433/dev")
    assert cpi.resolve_db_url() == "postgresql://dev:pass@localhost:5433/dev"


@pytest.mark.asyncio
async def test_cpi_annual_rejects_invalid_series_id():
    for bad in ("", "A", "BAD SERIES!", "DROP TABLE cpi_annual;", "../etc/passwd"):
        with pytest.raises(HTTPException) as exc:
            await cpi.cpi_annual(series_id=bad)
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_cpi_annual_concurrent_deduplication_and_case_normalization(
    monkeypatch: pytest.MonkeyPatch,
):
    fetch_calls = 0

    def fake_fetch(series_id: str):
        nonlocal fetch_calls
        fetch_calls += 1
        time.sleep(0.02)
        assert series_id == "CUUR0000SA0"
        return [
            (2023, 304.702, True),
            (2024, 313.689, True),
            (2025, 320.100, False),
        ]

    monkeypatch.setattr(cpi, "_fetch_cpi_series_sync", fake_fetch)

    results = await asyncio.gather(
        cpi.cpi_annual("cuur0000sa0"),
        cpi.cpi_annual("CUUR0000SA0"),
        cpi.cpi_annual("Cuur0000Sa0"),
    )

    assert fetch_calls == 1
    for res in results:
        assert res["series_id"] == "CUUR0000SA0"
        assert res["latest_year"] == 2025
        assert res["by_year"] == {"2023": 304.702, "2024": 313.689, "2025": 320.1}
        assert res["from_official_annual"] == {"2023": True, "2024": True, "2025": False}
    assert "CUUR0000SA0" not in cpi._inflight_locks


@pytest.mark.asyncio
async def test_cpi_annual_does_not_cache_empty_results_and_bounds_cache(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cpi, "_MAX_CACHE_ENTRIES", 2)

    def fake_fetch(series_id: str):
        if series_id == "EMPTY001":
            return []
        return [(2024, 313.689, True)]

    monkeypatch.setattr(cpi, "_fetch_cpi_series_sync", fake_fetch)

    empty_res = await cpi.cpi_annual("EMPTY001")
    assert empty_res["latest_year"] is None
    assert empty_res["by_year"] == {}
    assert "EMPTY001" not in cpi._CACHE

    await cpi.cpi_annual("SER00001")
    await cpi.cpi_annual("SER00002")
    await cpi.cpi_annual("SER00003")

    assert len(cpi._CACHE) == 2
    assert "SER00001" not in cpi._CACHE
    assert "SER00002" in cpi._CACHE
    assert "SER00003" in cpi._CACHE


@pytest.mark.asyncio
async def test_cpi_annual_hides_internal_db_error_details(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_fail(series_id: str):
        raise psycopg2.OperationalError("password authentication failed for user postgres")

    monkeypatch.setattr(cpi, "_fetch_cpi_series_sync", fake_fail)

    with pytest.raises(HTTPException) as exc:
        await cpi.cpi_annual("CUUR0000SA0")
    assert exc.value.status_code == 500
    assert exc.value.detail == "CPI query failed"
    assert "password" not in str(exc.value.detail)
