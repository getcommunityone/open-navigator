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
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

PDF_EXTS = {".pdf"}
try:
    from .governance_meeting_llm import AUDIO_EXTS
except ImportError:
    AUDIO_EXTS = {
        ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
        ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
    }

# YYYYMMDD embedded in URLs/filenames (e.g. 20260506-Agenda.pdf).
_YYYYMMDD = re.compile(
    r"(?<![0-9])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?![0-9])"
)

_MEETINGS_FOLDER_DATE = re.compile(
    r"^(?:(\d{4}-\d{2}-\d{2})|(\d{4})_(\d{2})_(\d{2})_meeting)"
)
_MEETINGS_DATE_DIR = re.compile(r"^(20\d{2})_(\d{2})_(\d{2})$")

_CALENDAR_YEAR_FOLDER = re.compile(r"^20\d{2}$")

_MONTH_WORD_TO_NUM = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH_DAY_YEAR_TEXT = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"\s+([0-3]?\d)(?:st|nd|rd|th)?,?\s*((?:19|20)\d{2})\b",
    re.I,
)
_MEETING_AGENDA_HEADING = re.compile(
    r"\b(?:county|city|town|municipal)\s+commission\b.*\bagenda\b|\bmeeting\s+agenda\b",
    re.I | re.S,
)


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
    """``YYYY-MM-DD`` from ISO, ``20260406``, ``February 4, 2026``, etc."""
    text = blob or ""
    iso = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    mdy = _MONTH_DAY_YEAR_TEXT.search(text)
    if mdy:
        mo = _MONTH_WORD_TO_NUM.get(mdy.group(1).lower())
        if mo:
            try:
                day = int(mdy.group(2))
                year = int(mdy.group(3))
                return f"{year}-{mo:02d}-{day:02d}"
            except ValueError:
                pass
    m = _YYYYMMDD.search(text.replace("_", "").replace("-", "").replace(",", " "))
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


def _newest_year_folder_for_jur_dir(jur_dir: Path) -> Optional[str]:
    years: Set[str] = set()
    for child in jur_dir.iterdir():
        if child.is_dir() and is_calendar_year_folder(child.name):
            years.add(child.name)
    gomeet = jur_dir / "_gomeet_downloads"
    if gomeet.is_dir():
        for child in gomeet.iterdir():
            if child.is_dir() and is_calendar_year_folder(child.name):
                years.add(child.name)
    return max(years) if years else None


