"""
Group meeting media into per-session folders and build agenda+minutes briefs for audio.

Layout under each jurisdiction::

    meetings/{YYYY_MM_DD}/                   # calendar day
        {instance_slug}/                    # e.g. city-council, planning-commission
            agenda/
            minutes/
            collateral/
            audio/

Legacy flat folders ``{YYYY_MM_DD}_meeting`` / ``_meeting_2`` are still recognized when reading paths.

Demo 4 prepends :func:`build_meeting_collateral_brief` (names, topics, title) to the
audio analysis prompt via :func:`format_audio_analysis_prompt`.
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

# Legacy: ``2026_05_06_meeting`` or ``2026_05_06_meeting_2``
_MEETING_FOLDER_RE = re.compile(
    r"^(20\d{2})_(\d{2})_(\d{2})_meeting(?:_(\d+))?$"
)
# New: ``2026_05_06`` date folder under ``meetings/``
_MEETING_DATE_DIR_RE = re.compile(r"^(20\d{2})_(\d{2})_(\d{2})$")

_GENERIC_INSTANCE_SLUGS = frozenset({
    "meeting",
    "session",
    "agenda-session",
    "board-meeting",
    "undated",
})

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
    """Best-effort ``YYYY-MM-DD`` from filename (``2026-04-06_…``, ``20260406``, etc.)."""
    stem = path.stem
    iso = re.match(r"^(20\d{2})-(\d{2})-(\d{2})(?:\b|_)", stem)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    compact = re.search(r"(20\d{2})(\d{2})(\d{2})", stem.replace("_", "").replace("-", ""))
    if compact:
        return f"{compact.group(1)}-{compact.group(2)}-{compact.group(3)}"
    try:
        from scripts.discovery.meeting_document_naming import pick_meeting_date

        d, _ = pick_meeting_date(url="", anchor=stem.replace("_", " "))
        return d.isoformat() if d else None
    except Exception:
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

    folder_basename: str = ""

    @property
    def folder_name(self) -> str:
        if self.folder_basename:
            return self.folder_basename
        return meeting_session_folder_relpath(self.meeting_date, self.instance_slug)


def meeting_date_dir_name(meeting_date: str) -> str:
    """``2026-05-06`` → ``2026_05_06`` (parent folder under ``meetings/``)."""
    d = (meeting_date or "undated").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return d.replace("-", "_")
    return "undated"


def meeting_session_folder_relpath(meeting_date: str, instance_slug: str) -> str:
    """Relative path under ``meetings/``: ``2026_05_06/city-council``."""
    slug = slugify_meeting_label(instance_slug or "session")
    return f"{meeting_date_dir_name(meeting_date)}/{slug}"


def meeting_folder_basename(meeting_date: str, sequence: int = 1) -> str:
    """Legacy flat name — prefer :func:`meeting_session_folder_relpath`."""
    d = (meeting_date or "undated").strip()
    if d == "undated" or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        slug = "undated_meeting" if sequence <= 1 else f"undated_meeting_{sequence}"
        return slug
    underscored = d.replace("-", "_")
    if sequence <= 1:
        return f"{underscored}_meeting"
    return f"{underscored}_meeting_{sequence}"


def assign_meeting_folder_basenames(groups: List[MeetingInstanceGroup]) -> None:
    """``{YYYY_MM_DD}/{instance_slug}``; duplicate slugs same day get ``-2``, ``-3``, …"""
    buckets: Dict[Tuple[str, str], List[MeetingInstanceGroup]] = {}
    for g in groups:
        buckets.setdefault((g.jurisdiction_prefix, g.meeting_date), []).append(g)
    for items in buckets.values():
        used: Dict[str, int] = {}
        items.sort(key=lambda g: (g.instance_slug, g.meeting_title))
        for g in items:
            slug = slugify_meeting_label(g.instance_slug or "session")
            if slug in used:
                used[slug] += 1
                slug = f"{slug}-{used[slug]}"
            else:
                used[slug] = 1
            g.folder_basename = meeting_session_folder_relpath(g.meeting_date, slug)
            g.instance_slug = slug


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
    date_s = (meeting_date or "").strip() or infer_meeting_date_from_path(path) or ""
    date_s = date_s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_s) else ""
    if not date_s:
        try:
            from meeting_date_scope import normalize_meeting_date, parse_yyyymmdd_from_blob

            date_s = normalize_meeting_date(parse_yyyymmdd_from_blob(path.name)) or ""
        except ImportError:
            pass
    if not date_s:
        date_s = "undated"
    title = (meeting_title or "").strip() or infer_instance_slug_from_path(path, doc_type).replace("-", " ").title()
    slug = (instance_slug or "").strip() or slugify_meeting_label(title)
    if slug in ("meeting", "undated") or len(slug) < 3:
        slug = infer_instance_slug_from_path(path, doc_type)
    if not (instance_slug or "").strip():
        if doc_type in ("meeting_agenda", "meeting_minutes", "meeting_audio"):
            inferred = slugify_meeting_label(slug)
            if inferred in _GENERIC_INSTANCE_SLUGS or "agenda" in inferred:
                slug = "session"
    slug = slugify_meeting_label(slug)
    key = f"{jur}|{date_s}|{slug}"
    return key, date_s, slug, title


def meeting_ai_identity_enabled() -> bool:
    """Use AI (PDF page 1–2 text + audio triage cues) to cluster same-day files."""
    return os.environ.get("GOVERNANCE_MEETING_AI_IDENTITY", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _doc_type_is_agenda(doc_type: str) -> bool:
    return (doc_type or "").lower() in ("meeting_agenda",)


def _doc_type_is_minutes(doc_type: str) -> bool:
    return (doc_type or "").lower() in ("meeting_minutes",)


def _doc_type_is_audio(doc_type: str) -> bool:
    return (doc_type or "").lower() in (
        "meeting_audio",
        "meeting_video",
        "audio_recording",
        "audio_transcript",
    )


@dataclass
class _FileMeetingEvidence:
    path: Path
    doc_type: str
    rel_path: str
    excerpt: str
    meeting_title: Optional[str] = None
    instance_slug: Optional[str] = None
    verdict: Any = None


def _gather_file_evidence(
    path: Path,
    raw_root: Path,
    verdict: Any = None,
) -> _FileMeetingEvidence:
    """First pages of PDFs or Gatekeeper audio/PDF triage text for same-day identity."""
    rel = ""
    try:
        rel = path.resolve().relative_to(raw_root.resolve()).as_posix()
    except ValueError:
        rel = path.name

    doc_type = (
        getattr(verdict, "document_or_audio_type", None) if verdict else None
    ) or doc_type_for_path(path, raw_root)
    title = getattr(verdict, "meeting_title", None) if verdict else None
    slug = getattr(verdict, "meeting_instance_slug", None) if verdict else None
    excerpt = ""

    if verdict and (getattr(verdict, "reasoning", None) or "").strip():
        excerpt = str(verdict.reasoning).strip()[:2000]
    if path.suffix.lower() == ".pdf":
        try:
            from gatekeeper_triage import extract_first_pages_text

            page_text = extract_first_pages_text(path, pages=2).strip()
            if page_text:
                excerpt = (excerpt + "\n\n" + page_text).strip() if excerpt else page_text[:2500]
        except Exception as exc:
            logger.debug("PDF excerpt for identity failed (%s): %s", path.name, exc)
    elif _doc_type_is_audio(doc_type):
        if not excerpt:
            excerpt = f"(audio file {path.name}; use structural meeting cues if triaged)"

    return _FileMeetingEvidence(
        path=path,
        doc_type=doc_type,
        rel_path=rel,
        excerpt=excerpt or f"({doc_type}, {path.name})",
        meeting_title=title,
        instance_slug=slug,
        verdict=verdict,
    )


_SAME_DAY_IDENTITY_SYSTEM = (
    "You cluster local-government meeting files from the SAME jurisdiction and calendar day. "
    "Return strict JSON only.\n\n"
    "Default rule: at most one agenda and one minutes on the same day is almost always "
    "ONE meeting session — put agenda, minutes, and any audio in the same cluster.\n"
    "Only create multiple clusters when excerpts clearly show different governing bodies "
    "or distinct official sessions (e.g. City Council vs Planning Commission)."
)

_SAME_DAY_IDENTITY_USER = """Calendar day: {meeting_date}
Jurisdiction path prefix: {jurisdiction}

