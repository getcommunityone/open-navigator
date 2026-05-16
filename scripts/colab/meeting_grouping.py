"""
Group Gatekeeper-approved files into per-meeting folders and build text briefs for audio.

Layout under each jurisdiction::

    meetings/{YYYY-MM-DD}_{instance_slug}/
        agenda/
        minutes/
        audio/
        collateral/

``instance_slug`` disambiguates multiple bodies/sessions on the same calendar day
(e.g. ``city-council`` vs ``planning-commission``).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

MEETINGS_DIRNAME = "meetings"

_DOC_SUBDIR: Dict[str, str] = {
    "meeting_agenda": "agenda",
    "meeting_minutes": "minutes",
    "meeting_audio": "audio",
    "meeting_video": "audio",
    "audio_recording": "audio",
    "audio_transcript": "audio",
    "reference_packet": "collateral",
    "other_governance_document": "collateral",
}


def slugify_meeting_label(text: str, *, max_len: int = 48) -> str:
    s = unicodedata.normalize("NFKD", (text or "").strip())
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    if not s:
        return "meeting"
    return s[:max_len].strip("-")


def infer_meeting_date_from_path(path: Path) -> Optional[str]:
    """Best-effort ``YYYY-MM-DD`` from filename stem (shared naming heuristics)."""
    try:
        from scripts.discovery.meeting_document_naming import pick_meeting_date

        d, _ = pick_meeting_date(url="", anchor=path.stem.replace("_", " "))
        return d.isoformat() if d else None
    except Exception:
        m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", path.stem)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None


def infer_instance_slug_from_path(path: Path, doc_type: str) -> str:
    stem = path.stem.lower()
    for hint, slug in (
        ("planning", "planning-commission"),
        ("zoning", "zoning-board"),
        ("school", "school-board"),
        ("commission", "county-commission"),
        ("council", "city-council"),
        ("board", "board-meeting"),
    ):
        if hint in stem:
            return slug
    if "agenda" in stem and "council" not in stem:
        return slugify_meeting_label(stem.replace("agenda", "").strip("-_") or "agenda-session")
    return slugify_meeting_label(stem) or "meeting"


@dataclass
class MeetingInstanceGroup:
    """Files belonging to one logical meeting session."""

    key: str
    meeting_date: str
    instance_slug: str
    meeting_title: str
    jurisdiction_prefix: str  # e.g. AL/county/county_01125
    files: List[Path] = field(default_factory=list)
    verdicts: List[Any] = field(default_factory=list)

    @property
    def folder_name(self) -> str:
        return f"{self.meeting_date}_{self.instance_slug}"


def jurisdiction_prefix_from_relative(rel: str) -> str:
    parts = Path(rel).parts
    if len(parts) >= 3:
        return "/".join(parts[:3])
    return str(Path(rel).parent) if len(parts) > 1 else ""


def meeting_instance_key(
    *,
    rel_path: str,
    doc_type: str,
    meeting_date: Optional[str],
    meeting_title: Optional[str],
    instance_slug: Optional[str],
) -> Tuple[str, str, str, str]:
    path = Path(rel_path)
    jur = jurisdiction_prefix_from_relative(rel_path)
    date_s = (meeting_date or "").strip() or infer_meeting_date_from_path(path) or "undated"
    title = (meeting_title or "").strip() or infer_instance_slug_from_path(path, doc_type).replace("-", " ").title()
    slug = (instance_slug or "").strip() or slugify_meeting_label(title)
    if slug in ("meeting", "undated") or len(slug) < 3:
        slug = infer_instance_slug_from_path(path, doc_type)
    key = f"{jur}|{date_s}|{slug}"
    return key, date_s, slug, title


def group_proceed_verdicts(verdicts: Sequence[Any]) -> List[MeetingInstanceGroup]:
    buckets: Dict[str, MeetingInstanceGroup] = {}
    for v in verdicts:
        rel = getattr(v, "relative_path", "") or ""
        if not rel:
            continue
        key, date_s, slug, title = meeting_instance_key(
            rel_path=rel,
            doc_type=getattr(v, "document_or_audio_type", "other"),
            meeting_date=getattr(v, "meeting_date", None),
            meeting_title=getattr(v, "meeting_title", None),
            instance_slug=getattr(v, "meeting_instance_slug", None),
        )
        if key not in buckets:
            jur = jurisdiction_prefix_from_relative(rel)
            buckets[key] = MeetingInstanceGroup(
                key=key,
                meeting_date=date_s,
                instance_slug=slug,
                meeting_title=title,
                jurisdiction_prefix=jur,
            )
        buckets[key].files.append(Path(getattr(v, "file_path", "")))
        buckets[key].verdicts.append(v)
    return sorted(buckets.values(), key=lambda g: (g.jurisdiction_prefix, g.meeting_date, g.instance_slug))


def _subdir_for_doc_type(doc_type: str) -> str:
    return _DOC_SUBDIR.get((doc_type or "").strip().lower(), "collateral")


def organize_proceed_into_meeting_folders(
    raw_root: Path,
    verdicts: Sequence[Any],
    *,
    dry_run: bool = False,
) -> List[Tuple[Path, Path]]:
    """
    Move each proceed file under ``…/meetings/{date}_{slug}/{agenda|minutes|audio|collateral}/``.

    Returns list of ``(src, dest)`` pairs (dest is prospective when ``dry_run``).
    """
    raw_root = raw_root.resolve()
    moves: List[Tuple[Path, Path]] = []
    for group in group_proceed_verdicts(verdicts):
        meeting_root = (
            raw_root
            / group.jurisdiction_prefix
            / MEETINGS_DIRNAME
            / group.folder_name
        )
        for v in group.verdicts:
            src = Path(getattr(v, "file_path", ""))
            if not src.is_file():
                continue
            sub = _subdir_for_doc_type(getattr(v, "document_or_audio_type", "other"))
            dest = meeting_root / sub / src.name
            moves.append((src, dest))
            if dry_run:
                logger.info("would organize %s → %s", src, dest.relative_to(raw_root))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.resolve() == src.resolve():
                continue
            if dest.exists():
                stem, suf = dest.stem, dest.suffix
                n = 2
                while dest.exists():
                    dest = dest.with_name(f"{stem}_dup{n}{suf}")
                    n += 1
            shutil.move(str(src), str(dest))
            logger.info("organized %s → %s", src.name, dest.relative_to(raw_root))
    return moves


def meeting_dir_for_media_file(media_path: Path, raw_root: Path) -> Optional[Path]:
    """If ``media_path`` lives under ``…/meetings/{folder}/…``, return that meeting folder."""
    try:
        rel = media_path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return None
    if MEETINGS_DIRNAME not in rel.parts:
        return None
    idx = rel.parts.index(MEETINGS_DIRNAME)
    if len(rel.parts) < idx + 2:
        return None
    return raw_root.joinpath(*rel.parts[: idx + 2])


def iter_meeting_dirs(raw_root: Path, jurisdiction_prefix: str) -> Iterable[Path]:
    base = raw_root / jurisdiction_prefix / MEETINGS_DIRNAME
    if not base.is_dir():
        return
    for p in sorted(base.iterdir()):
        if p.is_dir():
            yield p


def _collect_pdf_texts(meeting_dir: Path) -> Tuple[str, str]:
    from governance_meeting_llm import extract_pdf_digital_text

    agenda_parts: List[str] = []
    minutes_parts: List[str] = []
    for sub, bucket in (("agenda", agenda_parts), ("minutes", minutes_parts)):
        subdir = meeting_dir / sub
        if not subdir.is_dir():
            continue
        for pdf in sorted(subdir.glob("*.pdf"))[:6]:
            try:
                text = extract_pdf_digital_text(pdf).strip()
            except Exception as exc:
                logger.warning("brief: could not read %s: %s", pdf.name, exc)
                continue
            if text:
                bucket.append(f"### {pdf.name}\n{text[:12000]}")
    return "\n\n".join(agenda_parts), "\n\n".join(minutes_parts)


BRIEF_SYSTEM = (
    "You extract structured meeting context from local-government agenda and minutes text. "
    "Return strict JSON only."
)

BRIEF_USER_TEMPLATE = """Read the combined agenda and minutes excerpts below for ONE meeting session.

