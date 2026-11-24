"""Which saved analyses may be loaded into the database (#796).

The loader reads ``02_analysis/*.json`` files. A file is *skipped*, never deleted or changed, when:

* ``policy_excluded`` - the video's transcript was marked ``excluded:<reason>`` (promos, news, non-meetings);
* ``junk_channel``    - its channel is classified junk;
* ``non_meeting_type`` - its ``meeting_type`` is OTHER, UNKNOWN or blank;
* ``low_keep_score``  - its Jev keep-score is below the floor (humans' ``government_meeting`` / ``town_hall``
  overrides are respected; unscreened videos are never skipped).

A video with no row in ``bronze.bronze_event_youtube`` cannot be judged and is not skipped (it is counted).
The first matching rule, in the order above, is the reason reported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

SKIP_REASONS = ("policy_excluded", "junk_channel", "non_meeting_type", "low_keep_score")
NON_MEETING_TYPES = frozenset({"", "OTHER", "UNKNOWN"})
DEFAULT_MIN_MEETING_P = 0.6


def tier_from_path(path: Path) -> str:
    """``full`` for ``<stem>_full.json``, else ``light`` (full artifacts carry the suffix)."""
    return "full" if Path(path).stem.endswith("_full") else "light"


def meta_matches_file(meta: Optional[Mapping[str, Any]], analysis_path: Path) -> bool:
    """False when the metadata was written for the other tier's analysis file.

    Before #796 a full run overwrote the light run's ``<stem>.meta.json``; that shared file lists the
    full analysis file in ``files.analysis_json``. Pairing it with the light file would label a light
    analysis with the full run's model. No ``files.analysis_json`` means nothing to compare.

    Only the tier is compared, not the name (#820): an analysis and its metadata are renamed together
    when a meeting's date or title is corrected, and the path stored inside the metadata keeps the old
    name. A different name with the same tier is still this file's own record.
    """
    if not meta:
        return True
    files = meta.get("files")
    recorded = files.get("analysis_json") if isinstance(files, Mapping) else None
    if not recorded:
        return True
    return tier_from_path(Path(str(recorded))) == tier_from_path(Path(analysis_path))


def decide_skip(info: Optional[Mapping[str, Any]], low_keep: bool) -> Optional[str]:
    """The reason to skip a video, or ``None`` to load it. ``info`` is one row from :func:`fetch_video_info`."""
    if info is None:
        return None
    if info.get("excluded"):
        return "policy_excluded"
    if info.get("junk"):
        return "junk_channel"
    if str(info.get("meeting_type") or "").strip().upper() in NON_MEETING_TYPES:
        return "non_meeting_type"
    if low_keep:
        return "low_keep_score"
    return None


def fetch_video_info(conn: Any, video_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Meeting type, junk-channel and excluded flags per video, from the bronze tables.

    Optional tables (channel classification, transcripts) are checked for first; a warehouse
    without them simply has nothing to skip on."""
    ids = sorted({v for v in video_ids if v})
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('bronze.bronze_youtube_channel_classification') IS NOT NULL, "
            "       to_regclass('bronze.bronze_event_youtube_transcript') IS NOT NULL"
        )
        has_class, has_tx = cur.fetchone()
        junk_sql = (
            "EXISTS (SELECT 1 FROM bronze.bronze_youtube_channel_classification c "
            "WHERE c.channel_id = y.channel_id AND c.is_junk IS TRUE)"
            if has_class
            else "FALSE"
        )
        excl_sql = (
            "COALESCE((SELECT bool_or(COALESCE(t.transcript_source, '') LIKE 'excluded:%%') "
            "FROM bronze.bronze_event_youtube_transcript t WHERE t.video_id = y.video_id), FALSE)"
            if has_tx
            else "FALSE"
        )
        cur.execute(
            f"SELECT y.video_id, COALESCE(y.meeting_type, ''), {junk_sql}, {excl_sql} "
            "FROM bronze.bronze_event_youtube y WHERE y.video_id = ANY(%s)",
            (ids,),
        )
        return {
            vid: {"meeting_type": mt, "junk": bool(junk), "excluded": bool(excl)}
            for vid, mt, junk, excl in cur.fetchall()
        }
