"""
Local transcript cache paths — basename matches YouTube Opus layout (``YYYY-MM-DD_<title>``).

Audio: ``data/cache/youtube_audio/al/city_of_tuscaloosa_…/2026-03-31_Tuscaloosa ….opus``
Cache: ``data/cache/gemini_transcript_policy/<jurisdiction_id>/2026-03-31_Tuscaloosa ….json``
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def _sanitize_audio_title(text: str, *, max_length: int = 80) -> str:
    """Match ``YouTubeAudioDownloader.sanitize_filename`` for shared Opus/JSON basenames."""
    if not text:
        return "untitled"
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:max_length]

# Full policy runs (browser / API with timestamp stem) — not jurisdiction caption cache
_POLICY_OUTPUT_RE = re.compile(r"^\d{8}T\d{6}Z_")
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_DATE_IN_TITLE_PATTERNS = (
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
    r"(\d{1,2})-(\d{1,2})-(\d{4})",
    r"(\d{1,2})/(\d{1,2})/(\d{4})",
)


def _extract_date_from_title(title: str) -> Optional[str]:
    for pattern in _DATE_IN_TITLE_PATTERNS:
        match = re.search(pattern, title or "")
        if not match:
            continue
        groups = match.groups()
        try:
            if len(groups[0]) == 4:
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            else:
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            continue
    return None


def meeting_media_basename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    """Stem shared with Opus downloads: ``YYYY-MM-DD_<sanitized title>``."""
    date_str: Optional[str] = None
    if event_date:
        raw = event_date.strftime("%Y-%m-%d") if isinstance(event_date, datetime) else str(event_date).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
            date_str = raw[:10]
    if not date_str:
        date_str = _extract_date_from_title(title)
    if not date_str:
        date_str = "unknown-date"
    safe_title = _sanitize_audio_title(title or "untitled")
    return f"{date_str}_{safe_title}"


def transcript_cache_filename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    return f"{meeting_media_basename(title, event_date)}.json"


def transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    video_id: Optional[str] = None,
) -> Path:
    """Preferred cache path (audio-aligned basename)."""
    if title:
        return cache_dir / jurisdiction_id / transcript_cache_filename(title, event_date)
    if video_id:
        return legacy_transcript_cache_path(cache_dir, jurisdiction_id, video_id)
    raise ValueError("transcript_cache_path requires title or video_id")


def legacy_transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    video_id: str,
) -> Path:
    return cache_dir / jurisdiction_id / f"{video_id.strip()}_transcript.json"


def is_transcript_cache_file(path: Path) -> bool:
    """Caption-cache JSON only (excludes policy-run ``*_analysis.json`` / timestamp stems)."""
    name = path.name
    if not name.endswith(".json") or not path.is_file():
        return False
    if name.endswith("_meta.json") or name.endswith("_analysis.json"):
        return False
    if _POLICY_OUTPUT_RE.match(name):
        return False
    if name.endswith("_transcript.json"):
        stem = name[: -len("_transcript.json")]
        return bool(_YOUTUBE_ID_RE.fullmatch(stem))
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}_", name))


def iter_transcript_cache_files(folder: Path) -> List[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if is_transcript_cache_file(p))


def resolve_transcript_cache_path(
    folder: Path,
    *,
    video_id: Optional[str] = None,
    title: Optional[str] = None,
    event_date: Optional[Union[str, datetime]] = None,
) -> Optional[Path]:
    """Find cache file by new name, legacy ``{video_id}_transcript.json``, or scan by ``video_id`` in JSON."""
    if title:
        candidate = folder / transcript_cache_filename(title, event_date)
        if candidate.is_file():
            return candidate
    vid = (video_id or "").strip()
    if vid:
        legacy = folder / f"{vid}_transcript.json"
        if legacy.is_file():
            return legacy
        for path in iter_transcript_cache_files(folder):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if (data.get("video_id") or "").strip() == vid:
                return path
    return None


def migrate_transcript_cache_names(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """
    Rename legacy ``{video_id}_transcript.json`` → ``YYYY-MM-DD_<title>.json``.

    Returns (renamed_count, skipped_count, warnings).
    """
    renamed = 0
    skipped = 0
    warnings: List[str] = []
    for path in sorted(folder.glob("*_transcript.json")):
        if not path.is_file():
            continue
        stem = path.stem.replace("_transcript", "")
        if not _YOUTUBE_ID_RE.fullmatch(stem):
            skipped += 1
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warnings.append(f"{path.name}: unreadable ({exc})")
            skipped += 1
            continue
        title = str(data.get("title") or "").strip()
        if not title:
            warnings.append(f"{path.name}: missing title; not renamed")
            skipped += 1
            continue
        dest = folder / transcript_cache_filename(title, data.get("event_date"))
        if dest.resolve() == path.resolve():
            skipped += 1
            continue
        if dest.is_file() and dest.resolve() != path.resolve():
            warnings.append(f"{path.name}: target exists {dest.name}; removing duplicate legacy file")
            if not dry_run:
                path.unlink()
            renamed += 1
            continue
        if dry_run:
            warnings.append(f"would rename: {path.name} -> {dest.name}")
        else:
            path.rename(dest)
        renamed += 1
    return renamed, skipped, warnings


def load_local_transcript_payload(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    video_id: str,
    title: Optional[str] = None,
    event_date: Optional[Union[str, datetime]] = None,
) -> Optional[tuple[Path, Dict[str, Any]]]:
    """Return ``(path, payload)`` when a caption-cache JSON exists for this video."""
    folder = cache_dir / jurisdiction_id
    path = resolve_transcript_cache_path(
        folder,
        video_id=video_id,
        title=title,
        event_date=event_date,
    )
    if path is None:
        return None
    return path, json.loads(path.read_text(encoding="utf-8"))


def payload_from_row_or_path(
    row: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
) -> Tuple[str, Optional[str], str]:
    """Return (title, event_date, video_id) for path construction."""
    if row:
        return (
            str(row.get("title") or ""),
            row.get("event_date"),
            str(row.get("video_id") or ""),
        )
    if path and path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            str(data.get("title") or ""),
            data.get("event_date"),
            str(data.get("video_id") or path.stem.replace("_transcript", "")),
        )
    raise ValueError("payload_from_row_or_path requires row or path")
