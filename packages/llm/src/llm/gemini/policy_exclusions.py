"""
Exclude non-meeting YouTube uploads from the policy pipeline.

Moves ``01_transcripts`` … ``04_runs`` artifacts into ``05_exceptions/<stem>/`` and
records them in ``05_exceptions/_excluded_videos.json``. Optionally marks bronze
``transcript_source`` as ``excluded:<reason>`` with ``has_transcript=false``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from llm.gemini.transcript_cache_paths import (
    DIR_ANALYSIS,
    DIR_EXCEPTIONS,
    DIR_REPORTS,
    DIR_RUNS,
    DIR_TRANSCRIPTS,
    EXCLUDED_MANIFEST,
    _POLICY_PIPELINE_SUBDIRS,
    _read_json_metadata,
    _YOUTUBE_ID_IN_NAME_RE,
    channel_root_from_policy_path,
    list_policy_channel_roots,
    video_id_from_analysis,
)

DEFAULT_REASON = "non_meeting"
EXCLUDED_BRONZE_PREFIX = "excluded:"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def exceptions_dir(channel_root: Path) -> Path:
    return channel_root / DIR_EXCEPTIONS


def manifest_path(channel_root: Path) -> Path:
    return exceptions_dir(channel_root) / EXCLUDED_MANIFEST


def load_excluded_manifest(channel_root: Path) -> Dict[str, Any]:
    path = manifest_path(channel_root)
    if not path.is_file():
        return {"videos": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"videos": []}
    if not isinstance(data, dict):
        return {"videos": []}
    videos = data.get("videos")
    if not isinstance(videos, list):
        data["videos"] = []
    return data


def excluded_video_ids(channel_root: Path) -> Set[str]:
    out: Set[str] = set()
    for row in load_excluded_manifest(channel_root).get("videos") or []:
        if isinstance(row, dict):
            vid = str(row.get("video_id") or "").strip()
            if vid:
                out.add(vid)
    return out


def load_excluded_video_ids_for_jurisdiction(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> Set[str]:
    out: Set[str] = set()
    for root in list_policy_channel_roots(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
    ):
        out |= excluded_video_ids(root)
    return out


def is_policy_video_excluded(
    cache_dir: Path,
    jurisdiction_id: str,
    video_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> bool:
    vid = (video_id or "").strip()
    if not vid:
        return False
    if channel_id:
        from llm.gemini.transcript_cache_paths import canonical_jurisdiction_root

        root = canonical_jurisdiction_root(
            cache_dir,
            jurisdiction_id,
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            channel_id=channel_id,
        )
        if vid in excluded_video_ids(root):
            return True
    return vid in load_excluded_video_ids_for_jurisdiction(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
    )


def _normalize_policy_stem(stem: str) -> str:
    for suffix in (".mermaid-errors", ".diagrams", ".meta", "_analysis", "_report", "_transcript"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def policy_stem_from_path(path: Path) -> str:
    p = path.resolve()
    if p.parent.name in _POLICY_PIPELINE_SUBDIRS:
        return _normalize_policy_stem(p.stem)
    if p.parent.parent.name == DIR_EXCEPTIONS:
        return p.parent.name
    return _normalize_policy_stem(p.stem)


def _video_id_from_path(path: Path) -> str:
    title, event_date, vid = _read_json_metadata(path)
    if vid:
        return vid
    if path.suffix == ".json" and path.parent.name == DIR_ANALYSIS:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                found = video_id_from_analysis(data)
                if found:
                    return found
                frag = data.get("parsed_fragment")
                if isinstance(frag, dict):
                    found = video_id_from_analysis(frag)
                    if found:
                        return found
        except (json.JSONDecodeError, OSError):
            pass
    channel_root = channel_root_from_policy_path(path)
    stem = policy_stem_from_path(path)
    meta = channel_root / DIR_RUNS / f"{stem}.meta.json"
    if meta.is_file():
        _, _, vid = _read_json_metadata(meta)
        if vid:
            return vid
    transcript = channel_root / DIR_TRANSCRIPTS / f"{stem}.json"
    if transcript.is_file():
        _, _, vid = _read_json_metadata(transcript)
        if vid:
            return vid
    m = _YOUTUBE_ID_IN_NAME_RE.search(path.name)
    return m.group(1) if m else ""


def collect_policy_artifacts(
    channel_root: Path,
    stem: str,
    *,
    video_id: str = "",
) -> List[Path]:
    """All pipeline files for one meeting basename under a channel folder."""
    stem = (stem or "").strip()
    vid = (video_id or "").strip()
    found: List[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p.resolve())
        if key not in seen and p.is_file():
            seen.add(key)
            found.append(p)

    for sub in _POLICY_PIPELINE_SUBDIRS:
        subdir = channel_root / sub
        if not subdir.is_dir():
            continue
        for path in subdir.iterdir():
            if not path.is_file():
                continue
            if stem and _normalize_policy_stem(path.stem) == stem:
                add(path)
            elif vid and vid in path.name:
                add(path)
            if stem and sub == DIR_REPORTS:
                sidecar = subdir / f"{stem}.mermaid-errors.json"
                if sidecar.is_file():
                    add(sidecar)
            if stem and sub == DIR_RUNS:
                for extra_suffix in (".meta.json", ".diagrams.md"):
                    extra = subdir / f"{stem}{extra_suffix}"
                    if extra.is_file():
                        add(extra)

    if vid:
        legacy = channel_root / f"{vid}_transcript.json"
        if legacy.is_file():
            add(legacy)
        for name in (f"{vid}_analysis.json", f"{vid}_report.md", f"{vid}_meta.json"):
            legacy2 = channel_root / name
            if legacy2.is_file():
                add(legacy2)
    return found


def _save_manifest(channel_root: Path, manifest: Dict[str, Any]) -> None:
    ex = exceptions_dir(channel_root)
    ex.mkdir(parents=True, exist_ok=True)
    manifest_path(channel_root).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _upsert_manifest_entry(
    manifest: Dict[str, Any],
    *,
    video_id: str,
    stem: str,
    reason: str,
    note: str,
    title: str,
    moved: List[str],
) -> None:
    videos = manifest.setdefault("videos", [])
    entry = {
        "video_id": video_id,
        "stem": stem,
        "reason": reason,
        "note": note,
        "title": title,
        "excluded_at": _utc_now_iso(),
        "moved_files": moved,
    }
    replaced = False
    for i, row in enumerate(videos):
        if isinstance(row, dict) and str(row.get("video_id") or "") == video_id:
            videos[i] = {**row, **entry}
            replaced = True
            break
    if not replaced:
        videos.append(entry)


def write_bronze_policy_exclusion(
    database_url: str,
    *,
    event_id: int,
    video_id: str,
    reason: str,
) -> None:
    import psycopg2

    source = f"{EXCLUDED_BRONZE_PREFIX}{(reason or DEFAULT_REASON).strip()}"[:120]
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bronze.bronze_event_youtube_transcript (
                    event_id, video_id, raw_text, segments, language,
                    is_auto_generated, transcript_source, has_transcript, transcript_quality
                ) VALUES (
                    %(event_id)s, %(video_id)s, NULL, NULL, NULL,
                    false, %(transcript_source)s, false, 'none'
                )
                ON CONFLICT (video_id) DO UPDATE SET
                    event_id = COALESCE(EXCLUDED.event_id, bronze.bronze_event_youtube_transcript.event_id),
                    raw_text = NULL,
                    segments = NULL,
                    language = NULL,
                    is_auto_generated = false,
                    transcript_source = EXCLUDED.transcript_source,
                    has_transcript = false,
                    transcript_quality = 'none',
                    last_updated = CURRENT_TIMESTAMP
                """,
                {
                    "event_id": event_id,
                    "video_id": video_id,
                    "transcript_source": source,
                },
            )
        conn.commit()
    finally:
        conn.close()