def discover_most_recent_year_folder_per_jurisdiction(
    raw_root: Path,
    *,
    jurisdiction_root: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Scan jurisdiction roots only (no deep file walk) for the newest ``20xx/`` folder.

    Includes ``_gomeet_downloads/20xx`` when present.
    When ``jurisdiction_root`` is set, only that directory is scanned (faster single-jur runs).
    """
    raw_root = raw_root.resolve()
    allowed: Dict[str, str] = {}
    if not raw_root.is_dir():
        return allowed

    if jurisdiction_root is not None:
        jur_dir = jurisdiction_root.resolve()
        if not jur_dir.is_dir():
            return allowed
        try:
            rel = jur_dir.relative_to(raw_root)
        except ValueError:
            return allowed
        parts = rel.parts
        if len(parts) >= 3:
            jur = "/".join(parts[:3])
            year = _newest_year_folder_for_jur_dir(jur_dir)
            if year:
                allowed[jur] = year
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
                year = _newest_year_folder_for_jur_dir(jur_dir)
                if year:
                    allowed[jur] = year
    return allowed


def discover_year_folders_scoped(
    raw_root: Path,
    *,
    jurisdiction_root: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Like :func:`discover_most_recent_year_folder_per_jurisdiction` with optional
    single-jurisdiction scope. Tolerates older ``meeting_date_scope`` without
    ``jurisdiction_root`` (Colab sessions before ``git pull``).
    """
    try:
        return discover_most_recent_year_folder_per_jurisdiction(
            raw_root, jurisdiction_root=jurisdiction_root
        )
    except TypeError:
        return discover_most_recent_year_folder_per_jurisdiction(raw_root)


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
    # Organized layout: ``meetings/2026_05_06/…`` (not a bare ``2026/`` segment).
    folder_date = _date_from_meetings_folder(path, raw_root)
    if folder_date:
        return folder_date[:4] == need
    meeting_date = infer_meeting_date_for_file(path, raw_root)
    if meeting_date:
        return meeting_date[:4] == need
    # Agenda/minutes under ``meetings/`` (incl. ``undated_meeting``) still belong to
    # the active scrape year — do not drop everything after organize moves files.
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
        if "meetings" in rel.parts and file_media_role(path, raw_root) in (
            "pdf",
            "audio",
            "collateral",
        ):
            return True
    except ValueError:
        pass
    stem = path.stem.lower()
    if yfolder is None and ("agenda" in stem or "minutes" in stem):
        return True
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
        if "_video_assets" in rel.parts:
            return True
    except ValueError:
        pass
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


def resolve_pinned_meeting_date() -> Optional[str]:
    """When set (``GOVERNANCE_DEMO_MEETING_DATE_PIN``), only files for this ``YYYY-MM-DD``."""
    raw = os.environ.get("GOVERNANCE_DEMO_MEETING_DATE_PIN", "").strip()
    return normalize_meeting_date(raw) if raw else None


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
    jur_root_path = Path(jurisdiction_root)
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
            p_path = Path(p)
            resolved = str(p_path.resolve())
            by_path[resolved] = row
            try:
                rel_under_jur = p_path.resolve().relative_to(jur_root_path.resolve())
                by_path[str(jur_root_path / rel_under_jur)] = row
                by_path[rel_under_jur.as_posix()] = row
            except ValueError:
                pass
            hm = _HASH_TOKEN_RE.search(p_path.stem)
            if hm:
                by_hash[hm.group(1).lower()] = row
    return by_path, by_hash


def _lookup_manifest_row(path: Path, jur_root: Path) -> Optional[ManifestRow]:
    by_path, by_hash = _manifest_indexes(str(jur_root.resolve()))
    resolved = str(path.resolve())
    if resolved in by_path:
        return by_path[resolved]
    try:
        rel = path.resolve().relative_to(jur_root.resolve())
        for key in (str(jur_root / rel), rel.as_posix(), str(rel)):
            if key in by_path:
                return by_path[key]
    except ValueError:
        pass
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
                from scrapers.discovery.meeting_document_naming import pick_meeting_date

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

    if path.suffix.lower() == ".pdf":
        d = _infer_meeting_date_from_pdf_pages(path)
        if d:
            return d

    try:
        from .meeting_grouping import infer_meeting_date_from_path

        return infer_meeting_date_from_path(path)
    except Exception:
        return None


def _pdf_excerpt_suggests_meeting_agenda(path: Path, *, pages: int = 1) -> bool:
    """
    True when page-1 text looks like a county/city commission agenda
    (e.g. ``TUSCALOOSA COUNTY COMMISSION MEETING AGENDA`` + ``February 4, 2026``).
    """
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return False
    try:
        import fitz
    except ImportError:
        return False
    try:
        with fitz.open(path) as doc:
            if doc.page_count < 1:
                return False
            text = doc.load_page(0).get_text("text") or ""
    except Exception:
        return False
    if not text.strip():
        return False
    if _MEETING_AGENDA_HEADING.search(text):
        return True
    low = text.lower()
    return (
        "meeting agenda" in low
        and ("commission" in low or "council" in low or "board" in low)
        and parse_yyyymmdd_from_blob(text) is not None
    )


def _infer_meeting_date_from_pdf_pages(path: Path, *, pages: int = 2) -> Optional[str]:
    """Read the first page(s) digital text and pull ``YYYY-MM-DD`` when present."""
    if not path.is_file():
        return None
    try:
        import fitz
    except ImportError:
        return None
    try:
        parts: List[str] = []
        with fitz.open(path) as doc:
            for i in range(min(max(1, pages), doc.page_count)):
                parts.append(doc.load_page(i).get_text("text") or "")
        return parse_yyyymmdd_from_blob("\n".join(parts))
    except Exception:
        return None


def apply_year_folder_scope_to_candidates(
    candidates: List[Path], raw_root: Path
) -> List[Path]:
    """Apply DEMO newest-``20xx/`` filter with fallback when it would remove everything."""
    if not resolve_demo_year_folder_scope():
        return candidates
    allowed_years = discover_most_recent_year_folder_per_jurisdiction(raw_root)
    if not allowed_years:
        return candidates
    before_year = len(candidates)
    year_filtered = [
        p for p in candidates if path_matches_year_folder_scope(p, raw_root, allowed_years)
    ]
    if before_year > 0 and len(year_filtered) == 0:
        logger.warning(
            "Year folder scope removed all %d media file(s) — keeping all media candidates "
            "for Gatekeeper (common after organize moves files under meetings/).",
            before_year,
        )
        return candidates
    logger.info(
        "Year folder scope | %d → %d media file(s) | newest calendar folder per jurisdiction",
        before_year,
        len(year_filtered),
    )
    for jur, year in sorted(allowed_years.items()):
        logger.info("  %s → %s/", jur, year)
    return year_filtered


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
    parts_lower = [p.lower() for p in rel.parts]
    if doc_type in ("agenda", "minutes"):
        return "pdf"
    if "agenda" in stem or "minutes" in stem:
        return "pdf"
    if path.suffix.lower() == ".pdf":
        try:
            from .gatekeeper_triage import gatekeeper_rules_only_enabled

            if gatekeeper_rules_only_enabled():
                if (
                    "agenda" in parts_lower
                    or "minutes" in parts_lower
                    or "agenda" in stem
                    or "minutes" in stem
                ):
                    return "pdf"
        except ImportError:
            pass
        skip_probe = os.environ.get("GOVERNANCE_GATEKEEPER_SKIP_PDF_PROBE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not skip_probe and _pdf_excerpt_suggests_meeting_agenda(path):
            return "pdf"
    if "meetings" in parts_lower and (
        "agenda" in parts_lower or "minutes" in parts_lower or "audio" in parts_lower
    ):
        return "pdf"
    if any(is_calendar_year_folder(p) for p in rel.parts):
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

    candidates = apply_year_folder_scope_to_candidates(candidates, raw_root)

    total = len(candidates)
    if cap is None:
        return list(candidates), total, {}

    allowed = _allowed_dates_per_jurisdiction(candidates, raw_root, max_dates=cap)
    pin = resolve_pinned_meeting_date()
    if pin:
        jurs = {jurisdiction_prefix_from_path(p, raw_root) for p in candidates}
        allowed = {j: {pin} for j in jurs}
        logger.info("Date scope: pinned to meeting date %s only", pin)
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


def gatekeeper_include_collateral() -> bool:
    return os.environ.get("GOVERNANCE_GATEKEEPER_INCLUDE_COLLATERAL", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def resolve_gatekeeper_max_meeting_sessions(explicit: Optional[int] = None) -> Optional[int]:
    """Max ``meetings/<session>/`` folders per jurisdiction (DEMO default = meeting-date cap)."""
    if explicit is not None:
        return explicit if explicit > 0 else None
    for key in (
        "GOVERNANCE_GATEKEEPER_MAX_MEETING_SESSIONS",
        "GOVERNANCE_GATEKEEPER_MAX_MEETING_DATES",
    ):
        env = os.environ.get(key, "").strip()
        if env:
            n = int(env)
            return n if n > 0 else None
    if os.environ.get("GOVERNANCE_MODE", "").strip().upper() == "DEMO":
        return resolve_demo_meeting_dates_limit()
    return None


def meeting_session_key(path: Path, raw_root: Path) -> Optional[str]:
    """
    ``jurisdiction_prefix|meetings/<session_folder>`` when under ``…/meetings/…``.

    Used to keep only the newest few meeting folders (e.g. after organize created
  hundreds of ``undated_meeting_N`` trees).
    """
    try:
        rel = path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return None
    if "meetings" not in rel.parts:
        return None
    idx = rel.parts.index("meetings")
    if idx + 1 >= len(rel.parts):
        return None
    jur = jurisdiction_prefix_from_path(path, raw_root)
    session = rel.parts[idx + 1]
    return f"{jur}|{session}"


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def limit_to_recent_meeting_sessions(
    paths: Sequence[Path],
    raw_root: Path,
    *,
    max_sessions: int,
) -> List[Path]:
    """Keep files only from the ``max_sessions`` newest ``meetings/<folder>/`` sessions."""
    if max_sessions <= 0:
        return list(paths)
    other: List[Path] = []
    by_session: Dict[str, List[Path]] = defaultdict(list)
    for path in paths:
        sk = meeting_session_key(path, raw_root)
        if sk:
            by_session[sk].append(path)
        else:
            other.append(path)
    if not by_session:
        return list(paths)

    ranked = sorted(
        by_session.keys(),
        key=lambda sk: max(_path_mtime(p) for p in by_session[sk]),
    )
    kept = set(ranked[-max_sessions:])
    out = list(other)
    for sk in sorted(kept):
        out.extend(by_session[sk])
    logger.info(
        "Gatekeeper session scope | %d meeting folder(s) → kept newest %d: %s",
        len(by_session),
        len(kept),
        ", ".join(sorted(sk.split("|", 1)[-1] for sk in ranked[-max_sessions:])),
    )
    return out


def _recency_sort_key(path: Path) -> tuple[float, int, str]:
    year = 0
    for part in path.parts:
        if len(part) == 4 and part.isdigit() and part.startswith("20"):
            year = max(year, int(part))
    return (_path_mtime(path), year, path.as_posix())


def narrow_gatekeeper_candidates(
    candidates: Sequence[Path],
    raw_root: Path,
    *,
    max_files: Optional[int] = None,
    max_dates: Optional[int] = None,
    max_sessions: Optional[int] = None,
) -> Tuple[List[Path], Dict[str, Set[str]]]:
    """
    Shrink Gatekeeper inputs to a hackathon-sized set per jurisdiction.

    Order: drop collateral → newest ``meetings/<session>/`` folders → recent
    calendar dates → dedupe scrape copies → newest-N file cap.
    """
    before = len(candidates)
    paths = list(candidates)

    if not gatekeeper_include_collateral():
        paths = [p for p in paths if file_media_role(p, raw_root) != "collateral"]

    session_cap = resolve_gatekeeper_max_meeting_sessions(max_sessions)
    if session_cap is not None and len(paths) > session_cap:
        paths = limit_to_recent_meeting_sessions(paths, raw_root, max_sessions=session_cap)

    selected, _total, allowed = filter_paths_by_recent_meeting_dates(
        paths, raw_root, max_dates=max_dates
    )
    if allowed:
        paths = selected
    else:
        paths = selected if selected else paths

    paths = dedupe_scrape_copies(paths, raw_root)

    try:
        from .gatekeeper_triage import resolve_gatekeeper_max_files
    except ImportError:
        resolve_gatekeeper_max_files = lambda explicit=None: None  # type: ignore

    file_cap = resolve_gatekeeper_max_files(max_files)
    paths.sort(key=_recency_sort_key)
    if file_cap is not None and len(paths) > file_cap:
        paths = paths[-file_cap:]

    logger.info(
        "Gatekeeper narrow | %d candidates → %d to triage (sessions=%s dates=%s files=%s)",
        before,
        len(paths),
        session_cap if session_cap is not None else "off",
        resolve_demo_meeting_dates_limit(max_dates) if allowed else "n/a",
        file_cap if file_cap is not None else "off",
    )
    return paths, allowed
