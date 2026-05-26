"""API route for batch job dashboard (Data explorer)."""

from __future__ import annotations

import asyncio

import httpx


def test_list_batch_jobs_endpoint():
    from api.main import app

    async def _run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get(
                "/api/batch-jobs",
                params={"refresh_files": "false"},
            )

    response = asyncio.run(_run())
    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    assert "totals" in body
    assert "batches" in body
    assert isinstance(body["batches"], list)
    assert body.get("source") in ("database", "files", None)


def test_batch_jobs_stream_route_exists():
    from api.main import app

    paths = {
        getattr(r, "path", None) or getattr(r, "path_format", None) for r in app.routes
    }
    assert "/api/batch-jobs/stream" in paths
