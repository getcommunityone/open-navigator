"""Meeting type label for decision and meeting pages (#797).

The stored value (``event_youtube_with_jurisdiction.meeting_type``, e.g. ``CITY_COUNCIL``) is shown as a short
label. Only capitalization and spacing are normalized; the words are never changed or guessed. A blank or
UNKNOWN value gives ``None`` so the page omits the label.
"""

from __future__ import annotations

import re
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


def meeting_type_subquery(alias: str) -> str:
    """Correlated subquery for a decision-list row: the raw meeting_type of the decision's meeting recording,
    read from event_youtube_with_jurisdiction by video_id. Selected as ``meeting_type`` (NULL when none)."""
    return (
        f"(SELECT y.meeting_type FROM event_decision ed "
        f"JOIN event_meeting m ON m.c1_event_id = ed.c1_event_id "
        f"JOIN event_youtube_with_jurisdiction y ON y.video_id = m.video_id "
        f"WHERE ed.event_decision_id = {alias}.event_decision_id "
        f"AND m.video_id IS NOT NULL LIMIT 1) AS meeting_type"
    )
