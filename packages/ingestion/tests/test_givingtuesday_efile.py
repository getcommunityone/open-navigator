"""Unit tests for the IRS 990 e-file XML parser (ingestion.givingtuesday.efile).

Pure / network-free: parses a compact synthetic Return that mirrors the real
GivingTuesday raw-lake structure, including the 2015-era quirk where an
officer's name lands in a <BusinessName> wrapper rather than <PersonNm>.
"""
from __future__ import annotations

import httpx
import pytest

from ingestion.givingtuesday.efile import (
    _to_amount,
    fetch_990_xml,
    parse_990_xml,
    xml_url_for_object,
)

# Minimal but representative 990 return. Namespaced like the real filings.
_SAMPLE_990 = """<?xml version="1.0" encoding="utf-8"?>
<Return xmlns="http://www.irs.gov/efile" returnVersion="2015v2.1">
  <ReturnHeader>
    <ReturnTypeCd>990</ReturnTypeCd>
    <TaxYr>2015</TaxYr>
    <TaxPeriodBeginDt>2015-01-01</TaxPeriodBeginDt>
    <TaxPeriodEndDt>2015-12-31</TaxPeriodEndDt>
    <Filer>
      <EIN>396094742</EIN>
      <BusinessName><BusinessNameLine1Txt>Test Org Inc</BusinessNameLine1Txt></BusinessName>
      <PhoneNum>7153446087</PhoneNum>
      <USAddress>
        <AddressLine1Txt>1 Main St</AddressLine1Txt>
        <CityNm>Stevens Point</CityNm>
        <StateAbbreviationCd>WI</StateAbbreviationCd>
        <ZIPCd>54481</ZIPCd>
      </USAddress>
    </Filer>
    <BusinessOfficerGrp>
      <PersonNm>Jane Treasurer</PersonNm>
      <PersonTitleTxt>CFO</PersonTitleTxt>
    </BusinessOfficerGrp>
  </ReturnHeader>
  <ReturnData documentCnt="2">
    <IRS990>
      <GrossReceiptsAmt>681352380</GrossReceiptsAmt>
      <WebsiteAddressTxt>www.example.org</WebsiteAddressTxt>
      <ActivityOrMissionDesc>Improve oral health.</ActivityOrMissionDesc>
      <TotalEmployeeCnt>290</TotalEmployeeCnt>
      <CYTotalRevenueAmt>634789057</CYTotalRevenueAmt>
      <CYTotalExpensesAmt>629266162</CYTotalExpensesAmt>
      <NetAssetsOrFundBalancesEOYAmt>162760326</NetAssetsOrFundBalancesEOYAmt>
      <Form990PartVIISectionAGrp>
        <BusinessName><BusinessNameLine1Txt>Dennis Brown</BusinessNameLine1Txt></BusinessName>
        <TitleTxt>President &amp; CEO</TitleTxt>
        <AverageHoursPerWeekRt>45.0</AverageHoursPerWeekRt>
        <ReportableCompFromOrgAmt>1060657</ReportableCompFromOrgAmt>
        <ReportableCompFromRltdOrgAmt>0</ReportableCompFromRltdOrgAmt>
        <OtherCompensationAmt>51478</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
    </IRS990>
    <IRS990ScheduleI>
      <RecipientTable>
        <RecipientBusinessName>
          <BusinessNameLine1Txt>University of Manitoba</BusinessNameLine1Txt>
        </RecipientBusinessName>
        <RecipientEIN>986008078</RecipientEIN>
        <IRCSectionDesc>501(C)(3)</IRCSectionDesc>
        <CashGrantAmt>14490</CashGrantAmt>
        <PurposeOfGrantTxt>Dental caries research</PurposeOfGrantTxt>
      </RecipientTable>
    </IRS990ScheduleI>
  </ReturnData>
</Return>
"""


@pytest.fixture()
def doc() -> dict:
    return parse_990_xml(_SAMPLE_990, object_id="201602229349300615")


def test_url_builder():
    assert xml_url_for_object("201602229349300615") == (
        "https://gt990datalake-rawdata.s3.amazonaws.com/"
        "EfileData/XmlFiles/201602229349300615_public.xml"
    )


def test_url_builder_rejects_invalid_object_id():
    with pytest.raises(ValueError, match="Invalid 990 object_id"):
        xml_url_for_object("../../etc/passwd")
    with pytest.raises(ValueError, match="Invalid 990 object_id"):
        xml_url_for_object("12345")


