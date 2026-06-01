"""
Pick one YouTube upload per meeting when a channel posts the same session multiple times.

Prefer the copy that already has captions (bronze or local cache), then longer duration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, TypeVar

from loguru import logger

T = TypeVar("T")

# Within ±12% or ±5 minutes — treats mirror uploads as duplicates, not part 1 vs full meeting.
DEFAULT_REL_DURATION_TOL = 0.12
DEFAULT_ABS_DURATION_TOL_MIN = 5


def normalize_meeting_title(title: str) -> str:
    """Stable key for the same meeting title across uploads."""
    text = (title or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    def _norm_date(m: re.Match[str]) -> str:
        month, day, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if len(year) == 2:
            year = f"20{year}"
        return f"{month}/{day}/{year}"

    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", _norm_date, text)
    return text


def duration_minutes_close(
    a: Optional[int],
    b: Optional[int],
    *,
    rel_tol: float = DEFAULT_REL_DURATION_TOL,
    abs_tol_min: int = DEFAULT_ABS_DURATION_TOL_MIN,
) -> bool:
    if a is None or b is None:
        return True
    return abs(int(a) - int(b)) <= max(abs_tol_min, int(rel_tol * max(a, b, 1)))


def _row_video_id(row: Mapping[str, Any]) -> str:
    return str(row.get("video_id") or "").strip()


def _row_title(row: Mapping[str, Any]) -> str:
    return str(row.get("title") or "")


def _row_duration(row: Mapping[str, Any]) -> Optional[int]:
    raw = row.get("duration_minutes")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _has_captions(row: Mapping[str, Any]) -> bool:
    if row.get("has_transcript") is True or row.get("bronze_has_transcript") is True:
        return True
    if row.get("local_has_transcript") is True:
        return True
    raw = row.get("raw_text")
    return bool(raw) and len(str(raw).strip()) > 50


def _priority(row: Mapping[str, Any]) -> tuple:
    """Higher sort key = preferred upload."""
    return (
        1 if _has_captions(row) else 0,
        _row_duration(row) or 0,
        _row_video_id(row),
    )


@dataclass
class DedupeResult:
    kept: List[str]
    skipped: Dict[str, str]  # video_id -> winner video_id
    groups: int


def cluster_duplicate_meetings(
    rows: Sequence[Mapping[str, Any]],
    *,
    rel_duration_tol: float = DEFAULT_REL_DURATION_TOL,
    abs_duration_tol_min: int = DEFAULT_ABS_DURATION_TOL_MIN,
) -> List[List[Mapping[str, Any]]]:
    """
    Cluster rows with the same normalized title and roughly the same runtime.
    """
    by_title: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        vid = _row_video_id(row)
        if not vid:
            continue
        key = normalize_meeting_title(_row_title(row))
        if not key:
            key = vid
        by_title.setdefault(key, []).append(row)

    clusters: List[List[Mapping[str, Any]]] = []
    for title_key, group in by_title.items():
        if len(group) == 1:
            clusters.append(group)
            continue
        remaining = list(group)
        while remaining:
            seed = remaining.pop(0)
            cluster = [seed]
            rest: List[Mapping[str, Any]] = []
            seed_dur = _row_duration(seed)
            for other in remaining:
                if duration_minutes_close(
                    seed_dur,
                    _row_duration(other),
                    rel_tol=rel_duration_tol,
                    abs_tol_min=abs_duration_tol_min,
                ):
                    cluster.append(other)
                else:
                    rest.append(other)
            remaining = rest
            clusters.append(cluster)
    return clusters


def pick_preferred_upload(cluster: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return max(cluster, key=_priority)


def dedupe_meeting_rows(
    rows: Sequence[T],
    *,
    row_to_mapping: Optional[Callable[[T], Mapping[str, Any]]] = None,
    rel_duration_tol: float = DEFAULT_REL_DURATION_TOL,
    abs_duration_tol_min: int = DEFAULT_ABS_DURATION_TOL_MIN,
) -> tuple[List[T], DedupeResult]:
    """
    Return rows to process (one per duplicate cluster) and skipped video_id map.
    """
    if not rows:
        return [], DedupeResult(kept=[], skipped={}, groups=0)

    to_map = row_to_mapping or (lambda r: r if isinstance(r, Mapping) else {})  # type: ignore[return-value]
    mappings: List[Mapping[str, Any]] = [to_map(r) for r in rows]
    id_to_row = {_row_video_id(m): r for m, r in zip(mappings, rows) if _row_video_id(m)}

    kept_ids: List[str] = []
    skipped: Dict[str, str] = {}
    groups = 0

    for cluster in cluster_duplicate_meetings(
        mappings,
        rel_duration_tol=rel_duration_tol,
        abs_duration_tol_min=abs_duration_tol_min,
    ):
        if len(cluster) <= 1:
            vid = _row_video_id(cluster[0])
            if vid:
                kept_ids.append(vid)
            continue
        groups += 1
        winner = pick_preferred_upload(cluster)
        win_id = _row_video_id(winner)
        if not win_id:
            continue
        kept_ids.append(win_id)
        for row in cluster:
            vid = _row_video_id(row)
            if vid and vid != win_id:
                skipped[vid] = win_id

    kept_rows = [id_to_row[i] for i in kept_ids if i in id_to_row]
    return kept_rows, DedupeResult(kept=kept_ids, skipped=skipped, groups=groups)


def dedupe_video_id_map(
    event_ids: Dict[str, int],
    metadata_rows: Sequence[Mapping[str, Any]],
) -> tuple[Dict[str, int], DedupeResult]:
    """Filter ``event_ids`` (video_id -> event_pk) to preferred uploads only."""
    meta_by_id = {_row_video_id(r): r for r in metadata_rows if _row_video_id(r)}
    ordered = []
    for vid in event_ids:
        base = meta_by_id.get(vid, {"video_id": vid})
        ordered.append({**base, "video_id": vid})

    kept_meta, result = dedupe_meeting_rows(ordered)
    kept_set = {_row_video_id(r) for r in kept_meta}
    filtered = {vid: eid for vid, eid in event_ids.items() if vid in kept_set}
    return filtered, result


def log_duplicate_skips(
    result: DedupeResult,
    *,
    title_by_id: Optional[Mapping[str, str]] = None,
    row_by_id: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> None:
    if not result.skipped:
        return
    titles = title_by_id or {}
    rows = row_by_id or {}
    for loser, winner in sorted(result.skipped.items()):
        title = titles.get(loser) or titles.get(winner) or ""
        win_row = rows.get(winner) or {}
        reason = "with captions" if _has_captions(win_row) else "preferred upload"
        logger.info(
            "Skipping duplicate upload {} (prefer {} {}){}",
            loser,
            winner,
            reason,
            f" — {title[:60]}" if title else "",
        )
    logger.info(
        "Duplicate meeting dedupe: kept {} upload(s), skipped {} in {} group(s)",
        len(result.kept),
        len(result.skipped),
        result.groups,
    )


def fetch_youtube_rows_for_dedupe(
    database_url: str,
    jurisdiction_id: str,
    *,
    video_ids: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT
            y.video_id,
            y.title,
            y.event_date::text AS event_date,
            y.duration_minutes,
            COALESCE(t.has_transcript, false) AS has_transcript
        FROM bronze.bronze_event_youtube y
        LEFT JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
        WHERE y.jurisdiction_id = %s
          AND y.video_id IS NOT NULL
    """
    params: list[Any] = [jurisdiction_id]
    if video_ids is not None:
        ids = [v for v in video_ids if v]
        if not ids:
            return []
        sql += " AND y.video_id = ANY(%s)"
        params.append(ids)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
