"""
Write a jurisdiction-local ``contacts.json`` next to ``_contact_images/`` after a crawl.

The bundle deduplicates structured contact rows (by email), normalizes person names, and links
saved profile image paths when available.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.discovery.contact_extract_from_html import (
    dedupe_structured_contact_rows,
    is_city_council_person_row,
    is_generic_mailbox_email,
    normalize_structured_contact_row,
)


_NON_PERSON_PROFILE_NAME_RE = re.compile(
    r"(?is)\b("
    r"search|facebook|twitter|agenda|calendar|minutes|mission|district\s+map|"
    r"board\s+of\s+commissioners\s+agenda\s+appearance\s+form|"
    r"agenda\s+center|government\s+offices\s+closed|development\s+authority"
    r")\b"
)

_NON_PERSON_PROFILE_URL_RE = re.compile(
    r"(?is)(/assets/images/iconshare|/common/images/calendar/closebutton|"
    r"/common/images/getacro\.gif|homeiconminutes|iconshare(?:facebook|twitter|email)|"
    r"documentid=161\b|documentid=231\b)"
)


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
    if pname.endswith(":"):
        return False
    # Require at least one alpha token pair (e.g., first + last) for portrait contacts.
    toks = [t for t in re.findall(r"[A-Za-z]+", pname) if len(t) >= 2]
    return len(toks) >= 2


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
        from scripts.discovery.contact_extract_from_html import infer_profile_url_from_source_page

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

    by_email: Dict[str, Dict[str, Any]] = {}
    for row in person_rows:
        em = str(row.get("email") or "").strip().lower()
        if em:
            by_email[em] = row

    # Link saved headshots by email (from structured row) or person_stem / person_name match.
    for img in contact_profile_images or []:
        if not _is_person_profile_image_record(img):
            continue
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

    return {
        "schema_version": 2,
        "jurisdiction_id": jurisdiction_id,
        "state": state,
        "homepage_url": homepage_url,
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
        "scrape_batch_id": scrape_batch_id,
        "contact_count": len(person_rows),
        "department_office_count": len(department_offices),
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
            for img in (contact_profile_images or [])
            if _is_person_profile_image_record(img)
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
