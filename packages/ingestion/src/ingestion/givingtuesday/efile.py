"""Fetch and parse IRS Form 990 e-file XML returns from the GivingTuesday raw lake.

Every row in ``bronze.bronze_irs990_efile`` (and the downstream ``organization`` /
``grant`` marts) carries an ``object_id`` — the GivingTuesday Data Lake key for
the filing. The raw XML for any ``object_id`` is publicly readable, with no
credentials, at::

    https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{object_id}_public.xml

Wait-free alternative to bulk-downloading 600k XML files: fetch on demand when a
user opens a nonprofit's 990 in the UI, parse the IRS e-file XML into a clean
JSON document (header + Part I summary + Part VIII revenue + Part IX expenses +
Part X balance sheet + Part VII officers + Schedule I grants + a generic tree of
every schedule present), and return it.

CLI usage (for quick inspection / debugging)::

    python -m ingestion.givingtuesday.efile 201602229349300615
    python -m ingestion.givingtuesday.efile 201602229349300615 --section IRS990ScheduleI
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from loguru import logger

RAW_BUCKET_HOST = "https://gt990datalake-rawdata.s3.amazonaws.com"
XML_KEY_PREFIX = "EfileData/XmlFiles/"
_EFILE_NS = "{http://www.irs.gov/efile}"
_OBJECT_ID_RE = re.compile(r"^\d{8,32}$")
MAX_990_XML_BYTES = 25 * 1024 * 1024  # 25 MB safety ceiling per filing

# Headline financial fields, keyed by the label the viewer shows. Each value is
# an ordered list of candidate IRS e-file tag names — the return version varies
# the tag, so the first one present anywhere in the return wins.
_SUMMARY_FIELDS: dict[str, list[str]] = {
    "gross_receipts": ["GrossReceiptsAmt"],
    "total_revenue_cy": ["CYTotalRevenueAmt", "TotalRevenueAmt", "RevenueAmt"],
    "total_revenue_py": ["PYTotalRevenueAmt"],
    "total_expenses_cy": ["CYTotalExpensesAmt", "TotalExpensesAmt", "ExpenseAmt"],
    "total_expenses_py": ["PYTotalExpensesAmt"],
    "revenue_less_expenses_cy": ["CYRevenuesLessExpensesAmt"],
    "contributions_grants_cy": ["CYContributionsGrantsAmt"],
    "program_service_revenue_cy": ["CYProgramServiceRevenueAmt"],
    "investment_income_cy": ["CYInvestmentIncomeAmt"],
    "grants_paid_cy": ["CYGrantsAndSimilarPaidAmt"],
    "salaries_etc_cy": ["CYSalariesCompEmpBnftPaidAmt"],
    "total_assets_eoy": ["TotalAssetsEOYAmt"],
    "total_assets_boy": ["TotalAssetsBOYAmt"],
    "total_liabilities_eoy": ["TotalLiabilitiesEOYAmt"],
    "net_assets_eoy": ["NetAssetsOrFundBalancesEOYAmt"],
    "net_assets_boy": ["NetAssetsOrFundBalancesBOYAmt"],
    "employee_count": ["TotalEmployeeCnt", "EmployeeCnt"],
    "volunteer_count": ["TotalVolunteersCnt"],
    "voting_members": ["VotingMembersGoverningBodyCnt", "GoverningBodyVotingMembersCnt"],
    "voting_members_independent": ["VotingMembersIndependentCnt", "IndependentVotingMemberCnt"],
}


def validate_object_id(object_id: str) -> str:
    """Validate that ``object_id`` is an 8-to-32 digit numeric identifier."""
    cleaned = (object_id or "").strip()
    if not _OBJECT_ID_RE.match(cleaned):
        raise ValueError(f"Invalid 990 object_id: {object_id!r}")
    return cleaned


def xml_url_for_object(object_id: str) -> str:
    """Public S3 URL for a raw 990 return given its GT object id."""
    clean_id = validate_object_id(object_id)
    return f"{RAW_BUCKET_HOST}/{XML_KEY_PREFIX}{clean_id}_public.xml"


def _strip_ns(tag: str) -> str:
    """Drop the ``{http://www.irs.gov/efile}`` namespace from a tag."""
    return tag.split("}", 1)[-1]


def _coerce(text: str) -> Any:
    """Best-effort scalar coercion for a leaf value (keep years as strings)."""
    s = text.strip()
    if not s:
        return None
    if s in ("true", "false"):
        return s == "true"
    # Plain integers only (avoid mangling EINs/ZIPs that have leading zeros).
    if (s.lstrip("-").isdigit()) and not (len(s) > 1 and s[0] == "0"):
        try:
            return int(s)
        except ValueError:
            return s
    return s


def _elem_to_obj(elem: ET.Element) -> Any:
    """Recursively convert an element into a JSON-friendly value.

    Leaf -> coerced scalar; branch -> dict (repeated child tags become lists).
    This preserves the full return content without hard-coding every field.
    """
    children = list(elem)
    if not children:
        return _coerce(elem.text or "")
    out: dict[str, Any] = {}
    for child in children:
        key = _strip_ns(child.tag)
        val = _elem_to_obj(child)
        if key in out:
            if not isinstance(out[key], list):
                out[key] = [out[key]]
            out[key].append(val)
        else:
            out[key] = val
    return out


def _find_first_text(root: ET.Element | None, tagname: str) -> str | None:
    """First text value for ``tagname`` anywhere in the tree, else None."""
    if root is None:
        return None
    el = root.find(f".//{_EFILE_NS}{tagname}")
    if el is not None and el.text and el.text.strip():
        return el.text.strip()
    return None


def _findall(root: ET.Element, tagname: str) -> list[ET.Element]:
    return root.findall(f".//{_EFILE_NS}{tagname}")


def _address(node: ET.Element | None) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "line1": _find_first_text(node, "AddressLine1Txt"),
        "line2": _find_first_text(node, "AddressLine2Txt"),
        "city": _find_first_text(node, "CityNm"),
        "state": _find_first_text(node, "StateAbbreviationCd"),
        "zip": _find_first_text(node, "ZIPCd"),
        "country": _find_first_text(node, "CountryCd"),
    }


