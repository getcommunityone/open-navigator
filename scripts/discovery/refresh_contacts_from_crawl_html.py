#!/usr/bin/env python3
"""
Re-run structured contact extraction on saved ``_crawl_html/page_*.html`` snapshots.

Useful when extraction rules improve but pages were already fetched (resume skips re-fetch).
Updates ``_manifest.json`` ``structured_contacts`` / ``contact_directory_pages`` and writes
``_contact_images/contacts.json``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.contact_directory_heuristics import classify_contact_directory_page
from scripts.discovery.contact_extract_from_html import (
    extract_contacts_from_page,
    extract_structured_contacts_from_html,
    infer_profile_url_from_source_page,
    merge_contact_manifest_rows,
)
from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import (
    _merge_contact_directory_pages,
    _merge_prior_extracted_contacts,
    _merge_structured_contact_rows,
)
from scripts.discovery.contact_profile_images import download_profile_images
from scripts.discovery.contacts_bundle import build_contacts_bundle, write_contacts_bundle_json


def _ai_fallback_max_pages_per_jurisdiction() -> int:
    try:
        return max(1, min(20, int((os.getenv("SCRAPED_CONTACT_AI_MAX_PAGES_PER_JURISDICTION") or "3").strip())))
    except ValueError:
        return 3


def _structured_contact_page_quality(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    total = 0.0
    max_total = float(len(rows) * 7)
    for row in rows:
        if str(row.get("person_name") or "").strip():
            total += 2
        if str(row.get("title_or_role") or "").strip():
            total += 2
        if str(row.get("email") or "").strip():
            total += 1
        if str(row.get("phone") or "").strip():
            total += 1
        if str(row.get("profile_image_url") or "").strip():
            total += 1
    return total / max_total if max_total > 0 else 0.0


def _structured_contact_rows_named_count(rows: List[Dict[str, Any]]) -> int:
    return sum(1 for r in rows if str(r.get("person_name") or "").strip())


def _should_try_ai_fallback(
    *,
    page_url: str,
    html: str,
    directory_score: int,
    person_adjacent_image_score: int,
    page_structured: List[Dict[str, Any]],
    low_confidence_score_max: int,
    min_quality: float,
) -> bool:
    quality = _structured_contact_page_quality(page_structured)
    named_count = _structured_contact_rows_named_count(page_structured)
    with_profile_image = sum(1 for r in page_structured if str(r.get("profile_image_url") or "").strip())
    missing_many_images = named_count >= 2 and with_profile_image < max(1, named_count // 2)
    low_confidence = (
        not page_structured
        or quality < min_quality
        or (named_count < 2 and directory_score <= low_confidence_score_max)
        or missing_many_images
    )
    if not low_confidence:
        return False
    if directory_score >= 18 and int(person_adjacent_image_score or 0) >= 6:
        return True
    try:
        from scripts.discovery.contact_extract_crawl4ai import looks_like_contact_roster_page

        return looks_like_contact_roster_page(page_url, html)
    except Exception:
        return False


def _snapshot_stem_to_page_url(homepage: str, snap_stem: str) -> str:
    """``page__220_City-Council`` → ``https://host/220/City-Council``."""
    slug = snap_stem[5:] if snap_stem.startswith("page_") else snap_stem
    slug = slug.lstrip("_")
    if slug == "index":
        path = "/"
    elif slug.isdigit():
        path = f"/{slug}"
    else:
        m = re.match(r"^(\d+)_(.+)$", slug)
        if m:
            path = f"/{m.group(1)}/{m.group(2)}"
        else:
            path = "/" + slug.replace("_", "/")
    base = (homepage or "").strip().rstrip("/")
    if not base:
        return path
    p = urlparse(base)
    return urljoin(f"{p.scheme}://{p.netloc}", path)


