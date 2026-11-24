"""Which saved analyses may be loaded into the database (#796).

The loader reads ``02_analysis/*.json`` files. A file is *skipped*, never deleted or changed, when:

* ``policy_excluded`` - the video's transcript was marked ``excluded:<reason>`` (promos, news, non-meetings);
* ``junk_channel``    - its channel is classified junk;
* ``non_meeting_type`` - its ``meeting_type`` is OTHER, UNKNOWN or blank **and nothing else says it is a
  meeting** (#829). The scraper types a video from a handful of title words and calls the rest ``Other``, so
  committee meetings, commissions, work sessions and briefings all arrive as ``Other``. One is kept when a
  person marked it ``government_meeting`` / ``town_hall``, when its Jev keep-score is at or above the floor,
  or when its title names a public body or a meeting form;
* ``low_keep_score``  - its Jev keep-score is below the floor (humans' ``government_meeting`` / ``town_hall``
  overrides are respected; unscreened videos are never skipped).

A video with no row in ``bronze.bronze_event_youtube`` cannot be judged and is not skipped (it is counted).
The first matching rule, in the order above, is the reason reported.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

SKIP_REASONS = ("policy_excluded", "junk_channel", "non_meeting_type", "low_keep_score")
NON_MEETING_TYPES = frozenset({"", "OTHER", "UNKNOWN"})
DEFAULT_MIN_MEETING_P = 0.6
# A person's verdict on the Meeting kinds tab that means "this is a meeting".
KEEP_OVERRIDE_KINDS = frozenset({"government_meeting", "town_hall"})
SCREEN_TABLE = "bronze.bronze_transcript_screen_jev"
OVERRIDE_TABLE = "bronze.bronze_video_meeting_kind_override"

# A public body, or a form a public meeting takes. Whole words only, so "skateboard" and "onboarding"
# don't count; "board game" is the one common false friend. Place names (county, town) are deliberately
# absent: "County celebrates water park opening" is not a meeting.
_PUBLIC_MEETING_RE = re.compile(
    r"\b(?:"
    r"council|commission|commissioners?|committee|subcommittee|board(?!\s+games?)|authority|"
    r"aldermen|selectmen|trustees|supervisors|caucus|legislature|"
    r"work\s*session|study\s+session|executive\s+session|briefing|public\s+hearing|hearing|town\s+hall|workshop|"
    r"(?:regular|special|called|public|annual|monthly|emergency|organizational)\s+(?:meeting|session)"
    r")\b",
    re.IGNORECASE,
)


def title_names_public_meeting(title: Optional[str]) -> bool:
    """True when a video title names a public body or a meeting form (committee, work session, briefing...)."""
    return bool(title) and bool(_PUBLIC_MEETING_RE.search(str(title)))


def meeting_evidence(info: Mapping[str, Any], min_meeting_p: float = DEFAULT_MIN_MEETING_P) -> Optional[str]:
    """What says a video typed ``Other`` is a meeting after all: ``override``, ``keep_score``, ``title``, or ``None``.

    A person's verdict wins in both directions: marked as a meeting, it is one; marked as anything
    else, the title and the score are not consulted."""
    override = str(info.get("override_kind") or "").strip().lower()
    if override:
        return "override" if override in KEEP_OVERRIDE_KINDS else None
    keep_p = info.get("keep_p")
    if isinstance(keep_p, (int, float)) and not isinstance(keep_p, bool) and keep_p >= min_meeting_p:
        return "keep_score"
    if title_names_public_meeting(info.get("title")):
        return "title"
    return None


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


def is_untyped(info: Mapping[str, Any]) -> bool:
    """True when the scraper's ``meeting_type`` says nothing useful (OTHER, UNKNOWN or blank)."""
    return str(info.get("meeting_type") or "").strip().upper() in NON_MEETING_TYPES


def decide_skip(info: Optional[Mapping[str, Any]], low_keep: bool,
                min_meeting_p: float = DEFAULT_MIN_MEETING_P) -> Optional[str]:
    """The reason to skip a video, or ``None`` to load it. ``info`` is one row from :func:`fetch_video_info`."""
    if info is None:
        return None
    if info.get("excluded"):
        return "policy_excluded"
    if info.get("junk"):
        return "junk_channel"
    if is_untyped(info) and meeting_evidence(info, min_meeting_p) is None:
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
            "       to_regclass('bronze.bronze_event_youtube_transcript') IS NOT NULL, "
            f"       to_regclass('{SCREEN_TABLE}') IS NOT NULL, "
            f"       to_regclass('{OVERRIDE_TABLE}') IS NOT NULL"
        )
        has_class, has_tx, has_screen, has_override = (tuple(cur.fetchone()) + (False, False))[:4]
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
        # Jev keep-score P(government_meeting) + P(town_hall); NULL when unscreened or asked with older wording.
        keep_sql = (
            "(SELECT CASE WHEN s.meeting_kind_probabilities ? 'government_meeting' "
            "OR s.meeting_kind_probabilities ? 'town_hall' THEN "
            "COALESCE((s.meeting_kind_probabilities->>'government_meeting')::float, 0) + "
            "COALESCE((s.meeting_kind_probabilities->>'town_hall')::float, 0) END "
            f"FROM {SCREEN_TABLE} s WHERE s.video_id = y.video_id)"
            if has_screen
            else "NULL::float"
        )
        override_sql = (
            f"(SELECT o.override_kind FROM {OVERRIDE_TABLE} o WHERE o.video_id = y.video_id)"
            if has_override
            else "NULL::text"
        )
        cur.execute(
            f"SELECT y.video_id, COALESCE(y.meeting_type, ''), {junk_sql}, {excl_sql}, "
            f"COALESCE(y.title, ''), {keep_sql}, {override_sql} "
            "FROM bronze.bronze_event_youtube y WHERE y.video_id = ANY(%s)",
            (ids,),
        )
        return {
            vid: {"meeting_type": mt, "junk": bool(junk), "excluded": bool(excl), "title": title or "",
                  "keep_p": float(keep_p) if keep_p is not None else None, "override_kind": override or None}
            for vid, mt, junk, excl, title, keep_p, override in cur.fetchall()
        }
