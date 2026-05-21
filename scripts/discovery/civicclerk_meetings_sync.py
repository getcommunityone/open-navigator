#!/usr/bin/env python3
"""
Sync CivicClerk public API events and agenda/minutes PDFs into scraped meetings cache.

Bypasses the JS calendar on pages like https://www.northportal.gov/129/Agendas-Minutes by calling
``https://{tenant}.api.civicclerk.com/v1/Events`` (OData) and downloading ``publishedFiles``.

Examples::

    .venv/bin/python scripts/discovery/civicclerk_meetings_sync.py \\
        --state AL --geoid 0155200 --type municipality \\
        --tenant northportal --max-pdfs 80

    .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \\
        --state AL --geoid 0155200 --type municipality \\
        --url https://www.northportal.gov/129/Agendas-Minutes \\
        --civicclerk-tenant northportal --max-pdfs 80 --max-pages 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.civicclerk_public_api import (
    civicclerk_doc_type,
    civicclerk_portal_event_url,
    detect_civicclerk_tenant,
    download_meeting_file_bytes,
    event_anchor_text,
    fetch_event_detail,
    iter_all_events,
    published_files_from_event,
)
from scripts.discovery.meeting_document_naming import (
    allocate_unique_pdf_path,
    infer_calendar_folder_year,
)
from scripts.discovery.meetings_platform_heuristics import classify_document
from scripts.utils.gdrive_paths import resolve_scraped_meetings_output_root
from scripts.utils.http_url_normalize import normalize_http_url_path_encoding as _normalize_http_url_path_encoding

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 OpenNavigatorMeetings/1.0"
)

_DOWNLOADABLE_TYPES = frozenset(
    {"agenda", "agenda packet", "minutes", "notice", "other", "packet", "supplement"}
)


def _civicclerk_sync_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_CIVICCLERK_SYNC") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _jurisdiction_base_dir(output_root: Path, state: str, jurisdiction_id: str) -> Path:
    jt = "county" if jurisdiction_id.startswith("county_") else "municipality"
    return output_root / state.strip().upper() / jt / jurisdiction_id.strip()


def _event_summary_row(tenant: str, event: Dict[str, Any]) -> Dict[str, Any]:
    eid = int(event.get("id") or 0)
    start = str(event.get("startDateTime") or event.get("eventDate") or "")
    year_s = start[:4] if len(start) >= 4 and start[:4].isdigit() else ""
    return {
        "event_id": eid,
        "start_date_time": start,
        "year": year_s,
        "event_name": str(event.get("eventName") or "")[:500],
        "category_name": str(event.get("categoryName") or event.get("eventCategoryName") or "")[:200],
        "portal_url": civicclerk_portal_event_url(tenant, eid) if eid else None,
        "has_agenda": bool(event.get("hasAgenda")),
        "has_media": bool(event.get("hasMedia")),
        "is_published": str(event.get("isPublished") or ""),
        "published_file_count": len(published_files_from_event(event)),
    }


async def sync_civicclerk_meetings_async(
    *,
    output_root: Path,
    state: str,
    jurisdiction_id: str,
    tenant: str,
    homepage_url: str,
    max_pdfs: int,
    existing_pdfs: Optional[List[Dict[str, Any]]] = None,
    pdf_count_start: int = 0,
    timeout_s: float = 120.0,
    detail_concurrency: int = 6,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], int]:
    """
    Return ``(civicclerk_events, new_pdf_rows, errors, pdf_count)``.
    """
    errors: List[str] = []
    civicclerk_events: List[Dict[str, Any]] = []
    new_pdf_rows: List[Dict[str, Any]] = []
    pdf_count = int(pdf_count_start)
    pdfs_seen: Set[str] = set()
    for row in existing_pdfs or []:
        u = str(row.get("url") or "").strip()
        if u:
            pdfs_seen.add(_normalize_http_url_path_encoding(u))

    base_dir = _jurisdiction_base_dir(output_root, state, jurisdiction_id)
    year_now = datetime.now(timezone.utc).year

    def _target_dir(year: int) -> Path:
        return base_dir / str(year)

    reserved_names: Set[str] = set()
    reserved_paths: Set[str] = set()

    need_detail: List[Dict[str, Any]] = []
    with httpx.Client(
        headers={"User-Agent": _DEFAULT_UA, "Accept": "application/json"},
        follow_redirects=True,
        timeout=timeout_s,
    ) as sync_client:
        summaries = list(iter_all_events(sync_client, tenant))
        for ev in summaries:
            if ev.get("isDeleted"):
                continue
            if str(ev.get("isPublished") or "").lower() not in ("published",):
                continue
            eid = int(ev.get("id") or 0)
            if not eid:
                continue
            civicclerk_events.append(_event_summary_row(tenant, ev))
            if ev.get("hasAgenda") or ev.get("hasMedia") or int(ev.get("agendaId") or 0) > 0:
                need_detail.append(ev)

        sem = asyncio.Semaphore(max(1, detail_concurrency))

        async def _fetch_one(ev: Dict[str, Any]) -> Dict[str, Any]:
            eid = int(ev.get("id") or 0)
            async with sem:
                return await asyncio.to_thread(fetch_event_detail, sync_client, tenant, eid)

        details: List[Dict[str, Any]] = []
        if need_detail:
            details = await asyncio.gather(*[_fetch_one(ev) for ev in need_detail])

    async with httpx.AsyncClient(
        headers={"User-Agent": _DEFAULT_UA, "Accept": "application/json, application/pdf"},
        follow_redirects=True,
        timeout=timeout_s,
    ) as client:
        for event in details:
            if pdf_count >= max_pdfs:
                break
            eid = int(event.get("id") or 0)
            start_raw = str(event.get("startDateTime") or event.get("eventDate") or "")
            ys = start_raw[:4]
            if ys.isdigit() and len(ys) == 4:
                y = int(ys)
            else:
                y = infer_calendar_folder_year(
                    civicclerk_portal_event_url(tenant, eid),
                    str(event.get("eventName") or ""),
                    "",
                    fallback_year=year_now,
                )
            dest_dir = _target_dir(y)
            dest_dir.mkdir(parents=True, exist_ok=True)

            for pf in published_files_from_event(event):
                if pdf_count >= max_pdfs:
                    break
                ft = str(pf.get("type") or "").strip()
                if ft.lower() not in _DOWNLOADABLE_TYPES and "agenda" not in ft.lower():
                    continue
                api_url = str(pf.get("url") or "").strip()
                if not api_url or api_url in pdfs_seen:
                    continue
                pdfs_seen.add(api_url)

                blob, why = await download_meeting_file_bytes(client, api_url)
                if blob is None:
                    errors.append(f"civicclerk_download:{eid}:{api_url[:80]}:{why}")
                    continue

                anchor = event_anchor_text(event, pf)
                doc_label = civicclerk_doc_type(ft, str(pf.get("name") or ""))
                if doc_label == "unknown":
                    doc_label = classify_document(api_url, anchor)

                dest = allocate_unique_pdf_path(
                    dest_dir,
                    api_url,
                    anchor,
                    doc_label,
                    year_fallback=str(y),
                    reserved_basenames=reserved_names,
                    reserved_paths=reserved_paths,
                )
                dest.write_bytes(blob)
                reserved_names.add(dest.name)
                try:
                    reserved_paths.add(str(dest.resolve()))
                except OSError:
                    reserved_paths.add(str(dest))

                row: Dict[str, Any] = {
                    "url": api_url,
                    "path": str(dest.resolve()),
                    "year": str(y),
                    "bytes": len(blob),
                    "doc_type": doc_label,
                    "anchor_text": anchor,
                    "storage_suffix": ".pdf",
                    "source_kind": "civicclerk_api",
                    "civicclerk_event_id": eid,
                    "civicclerk_file_type": ft,
                    "civicclerk_portal_url": civicclerk_portal_event_url(tenant, eid),
                    "discovered_on": homepage_url or civicclerk_portal_event_url(tenant, eid),
                }
                new_pdf_rows.append(row)
                pdf_count += 1

    return civicclerk_events, new_pdf_rows, errors, pdf_count


def merge_manifest_civicclerk(
    manifest_path: Path,
    *,
    civicclerk_events: List[Dict[str, Any]],
    new_pdf_rows: List[Dict[str, Any]],
    errors: List[str],
    tenant: str,
) -> None:
    try:
        data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}

    prior_events = data.get("civicclerk_events")
    if not isinstance(prior_events, list):
        prior_events = []
    seen_eid = {int(r.get("event_id") or 0) for r in prior_events if isinstance(r, dict)}
    for row in civicclerk_events:
        if not isinstance(row, dict):
            continue
        eid = int(row.get("event_id") or 0)
        if eid and eid not in seen_eid:
            prior_events.append(row)
            seen_eid.add(eid)

    pdfs = data.get("pdfs")
    if not isinstance(pdfs, list):
        pdfs = []
    seen_url = {str(r.get("url") or "").strip() for r in pdfs if isinstance(r, dict)}
    for row in new_pdf_rows:
        u = str(row.get("url") or "").strip()
        if u and u not in seen_url:
            pdfs.append(row)
            seen_url.add(u)

    stacks = data.get("detected_stacks")
    if not isinstance(stacks, list):
        stacks = []
    if "civicclerk" not in stacks:
        stacks.append("civicclerk")

    data["civicclerk_events"] = prior_events
    data["civicclerk_tenant"] = tenant
    data["pdfs"] = pdfs
    data["detected_stacks"] = stacks
    data["civicclerk_synced_at"] = datetime.now(timezone.utc).isoformat()

    errs = data.get("errors")
    if not isinstance(errs, list):
        errs = []
    errs.extend(errors[:50])
    data["errors"] = errs

    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def _async_main(args: argparse.Namespace) -> int:
    output_root = (
        Path(args.output_root).expanduser().resolve()
        if args.output_root.strip()
        else resolve_scraped_meetings_output_root().resolve()
    )
    jtype = "county" if args.type == "county" else "municipality"
    jid = f"{jtype}_{args.geoid.strip()}"
    base_dir = _jurisdiction_base_dir(output_root, args.state, jid)
    manifest_path = base_dir / "_manifest.json"

    tenant = (args.tenant or "").strip().lower()
    if not tenant and manifest_path.is_file():
        try:
            prior = json.loads(manifest_path.read_text(encoding="utf-8"))
            tenant = str(prior.get("civicclerk_tenant") or "").strip().lower()
        except (OSError, json.JSONDecodeError):
            pass
    if not tenant:
        html = ""
        crawl = base_dir / "_crawl_html"
        for name in ("page__129_Agendas-Minutes.html", "page__AgendaCenter.html"):
            p = crawl / name
            if p.is_file():
                html = p.read_text(encoding="utf-8", errors="replace")
                break
        tenant = detect_civicclerk_tenant(
            homepage_url=args.homepage_url or "https://www.northportal.gov/",
            html=html,
        ) or ""
    if not tenant:
        print("Could not detect CivicClerk tenant; pass --tenant northportal", file=sys.stderr)
        return 1

    prior_pdfs: List[Dict[str, Any]] = []
    if manifest_path.is_file():
        try:
            prior = json.loads(manifest_path.read_text(encoding="utf-8"))
            prior_pdfs = list(prior.get("pdfs") or [])
        except (OSError, json.JSONDecodeError):
            pass

    events, pdf_rows, errors, _ = await sync_civicclerk_meetings_async(
        output_root=output_root,
        state=args.state,
        jurisdiction_id=jid,
        tenant=tenant,
        homepage_url=args.homepage_url or "https://www.northportal.gov/129/Agendas-Minutes",
        max_pdfs=max(0, int(args.max_pdfs)),
        existing_pdfs=prior_pdfs,
        pdf_count_start=len(prior_pdfs),
        timeout_s=float(args.timeout),
    )

    base_dir.mkdir(parents=True, exist_ok=True)
    merge_manifest_civicclerk(
        manifest_path,
        civicclerk_events=events,
        new_pdf_rows=pdf_rows,
        errors=errors,
        tenant=tenant,
    )

    print(
        json.dumps(
            {
                "tenant": tenant,
                "events_indexed": len(events),
                "pdfs_downloaded": len(pdf_rows),
                "errors": len(errors),
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )
    return 0 if not errors else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync CivicClerk API agendas/minutes into scrape cache.")
    ap.add_argument("--state", required=True)
    ap.add_argument("--geoid", required=True)
    ap.add_argument("--type", default="municipality", choices=("municipality", "county"))
    ap.add_argument("--tenant", default="", help="CivicClerk tenant slug (e.g. northportal)")
    ap.add_argument("--homepage-url", default="https://www.northportal.gov/129/Agendas-Minutes")
    ap.add_argument("--output-root", default="")
    ap.add_argument("--max-pdfs", type=int, default=80)
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
