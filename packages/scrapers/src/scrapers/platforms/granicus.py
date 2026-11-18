"""Read meetings from a Granicus portal (#536).

A Granicus portal (``<city>.granicus.com``) lists its archive at
``ViewPublisher.php?view_id=N`` (an HTML table, one row per clip or upcoming event)
and as RSS at ``ViewPublisherRSS.php?view_id=N``. Each row links the agenda
(``AgendaViewer.php``), the minutes (``MinutesViewer.php``) and the video player
(``MediaPlayer.php?clip_id=M``). When the player page links a caption track (a
``<track kind="captions|subtitles">`` or a ``.vtt``/``.srt`` URL), the caption text
is read and parsed into timed cues.

robots.txt comes first. Every Granicus host in the #460 survey publishes
``User-agent: *`` / ``Disallow: /`` (only named search engines are let in), so for
those this reader makes no request beyond robots.txt and reports the portal as
``robots_disallowed``. It reads a portal whose robots.txt allows it. Their meetings
still arrive through Legistar when the government uses it: the Legistar event
carries the Granicus clip id (see :mod:`scrapers.platforms.legistar`).

Usage (dry run)::

    python -m scrapers.platforms.granicus loudoun.granicus.com --view-id 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date, datetime
from typing import Any, Optional, Sequence
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from loguru import logger

from scrapers.platforms.http import PlatformFetchError, PoliteClient, RobotsDisallowed
from scrapers.platforms.model import CaptionCue, MeetingCaption, PlatformMeeting, PortalResult

PLATFORM = "granicus"

_URL_IN_JS = re.compile(r"""['"]((?:https?:)?//[^'"]+|[A-Za-z]+\.php\?[^'"]+)['"]""")
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%a, %d %b %Y")


def portal_host(url_or_host: str) -> str:
    """``https://loudoun.granicus.com/`` or ``loudoun.granicus.com`` -> ``loudoun.granicus.com``."""
    s = url_or_host.strip()
    if "//" not in s:
        s = "https://" + s
    return (urlsplit(s).hostname or "").lower()


def view_publisher_url(host: str, view_id: int) -> str:
    return f"https://{host}/ViewPublisher.php?view_id={view_id}"


def rss_url(host: str, view_id: int) -> str:
    return f"https://{host}/ViewPublisherRSS.php?view_id={view_id}"


def parse_date(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    s = " ".join(text.replace("\xa0", " ").split())
    s = re.sub(r"\s+\d{1,2}:\d{2}.*$", "", s)  # drop a trailing time
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})", s)
    if m:
        cand = m.group(1).replace(".", "").replace(",", "")
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(cand, fmt).date()
            except ValueError:
                continue
    return None


def _abs(url: str, base: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base, url)


def _row_urls(row: Any, base: str) -> list[str]:
    urls: list[str] = []
    for tag in row.find_all(["a", "button"]):
        href = tag.get("href") or ""
        if href and not href.lower().startswith(("javascript:", "#", "mailto:")):
            urls.append(_abs(href, base))
        for attr in ("onclick", "href"):
            for m in _URL_IN_JS.finditer(tag.get(attr) or ""):
                urls.append(_abs(m.group(1), base))
    return urls


def _query_id(url: str, key: str) -> Optional[str]:
    vals = parse_qs(urlsplit(url).query).get(key)
    return vals[0] if vals and vals[0].isdigit() else None