Numbered files (type + excerpt from page 1–2 or audio triage):

{file_block}

Return JSON:
{{
  "meetings": [
    {{
      "instance_slug": "city-council",
      "meeting_title": "City Council Regular Meeting",
      "file_indexes": [1, 2, 3]
    }}
  ]
}}

Use snake_case instance_slug. Every file index must appear in exactly one cluster.
"""


def _default_same_day_clusters(evidence: Sequence[_FileMeetingEvidence]) -> List[List[int]]:
    """One meeting when ≤1 agenda and ≤1 minutes (general assumption)."""
    if not evidence:
        return []
    agenda_idx = [i for i, e in enumerate(evidence) if _doc_type_is_agenda(e.doc_type)]
    minutes_idx = [i for i, e in enumerate(evidence) if _doc_type_is_minutes(e.doc_type)]
    if len(agenda_idx) <= 1 and len(minutes_idx) <= 1:
        return [list(range(len(evidence)))]
    return []


def _ai_same_day_clusters(
    evidence: Sequence[_FileMeetingEvidence],
    *,
    client: Any,
    model: str,
    meeting_date: str,
    jurisdiction_prefix: str,
) -> List[List[int]]:
    lines: List[str] = []
    for i, ev in enumerate(evidence, start=1):
        lines.append(
            f"{i}. [{ev.doc_type}] {ev.rel_path}\n"
            f"   gatekeeper_slug={ev.instance_slug or '—'} title={ev.meeting_title or '—'}\n"
            f"   excerpt: {ev.excerpt[:1200]}"
        )
    user = _SAME_DAY_IDENTITY_USER.format(
        meeting_date=meeting_date,
        jurisdiction=jurisdiction_prefix or "(root)",
        file_block="\n\n".join(lines),
    )
    try:
        from gatekeeper_triage import call_gemma_triage

        parsed, _raw = call_gemma_triage(
            client=client,
            model=model,
            system_instruction=_SAME_DAY_IDENTITY_SYSTEM,
            user_text=user,
            media=[],
            media_resolution_high=False,
            thinking_budget=0,
            timeout_seconds=int(os.environ.get("GOVERNANCE_MEETING_IDENTITY_TIMEOUT_SECONDS", "90")),
        )
    except Exception as exc:
        logger.warning("same-day meeting identity AI failed: %s", exc)
        return []

    if not isinstance(parsed, dict):
        return []
    meetings = parsed.get("meetings")
    if not isinstance(meetings, list):
        return []

    n = len(evidence)
    clusters: List[List[int]] = []
    assigned: set[int] = set()
    for m in meetings:
        if not isinstance(m, dict):
            continue
        raw_indexes = m.get("file_indexes") or m.get("files") or []
        if not isinstance(raw_indexes, list):
            continue
        idxs: List[int] = []
        for x in raw_indexes:
            try:
                j = int(x) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= j < n and j not in assigned:
                idxs.append(j)
                assigned.add(j)
        if idxs:
            clusters.append(idxs)
    for j in range(n):
        if j not in assigned:
            clusters.append([j])
    return clusters


def _groups_from_clusters(
    *,
    clusters: List[List[int]],
    evidence: Sequence[_FileMeetingEvidence],
    jurisdiction_prefix: str,
    meeting_date: str,
    source_groups: Sequence[MeetingInstanceGroup],
) -> List[MeetingInstanceGroup]:
    verdict_by_path: Dict[Path, Any] = {}
    for g in source_groups:
        for v in g.verdicts:
            p = Path(getattr(v, "file_path", ""))
            if p.is_file():
                verdict_by_path[p.resolve()] = v

    out: List[MeetingInstanceGroup] = []
    for cluster in clusters:
        if not cluster:
            continue
        slug = "session"
        title = "Meeting"
        for j in cluster:
            ev = evidence[j]
            if ev.instance_slug and slugify_meeting_label(ev.instance_slug) not in _GENERIC_INSTANCE_SLUGS:
                slug = slugify_meeting_label(ev.instance_slug)
            if ev.meeting_title:
                title = ev.meeting_title
        g = MeetingInstanceGroup(
            key=f"{jurisdiction_prefix}|{meeting_date}|{slug}",
            meeting_date=meeting_date,
            instance_slug=slug,
            meeting_title=title,
            jurisdiction_prefix=jurisdiction_prefix,
        )
        for j in cluster:
            ev = evidence[j]
            g.files.append(ev.path)
            v = ev.verdict or verdict_by_path.get(ev.path.resolve())
            if v is not None:
                g.verdicts.append(v)
        out.append(g)
    return out


def resolve_same_day_meeting_groups(
    groups: List[MeetingInstanceGroup],
    raw_root: Path,
    *,
    client: Any = None,
    model: Optional[str] = None,
) -> List[MeetingInstanceGroup]:
    """
    Cluster files on the same calendar day using AI excerpts + default 1 agenda / 1 minutes rule.
    """
    if not groups:
        return groups

    if client is None or not model:
        client, model = _optional_identity_client_and_model()

    by_day: Dict[Tuple[str, str], List[MeetingInstanceGroup]] = {}
    for g in groups:
        by_day.setdefault((g.jurisdiction_prefix, g.meeting_date), []).append(g)

    resolved: List[MeetingInstanceGroup] = []
    for (jur, date_s), day_groups in sorted(by_day.items()):
        evidence: List[_FileMeetingEvidence] = []
        seen: set[Path] = set()
        for g in day_groups:
            for p in g.files:
                rp = p.resolve()
                if rp in seen:
                    continue
                seen.add(rp)
                v = None
                for ver in g.verdicts:
                    if Path(getattr(ver, "file_path", "")).resolve() == rp:
                        v = ver
                        break
                evidence.append(_gather_file_evidence(p, raw_root, v))

        if len(evidence) <= 1:
            resolved.extend(day_groups if len(day_groups) == 1 else _groups_from_clusters(
                [[0]], evidence, jur, date_s, day_groups
            ))
            continue

        clusters: List[List[int]] = []
        if meeting_ai_identity_enabled() and client and model:
            clusters = _ai_same_day_clusters(
                evidence,
                client=client,
                model=model,
                meeting_date=date_s,
                jurisdiction_prefix=jur,
            )
        if not clusters:
            clusters = _default_same_day_clusters(evidence)
        if not clusters:
            resolved.extend(consolidate_same_day_groups(day_groups, raw_root))
            continue

        logger.info(
            "same-day identity | %s | %s | %d file(s) → %d meeting cluster(s)",
            jur or "(root)",
            date_s,
            len(evidence),
            len(clusters),
        )
        resolved.extend(
            _groups_from_clusters(
                clusters=clusters,
                evidence=evidence,
                jurisdiction_prefix=jur,
                meeting_date=date_s,
                source_groups=day_groups,
            )
        )

    return sorted(
        resolved,
        key=lambda g: (g.jurisdiction_prefix, g.meeting_date, g.instance_slug),
    )


def _optional_identity_client_and_model() -> Tuple[Any, Optional[str]]:
    key = (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )
    if not key:
        return None, None
    try:
        from gatekeeper_triage import (
            _GEMMA_GATEKEEPER_AI_FALLBACKS,
            _build_genai_client,
            resolve_model_id,
        )

        client = _build_genai_client(key)
        requested = os.environ.get("GOVERNANCE_GATEKEEPER_MODEL", "gemma-3n-e2b-it").strip()
        model = resolve_model_id(
            client,
            requested,
            fallbacks=_GEMMA_GATEKEEPER_AI_FALLBACKS,
            role="Meeting identity",
        )
        return client, model
    except Exception as exc:
        logger.warning("Could not build client for meeting identity: %s", exc)
        return None, None


def consolidate_same_day_groups(
    groups: List[MeetingInstanceGroup], raw_root: Path
) -> List[MeetingInstanceGroup]:
    """
    Merge same-day groups that were split only because filenames lacked a body slug
    (e.g. agenda PDF vs minutes PDF → one ``session`` folder).
    """
    del raw_root  # reserved for future manifest-aware merges
    buckets: Dict[Tuple[str, str], List[MeetingInstanceGroup]] = {}
    for g in groups:
        buckets.setdefault((g.jurisdiction_prefix, g.meeting_date), []).append(g)
    out: List[MeetingInstanceGroup] = []
    for _key, items in buckets.items():
        if len(items) <= 1:
            out.extend(items)
            continue
        specific = [
            g
            for g in items
            if slugify_meeting_label(g.instance_slug) not in _GENERIC_INSTANCE_SLUGS
        ]
        generic = [g for g in items if g not in specific]
        if len(specific) >= 2:
            out.extend(items)
            continue
        if len(specific) == 1 and generic:
            target = specific[0]
            for g in generic:
                target.files.extend(g.files)
                target.verdicts.extend(g.verdicts)
            out.append(target)
            continue
        if len(items) >= 2 and not specific:
            merged = items[0]
            for g in items[1:]:
                merged.files.extend(g.files)
                merged.verdicts.extend(g.verdicts)
            merged.instance_slug = slugify_meeting_label(
                merged.meeting_title or merged.instance_slug or "session"
            )
            if merged.instance_slug in _GENERIC_INSTANCE_SLUGS:
                merged.instance_slug = "session"
            out.append(merged)
            continue
        out.extend(items)
    return out


def group_proceed_verdicts(
    verdicts: Sequence[Any],
    raw_root: Path,
    *,
    client: Any = None,
    model: Optional[str] = None,
) -> List[MeetingInstanceGroup]:
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
    groups = sorted(
        buckets.values(),
        key=lambda g: (g.jurisdiction_prefix, g.meeting_date, g.instance_slug),
    )
    groups = resolve_same_day_meeting_groups(
        groups, raw_root, client=client, model=model
    )
    assign_meeting_folder_basenames(groups)
    return groups


def _path_already_in_session_folder(rel: Path) -> bool:
    """True when file is already under ``meetings/{date}/{slug}/…`` (not ``undated_meeting``)."""
    if MEETINGS_DIRNAME not in rel.parts:
        return False
    midx = rel.parts.index(MEETINGS_DIRNAME)
    rest = rel.parts[midx + 1 :]
    if not rest:
        return False
    if rest[0].startswith("undated"):
        return False
    if _MEETING_DATE_DIR_RE.match(rest[0]) and len(rest) >= 3:
        return True
    if _MEETING_FOLDER_RE.match(rest[0]) and len(rest) >= 2:
        return True
    return False


def doc_type_for_path(path: Path, raw_root: Path) -> str:
    """Map a filesystem path to Gatekeeper-style document types for subfolders."""
    try:
        from meeting_date_scope import file_media_role, jurisdiction_prefix_from_path

        role = file_media_role(path, raw_root)
        if role == "audio":
            return "meeting_audio"
        jur = jurisdiction_prefix_from_path(path, raw_root)
        if jur:
            from meeting_date_scope import _lookup_manifest_row

            row = _lookup_manifest_row(path, raw_root / Path(*jur.split("/")))
            if row:
                dt = (row.doc_type or "").lower()
                if dt == "agenda":
                    return "meeting_agenda"
                if dt == "minutes":
                    return "meeting_minutes"
    except ImportError:
        pass
    stem = path.stem.lower()
    if any(x in stem for x in (".mp3", ".mp4", ".wav", ".m4a")) or path.suffix.lower() in {
        ".mp3",
        ".wav",
        ".m4a",
        ".mp4",
        ".webm",
    }:
        return "meeting_audio"
    if "minutes" in stem:
        return "meeting_minutes"
    if "agenda" in stem:
        return "meeting_agenda"
    return "other_governance_document"


def group_paths_for_organization(
    paths: Sequence[Path], raw_root: Path
) -> List[MeetingInstanceGroup]:
    """Group loose files (post–date-scope inventory) into meeting instances."""
    buckets: Dict[str, MeetingInstanceGroup] = {}
    raw_root = raw_root.resolve()
    for path in paths:
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(raw_root)
        except ValueError:
            continue
        if _path_already_in_session_folder(rel):
            continue
        doc_type = doc_type_for_path(path, raw_root)
        inferred_date: Optional[str] = None
        try:
            from meeting_date_scope import infer_meeting_date_for_file, normalize_meeting_date

            inferred_date = infer_meeting_date_for_file(path, raw_root)
            inferred_date = normalize_meeting_date(inferred_date)
        except ImportError:
            inferred_date = infer_meeting_date_from_path(path)
        key, date_s, slug, title = meeting_instance_key(
            rel_path=rel.as_posix(),
            doc_type=doc_type,
            meeting_date=inferred_date,
            meeting_title=None,
            instance_slug=None,
        )
        if key not in buckets:
            buckets[key] = MeetingInstanceGroup(
                key=key,
                meeting_date=date_s,
                instance_slug=slug,
                meeting_title=title,
                jurisdiction_prefix=jurisdiction_prefix_from_relative(rel.as_posix()),
            )
        buckets[key].files.append(path)
    groups = sorted(
        buckets.values(),
        key=lambda g: (g.jurisdiction_prefix, g.meeting_date, g.instance_slug),
    )
    groups = resolve_same_day_meeting_groups(
        groups, raw_root, client=client, model=model
    )
    assign_meeting_folder_basenames(groups)
    return groups


def _subdir_for_doc_type(doc_type: str) -> str:
    return _DOC_SUBDIR.get((doc_type or "").strip().lower(), "collateral")


def _move_into_meeting_groups(
    raw_root: Path,
    groups: Sequence[MeetingInstanceGroup],
    *,
    dry_run: bool = False,
) -> List[Tuple[Path, Path]]:
    """Shared mover for verdict- or path-grouped meetings."""
    raw_root = raw_root.resolve()
    moves: List[Tuple[Path, Path]] = []
    for group in groups:
        meeting_root = (
            raw_root / group.jurisdiction_prefix / MEETINGS_DIRNAME / group.folder_name
        )
        items: List[Tuple[Path, str]] = []
        if group.verdicts:
            for v in group.verdicts:
                src = Path(getattr(v, "file_path", ""))
                if not src.is_file():
                    continue
                sub = _subdir_for_doc_type(getattr(v, "document_or_audio_type", "other"))
                items.append((src, sub))
        else:
            for src in group.files:
                if not src.is_file():
                    continue
                doc_type = doc_type_for_path(src, raw_root)
                sub = _subdir_for_doc_type(doc_type)
                items.append((src, sub))
        for src, sub in items:
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


def organize_proceed_into_meeting_folders(
    raw_root: Path,
    verdicts: Sequence[Any],
    *,
    dry_run: bool = False,
    client: Any = None,
    model: Optional[str] = None,
) -> List[Tuple[Path, Path]]:
    """
    Move Gatekeeper **proceed** files under ``…/meetings/{YYYY_MM_DD}/{slug}/…``.
    """
    groups = group_proceed_verdicts(
        verdicts, raw_root, client=client, model=model
    )
    return _move_into_meeting_groups(raw_root, groups, dry_run=dry_run)


def organize_paths_into_meeting_folders(
    raw_root: Path,
    paths: Sequence[Path],
    *,
    dry_run: bool = False,
) -> List[Tuple[Path, Path]]:
    """Organize flat inventory files into ``meetings/{YYYY_MM_DD}/{slug}/…``."""
    groups = group_paths_for_organization(paths, raw_root)
    return _move_into_meeting_groups(raw_root, groups, dry_run=dry_run)


def apply_path_moves_to_inventories(
    inventories: Sequence[Any], moves: Sequence[Tuple[Path, Path]]
) -> None:
    """Update ``MeetingInventory`` paths after :func:`organize_paths_into_meeting_folders`."""
    mapping = {src.resolve(): dest for src, dest in moves}

    def _map_list(paths: List[Path]) -> List[Path]:
        out: List[Path] = []
        for p in paths:
            out.append(mapping.get(p.resolve(), p))
        return out

    for inv in inventories:
        inv.pdfs = _map_list(list(inv.pdfs))
        inv.audio = _map_list(list(inv.audio))


def organize_inventory_into_meeting_folders(
    raw_root: Path,
    inventories: Sequence[Any],
    *,
    dry_run: bool = False,
) -> List[Tuple[Path, Path]]:
    """Organize all inventoried PDFs/audio; refresh inventory paths in place."""
    paths: List[Path] = []
    for inv in inventories:
        paths.extend(inv.pdfs)
        paths.extend(inv.audio)
    moves = organize_paths_into_meeting_folders(raw_root, paths, dry_run=dry_run)
    if not dry_run:
        apply_path_moves_to_inventories(inventories, moves)
    return moves


def meeting_dir_for_media_file(media_path: Path, raw_root: Path) -> Optional[Path]:
    """If under ``meetings/{date}/{slug}/…`` or legacy ``meetings/{date}_meeting/…``, return session dir."""
    try:
        rel = media_path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return None
    if MEETINGS_DIRNAME not in rel.parts:
        return None
    idx = rel.parts.index(MEETINGS_DIRNAME)
    if len(rel.parts) < idx + 2:
        return None
    first = rel.parts[idx + 1]
    if _MEETING_DATE_DIR_RE.match(first) and len(rel.parts) >= idx + 3:
        return raw_root.joinpath(*rel.parts[: idx + 3])
    if _MEETING_FOLDER_RE.match(first) or first.startswith("20"):
        return raw_root.joinpath(*rel.parts[: idx + 2])
    return None


def resolve_meeting_dir(media_path: Path, raw_root: Path) -> Optional[Path]:
    """
    Meeting folder for brief + audio pairing.

    Uses path if already under ``meetings/``; otherwise finds
    ``meetings/{YYYY_MM_DD_meeting*}`` with matching calendar date and agenda/minutes.
    """
    direct = meeting_dir_for_media_file(media_path, raw_root)
    if direct is not None:
        return direct
    try:
        from meeting_date_scope import infer_meeting_date_for_file, jurisdiction_prefix_from_path
    except ImportError:
        infer_meeting_date_for_file = infer_meeting_date_from_path  # type: ignore
        jurisdiction_prefix_from_path = lambda p, r: jurisdiction_prefix_from_relative(  # type: ignore
            str(p.relative_to(r)) if p.is_relative_to(r) else ""
        )

    date_s = infer_meeting_date_for_file(media_path, raw_root)
    if not date_s or date_s == "undated":
        return None
    jur = jurisdiction_prefix_from_path(media_path, raw_root)
    if not jur:
        return None
    date_dir = meeting_date_dir_name(date_s)
    base = raw_root / Path(*jur.split("/")) / MEETINGS_DIRNAME
    if not base.is_dir():
        return None
    candidates: List[Path] = []
    nested = base / date_dir
    if nested.is_dir():
        candidates.extend(p for p in nested.iterdir() if p.is_dir())
    legacy_prefix = date_s.replace("-", "_") + "_meeting"
    candidates.extend(
        p for p in base.iterdir() if p.is_dir() and p.name.startswith(legacy_prefix)
    )
    if not candidates:
        return None

    def _score(p: Path) -> Tuple[int, int, str]:
        has_a = bool(list((p / "agenda").glob("*.pdf"))) if (p / "agenda").is_dir() else False
        has_m = bool(list((p / "minutes").glob("*.pdf"))) if (p / "minutes").is_dir() else False
        return (int(has_a and has_m), int(has_a or has_m), p.name)

    return max(candidates, key=_score)


def iter_meeting_dirs(raw_root: Path, jurisdiction_prefix: str) -> Iterable[Path]:
    """Yield session folders (``meetings/{date}/{slug}`` or legacy flat names)."""
    base = raw_root / jurisdiction_prefix / MEETINGS_DIRNAME
    if not base.is_dir():
        return
    for p in sorted(base.iterdir()):
        if not p.is_dir():
            continue
        if _MEETING_DATE_DIR_RE.match(p.name):
            for session in sorted(p.iterdir()):
                if session.is_dir():
                    yield session
        elif _MEETING_FOLDER_RE.match(p.name) or p.name.startswith("20"):
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
    cache_path: Optional[Path] = None,
) -> str:
    """
    Combine agenda + minutes PDF text → names, topics, meeting title for audio prompts.

    Writes ``meeting_brief.txt`` under ``meeting_dir`` when extraction succeeds.
    """
    if cache_path is None:
        cache_path = meeting_dir / "meeting_brief.txt"
    if cache_path.is_file():
        cached = cache_path.read_text(encoding="utf-8").strip()
        if cached:
            return cached + "\n"

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
    brief = "\n".join(lines)
    try:
        cache_path.write_text(brief, encoding="utf-8")
    except OSError as exc:
        logger.warning("could not cache meeting brief: %s", exc)
    return brief


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