Extract:
- meeting_date (YYYY-MM-DD or null)
- meeting_title (short label)
- governing_body (e.g. City Council, Planning Commission)
- members_present (array of individual names as written — officials only, not public commenters)
- staff_present (array of names if listed)
- agenda_topics (array of short topic strings)
- key_motions (array of brief motion descriptions)

Return JSON with those keys. Use empty arrays when unknown.

=== AGENDA TEXT ===
{agenda}

=== MINUTES TEXT ===
{minutes}
"""


def build_meeting_collateral_brief(
    meeting_dir: Path,
    *,
    api_key: str,
    model: str,
    client: Any = None,
) -> str:
    """
    Run text analysis on agenda + minutes PDFs; return a block to prepend to audio prompts.
    """
    agenda_text, minutes_text = _collect_pdf_texts(meeting_dir)
    if not agenda_text and not minutes_text:
        return ""

    user = BRIEF_USER_TEMPLATE.format(
        agenda=agenda_text or "(no agenda text extracted)",
        minutes=minutes_text or "(no minutes text extracted)",
    )

    try:
        from gatekeeper_triage import call_gemma_triage

        parsed, _raw = call_gemma_triage(
            client=client,
            model=model,
            system_instruction=BRIEF_SYSTEM,
            user_text=user,
            media=[],
            media_resolution_high=False,
            thinking_budget=0,
            max_output_tokens=2048,
        )
    except Exception as exc:
        logger.warning("meeting brief LLM failed: %s", exc)
        return _fallback_brief_from_text(agenda_text, minutes_text)

    if not isinstance(parsed, dict):
        return _fallback_brief_from_text(agenda_text, minutes_text)

    names = list(parsed.get("members_present") or []) + list(parsed.get("staff_present") or [])
    topics = parsed.get("agenda_topics") or []
    lines = [
        "=== MEETING DOCUMENT BRIEF (from agenda + minutes text; use for audio analysis) ===",
        f"meeting_title: {parsed.get('meeting_title') or meeting_dir.name}",
        f"meeting_date: {parsed.get('meeting_date') or 'unknown'}",
        f"governing_body: {parsed.get('governing_body') or 'unknown'}",
    ]
    if names:
        lines.append("individual_names: " + ", ".join(str(n) for n in names[:40]))
    if topics:
        lines.append("agenda_topics: " + "; ".join(str(t) for t in topics[:20]))
    motions = parsed.get("key_motions") or []
    if motions:
        lines.append("key_motions: " + "; ".join(str(m) for m in motions[:15]))
    lines.append(
        "When analyzing audio, align speaker references to these names when plausible."
    )
    lines.append("")
    return "\n".join(lines)


def _fallback_brief_from_text(agenda_text: str, minutes_text: str) -> str:
    blob = f"{agenda_text}\n{minutes_text}"[:8000]
    names = sorted(set(re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", blob)))[:25]
    lines = [
        "=== MEETING DOCUMENT BRIEF (heuristic; agenda+minutes text only) ===",
    ]
    if names:
        lines.append("possible_names: " + ", ".join(names))
    lines.append("")
    return "\n".join(lines)


def format_audio_analysis_prompt(*, policy_prompt: str, meeting_brief: str, geo_hint: str, chunk_hint: str) -> str:
    parts = []
    if meeting_brief.strip():
        parts.append(meeting_brief.strip())
    parts.append(policy_prompt)
    parts.append("---")
    parts.append(geo_hint)
    parts.append(chunk_hint)
    parts.append(
        "The attached audio is one slice of the meeting described above. "
        "Use the individual_names list when attributing speakers or votes."
    )
    return "\n\n".join(parts)