def parse_view_publisher(html: str, host: str, view_id: int) -> list[dict[str, Any]]:
    """Rows of a ``ViewPublisher.php`` page: name, date, clip/event id and the links."""
    base = view_publisher_url(host, view_id)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        urls = _row_urls(tr, base)
        clip_id = next((c for c in (_query_id(u, "clip_id") for u in urls) if c), None)
        event_id = next((e for e in (_query_id(u, "event_id") for u in urls) if e), None)
        if not clip_id and not event_id:
            continue
        name_cell = tr.find("td", attrs={"headers": re.compile(r"name", re.I)}) or cells[0]
        name = " ".join(name_cell.get_text(" ").split()) or None
        meeting_date = None
        date_cell = tr.find("td", attrs={"headers": re.compile(r"date", re.I)})
        for cell in ([date_cell] if date_cell else []) + list(cells):
            meeting_date = parse_date(cell.get_text(" "))
            if meeting_date:
                break
        rows.append(
            {
                "name": name,
                "meeting_date": meeting_date,
                "clip_id": clip_id,
                "event_id": event_id,
                "agenda_url": next((u for u in urls if "agendaviewer.php" in u.lower()), None),
                "minutes_url": next((u for u in urls if "minutesviewer.php" in u.lower()), None),
                "video_url": next((u for u in urls if "mediaplayer.php" in u.lower()), None),
                "view_id": view_id,
            }
        )
    return rows


