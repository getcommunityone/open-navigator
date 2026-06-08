"""
Load meeting transcripts straight from the warehouse.

The analyze pipeline historically read transcript text from on-disk JSON caches
and fell back to live YouTube captions. This module makes
``bronze.bronze_event_youtube_transcript`` the primary source.

The transcript text in that table lives in one of three columns, depending on how
the row was captioned:

1. ``segments``           — JSONB array of ``{text, start, duration}`` objects.
2. ``caption_text_timed`` — text with ``{HH:MM:SS}`` timestamp markers inline.
3. ``raw_text``           — a single untimed blob (last resort).

``fetch_db_transcript`` normalizes whichever is present into the same ``yt`` dict
shape the rest of the pipeline expects from ``fetch_youtube_transcript``:
``{video_id, language, is_auto_generated, raw_text, segments, transcript_source}``
where each segment is ``{text, start, duration}`` (seconds).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

# ``{HH:MM:SS}`` or ``{MM:SS}`` markers used in ``caption_text_timed``.
_TS_RE = re.compile(r"\{(\d{1,2}):(\d{2})(?::(\d{2}))?\}")


def _norm_segments_jsonb(raw: Any) -> List[Dict[str, Any]]:
    """Pass through a ``segments`` JSONB array, keeping only usable rows."""
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        seg: Dict[str, Any] = {
            "text": text,
            "start": float(item.get("start") or 0.0),
        }
        if item.get("duration") is not None:
            seg["duration"] = float(item.get("duration") or 0.0)
        # Preserve diarization hints when a previous stage already set them.
        if item.get("speaker") is not None:
            seg["speaker"] = item.get("speaker")
        if item.get("speaker_guess") is not None:
            seg["speaker_guess"] = item.get("speaker_guess")
        out.append(seg)
    return out


def _parse_caption_text_timed(text: str) -> List[Dict[str, Any]]:
    """Split ``{HH:MM:SS} words {HH:MM:SS} words`` into ``{text, start}`` segments."""
    if not text:
        return []
    marks = list(_TS_RE.finditer(text))
    if not marks:
        return []
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(marks):
        g1, g2, g3 = m.group(1), m.group(2), m.group(3)
        if g3 is not None:  # {HH:MM:SS}
            start = int(g1) * 3600 + int(g2) * 60 + int(g3)
        else:  # {MM:SS}
            start = int(g1) * 60 + int(g2)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = " ".join(text[m.end() : end].split()).strip()
        if body:
            out.append({"text": body, "start": float(start)})
    return out


def normalize_transcript_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Turn a ``bronze_event_youtube_transcript`` row into a ``yt`` dict, or ``None``.

    Tries ``segments`` → ``caption_text_timed`` → ``raw_text`` in that order and
    returns ``None`` when none of them yield any usable text.
    """
    video_id = str(row.get("video_id") or "").strip()
    language = row.get("language") or "en"
    is_auto = bool(row.get("is_auto_generated"))
    raw_text = (row.get("raw_text") or "").strip()

    segments = _norm_segments_jsonb(row.get("segments"))
    origin = "segments"
    if not segments:
        segments = _parse_caption_text_timed(row.get("caption_text_timed") or "")
        origin = "caption_text_timed"
    if not segments and raw_text:
        segments = [{"text": raw_text, "start": 0.0}]
        origin = "raw_text"
    if not segments:
        return None

    return {
        "video_id": video_id,
        "language": language,
        "is_auto_generated": is_auto,
        "raw_text": raw_text or " ".join(s["text"] for s in segments),
        "segments": segments,
        "transcript_source": f"database:bronze_event_youtube_transcript ({origin})",
    }


def fetch_db_transcript(database_url: str, video_id: str) -> Optional[Dict[str, Any]]:
    """Fetch + normalize a single video's transcript from the warehouse.

    Returns the ``yt`` dict (see module docstring) or ``None`` when the video has
    no row, or a row with no usable text in any of the three columns.
    """
    vid = (video_id or "").strip()
    if not vid:
        return None

    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT video_id, language, is_auto_generated,
               segments, caption_text_timed, raw_text
        FROM bronze.bronze_event_youtube_transcript
        WHERE video_id = %s
        ORDER BY (segments IS NOT NULL) DESC,
                 length(COALESCE(caption_text_timed, '')) DESC,
                 last_updated DESC NULLS LAST
        LIMIT 1
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [vid])
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    yt = normalize_transcript_row(dict(row))
    if yt is not None:
        logger.info(
            "Using DB transcript for {} ({} segments, {})",
            vid,
            len(yt["segments"]),
            yt["transcript_source"],
        )
    return yt


def fetch_meeting_document_text(
    database_url: str,
    *,
    census_geoid: str,
    event_date: Optional[str],
    max_chars: int = 40_000,
) -> str:
    """Concatenated agenda/minutes text for a meeting, as analysis context.

    Matches scraped documents (bronze.bronze_meeting_document_text) to the video
    being analyzed by census_geoid + exact meeting date — the official record
    carries dollar amounts / staff recommendations / vote detail the spoken
    transcript often only alludes to. Agenda(s) first, then minutes; only rows
    with real extracted text (extraction_method='pymupdf_text'). Truncated to
    ``max_chars`` to bound prompt size/cost. Returns '' when nothing matches
    (e.g. scanned-only minutes, or no scraped docs) — never fabricates.
    """
    geoid = (census_geoid or "").strip()
    day = (event_date or "").strip()[:10]
    if not geoid or not day:
        return ""

    import psycopg2

    sql = """
        SELECT doc_type, content
        FROM bronze.bronze_meeting_document_text
        WHERE census_geoid = %s
          AND meeting_date = %s::date
          AND extraction_method = 'pymupdf_text'
          AND content IS NOT NULL
        ORDER BY CASE doc_type WHEN 'agenda' THEN 0 WHEN 'minutes' THEN 1 ELSE 2 END
    """
    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:  # noqa: BLE001 — context is best-effort, never fatal
        logger.warning("Meeting-document-text connect failed (geoid={}): {}", geoid, exc)
        return ""
    try:
        with conn.cursor() as cur:
            cur.execute(sql, [geoid, day])
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Meeting-document-text query failed (geoid={}, {}): {}", geoid, day, exc)
        return ""
    finally:
        conn.close()

    if not rows:
        return ""
    blocks: list[str] = []
    for doc_type, content in rows:
        text = (content or "").strip()
        if text:
            blocks.append(f"--- {doc_type.upper()} ---\n{text}")
    joined = "\n\n".join(blocks).strip()
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n…[truncated]"
    if joined:
        logger.info("Attached {} official-record doc(s) ({} chars) for {} on {}", len(rows), len(joined), geoid, day)
    return joined
