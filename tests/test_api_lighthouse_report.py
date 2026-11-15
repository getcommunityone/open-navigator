"""GET /api/lighthouse/report with a stored Lighthouse audit (#304).

The endpoint answered 500 whenever an audit row existed: `_lhr_from_row` raised NameError before it could read the
stored report. The database pool is stubbed, so these tests need no database.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx

from api.main import app
from api.routes import lighthouse_reports as lr

LHR = {
    "requestedUrl": "https://example.gov/",
    "runWarnings": ["The page loaded too slowly to finish within the time limit."],
    "categories": {
        "performance": {"score": 0.91},
        "accessibility": {"score": 0.88},
        "best-practices": {"score": 0.75},
        "seo": {"score": 1.0},
    },
}


def _row(results, **columns):
    row = {
        "scan_key": "scan-1",
        "batch_id": "batch-1",
        "jurisdiction_id": "jur-1",
        "website_url": "https://example.gov/",
        "final_url": "https://example.gov/",
        "scanned_at": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        "status": "ok",
        "lighthouse_version": "12.0.0",
        "score_accessibility": None,
        "score_performance": None,
        "score_best_practices": None,
        "results": results,
    }
    row.update(columns)
    return row


class _Conn:
    def __init__(self, row):
        self.row = row

    async def fetchrow(self, sql, *params):
        return self.row


class _Acquire:
    def __init__(self, row):
        self.row = row

    async def __aenter__(self):
        return _Conn(self.row)

    async def __aexit__(self, *exc):
        return False


class _Pool:
    def __init__(self, row):
        self.row = row

    def acquire(self):
        return _Acquire(self.row)


def _get(row):
    async def go():
        with patch.object(lr, "get_db_pool", new=AsyncMock(return_value=_Pool(row))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/api/lighthouse/report", params={"website_url": "https://example.gov"})

    return asyncio.run(go())


def test_the_stored_report_is_read_from_a_dict_or_from_json_text():
    assert lr._lhr_from_row({"lhr": LHR}) == LHR
    assert lr._lhr_from_row(json.dumps({"lhr": LHR})) == LHR
    assert lr._lhr_from_row({"no_report": True}) is None
    assert lr._lhr_from_row(None) is None


def test_a_stored_audit_comes_back_with_its_scores_instead_of_a_server_error():
    resp = _get(_row({"lhr": LHR}))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scores"] == {"performance": 91, "accessibility": 88, "best_practices": 75, "seo": 100}
    assert body["requested_url"] == "https://example.gov/"
    assert body["run_warnings"] == LHR["runWarnings"]
    assert body["scanned_at"] == "2026-11-01T12:00:00+00:00"


def test_a_score_stored_in_its_own_column_wins_over_the_report():
    resp = _get(_row({"lhr": LHR}, score_performance=50))
    assert resp.status_code == 200, resp.text
    assert resp.json()["scores"]["performance"] == 50


def test_no_audit_is_still_a_404():
    resp = _get(None)
    assert resp.status_code == 404
