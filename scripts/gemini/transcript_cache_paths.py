"""
Local policy cache layout — mirrors YouTube Opus naming under typed subfolders.

``data/cache/gemini_transcript_policy/<jurisdiction_id>/``

- ``01_transcripts/`` — YouTube captions (``YYYY-MM-DD_<title>.json``)
- ``02_analysis/`` — Part 1 structured JSON (same basename)
- ``03_reports/`` — Part 2 Smart Brevity markdown (``.md``)
- ``04_runs/`` — run metadata (``.meta.json``), optional diagrams (``.diagrams.md``)
- ``README.md`` — what each folder is

Legacy flat files at the jurisdiction root are still read; use ``migrate_policy_cache_layout.py``.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DIR_TRANSCRIPTS = "01_transcripts"
DIR_ANALYSIS = "02_analysis"
DIR_REPORTS = "03_reports"
DIR_RUNS = "04_runs"
README_NAME = "README.md"

_POLICY_SUBDIRS = (DIR_TRANSCRIPTS, DIR_ANALYSIS, DIR_REPORTS, DIR_RUNS)

_JURISDICTION_README = """# Meeting policy cache — {jurisdiction_id}

Files are grouped by pipeline step. Within each folder, names sort **newest-first by date** (`YYYY-MM-DD_<meeting title>.…`).

| Folder | Contents |
|--------|----------|
| **{dir_transcripts}** | YouTube caption JSON (source text + `youtube.segments`) |
| **{dir_analysis}** | Part 1 policy JSON (`decisions[]`, `uncontested_items[]`, `places[]`) |
| **{dir_reports}** | Part 2 resident-facing Markdown summaries |
| **{dir_runs}** | Run metadata (`.meta.json`) and optional Mermaid sidecars (`.diagrams.md`) |

Basenames match Opus audio under `data/cache/youtube_audio/…/city_of_tuscaloosa_…/`.

Regenerate layout from repo root::

    python scripts/gemini/migrate_policy_cache_layout.py --jurisdiction-id {jurisdiction_id}