def exclude_policy_video_at_path(
    path: Path,
    *,
    reason: str = DEFAULT_REASON,
    note: str = "",
    dry_run: bool = False,
    write_bronze: bool = True,
    database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Move policy cache artifacts for one video into ``05_exceptions/<stem>/``.

    ``path`` may be any artifact under ``01_transcripts`` … ``04_runs`` (or already under
    ``05_exceptions``).
    """
    src = path.expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(src)

    channel_root = channel_root_from_policy_path(src)
    stem = policy_stem_from_path(src)
    video_id = _video_id_from_path(src)
    title, _, vid2 = _read_json_metadata(src)
    if not video_id:
        video_id = vid2
    if not video_id:
        raise ValueError(f"Could not determine video_id from {src}")

    artifacts = collect_policy_artifacts(channel_root, stem, video_id=video_id)
    if not artifacts:
        raise FileNotFoundError(
            f"No pipeline artifacts for stem={stem!r} video_id={video_id} under {channel_root}"
        )

    dest_dir = exceptions_dir(channel_root) / stem
    moved: List[str] = []
    for artifact in artifacts:
        rel = artifact.relative_to(channel_root)
        dest = dest_dir / artifact.name
        moved.append(str(rel))
        if dry_run:
            logger.info("[dry-run] would move {} -> {}", rel, dest.relative_to(channel_root))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            dest.unlink()
        artifact.rename(dest)
        logger.info("Moved {} -> {}", rel, dest.relative_to(channel_root))

    manifest = load_excluded_manifest(channel_root)
    _upsert_manifest_entry(
        manifest,
        video_id=video_id,
        stem=stem,
        reason=reason,
        note=note,
        title=title,
        moved=moved,
    )
    if not dry_run:
        _save_manifest(channel_root, manifest)

    if write_bronze and database_url and not dry_run:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT event_id FROM bronze.bronze_event_youtube
                    WHERE video_id = %s
                    ORDER BY last_updated DESC NULLS LAST
                    LIMIT 1
                    """,
                    (video_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if row and row.get("event_id"):
            write_bronze_policy_exclusion(
                database_url,
                event_id=int(row["event_id"]),
                video_id=video_id,
                reason=reason,
            )
            logger.info("Bronze marked excluded:{} for {}", reason, video_id)

    return {
        "channel_root": str(channel_root),
        "video_id": video_id,
        "stem": stem,
        "reason": reason,
        "moved": moved,
        "dry_run": dry_run,
    }


def filter_rows_not_excluded(
    rows: List[Dict[str, Any]],
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    excluded = load_excluded_video_ids_for_jurisdiction(
        cache_dir, jurisdiction_id, state_code=state_code
    )
    if not excluded:
        return rows
    out = [r for r in rows if str(r.get("video_id") or "").strip() not in excluded]
    skipped = len(rows) - len(out)
    if skipped:
        logger.info("Skipped {} video(s) marked excluded in policy cache", skipped)
    return out
