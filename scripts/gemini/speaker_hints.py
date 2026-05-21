"""
Build speaker hints from scraped-meetings ``_contact_images/contacts.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def default_scrape_cache_dir(jurisdiction_id: str, *, repo_root: Optional[Path] = None) -> Path:
    """``data/cache/scraped_meetings/.../municipality_XXXX`` from ``municipality_0177256``."""
    root = repo_root or Path(__file__).resolve().parents[2]
    jid = (jurisdiction_id or "").strip()
    m = re.match(r"^municipality_(\d+)$", jid)
    if m:
        state_hint = "AL"  # caller should pass explicit cache dir when not AL
        return root / "data/cache/scraped_meetings" / state_hint / "municipality" / jid
    return root / "data/cache/scraped_meetings" / jid


def load_contacts_bundle(cache_dir: Path) -> Dict[str, Any]:
    path = cache_dir / "_contact_images" / "contacts.json"
    if not path.is_file():
        raise FileNotFoundError(f"contacts.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def format_speaker_hints_block(bundle: Dict[str, Any]) -> str:
    """Plain-text block prepended to policy prompts for Flash-Lite."""
    lines = [
        "=== KNOWN SPEAKERS (from jurisdiction contact directory; use for attribution) ===",
        f"jurisdiction_id: {bundle.get('jurisdiction_id')}",
        f"governing_body: City Council (use when department/title mentions Councilor)",
    ]
    office = bundle.get("department_offices") or []
    if office:
        o0 = office[0] if isinstance(office, list) else office
        if isinstance(o0, dict):
            lines.append(
                f"department_office: {o0.get('office_heading') or o0.get('department')}"
            )
            if o0.get("phone"):
                lines.append(f"office_phone: {o0.get('phone')}")
            if o0.get("mailing_address"):
                lines.append(f"office_mailing: {o0.get('mailing_address')}")

    contacts = bundle.get("contacts") or []
    for c in contacts:
        if not isinstance(c, dict):
            continue
        name = (c.get("person_name") or "").strip()
        if not name:
            continue
        title = (c.get("title_or_role") or "").strip()
        dept = (c.get("department") or "").strip()
        email = (c.get("email") or "").strip()
        bits = [name]
        if title:
            bits.append(title)
        if dept:
            bits.append(dept)
        if email:
            bits.append(email)
        lines.append(" - " + " | ".join(bits))

    lines.append(
        "When the transcript uses SPEAKER_00 labels, map to these names when content "
        "or roll call supports it. Set person_id slugs per policy prompt rules."
    )
    lines.append("")
    return "\n".join(lines)


def known_speaker_names(bundle: Dict[str, Any]) -> List[Dict[str, str]]:
    """Structured list for diarization post-labeling."""
    out: List[Dict[str, str]] = []
    for c in bundle.get("contacts") or []:
        if not isinstance(c, dict):
            continue
        name = (c.get("person_name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "person_name": name,
                "title_or_role": (c.get("title_or_role") or "").strip(),
                "department": (c.get("department") or "").strip(),
                "email": (c.get("email") or "").strip(),
            }
        )
    return out
