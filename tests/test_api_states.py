"""Tests for GET /states and GET /api/states endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.main import app
from config import settings


def _run_async(coro):
    return asyncio.run(coro)


def test_states_routes_registered_in_openapi():
    """Verify both /states and /api/states routes are registered in OpenAPI schema."""
    paths = set(app.openapi().get("paths", {}).keys())
    assert "/states" in paths
    assert "/api/states" in paths


def test_get_states_offline_without_target_states_is_empty(monkeypatch):
    """When DB pool is None and target_states is unset, returns an empty list (no invented states)."""
    monkeypatch.setattr(settings, "target_states", None)

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = None
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/states")
                assert resp.status_code == 200
                data = resp.json()
                assert data == {"states": [], "count": 0}

                # Test /api/states alias
                api_resp = await client.get("/api/states")
                assert api_resp.status_code == 200
                assert api_resp.json() == data

    _run_async(_test())


def test_get_states_configured_target_states(monkeypatch):
    """When settings.target_states is configured, returns those uppercased and sorted."""
    monkeypatch.setattr(settings, "target_states", ["in", "al", "wi", "al"])

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = None
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/states")
                assert resp.status_code == 200
                data = resp.json()
                assert data["states"] == ["AL", "IN", "WI"]
                assert data["count"] == 3

    _run_async(_test())


def test_get_states_from_database():
    """When DB is active, returns distinct uppercase state codes from bills."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {"state_code": "wa"},
        {"state_code": "ga"},
        {"state_code": "in"},
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/states")
                assert resp.status_code == 200
                data = resp.json()
                assert data["states"] == ["GA", "IN", "WA"]
                assert data["count"] == 3

    _run_async(_test())


def test_get_states_db_error_without_target_states_is_empty(monkeypatch):
    """When the DB query raises and target_states is unset, returns [] rather than invented states."""
    monkeypatch.setattr(settings, "target_states", None)
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = RuntimeError("Postgres connection timeout")

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/states")
                assert resp.status_code == 200
                assert resp.json() == {"states": [], "count": 0}

    _run_async(_test())


def test_get_states_db_error_uses_configured_target_states(monkeypatch):
    """When the DB query raises, configured target_states (real configuration) are returned."""
    monkeypatch.setattr(settings, "target_states", ["wi", "al"])
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = RuntimeError("Postgres connection timeout")

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/states")
                assert resp.status_code == 200
                assert resp.json() == {"states": ["AL", "WI"], "count": 2}

    _run_async(_test())


def test_get_states_empty_db_result_without_target_states_is_empty(monkeypatch):
    """When the query returns no rows and target_states is unset, returns []."""
    monkeypatch.setattr(settings, "target_states", None)
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    async def _test():
        with patch("api.routes.bills_neon.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/states")
                assert resp.json() == {"states": [], "count": 0}

    _run_async(_test())
