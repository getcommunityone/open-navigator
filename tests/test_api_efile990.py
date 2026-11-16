"""Unit tests for api/routes/efile990.py bounded caching, concurrency deduplication, and error handling."""
from __future__ import annotations

import asyncio
import httpx
import pytest
from fastapi import HTTPException

from api.routes import efile990

_SAMPLE_990_BYTES = b"""<?xml version="1.0" encoding="utf-8"?>
<Return xmlns="http://www.irs.gov/efile" returnVersion="2015v2.1">
  <ReturnHeader>
    <ReturnTypeCd>990</ReturnTypeCd>
    <TaxYr>2015</TaxYr>
    <Filer>
      <EIN>396094742</EIN>
      <BusinessName><BusinessNameLine1Txt>Test Org Inc</BusinessNameLine1Txt></BusinessName>
    </Filer>
    <BusinessOfficerGrp>
      <PersonNm>Jane Treasurer</PersonNm>
      <PersonTitleTxt>CFO</PersonTitleTxt>
    </BusinessOfficerGrp>
  </ReturnHeader>
  <ReturnData documentCnt="1">
    <IRS990>
      <CYTotalRevenueAmt>634789057</CYTotalRevenueAmt>
    </IRS990>
  </ReturnData>
</Return>
"""


@pytest.fixture(autouse=True)
def _clear_cache():
    efile990.clear_efile990_cache()
    yield
    efile990.clear_efile990_cache()


@pytest.mark.asyncio
async def test_concurrent_json_and_raw_requests_deduplicate_s3_fetch(
    monkeypatch: pytest.MonkeyPatch,
):
    fetch_calls = 0

    async def fake_fetch(object_id: str) -> bytes:
        nonlocal fetch_calls
        fetch_calls += 1
        await asyncio.sleep(0.02)
        return _SAMPLE_990_BYTES

    monkeypatch.setattr(efile990, "fetch_990_xml", fake_fetch)

    oid = "201602229349300615"
    parsed_res, raw_res, parsed_res_2 = await asyncio.gather(
        efile990.get_efile_990(oid),
        efile990.get_efile_990_raw(oid),
        efile990.get_efile_990(oid),
    )

    assert fetch_calls == 1
    assert parsed_res.object_id == oid
    assert parsed_res.header.filer.name == "Test Org Inc"
    assert raw_res.body == _SAMPLE_990_BYTES
    assert parsed_res_2.summary["total_revenue_cy"] == 634789057
    assert oid not in efile990._inflight_locks


@pytest.mark.asyncio
async def test_get_efile_990_serves_parsed_cache_without_reparsing(
    monkeypatch: pytest.MonkeyPatch,
):
    parse_calls = 0
    real_parse = efile990.parse_990_xml

    async def fake_fetch(object_id: str) -> bytes:
        return _SAMPLE_990_BYTES

    def counting_parse(xml_bytes: bytes, *, object_id: str | None = None):
        nonlocal parse_calls
        parse_calls += 1
        return real_parse(xml_bytes, object_id=object_id)

    monkeypatch.setattr(efile990, "fetch_990_xml", fake_fetch)
    monkeypatch.setattr(efile990, "parse_990_xml", counting_parse)

    oid = "201602229349300615"
    first = await efile990.get_efile_990(oid)
    second = await efile990.get_efile_990(oid)

    assert parse_calls == 1
    assert first.object_id == second.object_id


@pytest.mark.asyncio
async def test_bounded_xml_cache_evicts_by_count_and_byte_budget(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(efile990, "_MAX_CACHE_ENTRIES", 2)

    async def fake_fetch(object_id: str) -> bytes:
        return _SAMPLE_990_BYTES

    monkeypatch.setattr(efile990, "fetch_990_xml", fake_fetch)

    await efile990.get_efile_990("1000000001")
    await efile990.get_efile_990("1000000002")
    await efile990.get_efile_990("1000000003")

    assert len(efile990._xml_cache) == 2
    assert "1000000001" not in efile990._xml_cache
    assert "1000000001" not in efile990._parsed_cache
    assert "1000000002" in efile990._xml_cache
    assert "1000000003" in efile990._xml_cache


@pytest.mark.asyncio
async def test_s3_errors_and_oversized_payload_translation(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_404(object_id: str) -> bytes:
        req = httpx.Request("GET", "https://example.com")
        resp = httpx.Response(404, request=req)
        raise httpx.HTTPStatusError("Not Found", request=req, response=resp)

    monkeypatch.setattr(efile990, "fetch_990_xml", fake_404)
    with pytest.raises(HTTPException) as exc_404:
        await efile990.get_efile_990("201602229349300615")
    assert exc_404.value.status_code == 404

    async def fake_oversized(object_id: str) -> bytes:
        raise ValueError("990 XML payload exceeds maximum allowed")

    monkeypatch.setattr(efile990, "fetch_990_xml", fake_oversized)
    with pytest.raises(HTTPException) as exc_413:
        await efile990.get_efile_990("201602229349300615")
    assert exc_413.value.status_code == 413
