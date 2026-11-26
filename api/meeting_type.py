"""Meeting type label for decision and meeting pages (#797).

The stored value (``event_youtube_with_jurisdiction.meeting_type``, e.g. ``CITY_COUNCIL``) is shown as a short
label. Only capitalization and spacing are normalized; the words are never changed or guessed. A blank or
UNKNOWN value gives ``None`` so the page omits the label.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

_OMIT = {"", "unknown"}
_SMALL_WORDS = {"of", "and", "the", "for", "to", "a", "an", "on", "in"}
_ACRONYMS = {"id", "pta", "pto", "tif", "cip", "hoa", "ems", "mpo"}


def meeting_type_label(raw: Any) -> Optional[str]:
    """``CITY_COUNCIL`` -> ``City Council``; None for blank/UNKNOWN."""
    if raw is None:
        return None
    text = re.sub(r"[\s_]+", " ", str(raw)).strip()
    if text.lower() in _OMIT:
        return None
    words = []
    for i, w in enumerate(text.split(" ")):
        lw = w.lower()
        if lw in _ACRONYMS:
            words.append(w.upper())
        elif i > 0 and lw in _SMALL_WORDS:
            words.append(lw)
        else:
            words.append(lw[:1].upper() + lw[1:])
    return " ".join(words)


#: The relation the type is read from. It is built in ``gold`` and is not in the public serving list, so an API
#: that reads ``public`` cannot resolve it (#840).
MEETING_TYPE_RELATION = "event_youtube_with_jurisdiction"

#: How long a "relation is missing" answer is trusted before it is checked again.
_MISSING_RECHECK_SECONDS = 300.0

_available: bool | None = None
_checked_at: float = 0.0


async def meeting_type_available(conn: Any) -> bool:
    """Whether ``event_youtube_with_jurisdiction`` resolves on this connection's search path.

    A true answer is kept for the life of the process. A false one is kept for five minutes, so publishing the
    relation later needs no restart. A failed check counts as missing."""
    global _available, _checked_at
    now = time.monotonic()
    if _available is True:
        return True
    if _available is False and now - _checked_at < _MISSING_RECHECK_SECONDS:
        return False
    try:
        found = bool(await conn.fetchval("SELECT to_regclass($1::text) IS NOT NULL", MEETING_TYPE_RELATION))
    except Exception:  # noqa: BLE001 - the label is optional; never fail the page for it
        found = False
    _available, _checked_at = found, now
    return found


def meeting_type_by_video_sql(video_expr: str, available: bool = True) -> str:
    """``meeting_type`` column for a row that has the meeting's video id in ``video_expr``.

    NULL when the relation is not published to the schema the API reads (``available`` false)."""
    if not available:
        return "NULL::text AS meeting_type"
    return (
        f"(SELECT y.meeting_type FROM {MEETING_TYPE_RELATION} y "
        f"WHERE y.video_id = {video_expr} LIMIT 1) AS meeting_type"
    )


def meeting_type_subquery(alias: str, available: bool = True) -> str:
    """Correlated subquery for a decision-list row: the raw meeting_type of the decision's meeting recording,
    read from event_youtube_with_jurisdiction by video_id. Selected as ``meeting_type`` (NULL when none, and
    NULL for every row when the relation is not published; see ``meeting_type_available``)."""
    if not available:
        return "NULL::text AS meeting_type"
    return (
        f"(SELECT y.meeting_type FROM event_decision ed "
        f"JOIN event_meeting m ON m.c1_event_id = ed.c1_event_id "
        f"JOIN {MEETING_TYPE_RELATION} y ON y.video_id = m.video_id "
        f"WHERE ed.event_decision_id = {alias}.event_decision_id "
        f"AND m.video_id IS NOT NULL LIMIT 1) AS meeting_type"
    )
