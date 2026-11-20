"""Score vote-phrase hits against Gemini Part 1 media anchors."""

from __future__ import annotations

import psycopg2
from loguru import logger

from llm.ner.phrases import PHRASE_PATTERNS
from llm.ner.store import TABLE

DESIGN_PHRASE_CODES: tuple[str, ...] = tuple(PHRASE_PATTERNS.keys())
NEARBY_WINDOW_SECONDS = 120.0

_GEMINI_ANCHORS_BODY = """
SELECT DISTINCT ON (a.video_id, COALESCE(dec->>'decision_id', 'idx-' || ord::text))
  a.video_id,
  COALESCE(dec->>'decision_id', 'idx-' || ord::text) AS decision_id,
  COALESCE(dec->>'headline', '') AS headline,
  (dec->'media_anchor'->>'timestamp_start_seconds')::double precision AS anchor_seconds
FROM bronze.bronze_events_analysis_ai a
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(a.structured_analysis->'decisions', '[]'::jsonb)
) WITH ORDINALITY AS t(dec, ord)
WHERE a.analysis_type = 'policy_frame_analysis'
  AND COALESCE(a.video_id, '') <> ''
  AND dec->'media_anchor'->>'timestamp_start_seconds' IS NOT NULL
  {analysis_filter}
ORDER BY a.video_id, COALESCE(dec->>'decision_id', 'idx-' || ord::text), a.updated_at DESC NULLS LAST
"""

_PREFERRED_ANALYSIS_FILTER = """
  AND a.id IN (SELECT DISTINCT analysis_id FROM public.event_decision)
"""

_FALLBACK_ANALYSIS_FILTER = """
  AND a.video_id IN (
    SELECT DISTINCT m.video_id
    FROM public.event_decision d
    JOIN public.event_meeting m ON m.event_meeting_id = d.analysis_id
    WHERE COALESCE(m.video_id, '') <> ''
  )
"""


def _hits_within(hits: list[tuple[float, str]], anchor_seconds: float, window: float) -> list[tuple[float, str]]:
    return [(t, code) for t, code in hits if abs(t - anchor_seconds) <= window]


def _anchor_key(row: dict) -> tuple[str, str]:
    return (row["video_id"], row["decision_id"])


def merge_anchor_rows(preferred: list[dict], fallback: list[dict]) -> tuple[list[dict], int]:
    """Prefer mart-linked analyses; fill remaining anchors from Part 1 videos."""
    seen = {_anchor_key(row) for row in preferred}
    # Fallback fills (video_id, decision_id) pairs the preferred analysis did not anchor.
    extra = [row for row in fallback if _anchor_key(row) not in seen]
    return preferred + extra, len(extra)


def nearby_transcript_lines(
    segments: list[dict],
    anchor_seconds: float,
    *,
    window: float = NEARBY_WINDOW_SECONDS,
    max_lines: int = 3,
) -> list[str]:
    """Return up to ``max_lines`` caption texts within ``window`` seconds of the anchor."""
    timed: list[tuple[float, float, str]] = []
    for seg in segments:
        start = seg.get("start")
        if start is None:
            continue
        t = float(start)
        delta = abs(t - anchor_seconds)
        if delta > window:
            continue
        text = (seg.get("text") or "").strip()
        if text:
            timed.append((delta, t, text))
    timed.sort(key=lambda item: (item[0], item[1]))
    return [text for _, _, text in timed[:max_lines]]


def score_anchors(
    anchors: list[dict],
    hits_by_video: dict[str, list[tuple[float, str]]],
    *,
    window: float = 60.0,
) -> dict:
    """Return summary counts and miss records for anchors without a hit within ``window``."""
    decisions_hit = 0
    decisions_missed: list[dict] = []

    for anchor in anchors:
        video_id = anchor["video_id"]
        anchor_seconds = float(anchor["anchor_seconds"])
        video_hits = hits_by_video.get(video_id, [])
        if _hits_within(video_hits, anchor_seconds, window):
            decisions_hit += 1
            continue

        nearby = _hits_within(video_hits, anchor_seconds, NEARBY_WINDOW_SECONDS)
        nearby_codes = sorted({code for _, code in nearby})
        missing_guess = [c for c in DESIGN_PHRASE_CODES if c not in nearby_codes]
        decisions_missed.append(
            {
                "video_id": video_id,
                "decision_id": anchor["decision_id"],
                "headline": anchor["headline"],
                "anchor_seconds": anchor_seconds,
                "nearby_phrase_codes": nearby_codes,
                "missing_codes_guess": missing_guess,
            }
        )

    return {
        "decisions_with_anchor": len(anchors),
        "decisions_hit": decisions_hit,
        "decisions_missed": decisions_missed,
    }


def _fetch_anchor_rows(cur, analysis_filter: str) -> list[dict]:
    sql = _GEMINI_ANCHORS_BODY.format(analysis_filter=analysis_filter)
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


def load_gemini_anchors(database_url: str, *, limit: int | None = None) -> list[dict]:
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            preferred = _fetch_anchor_rows(cur, _PREFERRED_ANALYSIS_FILTER)
            fallback = _fetch_anchor_rows(cur, _FALLBACK_ANALYSIS_FILTER)
            merged, fallback_only = merge_anchor_rows(preferred, fallback)
            logger.info(
                "Gemini anchors: {} from event_decision analyses, {} fallback-only",
                len(preferred),
                fallback_only,
            )
            if limit is not None:
                return merged[:limit]
            return merged
    finally:
        conn.close()


def load_hits_by_video(database_url: str, video_ids: set[str] | None = None) -> dict[str, list[tuple[float, str]]]:
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            if video_ids:
                cur.execute(
                    f"SELECT video_id, start_seconds, phrase_code FROM {TABLE} "
                    "WHERE video_id = ANY(%s)",
                    (list(video_ids),),
                )
            else:
                cur.execute(f"SELECT video_id, start_seconds, phrase_code FROM {TABLE}")
            by_video: dict[str, list[tuple[float, str]]] = {}
            for video_id, start_seconds, phrase_code in cur.fetchall():
                by_video.setdefault(video_id, []).append((float(start_seconds), phrase_code))
            return by_video
    finally:
        conn.close()