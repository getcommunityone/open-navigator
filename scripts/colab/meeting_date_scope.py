"""
DEMO scope for Colab runs:

1. **Year folder** — only files under each jurisdiction's newest ``20xx/`` calendar
   folder (e.g. ``…/county_30097/2026/``), then
2. **Meeting dates** — only the N most recent distinct meeting dates in that year.

Used by Gatekeeper (what to triage) and the notebook inventory walker (what demos run).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm", ".mp4"}

# YYYYMMDD embedded in URLs/filenames (e.g. 20260506-Agenda.pdf).
_YYYYMMDD = re.compile(
    r"(?<![0-9])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?![0-9])"
)

_MEETINGS_FOLDER_DATE = re.compile(
    r"^(?:(\d{4}-\d{2}-\d{2})|(\d{4})_(\d{2})_(\d{2})_meeting)"
)
_MEETINGS_DATE_DIR = re.compile(r"^(20\d{2})_(\d{2})_(\d{2})$")

_CALENDAR_YEAR_FOLDER = re.compile(r"^20\d{2}$")


@dataclass(frozen=True)
class ManifestRow:
    url: str
    anchor_text: str
    doc_type: str


def normalize_meeting_date(value: Optional[str]) -> Optional[str]:
    """Return ``YYYY-MM-DD`` or ``None``."""
    if not value:
        return None
    s = str(value).strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = _YYYYMMDD.search(s.replace("-", "").replace("/", ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def parse_yyyymmdd_from_blob(blob: str) -> Optional[str]:
    """``YYYY-MM-DD`` from ``2026-04-06_…``, ``20260406``, or similar."""
    text = blob or ""
    iso = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    m = _YYYYMMDD.search(text.replace("_", "").replace("-", ""))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def is_calendar_year_folder(name: str) -> bool:
    """True for scrape layout folders like ``2026`` (not ``2026_05_06_meeting``)."""
    if not _CALENDAR_YEAR_FOLDER.fullmatch(name or ""):
        return False
    y = int(name)
    # Ignore bogus dirs (e.g. numeric IDs mis-synced as ``2034/``); allow next calendar year.
    max_y = datetime.now().year + 1
    return 2000 <= y <= max_y


def resolve_demo_year_folder_scope() -> bool:
    """
    When True (DEMO default), restrict media to the newest ``20xx/`` folder per jurisdiction.

    Set ``GOVERNANCE_DEMO_YEAR_SCOPE=0`` to disable.
    """
    if os.environ.get("GOVERNANCE_DEMO_YEAR_SCOPE", "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    if os.environ.get("GOVERNANCE_MODE", "").strip().upper() == "DEMO":
        return True
    return os.environ.get("GOVERNANCE_DEMO_YEAR_SCOPE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def calendar_year_folder_in_path(path: Path, raw_root: Path) -> Optional[str]:
    """Largest ``20xx`` path segment under ``raw_root`` (e.g. ``2026`` in ``…/2026/foo.pdf``)."""
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return None
    years = [p for p in rel.parts if is_calendar_year_folder(p)]
    return max(years) if years else None


def discover_most_recent_year_folder_per_jurisdiction(raw_root: Path) -> Dict[str, str]:
    """
    Scan jurisdiction roots only (no deep file walk) for the newest ``20xx/`` folder.

    Includes ``_gomeet_downloads/20xx`` when present.
    """
    raw_root = raw_root.resolve()
    allowed: Dict[str, str] = {}
    if not raw_root.is_dir():
        return allowed

    skip_names = {"excluded_inputs", "__pycache__"}

    for state_dir in sorted(raw_root.iterdir()):
        if not state_dir.is_dir() or state_dir.name in skip_names:
            continue
        if state_dir.name.startswith("_"):
            continue
        for scope_dir in sorted(state_dir.iterdir()):
            if not scope_dir.is_dir():
                continue
            for jur_dir in sorted(scope_dir.iterdir()):
                if not jur_dir.is_dir() or jur_dir.name.startswith("_"):
                    continue
                jur = f"{state_dir.name}/{scope_dir.name}/{jur_dir.name}"
                years: Set[str] = set()
                for child in jur_dir.iterdir():
                    if child.is_dir() and is_calendar_year_folder(child.name):
                        years.add(child.name)
                gomeet = jur_dir / "_gomeet_downloads"
                if gomeet.is_dir():
                    for child in gomeet.iterdir():
                        if child.is_dir() and is_calendar_year_folder(child.name):
                            years.add(child.name)
                if years:
                    allowed[jur] = max(years)
    return allowed


def path_matches_year_folder_scope(
    path: Path, raw_root: Path, allowed_years: Dict[str, str]
) -> bool:
    """True when the file is under the jurisdiction's newest calendar-year folder."""
    jur = jurisdiction_prefix_from_path(path, raw_root)
    if not jur or jur not in allowed_years:
        return True
    need = allowed_years[jur]
    yfolder = calendar_year_folder_in_path(path, raw_root)
    if yfolder:
        return yfolder == need
    meeting_date = infer_meeting_date_for_file(path, raw_root)
    if meeting_date:
        return meeting_date[:4] == need
    return False


