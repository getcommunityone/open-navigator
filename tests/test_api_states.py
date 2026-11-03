"""Tests for GET /states and GET /api/states endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.main import FALLBACK_OPPORTUNITY_STATES, app
from config import settings


def _run_async(coro):
    return asyncio.run(coro)


def test_states_routes_registered_in_openapi():
    """Verify both /states and /api/states routes are registered in OpenAPI schema."""
    paths = set(app.openapi().get("paths", {}).keys())
    assert "/states" in paths
    assert "/api/states" in paths


def test_get_states_offline_fallback():
    """When DB pool is None, returns sorted fallback opportunity states."""
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
                assert "states" in data
                assert "count" in data
                assert data["states"] == sorted(FALLBACK_OPPORTUNITY_STATES)
                assert data["count"] == len(FALLBACK_OPPORTUNITY_STATES)

                # Test /api/states alias
                api_resp = await client.get("/api/states")
                assert api_resp.status_code == 200
                api_data = api_resp.json()
                assert api_data == data

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


def test_get_states_db_error_falls_back():
    """When DB query raises an exception, logs warning and falls back gracefully."""
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
                data = resp.json()
                assert "states" in data
                assert data["count"] == len(data["states"])

    _run_async(_test())