def parse_rss(xml_text: str) -> list[dict[str, Any]]:
    """Items of a ``ViewPublisherRSS.php`` feed: title, link, date, clip/event id."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        items.append(
            {
                "name": (item.findtext("title") or "").strip() or None,
                "link": _abs(link, "https://granicus.com/") if link else None,
                "meeting_date": parse_date(pub[:16]) if pub else None,
                "clip_id": _query_id(link, "clip_id"),
                "event_id": _query_id(link, "event_id"),
            }
        )
    return items


def caption_track_url(player_html: str, player_url: str) -> Optional[str]:
    """The caption track a ``MediaPlayer.php`` page links, if any."""
    soup = BeautifulSoup(player_html, "html.parser")
    for track in soup.find_all("track"):
        kind = (track.get("kind") or "").lower()
        if kind in ("captions", "subtitles") and track.get("src"):
            return _abs(track["src"], player_url)
    m = re.search(r"""['"]([^'"\s]+\.(?:vtt|srt)(?:\?[^'"\s]*)?)['"]""", player_html)
    return _abs(m.group(1), player_url) if m else None


_TS = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_CUE_TIME = re.compile(rf"{_TS}\s*-->\s*{_TS}")


def _secs(h: Optional[str], m: str, s: str, frac: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000


def parse_captions(text: str) -> list[CaptionCue]:
    """Cues from WebVTT or SRT text (tags such as ``<v Speaker>`` are removed)."""
    cues: list[CaptionCue] = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            m = _CUE_TIME.search(line)
            if not m:
                continue
            start = _secs(*m.group(1, 2, 3, 4))
            end = _secs(*m.group(5, 6, 7, 8))
            words = " ".join(re.sub(r"<[^>]+>", "", ln).strip() for ln in lines[i + 1 :])
            words = " ".join(words.split())
            if words:
                cues.append(CaptionCue(start=start, duration=round(max(0.0, end - start), 3), text=words))
            break
    return cues


def meeting_from_row(
    host: str, row: dict[str, Any], *, jurisdiction_id: Optional[str] = None, state_code: Optional[str] = None
) -> PlatformMeeting:
    native = f"clip{row['clip_id']}" if row.get("clip_id") else f"event{row['event_id']}"
    video_url = row.get("video_url") or (
        f"https://{host}/MediaPlayer.php?view_id={row.get('view_id')}&clip_id={row['clip_id']}" if row.get("clip_id") else None
    )
    return PlatformMeeting(
        platform=PLATFORM,
        meeting_uid=f"{host}:{native}",
        portal=host,
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        body_name=row.get("name"),
        title=row.get("name"),
        meeting_date=row.get("meeting_date"),
        agenda_url=row.get("agenda_url"),
        minutes_url=row.get("minutes_url"),
        video_url=video_url,
        video_url_source="granicus" if video_url else None,
        video_clip_id=row.get("clip_id"),
        detail_url=row.get("agenda_url") or video_url,
        raw={k: (v.isoformat() if isinstance(v, date) else v) for k, v in row.items()},
        has_video=bool(row.get("clip_id")),
    )


async def fetch_caption(http: PoliteClient, player_url: str) -> Optional[MeetingCaption]:
    try:
        player = await http.get(player_url)
    except PlatformFetchError as exc:
        logger.debug("granicus player {}: {}", player_url, exc)
        return None
    track = caption_track_url(player.text, player_url)
    if not track:
        return None
    try:
        resp = await http.get(track)
    except PlatformFetchError as exc:
        logger.debug("granicus captions {}: {}", track, exc)
        return None
    cues = parse_captions(resp.text)
    if not cues:
        return None
    fmt = "srt" if track.lower().split("?")[0].endswith(".srt") else "vtt"
    return MeetingCaption(
        caption_source=f"granicus_{fmt}",
        caption_url=track,
        caption_format=fmt,
        raw_text=" ".join(c.text for c in cues),
        cues=cues,
    )


async def read_portal(
    http: PoliteClient,
    host_or_url: str,
    *,
    view_ids: Sequence[int] = (1,),
    since: Optional[date] = None,
    jurisdiction_id: Optional[str] = None,
    state_code: Optional[str] = None,
    captions: bool = True,
    max_captions: int = 50,
    found_via: str = "survey",
    data_center: bool = False,
) -> PortalResult:
    """Read a Granicus portal's archive views; robots.txt decides whether anything is fetched."""
    host = portal_host(host_or_url)
    result = PortalResult(
        platform=PLATFORM,
        portal=host,
        portal_url=view_publisher_url(host, view_ids[0] if view_ids else 1),
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        found_via=found_via,
        data_center=data_center,
    )
    seen: set[str] = set()
    errors: list[str] = []
    for view_id in view_ids:
        try:
            page = await http.get(view_publisher_url(host, view_id))
            rows = parse_view_publisher(page.text, host, view_id)
        except RobotsDisallowed as exc:
            result.status, result.detail = exc.status, "robots.txt disallows ViewPublisher.php for all crawlers"
            logger.info("granicus {}: {}", host, result.detail)
            return result
        except PlatformFetchError as exc:
            errors.append(f"view {view_id}: {exc.status}: {exc}")
            if exc.status == "blocked":
                result.status, result.detail = "blocked", str(exc)[:500]
                return result
            continue
        if not rows:
            try:  # some views render the table with JavaScript; the RSS carries the same clips
                feed = await http.get(rss_url(host, view_id))
                rows = [dict(r, view_id=view_id) for r in parse_rss(feed.text)]
            except PlatformFetchError as exc:
                errors.append(f"rss {view_id}: {exc.status}")
        for row in rows:
            if since and row.get("meeting_date") and row["meeting_date"] < since:
                continue
            m = meeting_from_row(host, row, jurisdiction_id=jurisdiction_id, state_code=state_code)
            if m.meeting_uid in seen:
                continue
            seen.add(m.meeting_uid)
            result.meetings.append(m)
    if captions:
        for m in sorted(result.meetings, key=lambda x: x.meeting_date or date.min, reverse=True)[:max_captions]:
            if m.video_url and m.video_clip_id:
                m.caption = await fetch_caption(http, m.video_url)
    if result.meetings:
        result.status = "ok"
    elif errors:
        result.status = "error"
    else:
        result.status = "empty"
    result.detail = "; ".join(errors)[:500] or f"{len(result.meetings)} meetings"
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="List one Granicus portal's meetings (dry run, prints JSON).")
    parser.add_argument("host")
    parser.add_argument("--view-id", type=int, action="append")
    parser.add_argument("--no-captions", action="store_true")
    args = parser.parse_args(argv)

    async def go() -> PortalResult:
        async with PoliteClient() as http:
            return await read_portal(http, args.host, view_ids=args.view_id or [1], captions=not args.no_captions)

    res = asyncio.run(go())
    print(json.dumps({"status": res.status, "detail": res.detail, "meetings": [
        {"uid": m.meeting_uid, "date": str(m.meeting_date), "title": m.title, "video_url": m.video_url,
         "transcription_status": m.transcription_status} for m in res.meetings]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
