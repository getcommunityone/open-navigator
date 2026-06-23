"""QA guards for meeting calendar dates on recorded-video analyses."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Optional, Union

from llm.gemini.transcript_cache_paths import (
    extract_meeting_date_from_title,
    resolve_meeting_event_date,
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MEETING_ID_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})$")

PLAUSIBLE_MEETING_YEAR_MIN = 1990
PLAUSIBLE_MEETING_YEAR_MAX = 2035


def _as_date(value: Union[str, datetime, date, None]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()[:10]
    if not _ISO_DATE.fullmatch(raw):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def plausible_meeting_year(year: int) -> bool:
    return PLAUSIBLE_MEETING_YEAR_MIN <= int(year) <= PLAUSIBLE_MEETING_YEAR_MAX


def is_plausible_meeting_date(value: Union[str, datetime, date, None]) -> bool:
    parsed = _as_date(value)
    if parsed is None:
        return False
    return plausible_meeting_year(parsed.year)


def is_future_meeting_date(
    value: Union[str, datetime, date, None],
    *,
    as_of: Optional[date] = None,
) -> bool:
    parsed = _as_date(value)
    if parsed is None:
        return False
    ref = as_of or datetime.now(timezone.utc).date()
    return parsed > ref


def _date_from_meeting_id(meeting_id: str) -> Optional[str]:
    match = _MEETING_ID_DATE.search((meeting_id or "").strip())
    if not match:
        return None
    candidate = match.group(1)
    return candidate if is_plausible_meeting_date(candidate) else None


def suggest_recorded_video_meeting_date(
    *,
    title: str = "",
    meeting_id: str = "",
    published_at: Union[str, datetime, None] = None,
    transcript_text: str = "",
    as_of: Optional[date] = None,
) -> Optional[str]:
    """Best-effort non-future meeting date for a recorded video."""
    ref = as_of or datetime.now(timezone.utc).date()
    opening = (transcript_text or "")[:12_000]
    for candidate in (
        extract_meeting_date_from_title(opening),
        extract_meeting_date_from_title(title),
        _date_from_meeting_id(meeting_id),
        resolve_meeting_event_date(title, published_at=published_at),
    ):
        parsed = _as_date(candidate)
        if parsed is None or not is_plausible_meeting_date(parsed):
            continue
        if parsed <= ref:
            return parsed.isoformat()
    uploaded = _as_date(published_at)
    if uploaded is not None and is_plausible_meeting_date(uploaded) and uploaded <= ref:
        return uploaded.isoformat()
    return None


def qa_recorded_video_meeting_date(
    analysis: dict[str, Any],
    *,
    video_id: Optional[str],
    title: str = "",
    published_at: Union[str, datetime, None] = None,
    transcript_text: str = "",
    as_of: Optional[date] = None,
    fix: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """
    QA check: a recorded video cannot carry a future ``meeting_date``.

    When ``fix`` is true, replace a future date with a fallback (title,
    ``meeting_id``, or upload date) or clear it. Appends warnings under
    ``_meeting_date_qa`` on the analysis dict.
    """
    warnings: list[str] = []
    if not video_id or not isinstance(analysis, dict):
        return analysis, warnings

    meeting = analysis.get("meeting")
    if not isinstance(meeting, dict):
        return analysis, warnings

    meeting_id = str(meeting.get("meeting_id") or "")
    current = str(meeting.get("meeting_date") or analysis.get("event_date") or "").strip()[:10]
    if not current or not _ISO_DATE.fullmatch(current):
        return analysis, warnings
    if not is_future_meeting_date(current, as_of=as_of):
        return analysis, warnings

    msg = (
        f"Recorded video {video_id} has future meeting_date {current}; "
        "a recording cannot be from a meeting that has not happened yet."
    )
    warnings.append(msg)

    if not fix:
        qa = analysis.setdefault("_meeting_date_qa", [])
        if isinstance(qa, list):
            qa.extend(warnings)
        return analysis, warnings

    replacement = suggest_recorded_video_meeting_date(
        title=title,
        meeting_id=meeting_id,
        published_at=published_at,
        transcript_text=transcript_text,
        as_of=as_of,
    )
    if replacement:
        meeting["meeting_date"] = replacement
        if analysis.get("event_date"):
            analysis["event_date"] = replacement
        warnings.append(f"Corrected meeting_date to {replacement}.")
    else:
        meeting.pop("meeting_date", None)
        if analysis.get("event_date") == current:
            analysis.pop("event_date", None)
        warnings.append("Cleared future meeting_date (no non-future fallback found).")

    qa = analysis.setdefault("_meeting_date_qa", [])
    if isinstance(qa, list):
        qa.extend(warnings)
    return analysis, warnings