def prune_year_folder_dirnames(
    dirpath: Path,
    dirnames: List[str],
    raw_root: Path,
    allowed_years: Dict[str, str],
) -> None:
    """
    In-place ``os.walk`` prune: at jurisdiction root (and ``_gomeet_downloads``),
    do not descend into older ``20xx/`` siblings.
    """
    jur = jurisdiction_prefix_from_path(dirpath, raw_root)
    if not jur or jur not in allowed_years:
        return
    keep = allowed_years[jur]
    jur_root = (raw_root / Path(*jur.split("/"))).resolve()
    here = dirpath.resolve()
    if here == jur_root or here == (jur_root / "_gomeet_downloads").resolve():
        dirnames[:] = [
            d for d in dirnames
            if not is_calendar_year_folder(d) or d == keep
        ]


def resolve_demo_meeting_dates_limit(explicit: Optional[int] = None) -> Optional[int]:
    """
    How many distinct meeting **calendar dates** to keep per jurisdiction in DEMO scope.

    ``GOVERNANCE_DEMO_MEETING_DATES`` (or legacy ``GOVERNANCE_GATEKEEPER_MAX_MEETING_DATES``).
    DEMO mode default: **3**. Set ``0`` or ``GOVERNANCE_DEMO_DATE_SCOPE=0`` to disable.
    """
    if explicit is not None:
        return explicit if explicit > 0 else None
    if os.environ.get("GOVERNANCE_DEMO_DATE_SCOPE", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return None
    for key in ("GOVERNANCE_DEMO_MEETING_DATES", "GOVERNANCE_GATEKEEPER_MAX_MEETING_DATES"):
        env = os.environ.get(key, "").strip()
        if env:
            n = int(env)
            return n if n > 0 else None
    if os.environ.get("GOVERNANCE_MODE", "").strip().upper() == "DEMO":
        return 3
    return None


def jurisdiction_prefix_from_path(path: Path, raw_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return ""
    parts = rel.parts
    if len(parts) >= 3:
        return "/".join(parts[:3])
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def _date_from_meetings_folder(path: Path, raw_root: Path) -> Optional[str]:
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return None
    if "meetings" not in rel.parts:
        return None
    idx = rel.parts.index("meetings")
    if idx + 1 >= len(rel.parts):
        return None
    folder = rel.parts[idx + 1]
    m_date = _MEETINGS_DATE_DIR.match(folder)
    if m_date:
        return f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}"
    m = _MEETINGS_FOLDER_DATE.match(folder)
    if not m:
        return None
    if m.group(1):
        return normalize_meeting_date(m.group(1))
    return f"{m.group(2)}-{m.group(3)}-{m.group(4)}"


_HASH_TOKEN_RE = re.compile(r"_([0-9a-f]{6,12})(?:_\d+)?$", re.I)
# Trailing ``_2``, ``_8`` on scrape copies of the same manifest asset.
_SCRAPE_COPY_SUFFIX_RE = re.compile(r"_(\d+)$")


@lru_cache(maxsize=64)
def _manifest_indexes(jurisdiction_root: str) -> Tuple[Dict[str, ManifestRow], Dict[str, ManifestRow]]:
    """``(by_resolved_path, by_content_hash_token)`` → manifest row."""
    root = Path(jurisdiction_root)
    manifest_path = root / "_manifest.json"
    if not manifest_path.is_file():
        return {}, {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read %s: %s", manifest_path, exc)
        return {}, {}
    by_path: Dict[str, ManifestRow] = {}
    by_hash: Dict[str, ManifestRow] = {}
    for key in ("pdfs", "recordings", "videos", "audio"):
        for entry in data.get(key) or []:
            if not isinstance(entry, dict):
                continue
            p = entry.get("path")
            if not p:
                continue
            row = ManifestRow(
                url=str(entry.get("url") or ""),
                anchor_text=str(entry.get("anchor_text") or ""),
                doc_type=str(entry.get("doc_type") or "unknown"),
            )
            resolved = str(Path(p).resolve())
            by_path[resolved] = row
            hm = _HASH_TOKEN_RE.search(Path(p).stem)
            if hm:
                by_hash[hm.group(1).lower()] = row
    return by_path, by_hash


def _lookup_manifest_row(path: Path, jur_root: Path) -> Optional[ManifestRow]:
    by_path, by_hash = _manifest_indexes(str(jur_root.resolve()))
    resolved = str(path.resolve())
    if resolved in by_path:
        return by_path[resolved]
    hm = _HASH_TOKEN_RE.search(path.stem)
    if hm:
        return by_hash.get(hm.group(1).lower())
    return None


def infer_meeting_date_for_file(path: Path, raw_root: Path) -> Optional[str]:
    """Best-effort ``YYYY-MM-DD`` for a file under ``raw_root``."""
    folder_date = _date_from_meetings_folder(path, raw_root)
    if folder_date:
        return folder_date

    jur = jurisdiction_prefix_from_path(path, raw_root)
    if jur:
        jur_root = raw_root / Path(*jur.split("/"))
        row = _lookup_manifest_row(path, jur_root)
        if row:
            d = parse_yyyymmdd_from_blob(row.url) or parse_yyyymmdd_from_blob(
                Path(row.url).name
            )
            if d:
                return d
            try:
                from scripts.discovery.meeting_document_naming import pick_meeting_date

                picked, _ = pick_meeting_date(
                    url=row.url,
                    anchor=row.anchor_text,
                    doc_type=row.doc_type or None,
                )
                if picked:
                    return picked.isoformat()
            except Exception:
                pass

    d = parse_yyyymmdd_from_blob(path.name) or parse_yyyymmdd_from_blob(path.stem)
    if d:
        return d

    try:
        from meeting_grouping import infer_meeting_date_from_path

        return infer_meeting_date_from_path(path)
    except Exception:
        return None


def file_media_role(path: Path, raw_root: Path) -> Optional[str]:
    """
    ``pdf`` | ``audio`` | ``collateral`` | ``None`` (out of demo media scope).

    Collateral: under ``…/collateral/``, or non-agenda/minutes PDFs with a known meeting date.
    """
    ext = path.suffix.lower()
    try:
        rel = path.relative_to(raw_root.resolve())
    except ValueError:
        rel = path

    if "collateral" in rel.parts and ext in PDF_EXTS:
        return "collateral"

    if ext in AUDIO_EXTS:
        return "audio"

    if ext not in PDF_EXTS:
        return None

    jur = jurisdiction_prefix_from_path(path, raw_root)
    doc_type = ""
    if jur:
        row = _lookup_manifest_row(path, raw_root / Path(*jur.split("/")))
        if row:
            doc_type = (row.doc_type or "").lower()

    stem = path.stem.lower()
    if doc_type in ("agenda", "minutes"):
        return "pdf"
    if "agenda" in stem or "minutes" in stem:
        return "pdf"
    if infer_meeting_date_for_file(path, raw_root):
        return "collateral"
    return None


def content_identity_key(path: Path, raw_root: Path) -> str:
    """
    Stable id for one logical document (agenda/minutes/audio).

    Scrape duplicates share a hex token (``…_a5fb5b7c_8.pdf`` → ``a5fb5b7c``).
    """
    role = file_media_role(path, raw_root) or "file"
    hm = _HASH_TOKEN_RE.search(path.stem)
    if hm:
        return f"{role}:{hm.group(1).lower()}"
    stem = _SCRAPE_COPY_SUFFIX_RE.sub("", path.stem).lower()
    return f"{role}:{stem}"


def dedupe_scrape_copies(paths: Sequence[Path], raw_root: Path) -> List[Path]:
    """Keep one file per (jurisdiction, meeting date, logical document)."""
    best: Dict[Tuple[str, str, str], Path] = {}
    for path in paths:
        jur = jurisdiction_prefix_from_path(path, raw_root)
        date_s = infer_meeting_date_for_file(path, raw_root) or ""
        ident = content_identity_key(path, raw_root)
        key = (jur, date_s, ident)
        prev = best.get(key)
        if prev is None:
            best[key] = path
            continue
        try:
            if path.stat().st_mtime >= prev.stat().st_mtime:
                best[key] = path
        except OSError:
            best[key] = path
    return sorted(best.values(), key=lambda p: p.as_posix())


def _allowed_dates_per_jurisdiction(
    paths: Sequence[Path],
    raw_root: Path,
    *,
    max_dates: int,
) -> Dict[str, Set[str]]:
    """Map jurisdiction prefix → set of the ``max_dates`` most recent meeting dates."""
    dates_by_jur: Dict[str, Set[str]] = {}
    for path in paths:
        role = file_media_role(path, raw_root)
        if role is None:
            continue
        d = infer_meeting_date_for_file(path, raw_root)
        if not d:
            continue
        jur = jurisdiction_prefix_from_path(path, raw_root)
        dates_by_jur.setdefault(jur, set()).add(d)

    allowed: Dict[str, Set[str]] = {}
    for jur, dates in dates_by_jur.items():
        ordered = sorted(dates)
        allowed[jur] = set(ordered[-max_dates:])
    return allowed


def filter_paths_by_recent_meeting_dates(
    paths: Sequence[Path],
    raw_root: Path,
    *,
    max_dates: Optional[int] = None,
) -> Tuple[List[Path], int, Dict[str, Set[str]]]:
    """
    Keep only pdf / audio / collateral files whose meeting date is among the
    ``max_dates`` most recent per jurisdiction.

    Returns ``(selected, total_candidates, allowed_dates_by_jurisdiction)``.
    """
    cap = resolve_demo_meeting_dates_limit(max_dates)
    candidates = [p for p in paths if file_media_role(p, raw_root) is not None]

    if resolve_demo_year_folder_scope():
        allowed_years = discover_most_recent_year_folder_per_jurisdiction(raw_root)
        if allowed_years:
            before_year = len(candidates)
            candidates = [
                p
                for p in candidates
                if path_matches_year_folder_scope(p, raw_root, allowed_years)
            ]
            logger.info(
                "Year folder scope | %d → %d media file(s) | newest calendar folder per jurisdiction",
                before_year,
                len(candidates),
            )
            for jur, year in sorted(allowed_years.items()):
                logger.info("  %s → %s/", jur, year)
        else:
            logger.warning(
                "Year folder scope enabled but no 20xx/ folders found under %s",
                raw_root,
            )

    total = len(candidates)
    if cap is None:
        return list(candidates), total, {}

    allowed = _allowed_dates_per_jurisdiction(candidates, raw_root, max_dates=cap)
    if not allowed:
        logger.warning(
            "Date scope: no meeting dates inferred under %s — keeping all %d media files",
            raw_root,
            total,
        )
        return list(candidates), total, {}

    selected: List[Path] = []
    for path in sorted(candidates, key=lambda p: p.as_posix()):
        jur = jurisdiction_prefix_from_path(path, raw_root)
        d = infer_meeting_date_for_file(path, raw_root)
        if d and jur in allowed and d in allowed[jur]:
            selected.append(path)

    before_dedupe = len(selected)
    selected = dedupe_scrape_copies(selected, raw_root)
    if before_dedupe != len(selected):
        logger.info(
            "Date scope dedupe | %d files → %d unique documents (dropped scrape copies)",
            before_dedupe,
            len(selected),
        )

    return selected, total, allowed


def filter_inventory_media(
    pdfs: List[Path],
    audio: List[Path],
    raw_root: Path,
    jurisdiction_root: Path,
    *,
    max_dates: Optional[int] = None,
) -> Tuple[List[Path], List[Path]]:
    """Filter demo inventory lists to recent meeting dates (pdfs + collateral + audio)."""
    all_paths = list(pdfs) + list(audio)
    selected, _, _ = filter_paths_by_recent_meeting_dates(
        all_paths, raw_root, max_dates=max_dates
    )
    sel_set = {p.resolve() for p in selected}
    new_pdfs = [p for p in pdfs if p.resolve() in sel_set]
    new_audio = [p for p in audio if p.resolve() in sel_set]
    return new_pdfs, new_audio
