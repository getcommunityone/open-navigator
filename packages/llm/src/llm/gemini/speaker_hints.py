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
    root = repo_root or Path(__file__).resolve().parents[5]
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


def speaker_alias_index(known_speakers: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Map lowercase aliases (first name, last name, full name) → canonical person_name.
    """
    index: Dict[str, str] = {}
    for sp in known_speakers:
        name = (sp.get("person_name") or "").strip()
        if not name:
            continue
        parts = [p for p in re.split(r"[\s,]+", name) if p]
        if len(parts) >= 2:
            index[parts[0].lower()] = name
            index[parts[-1].lower()] = name
        if len(parts) == 1:
            index[parts[0].lower()] = name
        index[name.lower()] = name
    return index


def label_segments_from_contacts(
    segments: List[Dict[str, Any]],
    known_speakers: List[Dict[str, str]],
) -> None:
    """
    Set ``speaker_guess`` on caption segments using contact directory (no audio).

    Uses name mentions in text and council-meeting cues (e.g. ``Mike.`` before speech).
    """
    if not known_speakers:
        return
    from llm.gemini.diarize_postprocess import apply_name_hints_to_segments

    aliases = speaker_alias_index(known_speakers)
    apply_name_hints_to_segments(segments, known_speakers)

    for i, seg in enumerate(segments):
        if seg.get("speaker_guess"):
            continue
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        low = text.lower()
        # "for Tartan Cove phase 1, 2, and 6. Mike." → next segment often that speaker
        m = re.search(r"\.\s*([A-Za-z][A-Za-z.'-]{1,20})\.\s*$", text)
        if m:
            token = m.group(1).replace(".", "").lower()
            if token in aliases:
                seg["speaker_guess"] = aliases[token]
                if i + 1 < len(segments) and not segments[i + 1].get("speaker_guess"):
                    segments[i + 1]["speaker_guess"] = aliases[token]
                continue
        # ">> Good afternoon. Phil." style
        for token in re.findall(r"[A-Za-z][A-Za-z.'-]{2,}", text):
            key = token.replace(".", "").lower()
            if key in aliases and len(key) >= 3:
                seg["speaker_guess"] = aliases[key]
                break
        # Propagate guess to adjacent segments in same run (max 8 segments ~30s)
        if seg.get("speaker_guess") and i + 1 < len(segments):
            for j in range(i + 1, min(i + 9, len(segments))):
                nxt = segments[j]
                if nxt.get("speaker_guess"):
                    break
                if re.match(r"^(motion|second|all in favor|aye|agenda|thank)", (nxt.get("text") or "").lower()):
                    break
                nxt["speaker_guess"] = seg["speaker_guess"]


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
