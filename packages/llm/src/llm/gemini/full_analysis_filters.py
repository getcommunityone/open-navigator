"""Eligibility filters for full-tier analysis/reports (#755).

Multi-select keys are OR'd: a video matches if it satisfies any checked filter.
Full always requires a successful light analysis stamp first.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional, Sequence, Set

from loguru import logger

FULL_FILTER_KEYS = ("has_decisions", "interestingness", "data_center")
DEFAULT_FULL_FILTERS = ("has_decisions", "interestingness")

# Floor for interestingness_score (0–100 scale on public.item_interestingness).
_INTERESTINGNESS_FLOOR = float(os.getenv("FULL_INTERESTINGNESS_FLOOR", "40") or "40")
# Among light-analyzed videos in the candidate set, also keep the top 20%.
_INTERESTINGNESS_TOP_PCT = float(os.getenv("FULL_INTERESTINGNESS_TOP_PCT", "0.20") or "0.20")


def normalize_full_filters(raw: Optional[Iterable[str]]) -> list[str]:
    """Dedupe and keep only known keys; empty input → empty list (caller refuses)."""
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or ():
        key = str(item or "").strip().lower()
        if key not in FULL_FILTER_KEYS or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def eligible_full_video_ids(
    database_url: str,
    video_ids: Sequence[str],
    filters: Sequence[str],
    *,
    require_light: bool = True,
    require_full_analysis: bool = False,
) -> Set[str]:
    """Return video_ids that pass light/full prerequisites and any checked filter (OR).

    ``require_full_analysis`` is for reports-full (must already have analysis full).
    """
    import psycopg2

    vids = [str(v).strip() for v in video_ids if str(v).strip()]
    if not vids:
        return set()
    keys = normalize_full_filters(filters)
    if not keys:
        return set()

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            # Base set: light (and optionally full) stamps.
            if require_full_analysis:
                cur.execute(
                    """
                    SELECT video_id
                    FROM bronze.bronze_event_youtube
                    WHERE video_id = ANY(%s)
                      AND policy_analysis_full_at IS NOT NULL
                      AND (%s = FALSE OR policy_analysis_at IS NOT NULL)
                    """,
                    (vids, require_light),
                )
            else:
                cur.execute(
                    """
                    SELECT video_id
                    FROM bronze.bronze_event_youtube
                    WHERE video_id = ANY(%s)
                      AND (%s = FALSE OR policy_analysis_at IS NOT NULL)
                      AND policy_analysis_full_at IS NULL
                    """,
                    (vids, require_light),
                )
            base = {str(r[0]) for r in cur.fetchall()}
            if not base:
                return set()

            matched: Set[str] = set()
            base_list = list(base)

            if "has_decisions" in keys:
                matched |= _match_has_decisions(cur, base_list)

            if "data_center" in keys:
                matched |= _match_data_center(cur, base_list)

            if "interestingness" in keys:
                matched |= _match_interestingness(cur, base_list)

            return matched
    finally:
        conn.close()


def _match_has_decisions(cur: Any, video_ids: Sequence[str]) -> Set[str]:
    out: Set[str] = set()
    try:
        cur.execute(
            """
            SELECT video_id
            FROM bronze.bronze_transcript_screen_jev
            WHERE video_id = ANY(%s)
              AND has_decisions_p IS NOT NULL
              AND has_decisions_p >= 0.5
            """,
            (list(video_ids),),
        )
        out |= {str(r[0]) for r in cur.fetchall()}
    except Exception as exc:
        cur.connection.rollback()
        logger.debug("full filter has_decisions (jev) skipped: {}", exc)

    try:
        cur.execute(
            """
            SELECT DISTINCT video_id
            FROM bronze.bronze_policy_decisions
            WHERE video_id = ANY(%s)
            """,
            (list(video_ids),),
        )
        out |= {str(r[0]) for r in cur.fetchall()}
    except Exception as exc:
        cur.connection.rollback()
        logger.debug("full filter has_decisions (bronze decisions) skipped: {}", exc)
    return out


def _match_data_center(cur: Any, video_ids: Sequence[str]) -> Set[str]:
    try:
        cur.execute(
            """
            SELECT video_id
            FROM bronze.bronze_transcript_screen_jev
            WHERE video_id = ANY(%s)
              AND mentions_data_center_p IS NOT NULL
              AND mentions_data_center_p >= 0.5
            """,
            (list(video_ids),),
        )
        return {str(r[0]) for r in cur.fetchall()}
    except Exception as exc:
        cur.connection.rollback()
        logger.debug("full filter data_center skipped: {}", exc)
        return set()


def _match_interestingness(cur: Any, video_ids: Sequence[str]) -> Set[str]:
    """Top 20% by score among candidates, or score >= floor."""
    try:
        cur.execute(
            """
            SELECT em.video_id, MAX(ii.interestingness_score)::float AS score
            FROM public.event_meeting em
            JOIN public.item_interestingness ii
              ON ii.meeting_id = em.event_meeting_id
            WHERE em.video_id = ANY(%s)
              AND ii.interestingness_score IS NOT NULL
            GROUP BY em.video_id
            """,
            (list(video_ids),),
        )
        rows = [(str(r[0]), float(r[1])) for r in cur.fetchall()]
    except Exception as exc:
        cur.connection.rollback()
        logger.debug("full filter interestingness skipped: {}", exc)
        return set()

    if not rows:
        return set()
    rows.sort(key=lambda x: x[1], reverse=True)
    floor = _INTERESTINGNESS_FLOOR
    top_n = max(1, int(len(rows) * max(0.0, min(1.0, _INTERESTINGNESS_TOP_PCT)) + 0.999))
    top_ids = {vid for vid, _ in rows[:top_n]}
    floor_ids = {vid for vid, score in rows if score >= floor}
    return top_ids | floor_ids
