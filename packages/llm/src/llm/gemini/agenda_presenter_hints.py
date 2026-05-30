"""
Build agenda-segment hints from caption lines (no audio).

Helps Flash-Lite attach ``presenter_person_ids`` and ``media_anchor`` to
``uncontested_items[]`` when the transcript names staff before each item
(e.g. ``Mike.``, ``Agenda item two``, ``Brian.``).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from llm.gemini.speaker_hints import speaker_alias_index


_AGENDA_START = re.compile(
    r"(agenda\s+item|item\s+number|item\s+no\.?|new\s+business|resolution\s+accepting|"
    r"approval\s+of\s+a|authorization\s+of)",
    re.I,
)
_TRAILING_NAME = re.compile(r"\.\s*([A-Za-z][A-Za-z.'-]{1,20})\.\s*$")
_STANDALONE_NAME = re.compile(r"^>>?\s*([A-Za-z][A-Za-z.'-]{1,20})\.\s*$")


def _fmt_ts(seconds: float) -> str:
    s = max(0.0, float(seconds))
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _guess_presenter(
    text: str,
    aliases: Dict[str, str],
) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    m = _STANDALONE_NAME.match(t)
    if m:
        key = m.group(1).replace(".", "").lower()
        return aliases.get(key)
    m = _TRAILING_NAME.search(t)
    if m:
        key = m.group(1).replace(".", "").lower()
        return aliases.get(key)
    return None


def segment_agenda_blocks(
    segments: List[Dict[str, Any]],
    known_speakers: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Split captions into coarse agenda blocks with start/end seconds and presenter guess.
    """
    aliases = speaker_alias_index(known_speakers)
    blocks: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    pending_presenter: Optional[str] = None

    for seg in segments:
        text = (seg.get("text") or "").strip()
        start = float(seg.get("start") or 0)
        end = start + float(seg.get("duration") or 0)

        name = _guess_presenter(text, aliases)
        if name:
            pending_presenter = name

        if _AGENDA_START.search(text) or (
            current is None and re.search(r"minutes approved|new business", text, re.I)
        ):
            if current is not None:
                blocks.append(current)
            topic = text[:120]
            current = {
                "start_seconds": start,
                "end_seconds": end,
                "presenter_person_name": pending_presenter,
                "topic_snippet": topic,
            }
            pending_presenter = None
            continue

        if current is not None:
            current["end_seconds"] = end
            if not current.get("topic_snippet") and len(text) > 20:
                current["topic_snippet"] = text[:120]
            if pending_presenter and not current.get("presenter_person_name"):
                current["presenter_person_name"] = pending_presenter
                pending_presenter = None

    if current is not None:
        blocks.append(current)
    return blocks


def format_agenda_presenter_hints_block(
    blocks: List[Dict[str, Any]],
    *,
    jurisdiction_id: str,
) -> str:
    if not blocks:
        return ""
    lines = [
        "=== AGENDA SEGMENT HINTS (caption structure; map to people[].person_id) ===",
        f"jurisdiction_id: {jurisdiction_id}",
        "Use these anchors when filling uncontested_items[]: presenter_person_ids, "
        "media_anchor.timestamp_start_seconds / end_seconds, subject_id.",
        "Order U001, U002, … in the same order as these blocks when items are routine votes.",
        "",
    ]
    for i, b in enumerate(blocks, 1):
        start = _fmt_ts(b["start_seconds"])
        end = _fmt_ts(b["end_seconds"])
        presenter = b.get("presenter_person_name") or "unknown"
        topic = (b.get("topic_snippet") or "").replace("\n", " ")
        lines.append(
            f"block_{i:02d} | {start}-{end} | presenter_guess={presenter} | topic={topic}"
        )
    lines.append("")
    return "\n".join(lines)


def enrich_uncontested_media_anchors(
    analysis: Dict[str, Any],
    *,
    video_url: str,
) -> Dict[str, Any]:
    """Add playback_url with &t= on each uncontested item that has media_anchor.seconds."""
    out = dict(analysis)
    items = out.get("uncontested_items")
    if not isinstance(items, list) or not video_url:
        return out
    base = video_url.split("&")[0]
    for row in items:
        if not isinstance(row, dict):
            continue
        anchor = row.get("media_anchor")
        if not isinstance(anchor, dict):
            continue
        start = anchor.get("timestamp_start_seconds")
        if start is not None:
            anchor = dict(anchor)
            anchor["playback_url"] = f"{base}&t={int(float(start))}s"
            row["media_anchor"] = anchor
    out["uncontested_items"] = items
    return out
