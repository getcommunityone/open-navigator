"""
CivicClerk public portal OData API (no browser calendar navigation required).

Northport embeds ``clerkEmbedProps = { tenant: "northportal" }`` on
https://www.northportal.gov/129/Agendas-Minutes ; events and agenda PDFs are available at
``https://{tenant}.api.civicclerk.com/v1/Events`` with file blobs via ``Meetings/GetMeetingFile``.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

_CLERK_EMBED_TENANT_RE = re.compile(
    r"""clerkEmbedProps\s*=\s*\{[^}]*["']tenant["']\s*:\s*["']([^"']+)["']""",
    re.I | re.S,
)
_PORTAL_HOST_RE = re.compile(r"^([a-z0-9-]+)\.portal\.civicclerk\.com$", re.I)


def civicclerk_api_base(tenant: str) -> str:
    t = (tenant or "").strip().lower().replace(".portal.civicclerk.com", "")
    if not t:
        raise ValueError("CivicClerk tenant slug is required")
    return f"https://{t}.api.civicclerk.com/v1"


def civicclerk_portal_event_url(tenant: str, event_id: int) -> str:
    t = (tenant or "").strip().lower()
    return f"https://{t}.portal.civicclerk.com/event/{int(event_id)}"


def detect_civicclerk_tenant(
    *,
    homepage_url: str = "",
    html: str = "",
    extra_urls: Optional[List[str]] = None,
) -> Optional[str]:
    """Infer tenant slug from embed script, portal links, or ``{slug}.api.civicclerk.com``."""
    for blob in [html or ""] + list(extra_urls or []):
        m = _CLERK_EMBED_TENANT_RE.search(blob)
        if m:
            return m.group(1).strip().lower()
    for raw in list(extra_urls or []) + ([homepage_url] if homepage_url else []):
        try:
            host = (urlparse(raw).netloc or "").lower()
        except Exception:
            continue
        pm = _PORTAL_HOST_RE.match(host.split(":")[0])
        if pm:
            return pm.group(1).lower()
        if host.endswith(".api.civicclerk.com"):
            return host.split(".")[0].lower()
    try:
        host = (urlparse(homepage_url).netloc or "").lower().split(":")[0]
    except Exception:
        host = ""
    # northportal.gov -> northportal (CivicPlus site slug often matches Clerk tenant)
    if host and "." in host:
        label = host.split(".")[0]
        if label and label not in ("www", "cityof"):
            return label
    return None


def civicclerk_doc_type(file_type: str, file_name: str = "") -> str:
    ft = (file_type or "").strip().lower()
    name = (file_name or "").strip().lower()
    if "minute" in ft or "minute" in name:
        return "minutes"
    if "agenda packet" in ft or ("agenda" in ft and "packet" in ft):
        return "agenda_packet"
    if "agenda" in ft or "agenda" in name:
        return "agenda"
    if "packet" in ft or "packet" in name:
        return "agenda_packet"
    if "notice" in ft:
        return "packet"
    return "unknown"


def civicclerk_portal_file_url(tenant: str, event_id: int, pf: Dict[str, Any]) -> str:
    """
    Public portal deep link (e.g. ``…/event/3545/files/agenda/3290``) for a published file row.
    """
    t = (tenant or "").strip().lower()
    eid = int(event_id)
    fid = int(pf.get("fileId") or 0)
    if not t or not eid:
        return ""
    if not fid:
        return civicclerk_portal_event_url(t, eid)
    return f"https://{t}.portal.civicclerk.com/event/{eid}/files/agenda/{fid}"


def event_needs_civicclerk_detail(event: Dict[str, Any]) -> bool:
    """True when the event may have downloadable agenda/minutes (flags or embedded ``publishedFiles``)."""
    if event.get("hasAgenda") or event.get("hasMedia") or int(event.get("agendaId") or 0) > 0:
        return True
    return bool(published_files_from_event(event))


def _years_window() -> Tuple[int, int]:
    now = datetime.now(timezone.utc).year
    back = int((os.getenv("SCRAPED_MEETINGS_CIVICCLERK_YEARS_BACK") or "12").strip() or "12")
    ahead = int((os.getenv("SCRAPED_MEETINGS_CIVICCLERK_YEARS_AHEAD") or "3").strip() or "3")
    return now - max(1, back), now + max(0, ahead)


def iter_events_for_year(
    client: httpx.Client,
    tenant: str,
    calendar_year: int,
    *,
    page_size: int = 100,
) -> Iterator[Dict[str, Any]]:
    """Yield event summaries for one calendar year (OData ``year(startDateTime)`` filter)."""
    base = civicclerk_api_base(tenant)
    skip = 0
    while True:
        filt = f"year(startDateTime) eq {int(calendar_year)}"
        url = (
            f"{base}/Events?$filter={quote(filt)}"
            f"&$orderby=startDateTime desc&$top={int(page_size)}&$skip={int(skip)}"
        )
        resp = client.get(url, timeout=120.0)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("value") if isinstance(data, dict) else None
        if not isinstance(batch, list) or not batch:
            break
        for row in batch:
            if isinstance(row, dict):
                yield row
        if len(batch) < page_size:
            break
        skip += page_size


def fetch_event_detail(client: httpx.Client, tenant: str, event_id: int) -> Dict[str, Any]:
    base = civicclerk_api_base(tenant)
    resp = client.get(f"{base}/Events/{int(event_id)}", timeout=120.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


async def resolve_meeting_file_download_url(
    client: httpx.AsyncClient,
    api_file_url: str,
) -> Tuple[Optional[str], str]:
    """
    ``GetMeetingFile`` returns JSON ``{ "blobUri": "https://...pdf?..." }``.
    """
    raw = (api_file_url or "").strip()
    if not raw:
        return None, "empty_url"
    try:
        resp = await client.get(raw, timeout=120.0)
        if resp.status_code != 200:
            return None, f"get_meeting_file_http_{resp.status_code}"
        payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return None, f"get_meeting_file:{exc!r}"
    if not isinstance(payload, dict):
        return None, "get_meeting_file_not_object"
    blob = str(payload.get("blobUri") or "").strip()
    if not blob:
        return None, "no_blob_uri"
    return blob, ""


async def download_meeting_file_bytes(
    client: httpx.AsyncClient,
    api_file_url: str,
) -> Tuple[Optional[bytes], str]:
    blob_url, why = await resolve_meeting_file_download_url(client, api_file_url)
    if not blob_url:
        return None, why
    try:
        resp = await client.get(blob_url, timeout=180.0, follow_redirects=True)
        if resp.status_code != 200:
            return None, f"blob_http_{resp.status_code}"
        if not resp.content or len(resp.content) < 128:
            return None, "blob_empty_or_tiny"
        return resp.content, ""
    except httpx.HTTPError as exc:
        return None, f"blob_fetch:{exc!r}"


def published_files_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    files = event.get("publishedFiles")
    return list(files) if isinstance(files, list) else []


def event_anchor_text(
    event: Dict[str, Any],
    pf: Dict[str, Any],
    *,
    meeting_date: Optional[Any] = None,
) -> str:
    """Title for PDF naming; calendar date belongs in the filename prefix, not repeated here."""
    from datetime import date as _date

    from scripts.discovery.meeting_document_naming import strip_redundant_meeting_date_from_title

    name = str(pf.get("name") or "").strip()
    if meeting_date and isinstance(meeting_date, _date):
        name = strip_redundant_meeting_date_from_title(name, meeting_date) or name
    en = str(event.get("eventName") or "").strip()
    if meeting_date and isinstance(meeting_date, _date):
        en = strip_redundant_meeting_date_from_title(en, meeting_date) or en
    cat = str(event.get("categoryName") or event.get("eventCategoryName") or "").strip()
    parts = [p for p in (name, en, cat) if p]
    return " — ".join(parts)[:500]


def iter_all_events(
    client: httpx.Client,
    tenant: str,
    *,
    years_back: Optional[int] = None,
    years_ahead: Optional[int] = None,
    newest_calendar_years_first: bool = False,
) -> Iterator[Dict[str, Any]]:
    y_min, y_max = _years_window()
    if years_back is not None:
        y_min = datetime.now(timezone.utc).year - int(years_back)
    if years_ahead is not None:
        y_max = datetime.now(timezone.utc).year + int(years_ahead)
    years = list(range(y_min, y_max + 1))
    if newest_calendar_years_first:
        years = list(reversed(years))
    for year in years:
        yield from iter_events_for_year(client, tenant, year)