def _parse_header(header: ET.Element) -> dict[str, Any]:
    filer = header.find(f"{_EFILE_NS}Filer")
    officer = header.find(f"{_EFILE_NS}BusinessOfficerGrp")
    preparer = header.find(f"{_EFILE_NS}PreparerPersonGrp")
    preparer_firm = header.find(f"{_EFILE_NS}PreparerFirmGrp")
    if preparer_firm is None:
        preparer_firm = header.find(f"{_EFILE_NS}PreparerFirm")
    return {
        "return_type": _find_first_text(header, "ReturnTypeCd"),
        "tax_year": _find_first_text(header, "TaxYr"),  # wire: year stays a string
        "tax_period_begin": _find_first_text(header, "TaxPeriodBeginDt"),
        "tax_period_end": _find_first_text(header, "TaxPeriodEndDt"),
        "return_ts": _find_first_text(header, "ReturnTs"),
        "filer": {
            "ein": _find_first_text(filer, "EIN") if filer is not None else None,
            "name": _find_first_text(filer, "BusinessNameLine1Txt") if filer is not None else None,
            "phone": _find_first_text(filer, "PhoneNum") if filer is not None else None,
            "address": _address(filer.find(f"{_EFILE_NS}USAddress")) if filer is not None else None,
        },
        "officer": {
            "name": _find_first_text(officer, "PersonNm") if officer is not None else None,
            "title": _find_first_text(officer, "PersonTitleTxt") if officer is not None else None,
            "signature_date": _find_first_text(officer, "SignatureDt") if officer is not None else None,
        },
        "preparer": {
            "name": _find_first_text(preparer, "PreparerPersonNm") if preparer is not None else None,
            "firm": (
                _find_first_text(preparer_firm, "BusinessNameLine1Txt")
                or _find_first_text(header, "PreparerFirmName")
            ),
        },
    }


def _to_amount(text: str | None) -> int | None:
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except (TypeError, ValueError):
        try:
            return int(round(float(cleaned)))
        except (TypeError, ValueError, OverflowError):
            return None


def _parse_summary(root: ET.Element) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for label, candidates in _SUMMARY_FIELDS.items():
        value = None
        for tag in candidates:
            value = _find_first_text(root, tag)
            if value is not None:
                break
        summary[label] = _to_amount(value) if value is not None else None
    summary["mission"] = _find_first_text(root, "ActivityOrMissionDesc") or _find_first_text(root, "MissionDesc")
    summary["website"] = _find_first_text(root, "WebsiteAddressTxt")
    summary["state_of_domicile"] = _find_first_text(root, "LegalDomicileStateCd")
    summary["formation_year"] = _find_first_text(root, "FormationYr")
    return summary


def _parse_officers(root: ET.Element) -> list[dict[str, Any]]:
    """Form 990 Part VII Section A — officers, directors, key employees."""
    officers: list[dict[str, Any]] = []
    for grp in _findall(root, "Form990PartVIISectionAGrp"):
        # Person name is <PersonNm> in newer versions, but lands in a
        # <BusinessName><BusinessNameLine1Txt> wrapper in 2015-era returns.
        name = _find_first_text(grp, "PersonNm") or _find_first_text(grp, "BusinessNameLine1Txt")
        if not name:
            continue
        officers.append({
            "name": name,
            "title": _find_first_text(grp, "TitleTxt"),
            "avg_hours_per_week": _find_first_text(grp, "AverageHoursPerWeekRt"),
            "reportable_comp_org": _to_amount(_find_first_text(grp, "ReportableCompFromOrgAmt")),
            "reportable_comp_related": _to_amount(_find_first_text(grp, "ReportableCompFromRltdOrgAmt")),
            "other_comp": _to_amount(_find_first_text(grp, "OtherCompensationAmt")),
        })
    return officers


