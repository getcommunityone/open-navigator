"""Keep ``meeting.jurisdiction`` honest: never invent the Tuscaloosa demo place (#593).

Part 1 JSON's ``meeting.jurisdiction`` is a free-text label from the model. Demo
defaults and early CLI defaults taught many runs to write
``City of Tuscaloosa, Alabama`` (or the bare id ``tuscaloosa_0177256``) even when
the video's warehouse place is somewhere else. Scrub those inventions before the
analysis is cached or loaded to bronze.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, MutableMapping, Optional

# Display labels that are the Alabama demo scope, not a real extract from the tape.
_TUSCALOOSA_LABEL = re.compile(r"tuscaloosa", re.IGNORECASE)
# Bare warehouse / slug forms that must never be stored as the human jurisdiction line.
_ID_OR_SLUG = re.compile(
    r"^(?:city_of_)?tuscaloosa(?:[_ ]al(?:abama)?)?(?:[_ ]?\d+)?$",
    re.IGNORECASE,
)


def place_names_tuscaloosa(*, place_name: str = "", jurisdiction_id: str = "") -> bool:
    """True when the warehouse place for this video is actually Tuscaloosa."""
    return bool(
        _TUSCALOOSA_LABEL.search(place_name or "")
        or _TUSCALOOSA_LABEL.search(jurisdiction_id or "")
    )


def is_invented_tuscaloosa_jurisdiction(
    raw: Optional[str],
    *,
    place_name: str = "",
    jurisdiction_id: str = "",
) -> bool:
    """True when ``raw`` is a Tuscaloosa demo default that does not match the video's place."""
    text = (raw or "").strip()
    if not text:
        return False
    # Never keep a bare id / slug as the display jurisdiction.
    if text == (jurisdiction_id or "").strip() or _ID_OR_SLUG.match(text.replace(" ", "_")):
        return True
    if _TUSCALOOSA_LABEL.search(text) and not place_names_tuscaloosa(
        place_name=place_name, jurisdiction_id=jurisdiction_id
    ):
        return True
    return False


def scrub_meeting_jurisdiction(
    analysis: Mapping[str, Any] | MutableMapping[str, Any],
    *,
    place_name: str = "",
    jurisdiction_id: str = "",
) -> dict[str, Any]:
    """Return analysis with ``meeting.jurisdiction`` cleared when it is a demo invention."""
    out = dict(analysis)
    meeting = out.get("meeting")
    if not isinstance(meeting, dict):
        return out
    meeting = dict(meeting)
    raw = meeting.get("jurisdiction")
    if is_invented_tuscaloosa_jurisdiction(
        raw if isinstance(raw, str) else None,
        place_name=place_name,
        jurisdiction_id=jurisdiction_id,
    ):
        meeting["jurisdiction"] = None
    out["meeting"] = meeting
    return out
