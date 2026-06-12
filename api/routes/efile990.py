"""IRS 990 e-file viewer endpoint.

Fetches a single raw 990 return from the GivingTuesday raw Data Lake
(``gt990datalake-rawdata``) by its object id, parses the namespaced IRS e-file
XML into a viewer-friendly structure, and serves it as JSON. The heavy lifting
(fetch + parse) lives in the library module
``ingestion.givingtuesday.efile`` — this route is a thin serving wrapper with a
small in-process TTL cache and a raw-XML passthrough.

Final paths (router prefix ``/efile990`` + app prefix ``/api``):
    GET /api/efile990/{object_id}        -> parsed return JSON
    GET /api/efile990/{object_id}/raw    -> the raw XML (text/xml)
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response
from opentelemetry import trace
from pydantic import BaseModel

from ingestion.givingtuesday.efile import (
    fetch_990_xml,
    parse_990_xml,
    xml_url_for_object,
)

router = APIRouter(prefix="/efile990", tags=["efile990"])
tracer = trace.get_tracer(__name__)

# object ids in the raw lake are numeric (e.g. 201602229349300615).
_OBJECT_ID_PATTERN = r"^\d{8,32}$"

# Tiny TTL cache so re-opening a filing doesn't re-hit S3 each time.
_CACHE_TTL_S = 3600.0
_xml_cache: dict[str, tuple[float, bytes]] = {}


class Address(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class Filer(BaseModel):
    ein: str | None = None
    name: str | None = None
    phone: str | None = None
    address: Address | None = None


class Officer(BaseModel):
    name: str | None = None
    title: str | None = None


class ReturnHeader(BaseModel):
    return_type: str | None = None
    tax_year: str | None = None  # wire rule: a bare year is serialized as a string
    tax_period_begin: str | None = None
    tax_period_end: str | None = None
    return_ts: str | None = None
    filer: Filer
    officer: Officer
    preparer: dict[str, Any]


class OfficerComp(BaseModel):
    name: str | None = None
    title: str | None = None
    avg_hours_per_week: str | None = None
    reportable_comp_org: int | None = None
    reportable_comp_related: int | None = None
    other_comp: int | None = None


class Grant(BaseModel):
    recipient_name: str | None = None
    recipient_ein: str | None = None
    irc_section: str | None = None
    cash_grant: int | None = None
    non_cash_assistance: str | None = None
    purpose: str | None = None


class Efile990(BaseModel):
    object_id: str | None = None
    source_url: str | None = None
    return_version: str | None = None
    header: ReturnHeader
    summary: dict[str, Any]
    officers: list[OfficerComp]
    grants: list[Grant]
    schedules: list[str]
    sections: dict[str, Any]


async def _get_xml(object_id: str) -> bytes:
    """Fetch the raw XML (TTL-cached), translating S3/network errors to HTTP."""
    now = time.monotonic()
    cached = _xml_cache.get(object_id)
    if cached and now - cached[0] < _CACHE_TTL_S:
        return cached[1]
    try:
        xml = await fetch_990_xml(object_id)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (403, 404):
            raise HTTPException(
                status_code=404,
                detail=f"No 990 return found for object id {object_id}",
            ) from exc
        raise HTTPException(status_code=502, detail=f"Upstream S3 error ({status})") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach the 990 data lake: {exc}") from exc
    _xml_cache[object_id] = (now, xml)
    return xml


@router.get("/{object_id}", response_model=Efile990)
async def get_efile_990(
    object_id: str = Path(..., pattern=_OBJECT_ID_PATTERN, description="GivingTuesday raw-lake object id"),
) -> Efile990:
    """Parse and return a single IRS 990 e-file return."""
    with tracer.start_as_current_span("efile990.get") as span:
        span.set_attribute("object_id", object_id)
        xml = await _get_xml(object_id)
        try:
            doc = parse_990_xml(xml, object_id=object_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse return: {exc}") from exc
        span.set_attribute("return_type", doc["header"].get("return_type") or "")
        span.set_attribute("schedule_count", len(doc["schedules"]))
        return Efile990(**doc)


@router.get("/{object_id}/raw")
async def get_efile_990_raw(
    object_id: str = Path(..., pattern=_OBJECT_ID_PATTERN),
) -> Response:
    """Return the raw IRS e-file XML for the given object id."""
    xml = await _get_xml(object_id)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"X-Source-Url": xml_url_for_object(object_id)},
    )
