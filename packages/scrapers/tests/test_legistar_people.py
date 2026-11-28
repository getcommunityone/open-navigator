"""Legistar body membership reader (#1443): parsing and polite fetching, no network (httpx.MockTransport)."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx

from scrapers.platforms.http import PoliteClient
from scrapers.platforms.legistar_people import office_records_url, parse_body, parse_office_record, read_portal

RECORD = {
    "OfficeRecordId": 1064,
    "OfficeRecordFirstName": "Robert",
    "OfficeRecordLastName": "Harrington",
    "OfficeRecordEmail": "someone@example.gov",
    "OfficeRecordFullName": "Robert Harrington",
    "OfficeRecordStartDate": "2026-07-01T00:00:00",
    "OfficeRecordEndDate": "2027-12-06T00:00:00",
    "OfficeRecordPersonId": 2734,
    "OfficeRecordBodyId": 138,
    "OfficeRecordBodyName": "City Council Business Meeting",
    "OfficeRecordTitle": "Mayor",
    "OfficeRecordMemberType": "Member",
}


def test_parse_office_record_drops_email() -> None:
    rec = parse_office_record(RECORD)
    assert rec is not None
    assert rec["full_name"] == "Robert Harrington" and rec["title"] == "Mayor"
    assert rec["start_date"] == date(2026, 7, 1) and rec["end_date"] == date(2027, 12, 6)
    assert "email" not in rec and "someone@example.gov" not in str(rec)


def test_parse_skips_rows_without_name_or_id() -> None:
    assert parse_office_record({"OfficeRecordId": 1}) is None
    assert parse_body({"BodyId": None, "BodyName": "x"}) is None
    assert parse_body({"BodyId": 138, "BodyName": "City Council", "BodyActiveFlag": 1})["active_flag"] is True


def test_office_records_url_filters_current() -> None:
    url = office_records_url("charlottenc", date(2026, 11, 28))
    assert "OfficeRecordEndDate%20ge%20datetime%272026-11-28%27" in url and "$top=1000" in url


def _client(handler) -> PoliteClient:
    return PoliteClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), min_interval_s=0, use_vpn_bypass=False)


def test_read_portal_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        assert request.headers["user-agent"].startswith("OpenNavigator")
        if request.url.path.endswith("/bodies"):
            return httpx.Response(200, json=[{"BodyId": 138, "BodyName": "City Council"}])
        return httpx.Response(200, json=[RECORD])

    async def go():
        async with _client(handler) as http:
            return await read_portal(http, "charlottenc", "charlotte_3712000", today=date(2026, 11, 28))

    res = asyncio.run(go())
    assert res.status == "ok" and len(res.bodies) == 1 and len(res.records) == 1


def test_read_portal_stops_on_block() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(429)

    async def go():
        async with _client(handler) as http:
            return await read_portal(http, "x", None)

    res = asyncio.run(go())
    assert res.status == "blocked"
    assert len([c for c in calls if c != "/robots.txt"]) == 1  # no retry


def test_read_portal_honours_robots() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        raise AssertionError("fetched a disallowed URL")

    async def go():
        async with _client(handler) as http:
            return await read_portal(http, "x", None)

    assert asyncio.run(go()).status == "robots_disallowed"