async def _download_structured_profile_images(
    jurisdiction_dir: Path,
    structured_contacts: List[Dict[str, Any]],
    *,
    homepage_url: str,
    max_images: int = 48,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()
    for row in structured_contacts:
        img = str(row.get("profile_image_url") or "").strip()
        if not img or img in seen_urls:
            continue
        seen_urls.add(img)
        jobs.append(
            {
                "image_url": img,
                "person_name": str(row.get("person_name") or "").strip(),
                "title_or_role": str(row.get("title_or_role") or "").strip(),
                "source_page_url": str(row.get("source_page_url") or "").strip(),
            }
        )
    if not jobs:
        return []
    out_dir = jurisdiction_dir / "_contact_images"
    referer = (homepage_url or "").strip() or str(jobs[0].get("source_page_url") or "")
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        return await download_profile_images(
            client,
            jobs,
            out_dir,
            referer=referer,
            max_images=max_images,
            save_as_png=True,
        )


def _cleanup_contact_image_dir(jurisdiction_dir: Path, rows: List[Dict[str, Any]]) -> int:
    """Delete stale image files not referenced by the latest ``contact_profile_images`` rows."""
    img_dir = jurisdiction_dir / "_contact_images"
    if not img_dir.is_dir():
        return 0
    keep = {str(r.get("saved_filename") or "").strip() for r in rows}
    keep.discard("")
    deleted = 0
    for p in img_dir.iterdir():
        if not p.is_file():
            continue
        if p.name == "contacts.json":
            continue
        if p.name in keep:
            continue
        try:
            p.unlink(missing_ok=True)
            deleted += 1
        except OSError:
            continue
    return deleted


def refresh_jurisdiction_contacts(
    jurisdiction_dir: Path,
    *,
    page_url_contains: Optional[str] = None,
    seed_urls: Optional[List[str]] = None,
    replace_matching_pages: bool = False,
    replace_all_structured_contacts: bool = False,
    download_profile_images_flag: bool = False,
    max_profile_images: int = 48,
    use_ai: bool = False,
    use_ai_fallback: bool = True,
    ai_provider: Optional[str] = None,
    ai_low_confidence_score_max: int = 6,
    ai_min_quality: float = 0.42,
) -> Dict[str, Any]:
    jurisdiction_dir = jurisdiction_dir.expanduser().resolve()
    manifest_path = jurisdiction_dir / "_manifest.json"
    crawl_html = jurisdiction_dir / "_crawl_html"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    if not crawl_html.is_dir():
        raise FileNotFoundError(crawl_html)

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    homepage = str(data.get("homepage_url") or "").strip()
    jid = str(data.get("jurisdiction_id") or "").strip()
    st = str(data.get("state") or "").strip()

    seed_norm: Set[str] = set()
    for u in seed_urls or []:
        seed_norm.add(u.split("#")[0].rstrip("/"))

    fresh_structured: List[Dict[str, Any]] = []
    fresh_cdir: List[Dict[str, Any]] = []
    contact_page_rows: List[Dict[str, Any]] = []
    ai_fallback_pages_used = 0
    ai_fallback_pages_limit = _ai_fallback_max_pages_per_jurisdiction()

    filter_sub = (page_url_contains or "").strip().lower()

    for snap in sorted(crawl_html.glob("page_*.html")):
        page_url = _snapshot_stem_to_page_url(homepage, snap.stem)
        if filter_sub and filter_sub not in page_url.lower():
            continue
        html = snap.read_text(encoding="utf-8", errors="replace")
        seed_hit = any(
            page_url.split("#")[0].rstrip("/") == s or page_url.rstrip("/") == s
            for s in seed_norm
        )
        cdir = classify_contact_directory_page(page_url, html)
        flagged = bool(cdir.get("is_directory")) or seed_hit
        if not flagged:
            continue

        rec = {**cdir, "page_url": page_url, "is_directory": True}
        if seed_hit:
            rec["directory_kind"] = str(rec.get("directory_kind") or "seed_url")
            ms = list(rec.get("matched_signals") or [])
            ms.append("refresh_crawl_html")
            rec["matched_signals"] = ms
        fresh_cdir.append(rec)

        page_classification = str(
            cdir.get("directory_kind") or ("seed_url" if seed_hit else "unknown")
        )
        directory_score = int(cdir.get("score") or 0)
        person_adjacent_image_score = int(cdir.get("person_adjacent_image_score") or 0)

        if use_ai:
            from scripts.discovery.contact_extract_crawl4ai import (
                ai_record_to_structured_row,
                extract_contact_directory_sync,
            )

            ai_kwargs = {"provider": ai_provider} if ai_provider else {}
            directory = extract_contact_directory_sync(page_url, **ai_kwargs)
            for rec in directory.contacts:
                prow = ai_record_to_structured_row(
                    rec,
                    source_page_url=page_url,
                    page_classification=page_classification,
                    directory_score=directory_score,
                )
                infer_profile_url_from_source_page(prow)
                fresh_structured.append(prow)
        else:
            page_structured = extract_structured_contacts_from_html(html, page_url)
            if use_ai_fallback and _should_try_ai_fallback(
                page_url=page_url,
                html=html,
                directory_score=directory_score,
                person_adjacent_image_score=person_adjacent_image_score,
                page_structured=page_structured,
                low_confidence_score_max=max(0, ai_low_confidence_score_max),
                min_quality=max(0.0, min(1.0, ai_min_quality)),
            ) and ai_fallback_pages_used < ai_fallback_pages_limit:
                try:
                    from scripts.discovery.contact_extract_crawl4ai import (
                        ai_record_to_structured_row,
                        extract_contact_directory_from_html_sync,
                    )

                    ai_kwargs = {"provider": ai_provider} if ai_provider else {}
                    heuristic_count = len(page_structured)
                    ai_fallback_pages_used += 1
                    ai_directory = extract_contact_directory_from_html_sync(
                        html,
                        page_url,
                        **ai_kwargs,
                    )
                    ai_rows: List[Dict[str, Any]] = []
                    for rec in ai_directory.contacts:
                        ai_rows.append(
                            ai_record_to_structured_row(
                                rec,
                                source_page_url=page_url,
                                page_classification=page_classification,
                                directory_score=directory_score,
                                extraction_method="crawl4ai_llm_fallback",
                            )
                        )
                    if ai_rows:
                        page_structured = _merge_structured_contact_rows(page_structured, ai_rows)
                        print(
                            f"[contact_ai_fallback] page={page_url} heuristic={heuristic_count} ai={len(ai_rows)} merged={len(page_structured)}"
                        )
                except Exception as exc:
                    print(f"[contact_ai_fallback_error] page={page_url} detail={exc!r}")
            elif use_ai_fallback and ai_fallback_pages_used >= ai_fallback_pages_limit:
                print(
                    f"[contact_ai_fallback_skip_limit] page={page_url} "
                    f"used={ai_fallback_pages_used} limit={ai_fallback_pages_limit}"
                )

            for prow in page_structured:
                prow["source_page_url"] = page_url
                prow["page_classification"] = page_classification
                prow["directory_score"] = directory_score
                infer_profile_url_from_source_page(prow)
                fresh_structured.append(prow)

        contact_page_rows.append(extract_contacts_from_page(html, page_url))

    prior_sc = data.get("structured_contacts")
    if replace_all_structured_contacts:
        prior_sc = []
    elif replace_matching_pages and filter_sub and isinstance(prior_sc, list):
        kept = [
            r
            for r in prior_sc
            if isinstance(r, dict)
            and filter_sub not in str(r.get("source_page_url") or "").lower()
        ]
        prior_sc = kept

    if isinstance(prior_sc, list) and prior_sc:
        data["structured_contacts"] = _merge_structured_contact_rows(prior_sc, fresh_structured)
    else:
        data["structured_contacts"] = fresh_structured

    prior_cdp = data.get("contact_directory_pages")
    if isinstance(prior_cdp, list) and prior_cdp:
        data["contact_directory_pages"] = _merge_contact_directory_pages(prior_cdp, fresh_cdir)
    else:
        data["contact_directory_pages"] = fresh_cdir

    pec = data.get("extracted_contacts")
    fresh_flat = merge_contact_manifest_rows(contact_page_rows)
    if isinstance(pec, dict) and pec:
        data["extracted_contacts"] = _merge_prior_extracted_contacts(pec, fresh_flat)
    else:
        data["extracted_contacts"] = fresh_flat

    profile_dl: List[Dict[str, Any]] = []
    if download_profile_images_flag and data["structured_contacts"]:
        profile_dl = asyncio.run(
            _download_structured_profile_images(
                jurisdiction_dir,
                data["structured_contacts"],
                homepage_url=homepage,
                max_images=max_profile_images,
            )
        )
        # Replace old image rows even when empty so stale errors don't survive refresh runs.
        data["contact_profile_images"] = profile_dl
        _cleanup_contact_image_dir(jurisdiction_dir, profile_dl)

    data["contacts_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    bundle_path = None
    if data["structured_contacts"]:
        bundle = build_contacts_bundle(
            jurisdiction_id=jid,
            state=st,
            homepage_url=homepage,
            scraped_at=data.get("scraped_at"),
            scrape_batch_id=str(data.get("scrape_batch_id") or ""),
            structured_contacts=data["structured_contacts"],
            contact_profile_images=list(data.get("contact_profile_images") or []),
            extracted_contacts=data.get("extracted_contacts"),
        )
        bundle_path = write_contacts_bundle_json(jurisdiction_dir, bundle)

    saved_images = sum(1 for r in profile_dl if r.get("saved_filename"))
    return {
        "jurisdiction_id": jid,
        "structured_contacts": len(data["structured_contacts"]),
        "new_from_snapshots": len(fresh_structured),
        "contacts_json": str(bundle_path) if bundle_path else None,
        "profile_images_saved": saved_images,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh structured contacts from _crawl_html snapshots.")
    ap.add_argument(
        "--jurisdiction-dir",
        required=True,
        help="Path to jurisdiction folder (contains _manifest.json and _crawl_html/)",
    )
    ap.add_argument(
        "--page-url-contains",
        default="",
        help="Only process snapshots whose reconstructed URL contains this substring",
    )
    ap.add_argument(
        "--seed-url",
        action="append",
        default=[],
        help="Treat matching URLs as directory seeds (repeatable)",
    )
    ap.add_argument(
        "--replace-matching-pages",
        action="store_true",
        help="Drop prior structured_contacts rows whose source_page_url matches --page-url-contains before merge",
    )
    ap.add_argument(
        "--replace-all-structured-contacts",
        action="store_true",
        help="Replace all prior structured_contacts with freshly extracted rows (full cleanup mode).",
    )
    ap.add_argument(
        "--download-profile-images",
        action="store_true",
        help="Download profile_image_url from structured contacts into _contact_images/",
    )
    ap.add_argument(
        "--max-profile-images",
        type=int,
        default=48,
        help="Cap when using --download-profile-images (default 48)",
    )
    ap.add_argument(
        "--ai",
        action="store_true",
        help=(
            "Use crawl4ai + Groq LLM extraction instead of the heuristic HTML parser. "
            "Requires GROQ_API_KEY in env and `crawl4ai-setup` to have been run."
        ),
    )
    ap.add_argument(
        "--ai-provider",
        default=None,
        help="LiteLLM provider string (default: groq/llama-3.1-8b-instant). Only used with --ai.",
    )
    ap.add_argument(
        "--ai-fallback",
        action="store_true",
        help=(
            "Use fast heuristic extraction first, then invoke AI only on complex/low-confidence "
            "directory pages (board/commissioner layouts). Enabled by default unless --no-ai-fallback."
        ),
    )
    ap.add_argument(
        "--no-ai-fallback",
        action="store_true",
        help="Disable heuristic+AI fallback mode.",
    )
    ap.add_argument(
        "--ai-low-confidence-score-max",
        type=int,
        default=6,
        help="Directory heuristic score threshold for AI fallback (default 6).",
    )
    ap.add_argument(
        "--ai-min-quality",
        type=float,
        default=0.42,
        help="Minimum heuristic row quality before AI fallback is skipped (default 0.42).",
    )
    args = ap.parse_args()
    use_ai_fallback = False if args.no_ai_fallback else (True if not args.ai else bool(args.ai_fallback))
    summary = refresh_jurisdiction_contacts(
        Path(args.jurisdiction_dir),
        page_url_contains=args.page_url_contains or None,
        seed_urls=args.seed_url or None,
        replace_matching_pages=args.replace_matching_pages,
        replace_all_structured_contacts=args.replace_all_structured_contacts,
        download_profile_images_flag=args.download_profile_images,
        max_profile_images=args.max_profile_images,
        use_ai=args.ai,
        use_ai_fallback=use_ai_fallback,
        ai_provider=args.ai_provider,
        ai_low_confidence_score_max=args.ai_low_confidence_score_max,
        ai_min_quality=args.ai_min_quality,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