def _parse_grants(root: ET.Element) -> list[dict[str, Any]]:
    """Schedule I Part II — grants to domestic organizations."""
    grants: list[dict[str, Any]] = []
    for rec in _findall(root, "RecipientTable"):
        name = _find_first_text(rec, "BusinessNameLine1Txt") or _find_first_text(rec, "RecipientBusinessName")
        grants.append({
            "recipient_name": name,
            "recipient_ein": _find_first_text(rec, "RecipientEIN"),
            "irc_section": _find_first_text(rec, "IRCSectionDesc"),
            "cash_grant": _to_amount(_find_first_text(rec, "CashGrantAmt")),
            "non_cash_assistance": _find_first_text(rec, "NonCashAssistanceDesc"),
            "purpose": _find_first_text(rec, "PurposeOfGrantTxt"),
        })
    return grants


def parse_990_xml(
    xml_bytes: bytes | str,
    *,
    object_id: str | None = None,
    max_bytes: int = MAX_990_XML_BYTES,
) -> dict[str, Any]:
    """Parse a raw IRS 990 e-file return into a viewer-friendly dict.

    Returns a dict with ``object_id``, ``source_url``, ``return_version``,
    ``header``, ``summary``, ``officers``, ``grants``, ``schedules`` (list of
    schedule element names present) and ``sections`` (a generic, loss-less tree
    of every form/schedule under ``ReturnData``).

    Raises ``ValueError`` if the document is not a recognizable e-file Return,
    exceeds ``max_bytes``, or contains DTD/entity declarations.
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    if not xml_bytes:
        raise ValueError("Empty XML payload")
    if len(xml_bytes) > max_bytes:
        raise ValueError(f"XML payload size ({len(xml_bytes)} bytes) exceeds max allowed ({max_bytes} bytes)")

    head_upper = xml_bytes[:4096].upper()
    if b"<!DOCTYPE" in head_upper or b"<!ENTITY" in head_upper:
        raise ValueError("XML DTD and entity declarations are not permitted")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Not valid XML: {exc}") from exc

    if _strip_ns(root.tag) != "Return":
        raise ValueError(f"Root element is <{_strip_ns(root.tag)}>, expected <Return>")

    header = root.find(f"{_EFILE_NS}ReturnHeader")
    return_data = root.find(f"{_EFILE_NS}ReturnData")
    if header is None or return_data is None:
        raise ValueError("Return is missing ReturnHeader or ReturnData")

    schedules = [_strip_ns(child.tag) for child in return_data]
    sections = {_strip_ns(child.tag): _elem_to_obj(child) for child in return_data}

    return {
        "object_id": object_id,
        "source_url": xml_url_for_object(object_id) if object_id else None,
        "return_version": root.attrib.get("returnVersion"),
        "header": _parse_header(header),
        "summary": _parse_summary(return_data),
        "officers": _parse_officers(return_data),
        "grants": _parse_grants(return_data),
        "schedules": schedules,
        "sections": sections,
    }


async def fetch_990_xml(
    object_id: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_bytes: int = MAX_990_XML_BYTES,
) -> bytes:
    """Download the raw XML for a return id from the GT raw lake (anonymous)."""
    url = xml_url_for_object(object_id)
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        content_length = resp.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > max_bytes:
            raise ValueError(
                f"990 XML Content-Length ({content_length} bytes) exceeds maximum allowed ({max_bytes} bytes)"
            )
        content = resp.content
        if len(content) > max_bytes:
            raise ValueError(
                f"990 XML payload ({len(content)} bytes) exceeds maximum allowed ({max_bytes} bytes)"
            )
        return content
    finally:
        if owns_client:
            await client.aclose()


async def fetch_and_parse(object_id: str, *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Convenience: fetch + parse a return by object id."""
    xml = await fetch_990_xml(object_id, client=client)
    return parse_990_xml(xml, object_id=object_id)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and parse a raw IRS 990 e-file return.")
    parser.add_argument("object_id", help="GivingTuesday raw-lake object id, e.g. 201602229349300615")
    parser.add_argument("--section", help="Print only this section's generic tree (e.g. IRS990ScheduleI)")
    args = parser.parse_args()

    doc = asyncio.run(fetch_and_parse(args.object_id))
    if args.section:
        logger.info("Section {} of {}", args.section, args.object_id)
        print(json.dumps(doc["sections"].get(args.section, {}), indent=2, ensure_ascii=False))
    else:
        filer = doc["header"]["filer"]
        logger.success(
            "Parsed {} return for {} (EIN {}, TY {})",
            doc["header"]["return_type"], filer["name"], filer["ein"], doc["header"]["tax_year"],
        )
        # Drop the bulky generic tree from the headline print.
        print(json.dumps({k: v for k, v in doc.items() if k != "sections"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