def test_header_and_filer(doc):
    h = doc["header"]
    assert h["return_type"] == "990"
    # Wire rule: a bare calendar year is serialized as a string, not an int.
    assert h["tax_year"] == "2015"
    assert isinstance(h["tax_year"], str)
    assert h["filer"]["name"] == "Test Org Inc"
    # EIN must stay a string (no int coercion that could drop leading zeros).
    assert h["filer"]["ein"] == "396094742"
    assert h["filer"]["address"]["state"] == "WI"
    assert h["officer"]["name"] == "Jane Treasurer"
    # When <PreparerFirmGrp> is absent, preparer.firm must be None, not the Filer's name.
    assert h["preparer"]["firm"] is None


def test_summary_amounts_are_numeric(doc):
    s = doc["summary"]
    assert s["total_revenue_cy"] == 634789057
    assert s["total_expenses_cy"] == 629266162
    assert s["net_assets_eoy"] == 162760326
    assert s["gross_receipts"] == 681352380
    assert s["employee_count"] == 290
    assert s["mission"] == "Improve oral health."
    assert s["website"] == "www.example.org"


def test_officer_name_from_businessname_wrapper(doc):
    # The 2015-era quirk: person name is under <BusinessName>, not <PersonNm>.
    officers = doc["officers"]
    assert len(officers) == 1
    o = officers[0]
    assert o["name"] == "Dennis Brown"
    assert o["title"] == "President & CEO"
    assert o["reportable_comp_org"] == 1060657
    assert o["other_comp"] == 51478


def test_grants_schedule_i(doc):
    grants = doc["grants"]
    assert len(grants) == 1
    g = grants[0]
    assert g["recipient_name"] == "University of Manitoba"
    assert g["recipient_ein"] == "986008078"
    assert g["cash_grant"] == 14490
    assert g["purpose"] == "Dental caries research"


def test_schedules_and_generic_sections(doc):
    assert doc["return_version"] == "2015v2.1"
    assert doc["schedules"] == ["IRS990", "IRS990ScheduleI"]
    # The generic tree is loss-less: every form is present and reaches leaves.
    assert "IRS990" in doc["sections"]
    assert doc["sections"]["IRS990"]["GrossReceiptsAmt"] == 681352380


def test_rejects_non_return_xml():
    with pytest.raises(ValueError):
        parse_990_xml("<NotAReturn/>")


def test_rejects_dtd_and_oversized_xml():
    dtd_xml = """<?xml version="1.0"?>
    <!DOCTYPE Return [<!ENTITY lol "lol">]>
    <Return xmlns="http://www.irs.gov/efile"></Return>
    """
    with pytest.raises(ValueError, match="DTD and entity declarations"):
        parse_990_xml(dtd_xml)

    with pytest.raises(ValueError, match="exceeds max allowed"):
        parse_990_xml(_SAMPLE_990, max_bytes=128)


@pytest.mark.asyncio
async def test_fetch_990_xml_enforces_max_bytes():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=_SAMPLE_990.encode("utf-8"),
            headers={"Content-Length": str(len(_SAMPLE_990))},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            await fetch_990_xml("201602229349300615", client=client, max_bytes=100)
        data = await fetch_990_xml("201602229349300615", client=client, max_bytes=100_000)
        assert b"<Return" in data


@pytest.mark.asyncio
async def test_fetch_990_xml_stops_streaming_once_limit_passed():
    """With no Content-Length, the download is aborted as soon as it passes max_bytes."""
    chunk = b"x" * 1024
    total_chunks = 1000  # ~1 MB on offer
    yielded = {"n": 0}

    async def body():
        for _ in range(total_chunks):
            yielded["n"] += 1
            yield chunk

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body()))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            await fetch_990_xml("201602229349300615", client=client, max_bytes=10 * 1024)
    # Stopped just past the 10 KB limit, never read the whole ~1 MB body.
    assert yielded["n"] <= 11


@pytest.mark.asyncio
async def test_fetch_990_xml_rejects_on_content_length_before_reading():
    read = {"started": False}

    async def body():
        read["started"] = True
        yield b"<Return/>"

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=body(), headers={"Content-Length": "999999"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="Content-Length"):
            await fetch_990_xml("201602229349300615", client=client, max_bytes=100)
    assert read["started"] is False


def test_to_amount_rounds_decimal_strings():
    assert (_to_amount("1234"), _to_amount("1234.56"), _to_amount(" "), _to_amount("n/a")) == (1234, 1235, None, None)


def test_preparer_firm_read_from_preparer_firm_grp():
    xml = _SAMPLE_990.replace(
        "</BusinessOfficerGrp>",
        "</BusinessOfficerGrp><PreparerFirmGrp><PreparerFirmName>"
        "<BusinessNameLine1Txt>Audit Partners LLP</BusinessNameLine1Txt>"
        "</PreparerFirmName></PreparerFirmGrp>",
    )
    assert parse_990_xml(xml)["header"]["preparer"]["firm"] == "Audit Partners LLP"
