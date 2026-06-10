"""
Write a jurisdiction-local ``contacts.json`` next to ``_contact_images/`` after a crawl.

The bundle deduplicates structured contact rows (by email), normalizes person names, and links
saved profile image paths when available.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scrapers.discovery.contact_extract_from_html import (
    dedupe_structured_contact_rows,
    is_city_council_person_row,
    is_generic_mailbox_email,
    normalize_structured_contact_row,
)


_NON_PERSON_PROFILE_NAME_RE = re.compile(
    r"(?is)\b("
    r"search|facebook|twitter|agenda|calendar|minutes|mission|district\s+map|"
    r"board\s+of\s+commissioners\s+agenda\s+appearance\s+form|"
    r"agenda\s+center|government\s+offices\s+closed|development\s+authority|"
    r"a\s+place\s+of\s+beginnings|official\s+website|welcome"
    r")\b"
)

_NON_PERSON_PROFILE_URL_RE = re.compile(
    r"(?is)(/assets/images/iconshare|/common/images/calendar/closebutton|"
    r"/common/images/getacro\.gif|homeiconminutes|iconshare(?:facebook|twitter|email)|"
    r"documentid=161\b|documentid=231\b|"
    r"/(?:f\d*header\d*|header\d*|hero\d*|banner\d*|logo\d*)\.(?:jpg|jpeg|png|webp)\b|"
    r"/wp-content/plugins/(?:accessibility|onetap)[^/]*/|"
    r"weatherforyou\.net|icon-drop-down-menu\.png|"
    r"/assets/images/(?:english|german|spanish|french|italia|poland|portugal|rumania|slowakia|swedish|finnland)\.png)"
)
_NON_PERSON_PROFILE_SINGLE_WORD_RE = re.compile(
    r"(?is)^(?:flag|flags|icon|icons|menu|logo|image|avatar|placeholder)$"
)

_NON_PERSON_NAME_RE = re.compile(
    r"(?is)^(?:end\s+latest\s+posts\s+section|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2},\s+\d{4}\s+read\s+more)\s*$"
)

_NON_PERSON_TITLE_RE = re.compile(
    r"(?is)^(?:.+\s+search\s+results?|"
    r"meetings\s+search\s+results?|minutes\s+search\s+results?|agenda\s+search\s+results?|"
    r"board\s+search\s+results?|council\s+search\s+results?|commission\s+search\s+results?)\s*$"
)
_UI_ACTION_PERSON_NAME_RE = re.compile(
    r"(?is)^(?:view\s+(?:meeting\s+)?minutes|live\s+video\s+streaming|click\s+here)\b",
)


def _is_probable_non_person_contact(row: Dict[str, Any]) -> bool:
    """Return True for obvious search-result or UI artifact rows."""
    name = str(row.get("person_name") or "").strip()
    title = str(row.get("title_or_role") or "").strip()
    email = str(row.get("email") or "").strip()
    profile_url = str(row.get("profile_url") or "").strip()
    method = str(row.get("extraction_method") or "").strip().lower()
    page = str(row.get("source_page_url") or row.get("raw_row", {}).get("page_url") or "").strip().lower()

    if method == "heading_section_plaintext" and _UI_ACTION_PERSON_NAME_RE.match(name):
        return True
    if method == "heading_section_plaintext" and name.lower() in {
        "mayor",
        "council",
        "councilmember",
        "commissioner",
        "chair",
        "phone",
        "email",
    }:
        return True
    if re.match(r"(?is)^please\s+call\b", name):
        return True
    if name.lower() in {"overview", "overview:", "contact", "contacts"}:
        return True
    if method == "civicplus_staff_directory_hcard":
        page_l = page.lower()
        if any(
            x in page_l
            for x in (
                "/board",
                "/commission",
                "/beautification",
                "/library-board",
                "/personnel-board",
                "/planning",
                "/zoning",
                "/education",
                "/clinic",
                "/safety-board",
                "/housing",
                "/industrial",
            )
        ) and not is_city_council_person_row(row):
            return True
    if re.match(r"^\d{1,6}\s+", name):
        return True
    if _NON_PERSON_PROFILE_SINGLE_WORD_RE.match(name):
        return True

    # Keep rows that have stronger person signals.
    if email or profile_url:
        if email and not profile_url and not name and not title and not str(row.get("department") or "").strip():
            return True
        if not name and not title and not str(row.get("department") or "").strip() and email:
            if is_generic_mailbox_email(email):
                return True
        return False

    # Strong junk patterns observed on WordPress search pages.
    if _NON_PERSON_NAME_RE.match(name):
        return True
    if _NON_PERSON_TITLE_RE.match(title):
        return True

    # Heading plaintext rows coming from query-result pages are often non-person snippets.
    if method == "heading_section_plaintext" and ("?s=" in page or "/search" in page):
        if not email and not profile_url:
            return True

    return False


def _is_person_profile_image_record(img: Dict[str, Any]) -> bool:
    if img.get("error"):
        return False
    if not img.get("saved_filename"):
        return False
    pname = str(img.get("person_name") or "").strip()
    iurl = str(img.get("image_url") or "").strip().lower()
    if not pname:
        return False
    if _NON_PERSON_PROFILE_URL_RE.search(iurl):
        return False
    if _NON_PERSON_PROFILE_NAME_RE.search(pname):
        return False
    if _NON_PERSON_PROFILE_SINGLE_WORD_RE.match(pname):
        return False
    if re.match(r"^\d{1,6}\s+", pname):
        return False
    if "..." in pname:
        return False
    if pname.endswith(":"):
        return False

    # Require a plausible person-like name shape.
    toks = [t for t in re.findall(r"[A-Za-z]+", pname) if len(t) >= 2]
    if len(toks) < 2 or len(toks) > 5:
        return False
    lower_tokens = [t.lower() for t in toks]
    stop_tokens = {
        "city", "county", "department", "board", "commission", "meeting",
        "agenda", "minutes", "search", "results", "official", "welcome",
        "place", "beginnings",
    }
    if any(t in stop_tokens for t in lower_tokens):
        return False
    # At least two tokens should look like proper-name tokens.
    proper_like = sum(1 for t in toks if t[:1].isupper())
    return proper_like >= 2


def build_contacts_bundle(
    *,
    jurisdiction_id: str,
    state: str,
    homepage_url: str,
    scraped_at: Optional[str],
    scrape_batch_id: str,
    structured_contacts: List[Dict[str, Any]],
    contact_profile_images: List[Dict[str, Any]],
    extracted_contacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the on-disk contacts bundle (schema_version 2)."""
    rows = dedupe_structured_contact_rows(structured_contacts)
    department_offices: List[Dict[str, Any]] = []
    person_rows: List[Dict[str, Any]] = []
    for row in rows:
        normalize_structured_contact_row(row)
        from scrapers.discovery.contact_extract_from_html import infer_profile_url_from_source_page

        infer_profile_url_from_source_page(row)
        if str(row.get("contact_scope") or "").strip().lower() == "department":
            department_offices.append(row)
        else:
            person_rows.append(row)

    # Drop generic mailbox stubs (e.g. cityclerk@) when the council office block was captured.
    if department_offices:
        person_rows = [
            r
            for r in person_rows
            if (r.get("person_name") or "").strip()
            or not is_generic_mailbox_email(r.get("email"))
        ]

    office_snapshot: Optional[Dict[str, Any]] = None
    if department_offices:
        office_snapshot = {
            k: department_offices[0].get(k)
            for k in (
                "department",
                "office_heading",
                "mailing_address",
                "phone",
                "email",
                "profile_url",
                "source_page_url",
            )
            if department_offices[0].get(k) is not None
        }
        for r in person_rows:
            if is_city_council_person_row(r):
                r["department_office"] = office_snapshot

    rows = person_rows + department_offices

    # Sanity filter pass: suppress obvious non-person artifacts from search-result pages.
    pre_filter_person_count = len(person_rows)
    filtered_person_rows: List[Dict[str, Any]] = []
    removed_non_person_count = 0
    for row in person_rows:
        if _is_probable_non_person_contact(row):
            removed_non_person_count += 1
            continue
        filtered_person_rows.append(row)
    person_rows = filtered_person_rows
    rows = person_rows + department_offices

    by_email: Dict[str, Dict[str, Any]] = {}
    for row in person_rows:
        em = str(row.get("email") or "").strip().lower()
        if em:
            by_email[em] = row

    valid_profile_images = [
        img for img in (contact_profile_images or []) if _is_person_profile_image_record(img)
    ]
    filtered_profile_images_count = len(contact_profile_images or []) - len(valid_profile_images)

    # Link saved headshots by email (from structured row) or person_stem / person_name match.
    for img in valid_profile_images:
        rel = str(img.get("saved_relative_path") or "").strip()
        if not rel:
            rel = f"_contact_images/{img['saved_filename']}"
        em = str(img.get("email") or "").strip().lower()
        target = by_email.get(em) if em else None
        if not target:
            pname = str(img.get("person_name") or "").strip().lower()
            for row in person_rows:
                rn = str(row.get("person_name") or "").strip().lower()
                if rn and pname and rn == pname:
                    target = row
                    break
                # Image job may still carry honorific; match bare name suffix
                if rn and pname and rn in pname:
                    target = row
                    break
        if target is not None:
            target["profile_image_path"] = rel
            if not target.get("profile_image_url"):
                target["profile_image_url"] = img.get("image_url")

    scraped_at_iso = scraped_at or datetime.now(timezone.utc).isoformat()
    try:
        _dt_local = datetime.fromisoformat(scraped_at_iso).astimezone()
        scraped_time_local = _dt_local.strftime("%Y-%m-%d %I:%M:%S %p %Z").strip()
    except (TypeError, ValueError):
        scraped_time_local = ""

    extraction_methods = dict(
        Counter(
            str(r.get("extraction_method") or "unknown")
            for r in (person_rows + department_offices)
        )
    )

    noisy_bulk_suspected = (
        pre_filter_person_count >= 20
        and removed_non_person_count >= max(6, int(pre_filter_person_count * 0.3))
    )

    return {
        "schema_version": 2,
        "jurisdiction_id": jurisdiction_id,
        "state": state,
        "homepage_url": homepage_url,
        "scraped_at": scraped_at_iso,
        "scraped_time_local": scraped_time_local,
        "scrape_batch_id": scrape_batch_id,
        "contact_count": len(person_rows),
        "department_office_count": len(department_offices),
        "extraction_methods": extraction_methods,
        "sanity_checks": {
            "person_rows_before_filter": pre_filter_person_count,
            "person_rows_removed_as_non_person": removed_non_person_count,
            "noisy_bulk_suspected": noisy_bulk_suspected,
            "threshold_rule": "flag when before_filter>=20 and removed>=max(6,30%)",
            "profile_images_before_filter": len(contact_profile_images or []),
            "profile_images_removed_as_non_person": filtered_profile_images_count,
        },
        "contacts": person_rows,
        "department_offices": department_offices,
        "profile_images": [
            {
                k: img.get(k)
                for k in (
                    "person_name",
                    "title_or_role",
                    "email",
                    "image_url",
                    "saved_filename",
                    "saved_relative_path",
                    "person_stem",
                    "match_method",
                    "discovered_on",
                    "error",
                )
                if img.get(k) is not None
            }
            for img in valid_profile_images
        ],
        "extracted_contacts_summary": extracted_contacts or {},
    }


def write_contacts_bundle_json(
    base_dir: Path,
    bundle: Dict[str, Any],
    *,
    filename: str = "contacts.json",
) -> Path:
    """
    Write ``{base_dir}/_contact_images/contacts.json`` (creates ``_contact_images`` if needed).
    """
    out_dir = base_dir / "_contact_images"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path
