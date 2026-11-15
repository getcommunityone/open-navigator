"""ingestion.census.property_tax parses the ACS response into bronze rows (#137).

Uses an httpx mock transport, so no network call is made.
"""

from __future__ import annotations

import asyncio

import httpx
from ingestion.census import property_tax as pt


def _client(payload: list[list[str]], seen: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_requests_and_parses_median_household_income() -> None:
    payload = [
        ["NAME", pt.TAXES_VAR, pt.VALUE_VAR, pt.INCOME_VAR, "state", "place"],
        ["Testville city, Alabama", "900", "180000", "52000", "01", "12345"],
        ["Suppressed CDP, Alabama", "-666666666", "120000", "-666666666", "01", "54321"],
    ]
    seen: dict = {}

    async def run() -> list[dict]:
        async with _client(payload, seen) as client:
            return await pt._fetch(client, 2023, "place", "01", None)

    rows = asyncio.run(run())

    assert seen["params"]["get"] == f"NAME,{pt.TAXES_VAR},{pt.VALUE_VAR},{pt.INCOME_VAR}"
    assert pt.INCOME_VAR == "B19013_001E"
    assert rows[0]["geoid"] == "0112345"
    assert rows[0]["median_household_income"] == 52000
    assert rows[0]["median_home_value"] == 180000
    # ACS suppression sentinels become NULL, never a number.
    assert rows[1]["median_household_income"] is None
    assert rows[1]["median_real_estate_taxes_paid"] is None


def test_upsert_writes_the_income_column() -> None:
    sql = str(pt._UPSERT_SQL)
    assert ":median_household_income" in sql
    assert "median_household_income       = EXCLUDED.median_household_income" in sql
    assert "ADD COLUMN IF NOT EXISTS median_household_income" in str(pt._ADD_INCOME_COLUMN_SQL)
