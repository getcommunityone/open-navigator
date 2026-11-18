"""Read meetings from the Legistar Web API (#536).

``https://webapi.legistar.com/v1/<client>/events`` lists a client's meetings with the
body, date, time, location, agenda and minutes PDF links, the video path and the
Granicus clip id (``EventMedia``). ``/events/<id>/eventitems`` gives the agenda items
and, once minutes are taken, each item's minutes note, action and vote result. Those
are what this reader keeps as ``agenda_text`` and ``minutes_text``: text the platform
serves through its API, not PDF extraction.

The agenda/minutes PDFs live on ``<client>.legistar1.com`` / ``legistar*.granicus.com``,
whose robots.txt disallows all crawlers, so only their URLs are kept. Legistar serves
no captions.

Video: ``EventVideoPath`` when Legistar has one (``video_url_source='legistar'``).
Otherwise, when the event has a Granicus clip id and the government's Granicus host
is known from the #460 survey, the URL is the Granicus player for that clip
(``video_url_source='granicus_clip'``). A clip id with no known host leaves
``video_url`` empty; the meeting is ``video_url_unknown``, not queued.

Usage (one client, dry run)::

    python -m scrapers.platforms.legistar dakota --since 2026-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import quote

from loguru import logger

from scrapers.platforms.http import PlatformFetchError, PoliteClient
from scrapers.platforms.model import PlatformMeeting, PortalResult

API_BASE = "https://webapi.legistar.com/v1"
PAGE_SIZE = 1000  # the Web API's maximum $top
PLATFORM = "legistar"


class LegistarClientError(PlatformFetchError):
    """The Web API answered with an error message instead of data."""

    def __init__(self, message: str, status: str) -> None:
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------


def events_url(client: str, since: date, top: int = PAGE_SIZE, skip: int = 0, until: Optional[date] = None) -> str:
    cond = f"EventDate ge datetime'{since.isoformat()}'"
    if until is not None:
        cond += f" and EventDate le datetime'{until.isoformat()}'"
    flt = quote(cond, safe="")
    order = quote("EventDate desc,EventId desc", safe="")
    return f"{API_BASE}/{client}/events?$filter={flt}&$orderby={order}&$top={top}&$skip={skip}"


def event_items_url(client: str, event_id: int | str) -> str:
    return f"{API_BASE}/{client}/events/{event_id}/eventitems?AgendaNote=1&MinutesNote=1&Attachments=0"


def classify_error(payload: Any) -> Optional[tuple[str, str]]:
    """``(status, message)`` when a Web API response is an error message, else None."""
    if not isinstance(payload, dict):
        return None
    msg = str(payload.get("ExceptionMessage") or payload.get("Message") or "")
    low = msg.lower()
    if "not set up in insite" in low or "legistarconnectionstring" in low:
        return "not_configured", msg
    if "token" in low:
        return "token_required", msg
    return "error", msg or json.dumps(payload)[:300]


_RTF_DEST = re.compile(r"\\\*|\\(fonttbl|colortbl|stylesheet|info|pict|header|footer|listtable|listoverridetable|rsidtbl|generator|xmlnstbl|themedata|datastore|latentstyles)\b")


def rtf_to_text(value: Optional[str]) -> Optional[str]:
    """Plain text from an RTF string (Legistar stores minutes notes as RTF).

    Drops header groups (font/colour tables, ``{\\*...}`` destinations), turns
    ``\\par``/``\\line`` into line breaks, decodes ``\\'hh`` and ``\\uN`` escapes and
    removes the remaining control words. Non-RTF text is returned stripped.
    """
    if value is None:
        return None
    s = str(value)
    if not s.lstrip().startswith("{\\rtf"):
        out = s.strip()
        return out or None
    out: list[str] = []
    stack: list[bool] = []  # per group: is it a skipped destination?
    skip = False
    i, n = 0, len(s)
    uc_skip = 0
    while i < n:
        ch = s[i]
        if ch == "{":
            stack.append(skip)
            if _RTF_DEST.match(s, i + 1):
                skip = True
            i += 1
        elif ch == "}":
            skip = stack.pop() if stack else False
            i += 1
        elif ch == "\\":
            if i + 1 < n and s[i + 1] in "\\{}":
                if not skip:
                    out.append(s[i + 1])
                i += 2
                continue
            if i + 1 < n and s[i + 1] == "'":
                if not skip and uc_skip == 0:
                    try:
                        out.append(bytes([int(s[i + 2 : i + 4], 16)]).decode("cp1252"))
                    except (ValueError, UnicodeDecodeError):
                        pass
                uc_skip = max(0, uc_skip - 1)
                i += 4
                continue
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?", s[i:])
            if not m:
                i += 2
                continue
            word, arg = m.group(1), m.group(2)
            i += m.end()
            if skip:
                continue
            if word in ("par", "line", "row"):
                out.append("\n")
            elif word == "tab" or word == "cell":
                out.append("\t")
            elif word == "u" and arg is not None:
                code = int(arg)
                out.append(chr(code + 65536 if code < 0 else code))
                uc_skip = 1
        elif ch in "\r\n":
            i += 1
        else:
            if uc_skip:
                uc_skip -= 1  # the plain-text fallback after a \\uN escape
            elif not skip:
                out.append(ch)
            i += 1
    text = "".join(out)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _parse_date(value: Any) -> Optional[date]:
    s = _clean(value)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19]).date()
    except ValueError:
        return None


def _parse_utc(value: Any) -> Optional[datetime]:
    s = _clean(value)
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", ""))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _ordered(items: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda it: (it.get(key) is None, it.get(key) or 0, it.get("EventItemId") or 0))


def agenda_text(items: Sequence[dict[str, Any]]) -> Optional[str]:
    """The agenda as the API lists it: item number, title and agenda note, in order."""
    lines: list[str] = []
    for it in _ordered(items, "EventItemAgendaSequence"):
        title = rtf_to_text(_clean(it.get("EventItemTitle")))
        note = rtf_to_text(_clean(it.get("EventItemAgendaNote")))
        if not title and not note:
            continue
        num = _clean(it.get("EventItemAgendaNumber"))
        head = " ".join(p for p in (num, title) if p)
        lines.append(head if not note else f"{head}\n{note}" if head else note)
    return "\n\n".join(lines) or None


def minutes_text(items: Sequence[dict[str, Any]]) -> Optional[str]:
    """Minutes the API carries: each item's minutes note, action and vote result.

    None unless at least one item has a minutes note or action text; a vote flag on its
    own is not minutes.
    """
    if not any(_clean(it.get("EventItemMinutesNote")) or _clean(it.get("EventItemActionText")) for it in items):
        return None
    lines: list[str] = []
    for it in _ordered(items, "EventItemMinutesSequence"):
        note = rtf_to_text(_clean(it.get("EventItemMinutesNote")))
        action_text = rtf_to_text(_clean(it.get("EventItemActionText")))
        action = _clean(it.get("EventItemActionName"))
        passed = _clean(it.get("EventItemPassedFlagName"))
        if not (note or action_text or action or passed):
            continue
        title = rtf_to_text(_clean(it.get("EventItemTitle")))
        parts = [p for p in (title,) if p]
        result = " - ".join(p for p in (action, passed) if p)
        if result:
            parts.append(f"Action: {result}")
        if action_text:
            parts.append(action_text)
        if note:
            parts.append(note)
        lines.append("\n".join(parts))
    return "\n\n".join(lines) or None


def granicus_player_url(host: str, clip_id: str) -> str:
    return f"https://{host}/MediaPlayer.php?clip_id={clip_id}"


def meeting_from_event(
    client: str,
    event: dict[str, Any],
    items: Optional[Sequence[dict[str, Any]]] = None,
    *,
    jurisdiction_id: Optional[str] = None,
    state_code: Optional[str] = None,
    granicus_host: Optional[str] = None,
) -> PlatformMeeting:
    event_id = event.get("EventId")
    if event_id is None:
        raise ValueError("Legistar event has no EventId")
    body = _clean(event.get("EventBodyName"))
    comment = _clean(event.get("EventComment"))
    clip = _clean(event.get("EventMedia"))
    video_path = _clean(event.get("EventVideoPath"))
    video_url, video_source = None, None
    if video_path and video_path.lower().startswith(("http://", "https://")):
        video_url, video_source = video_path, "legistar"
    elif clip and clip.isdigit() and granicus_host:
        video_url, video_source = granicus_player_url(granicus_host, clip), "granicus_clip"
    raw = {k: v for k, v in event.items() if k != "EventItems"}
    return PlatformMeeting(
        platform=PLATFORM,
        meeting_uid=f"{client}:{event_id}",
        portal=client,
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        body_name=body,
        title=" - ".join(p for p in (body, comment) if p) or None,
        meeting_date=_parse_date(event.get("EventDate")),
        meeting_time=_clean(event.get("EventTime")),
        location=_clean(event.get("EventLocation")),
        agenda_url=_clean(event.get("EventAgendaFile")),
        minutes_url=_clean(event.get("EventMinutesFile")),
        video_url=video_url,
        video_url_source=video_source,
        video_clip_id=clip,
        detail_url=_clean(event.get("EventInSiteURL")),
        agenda_text=agenda_text(items) if items else None,
        minutes_text=minutes_text(items) if items else None,
        source_modified_at=_parse_utc(event.get("EventLastModifiedUtc")),
        raw=raw,
        has_video=bool(video_path or clip),
    )


# --------------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------------


async def _get_json(http: PoliteClient, url: str) -> Any:
    resp = await http.get(url, allow_status=(400, 401, 403, 404, 500))
    try:
        payload = resp.json()
    except ValueError as exc:
        raise PlatformFetchError(f"{url}: not JSON (HTTP {resp.status_code})") from exc
    err = classify_error(payload)
    if err:
        raise LegistarClientError(err[1], err[0])
    if resp.status_code >= 400:
        raise PlatformFetchError(f"{url}: HTTP {resp.status_code}")
    return payload


async def client_is_configured(http: PoliteClient, client: str) -> bool:
    """True when the Web API serves data for ``client`` (one cheap ``/bodies`` call)."""
    try:
        payload = await _get_json(http, f"{API_BASE}/{client}/bodies?$top=1")
    except PlatformFetchError:
        return False
    return isinstance(payload, list) and len(payload) > 0


async def list_events(
    http: PoliteClient, client: str, since: date, max_events: Optional[int] = None, until: Optional[date] = None
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    skip = 0
    while True:
        page = await _get_json(http, events_url(client, since, PAGE_SIZE, skip, until))
        if not isinstance(page, list):
            raise PlatformFetchError(f"{client}: events response is not a list")
        events.extend(page)
        if len(page) < PAGE_SIZE or (max_events and len(events) >= max_events):
            break
        skip += PAGE_SIZE
    return events[:max_events] if max_events else events


async def read_client(
    http: PoliteClient,
    client: str,
    *,
    since: date,
    jurisdiction_id: Optional[str] = None,
    state_code: Optional[str] = None,
    granicus_host: Optional[str] = None,
    max_events: Optional[int] = 400,
    known_modified: Optional[dict[str, Optional[datetime]]] = None,
    found_via: str = "survey",
    data_center: bool = False,
    today: Optional[date] = None,
    horizon_days: int = 60,
) -> PortalResult:
    """Read one Legistar client's meetings since ``since``.

    Event items (agenda/minutes text) are fetched for meetings on or before ``today``
    plus upcoming ones with a published agenda. Meetings scheduled more than
    ``horizon_days`` ahead (placeholders with no documents yet) are not listed; a meeting whose
    ``EventLastModifiedUtc`` equals ``known_modified[meeting_uid]`` (already landed,
    unchanged) is skipped, so a re-run only reads what changed.
    """
    result = PortalResult(
        platform=PLATFORM,
        portal=client,
        portal_url=f"https://{client}.legistar.com/Calendar.aspx",
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        found_via=found_via,
        data_center=data_center,
    )
    try:
        until = (today or date.today()) + timedelta(days=horizon_days)
        events = await list_events(http, client, since, max_events, until)
    except PlatformFetchError as exc:
        result.status, result.detail = exc.status, str(exc)[:500]
        logger.warning("legistar {}: {} ({})", client, result.status, result.detail)
        return result
    known = known_modified or {}
    for event in events:
        uid = f"{client}:{event.get('EventId')}"
        modified = _parse_utc(event.get("EventLastModifiedUtc"))
        if uid in known and known[uid] is not None and modified is not None and known[uid] == modified:
            continue  # unchanged since it was landed
        items: Optional[list[dict[str, Any]]] = None
        has_agenda = bool(_clean(event.get("EventAgendaFile")))
        held = (_parse_date(event.get("EventDate")) or date.max) <= (today or date.today())
        if held or has_agenda:
            try:
                got = await _get_json(http, event_items_url(client, event["EventId"]))
                items = got if isinstance(got, list) else None
            except PlatformFetchError as exc:
                logger.debug("legistar {} items for {}: {}", client, uid, exc)
        result.meetings.append(
            meeting_from_event(
                client, event, items, jurisdiction_id=jurisdiction_id, state_code=state_code, granicus_host=granicus_host
            )
        )
    result.status = "ok" if events else "empty"
    result.detail = f"{len(events)} events since {since.isoformat()}; {len(result.meetings)} new or changed"
    logger.info("legistar {}: {}", client, result.detail)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="List one Legistar client's meetings (dry run, prints JSON).")
    parser.add_argument("client")
    parser.add_argument("--since", type=date.fromisoformat, default=date(date.today().year, 1, 1))
    parser.add_argument("--max-events", type=int, default=20)
    args = parser.parse_args(argv)

    async def go() -> PortalResult:
        async with PoliteClient(min_interval_s=0.5) as http:
            return await read_client(http, args.client, since=args.since, max_events=args.max_events)

    res = asyncio.run(go())
    print(json.dumps({"status": res.status, "detail": res.detail, "meetings": [
        {"uid": m.meeting_uid, "date": str(m.meeting_date), "body": m.body_name, "agenda_url": m.agenda_url,
         "minutes_url": m.minutes_url, "video_url": m.video_url, "transcription_status": m.transcription_status,
         "agenda_chars": len(m.agenda_text or ""), "minutes_chars": len(m.minutes_text or "")}
        for m in res.meetings]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