"""


def _sanitize_audio_title(text: str, *, max_length: int = 80) -> str:
    if not text:
        return "untitled"
    text = text.replace("/", "-")
    text = re.sub(r'[<>:"\\|?*]', "", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return (text or "untitled")[:max_length]


def strip_meeting_date_from_title(
    title: str,
    *,
    resolved_date: Optional[str] = None,
) -> str:
    """
    Drop calendar date text from a meeting title when the same date is the filename prefix.

    Handles ``1/11/2024``, ``1-11-2024``, ``September 23, 2024``, and legacy compact
    suffixes like ``1112024`` (slashes removed by older sanitizers).
    """
    t = (title or "").strip()
    if not t:
        return "untitled"

    month_match = _MONTH_DAY_YEAR_RE.search(t)
    if month_match:
        t = (t[: month_match.start()] + t[month_match.end() :]).strip()
    else:
        for pattern in _DATE_IN_TITLE_PATTERNS:
            match = re.search(pattern, t)
            if match:
                t = (t[: match.start()] + t[match.end() :]).strip()
                break

    if resolved_date:
        try:
            d = datetime.strptime(str(resolved_date)[:10], "%Y-%m-%d")
        except ValueError:
            d = None
        if d is not None:
            variants = (
                f"{d.month}/{d.day}/{d.year}",
                f"{d.month}-{d.day}-{d.year}",
                f"{d.month:02d}/{d.day:02d}/{d.year}",
                f"{d.month:02d}-{d.day:02d}-{d.year}",
                f"{d.month}{d.day}{d.year}",
                f"{d.month:02d}{d.day:02d}{d.year}",
            )
            for fragment in variants:
                if t.endswith(fragment):
                    t = t[: -len(fragment)].strip()
                    break
                hyphenated = fragment.replace("/", "-")
                if hyphenated != fragment and t.endswith(hyphenated):
                    t = t[: -len(hyphenated)].strip()
                    break

    t = re.sub(r"[\s\-–—]+$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or "untitled"


_POLICY_OUTPUT_RE = re.compile(r"^\d{8}T\d{6}Z_")
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_DATE_IN_TITLE_PATTERNS = (
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
    r"(\d{1,2})-(\d{1,2})-(\d{4})",
    r"(\d{1,2})/(\d{1,2})/(\d{4})",
)
_MONTH_DAY_YEAR_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_DAY_YEAR_FMTS = ("%B %d, %Y", "%b %d, %Y")


def extract_meeting_date_from_title(title: str) -> Optional[str]:
    """Parse M/D/YYYY, MM-DD-YYYY, YYYY-MM-DD, or 'September 23, 2024' from a video title."""
    month_match = _MONTH_DAY_YEAR_RE.search(title or "")
    if month_match:
        fragment = month_match.group(0)
        for fmt in _MONTH_DAY_YEAR_FMTS:
            try:
                return datetime.strptime(fragment, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
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


_extract_date_from_title = extract_meeting_date_from_title


def _coerce_date_str(value: Optional[Union[str, datetime, date]]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    raw = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None


def resolve_meeting_event_date(
    title: str,
    event_date: Optional[Union[str, datetime, date]] = None,
    published_at: Optional[Union[str, datetime]] = None,
) -> Optional[str]:
    """
    Meeting calendar date for filenames and bronze.

    Prefer a date parsed from the title (e.g. ``9/23/2024`` in the council meeting title)
    over catalog ``event_date`` / YouTube ``published_at`` (often the upload day).
    """
    from_title = extract_meeting_date_from_title(title)
    if from_title:
        return from_title
    coerced = _coerce_date_str(event_date)
    if coerced:
        return coerced
    if published_at is not None:
        try:
            if isinstance(published_at, datetime):
                return published_at.date().strftime("%Y-%m-%d")
            return _coerce_date_str(str(published_at))
        except (ValueError, TypeError):
            pass
    return None


def meeting_media_basename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    date_str = resolve_meeting_event_date(title, event_date=event_date)
    if not date_str:
        date_str = "unknown-date"
    title_without_date = strip_meeting_date_from_title(title, resolved_date=date_str)
    safe_title = _sanitize_audio_title(title_without_date)
    return f"{date_str}_{safe_title}"


def media_filename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    *,
    suffix: str = ".json",
) -> str:
    return f"{meeting_media_basename(title, event_date)}{suffix}"


def jurisdiction_root(cache_dir: Path, jurisdiction_id: str) -> Path:
    return cache_dir / jurisdiction_id


def ensure_jurisdiction_layout(jid_root: Path) -> None:
    for name in _POLICY_SUBDIRS:
        (jid_root / name).mkdir(parents=True, exist_ok=True)
    readme = jid_root / README_NAME
    if not readme.is_file():
        jid = jid_root.name
        readme.write_text(
            _JURISDICTION_README.format(
                jurisdiction_id=jid,
                dir_transcripts=DIR_TRANSCRIPTS,
                dir_analysis=DIR_ANALYSIS,
                dir_reports=DIR_REPORTS,
                dir_runs=DIR_RUNS,
            ),
            encoding="utf-8",
        )


def transcripts_dir(cache_dir: Path, jurisdiction_id: str) -> Path:
    return jurisdiction_root(cache_dir, jurisdiction_id) / DIR_TRANSCRIPTS


def analysis_dir(cache_dir: Path, jurisdiction_id: str) -> Path:
    return jurisdiction_root(cache_dir, jurisdiction_id) / DIR_ANALYSIS


def reports_dir(cache_dir: Path, jurisdiction_id: str) -> Path:
    return jurisdiction_root(cache_dir, jurisdiction_id) / DIR_REPORTS


def runs_dir(cache_dir: Path, jurisdiction_id: str) -> Path:
    return jurisdiction_root(cache_dir, jurisdiction_id) / DIR_RUNS


def transcript_cache_filename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    return media_filename(title, event_date, suffix=".json")


def transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    video_id: Optional[str] = None,
) -> Path:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ensure_jurisdiction_layout(root)
    if title:
        return transcripts_dir(cache_dir, jurisdiction_id) / transcript_cache_filename(title, event_date)
    if video_id:
        return legacy_transcript_cache_path(cache_dir, jurisdiction_id, video_id)
    raise ValueError("transcript_cache_path requires title or video_id")


def analysis_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> Path:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ensure_jurisdiction_layout(root)
    return analysis_dir(cache_dir, jurisdiction_id) / media_filename(title, event_date, suffix=".json")


def report_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> Path:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ensure_jurisdiction_layout(root)
    return reports_dir(cache_dir, jurisdiction_id) / media_filename(title, event_date, suffix=".md")


def run_meta_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> Path:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ensure_jurisdiction_layout(root)
    return runs_dir(cache_dir, jurisdiction_id) / media_filename(title, event_date, suffix=".meta.json")


def run_diagrams_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> Path:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ensure_jurisdiction_layout(root)
    return runs_dir(cache_dir, jurisdiction_id) / media_filename(title, event_date, suffix=".diagrams.md")


def report_path_for_analysis(analysis_path: Path) -> Path:
    """``02_analysis/foo.json`` → ``03_reports/foo.md``."""
    name = analysis_path.name
    if analysis_path.parent.name == DIR_ANALYSIS:
        return analysis_path.parent.parent / DIR_REPORTS / f"{analysis_path.stem}.md"
    if name.endswith("_analysis.json"):
        base = name[: -len("_analysis.json")]
        return analysis_path.parent / DIR_REPORTS / f"{base}.md"
    return analysis_path.with_suffix(".md").parent.parent / DIR_REPORTS / f"{analysis_path.stem}.md"


def meta_path_for_analysis(analysis_path: Path) -> Path:
    """Sibling run metadata for a Part 1 analysis file."""
    if analysis_path.parent.name == DIR_ANALYSIS:
        return analysis_path.parent.parent / DIR_RUNS / f"{analysis_path.stem}.meta.json"
    name = analysis_path.name
    if name.endswith("_analysis.json"):
        return analysis_path.with_name(name.replace("_analysis.json", "_meta.json"))
    return analysis_path.with_suffix(".meta.json")


_LEGACY_RUN_STEM_RE = re.compile(
    r"^\d+_\d{8}T\d{6}Z_+_?(?P<vid>[A-Za-z0-9_-]{11})_(?P<title>.+?)_policy_analysis_part_1",
    re.IGNORECASE,
)
_YOUTUBE_ID_IN_NAME_RE = re.compile(r"_([A-Za-z0-9_-]{11})_")


def _strip_unknown_prefixes(name: str) -> str:
    stem = Path(name).stem
    while stem.startswith("unknown-date_"):
        stem = stem[len("unknown-date_") :]
    return stem + Path(name).suffix


def _parse_dated_basename(filename: str) -> Tuple[Optional[str], str]:
    stem = Path(_strip_unknown_prefixes(filename)).stem
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_(.+)$", stem)
    if match:
        return match.group(1), match.group(2)
    return None, stem


def _title_from_meeting_and_meta(folder: Path, meeting: Dict[str, Any]) -> Tuple[str, Optional[Any], str]:
    body = str(meeting.get("body_name") or "").strip()
    mdate = str(meeting.get("meeting_date") or meeting.get("date") or "").strip()[:10]
    if not body or not mdate:
        return "", None, ""
    body_key = re.sub(r"[^a-z0-9]+", "", body.lower())
    runs = folder / DIR_RUNS
    if not runs.is_dir():
        return "", None, ""
    for meta_path in sorted(runs.glob("*.meta.json"), key=lambda p: p.name, reverse=True):
        if not meta_path.name.startswith(mdate):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        title = str(meta.get("title") or "").strip()
        if not title:
            continue
        title_key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if body_key in title_key or body_key in re.sub(r"[^a-z0-9]+", "", meta_path.stem.lower()):
            return title, meta.get("event_date") or mdate, str(meta.get("video_id") or "").strip()
    return "", None, ""


def _title_from_legacy_filename(filename: str) -> Tuple[str, str]:
    """Parse legacy run stem; returns ``(title, video_id)``."""
    stem = Path(_strip_unknown_prefixes(filename)).stem
    for suffix in (
        "_analysis",
        "_meta",
        "_report",
        "_transcript",
        ".diagrams.md",
        ".diagrams",
    ):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    match = _LEGACY_RUN_STEM_RE.match(stem)
    if not match:
        return "", ""
    title = match.group("title").replace("_", " ")
    title = re.sub(r"_gemini-[\w-]+$", "", title, flags=re.IGNORECASE).strip()
    return title, match.group("vid")


def _read_json_metadata(path: Path) -> Tuple[str, Optional[Any], str]:
    title = ""
    event_date: Optional[Any] = None
    video_id = ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return title, event_date, video_id
    if isinstance(data, dict):
        title = str(data.get("title") or "").strip()
        event_date = data.get("event_date")
        video_id = str(data.get("video_id") or "").strip()
        meeting = data.get("meeting")
        if isinstance(meeting, dict):
            if not title:
                title = str(meeting.get("title") or "").strip()
            if not video_id:
                video_id = str(meeting.get("video_id") or "").strip()
            if not event_date:
                event_date = meeting.get("event_date") or meeting.get("date")
        transcript = data.get("transcript")
        if isinstance(transcript, dict):
            if not title:
                title = str(transcript.get("title") or "").strip()
            if not event_date:
                event_date = transcript.get("event_date")
    return title, event_date, video_id


def _lookup_run_meta(folder: Path, *, video_id: str = "", run_prefix: str = "") -> Tuple[str, Optional[Any], str]:
    """Find title/date from ``04_runs/*.meta.json`` by video id or legacy run id."""
    runs = folder / DIR_RUNS
    if not runs.is_dir():
        return "", None, ""
    candidates = sorted(runs.glob("*.meta.json"), key=lambda p: p.name, reverse=True)
    for meta_path in candidates:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        mid = str(meta.get("video_id") or "").strip()
        if video_id and mid:
            if mid != video_id:
                continue
        elif run_prefix and not meta_path.name.startswith(run_prefix):
            continue
        title = str(meta.get("title") or "").strip()
        event_date = meta.get("event_date")
        if not title:
            transcript = meta.get("transcript")
            if isinstance(transcript, dict):
                title = str(transcript.get("title") or "").strip()
                event_date = event_date or transcript.get("event_date")
        if title:
            return title, event_date, mid or video_id
    return "", None, video_id


def _run_prefix_from_name(name: str) -> str:
    match = re.match(r"^(\d+)_", name)
    return match.group(1) if match else ""


def _video_id_from_name(name: str) -> str:
    match = _YOUTUBE_ID_IN_NAME_RE.search(name)
    return match.group(1) if match else ""


def metadata_for_policy_file(path: Path, *, folder: Optional[Path] = None) -> Tuple[str, Optional[Any], str]:
    """Best-effort ``(title, event_date, video_id)`` for a cache file."""
    jid_root = folder or path.parent
    if jid_root.name in _POLICY_SUBDIRS:
        jid_root = jid_root.parent

    title, event_date, video_id = _read_json_metadata(path)
    if not video_id:
        video_id = _video_id_from_name(path.name)
    if not title:
        parsed_date, parsed_title = _parse_dated_basename(path.name)
        if parsed_date and parsed_title:
            title = parsed_title
            event_date = event_date or parsed_date
    if not title:
        stripped = Path(_strip_unknown_prefixes(path.name)).stem
        inferred = _extract_date_from_title(stripped)
        if inferred:
            title = stripped
            event_date = event_date or inferred
    if not title or not video_id:
        leg_title, leg_vid = _title_from_legacy_filename(path.name)
        title = title or leg_title
        video_id = video_id or leg_vid
    if not title and path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            meeting = data.get("meeting") if isinstance(data.get("meeting"), dict) else {}
            if meeting:
                mt, md, mv = _title_from_meeting_and_meta(jid_root, meeting)
                title = mt or title
                event_date = event_date or md
                video_id = video_id or mv
        except (json.JSONDecodeError, OSError):
            pass
    if not title:
        run_prefix = _run_prefix_from_name(_strip_unknown_prefixes(path.name))
        meta_title, meta_date, meta_vid = _lookup_run_meta(
            jid_root,
            video_id=video_id,
            run_prefix=run_prefix,
        )
        title = meta_title or title
        event_date = event_date or meta_date
        video_id = video_id or meta_vid
    return title, event_date, video_id


def classify_policy_cache_file(path: Path) -> Optional[str]:
    """Map a flat jurisdiction-root file to ``01_transcripts`` … ``04_runs``."""
    name = path.name
    if name == README_NAME or not path.is_file():
        return None
    if name.endswith("_analysis.json"):
        return DIR_ANALYSIS
    if name.endswith("_report.md"):
        return DIR_REPORTS
    if name.endswith("_meta.json"):
        return DIR_RUNS
    if name.endswith(".diagrams.md") or "_diagrams.md" in name:
        return DIR_RUNS
    if name.endswith("_transcript.json"):
        return DIR_TRANSCRIPTS
    if path.suffix == ".json" and _is_flat_caption_json(path):
        return DIR_TRANSCRIPTS
    if name.endswith("_report.md"):
        return DIR_REPORTS
    if path.suffix == ".md" and _LEGACY_RUN_STEM_RE.search(
        path.stem.replace("_report", "").replace(".diagrams", "")
    ):
        return DIR_REPORTS
    return None


def destination_for_policy_file(
    folder: Path,
    path: Path,
    *,
    kind: str,
) -> Optional[Path]:
    title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
    if not title:
        return None
    if kind == DIR_TRANSCRIPTS:
        return folder / DIR_TRANSCRIPTS / transcript_cache_filename(title, event_date)
    if kind == DIR_ANALYSIS:
        return folder / DIR_ANALYSIS / media_filename(title, event_date, suffix=".json")
    if kind == DIR_REPORTS:
        return folder / DIR_REPORTS / media_filename(title, event_date, suffix=".md")
    if kind == DIR_RUNS:
        if path.name.endswith(".diagrams.md") or "_diagrams.md" in path.name:
            return folder / DIR_RUNS / media_filename(title, event_date, suffix=".diagrams.md")
        return folder / DIR_RUNS / media_filename(title, event_date, suffix=".meta.json")
    return None


def _safe_move(src: Path, dest: Path, *, dry_run: bool) -> str:
    if dest.resolve() == src.resolve():
        return "same"
    if dest.is_file():
        if src.stat().st_mtime <= dest.stat().st_mtime:
            if dry_run:
                return "would_remove_older_duplicate"
            src.unlink()
            return "removed_older_duplicate"
        if dry_run:
            return "would_replace_newer"
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return "would_move"
    shutil.move(str(src), str(dest))
    return "moved"


def migrate_policy_cache_layout(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Move flat files under a jurisdiction folder into ``01_transcripts`` … ``04_runs``.

    Collapses duplicate legacy runs per meeting basename (keeps newest mtime).
    """
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)

    renamed, skipped, warnings = migrate_transcript_cache_names(folder, dry_run=dry_run)
    stats["transcript_renamed"] = renamed
    stats["transcript_skipped"] = skipped
    stats["warnings"] = len(warnings)

    pending: Dict[Path, List[Path]] = defaultdict(list)
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        kind = classify_policy_cache_file(path)
        if not kind:
            stats["unclassified"] += 1
            continue
        dest = destination_for_policy_file(folder, path, kind=kind)
        if dest is None:
            stats["skipped_no_title"] += 1
            warnings.append(f"{path.name}: could not derive meeting title")
            continue
        pending[dest].append(path)

    for dest, sources in pending.items():
        sources.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for i, src in enumerate(sources):
            action = _safe_move(src, dest, dry_run=dry_run)
            stats[action] += 1
            if i > 0 and action in ("removed_older_duplicate", "would_remove_older_duplicate"):
                continue
    repair_policy_cache_basenames(folder, dry_run=dry_run)
    return dict(stats)


def _needs_basename_repair(path: Path) -> bool:
    if path.name.startswith("unknown-date_") or bool(_POLICY_OUTPUT_RE.match(path.name)):
        return True
    return not bool(re.match(r"^\d{4}-\d{2}-\d{2}_", path.name))


def _is_junk_policy_artifact(path: Path) -> bool:
    stem = Path(_strip_unknown_prefixes(path.name)).stem
    return stem in ("_manifest",) or stem.startswith("_index")


def repair_policy_cache_basenames(folder: Path, *, dry_run: bool = False) -> Dict[str, int]:
    """Rename ``unknown-date_*`` (or legacy timestamp) files to ``YYYY-MM-DD_<title>.*``."""
    folder = folder.resolve()
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)
    pending: Dict[Path, List[Path]] = defaultdict(list)

    for sub in _POLICY_SUBDIRS:
        subdir = folder / sub
        if not subdir.is_dir():
            continue
        for path in subdir.iterdir():
            if not path.is_file():
                continue
            if _is_junk_policy_artifact(path):
                if not dry_run:
                    path.unlink()
                stats["removed_junk"] += 1
                continue
            if not _needs_basename_repair(path):
                continue
            kind = sub
            dest = destination_for_policy_file(folder, path, kind=kind)
            if dest is None:
                stats["skipped"] += 1
                continue
            pending[dest].append(path)

    for dest, sources in pending.items():
        sources.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for src in sources:
            stats[_safe_move(src, dest, dry_run=dry_run)] += 1
    return dict(stats)


def policy_output_stem(
    *,
    title: str = "",
    event_date: Optional[Union[str, datetime]] = None,
    video_id: str = "",
    prompt_tag: str = "policy",
    model_tag: str = "model",
) -> str:
    """Human basename (no subdir); used for legacy browser stem compatibility."""
    _ = (video_id, prompt_tag, model_tag)
    if (title or "").strip():
        return meeting_media_basename(title, event_date)
    return f"unknown-date_{(video_id or 'unknown').strip()}"


def legacy_transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    video_id: str,
) -> Path:
    return jurisdiction_root(cache_dir, jurisdiction_id) / f"{video_id.strip()}_transcript.json"


def _is_flat_caption_json(path: Path) -> bool:
    name = path.name
    if not name.endswith(".json") or not path.is_file():
        return False
    if any(x in name for x in ("_analysis", "_meta", ".diagrams", "_transcript")):
        return False
    if _POLICY_OUTPUT_RE.match(name):
        return False
    if name.endswith("_transcript.json"):
        stem = name[: -len("_transcript.json")]
        return bool(_YOUTUBE_ID_RE.fullmatch(stem))
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}_", name))


def is_transcript_cache_file(path: Path) -> bool:
    return _is_flat_caption_json(path)


def _iter_dir_sorted(folder: Path) -> List[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def iter_transcript_cache_files(cache_dir: Path, jurisdiction_id: str) -> List[Path]:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    out: List[Path] = []
    td = root / DIR_TRANSCRIPTS
    if td.is_dir():
        out.extend(p for p in _iter_dir_sorted(td) if _is_flat_caption_json(p))
    if not out:
        out.extend(p for p in _iter_dir_sorted(root) if _is_flat_caption_json(p))
    return out


def iter_analysis_files(cache_dir: Path, jurisdiction_id: str) -> List[Path]:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    ad = root / DIR_ANALYSIS
    if ad.is_dir():
        return [
            p
            for p in _iter_dir_sorted(ad)
            if p.suffix == ".json" and p.is_file()
        ]
    return sorted(
        (p for p in root.glob("*_analysis.json") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def iter_report_files(cache_dir: Path, jurisdiction_id: str) -> List[Path]:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    rd = root / DIR_REPORTS
    if rd.is_dir():
        return [p for p in _iter_dir_sorted(rd) if p.suffix == ".md" and p.is_file()]
    return sorted(
        (p for p in root.glob("*_report.md") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def resolve_transcript_cache_path(
    folder: Path,
    *,
    video_id: Optional[str] = None,
    title: Optional[str] = None,
    event_date: Optional[Union[str, datetime]] = None,
) -> Optional[Path]:
    """Find caption JSON under ``01_transcripts/`` or legacy flat layout."""
    jid_root = folder
    if title:
        candidate = jid_root / DIR_TRANSCRIPTS / transcript_cache_filename(title, event_date)
        if candidate.is_file():
            return candidate
        flat = jid_root / transcript_cache_filename(title, event_date)
        if flat.is_file():
            return flat
    vid = (video_id or "").strip()
    if vid:
        legacy = jid_root / f"{vid}_transcript.json"
        if legacy.is_file():
            return legacy
        for path in iter_transcript_cache_files(jid_root.parent, jid_root.name):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if (data.get("video_id") or "").strip() == vid:
                return path
    return None


def video_id_from_analysis(data: Dict[str, Any]) -> str:
    """YouTube id from Part 1 JSON (top-level, meeting, or first playback_url)."""
    vid = str(data.get("video_id") or "").strip()
    if vid:
        return vid
    meeting = data.get("meeting")
    if isinstance(meeting, dict):
        vid = str(meeting.get("video_id") or "").strip()
        if vid:
            return vid
    for bucket in (data.get("uncontested_items") or [], data.get("decisions") or []):
        if not isinstance(bucket, list):
            continue
        for row in bucket:
            if not isinstance(row, dict):
                continue
            anchor = row.get("media_anchor")
            if not isinstance(anchor, dict):
                continue
            url = str(anchor.get("playback_url") or "")
            match = re.search(r"(?:[?&]v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
            if match:
                return match.group(1)
    return ""


def resolve_analysis_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    video_id: str = "",
    title: str = "",
    event_date: Optional[Union[str, datetime]] = None,
) -> Optional[Path]:
    root = jurisdiction_root(cache_dir, jurisdiction_id)
    if title:
        p = root / DIR_ANALYSIS / media_filename(title, event_date, suffix=".json")
        if p.is_file():
            return p
    vid = (video_id or "").strip()
    for path in iter_analysis_files(cache_dir, jurisdiction_id):
        if vid:
            if vid in path.name:
                return path
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if video_id_from_analysis(data) != vid:
                continue
        return path
    return None


def _policy_file_dest(
    folder: Path,
    sub: str,
    path: Path,
    title: str,
    event_date: Optional[Union[str, datetime]],
) -> Path:
    """Target path using title-first meeting date (``meeting_media_basename``)."""
    subdir = folder / sub
    if sub == DIR_TRANSCRIPTS:
        return subdir / transcript_cache_filename(title, event_date)
    if sub == DIR_RUNS:
        if path.name.endswith(".diagrams.md"):
            return subdir / media_filename(title, event_date, suffix=".diagrams.md")
        return subdir / media_filename(title, event_date, suffix=".meta.json")
    return subdir / media_filename(title, event_date, suffix=path.suffix)


def _patch_json_event_date_field(
    path: Path,
    title: str,
    *,
    dry_run: bool,
) -> bool:
    """Set ``event_date`` inside a transcript or analysis JSON when title has a clearer date."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    resolved = resolve_meeting_event_date(title, event_date=data.get("event_date"))
    if not resolved or str(data.get("event_date") or "")[:10] == resolved:
        return False
    if not dry_run:
        data["event_date"] = resolved
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return True


def fix_policy_cache_dates_from_title(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Rename ``01_transcripts`` … ``04_runs`` files to ``YYYY-MM-DD_<title>.*`` using the
    meeting date parsed from the title (not the upload date prefix).

    Updates ``event_date`` inside transcript/analysis JSON when it disagrees.
    """
    folder = folder.resolve()
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)

    for sub in _POLICY_SUBDIRS:
        subdir = folder / sub
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.iterdir()):
            if not path.is_file() or path.name == README_NAME:
                continue
            if _is_junk_policy_artifact(path):
                continue
            title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
            if not (title or "").strip():
                stats["skipped_no_title"] += 1
                continue
            dest = _policy_file_dest(folder, sub, path, title, event_date)
            work_path = path
            if dest.resolve() != path.resolve():
                action = _safe_move(path, dest, dry_run=dry_run)
                stats[action] += 1
                work_path = dest
            else:
                stats["already_named"] += 1
            if sub in (DIR_TRANSCRIPTS, DIR_ANALYSIS) and work_path.suffix == ".json":
                if _patch_json_event_date_field(work_path, title, dry_run=dry_run):
                    stats["json_event_date_patched"] += 1

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        kind = classify_policy_cache_file(path)
        if not kind or kind not in _POLICY_SUBDIRS:
            continue
        title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
        if not (title or "").strip():
            stats["skipped_no_title"] += 1
            continue
        dest = _policy_file_dest(folder, kind, path, title, event_date)
        if dest.resolve() == path.resolve():
            stats["already_named"] += 1
            continue
        action = _safe_move(path, dest, dry_run=dry_run)
        stats[action] += 1

    return dict(stats)


def migrate_transcript_cache_names(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """Rename legacy ``{video_id}_transcript.json`` under transcripts dir or flat root."""
    target = folder / DIR_TRANSCRIPTS if (folder / DIR_TRANSCRIPTS).is_dir() else folder
    target.mkdir(parents=True, exist_ok=True)
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
        dest = target / transcript_cache_filename(title, data.get("event_date"))
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
            warnings.append(f"would rename: {path.name} -> {dest.relative_to(folder)}")
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
    folder = jurisdiction_root(cache_dir, jurisdiction_id)
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
