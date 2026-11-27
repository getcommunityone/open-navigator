"""Pure parsers for organization events (#1347): no network, no database.

Only what the page itself states is kept. An event without a start date, or whose date cannot be read, is dropped,
never guessed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

#: Hosts that are not the organization's own site (a social profile, a donation platform, a link shortener).
NOT_OWN_SITE = re.compile(
    r"(^|\.)(facebook|fb|instagram|twitter|x|linkedin|youtube|tiktok|guidestar|candid|charitynavigator|"
    r"paypal|gofundme|givebutter|networkforgood|bit|tinyurl|google|yelp|eventbrite|meetup)\.(com|org|ly|me)$",
    re.I,
)

#: Event pages and feeds a site commonly links (WordPress "The Events Calendar", Squarespace, Wix, generic).
EVENT_LINK_RE = re.compile(r"(\.ics(\?|$)|[?&]ical=1|^webcal:|/events?/?($|\?)|/calendar/?($|\?))", re.I)


def normalize_website(raw: str | None) -> Optional[str]:
    """``WWW.EXAMPLE.ORG`` -> ``https://www.example.org/``; ``N/A``, emails and social profiles -> None."""
    if not raw:
        return None
    s = raw.strip().strip("/").strip()
    if not s or "@" in s or " " in s or s.upper() in {"N/A", "NA", "NONE", "0"}:
        return None
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    parts = urlsplit(s)
    host = (parts.hostname or "").lower()
    if "." not in host or NOT_OWN_SITE.search(host):
        return None
    path = parts.path or "/"
    return f"https://{host}{path if path.endswith('/') or '.' in path.rsplit('/', 1)[-1] else path + '/'}"


def website_from_990_xml(xml_text: str) -> Optional[str]:
    """The ``WebsiteAddressTxt`` of a Form 990 e-file return, normalized."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "WebsiteAddressTxt" and el.text:
            return normalize_website(el.text)
    return None


@dataclass(frozen=True)
class OrgEvent:
    ein: str
    title: str
    start_at: Optional[datetime]
    start_date: date
    end_at: Optional[datetime]
    location: Optional[str]
    event_url: Optional[str]
    source_page_url: str
    source_format: str  # jsonld | ical

    @property
    def event_key(self) -> str:
        raw = f"{self.ein}|{self.event_url or self.source_page_url}|{self.start_date.isoformat()}|{self.title.lower()}"
        return hashlib.md5(raw.encode()).hexdigest()


def _clean(s: Any) -> Optional[str]:
    if s is None:
        return None
    if isinstance(s, (list, tuple)):
        s = next((x for x in s if isinstance(x, str) and x.strip()), None)
        if s is None:
            return None
    if not isinstance(s, str):
        return None
    t = re.sub(r"<[^>]+>", " ", unescape(s))
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def parse_when(value: Any) -> tuple[Optional[datetime], Optional[date]]:
    """An ISO 8601 date or date-time -> (datetime or None, date). A bare date has no time."""
    v = _clean(value)
    if not v:
        return None, None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v)
    if m:
        try:
            return None, date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None, None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    return dt, dt.date()


def _location(loc: Any) -> Optional[str]:
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return _clean(loc)
    if not isinstance(loc, dict):
        return None
    if str(loc.get("@type", "")).lower() == "virtuallocation":
        return "Online"
    name = _clean(loc.get("name"))
    addr = loc.get("address")
    if isinstance(addr, dict):
        bits = [_clean(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion")]
        addr_s = ", ".join(b for b in bits if b)
    else:
        addr_s = _clean(addr) or ""
    out = ", ".join(x for x in (name, addr_s) if x)
    return out or None


def _walk_jsonld(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, list):
        for n in node:
            yield from _walk_jsonld(n)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.endswith("Event") for x in types):
            yield node
        for k in ("@graph", "itemListElement", "item", "event", "events", "subEvent"):
            if k in node:
                yield from _walk_jsonld(node[k])


_JSONLD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_CANCELLED = re.compile(r"(EventCancelled|EventPostponed)$")


def events_from_jsonld(html: str, *, ein: str, page_url: str) -> list[OrgEvent]:
    """schema.org Event objects in a page's JSON-LD blocks (cancelled or postponed ones are dropped)."""
    out: list[OrgEvent] = []
    for block in _JSONLD_RE.findall(html or ""):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for ev in _walk_jsonld(data):
            if _CANCELLED.search(str(ev.get("eventStatus", ""))):
                continue
            title = _clean(ev.get("name"))
            start_at, start_d = parse_when(ev.get("startDate"))
            if not title or start_d is None:
                continue
            end_at, _ = parse_when(ev.get("endDate"))
            url = _clean(ev.get("url"))
            out.append(
                OrgEvent(
                    ein=ein,
                    title=title[:300],
                    start_at=start_at,
                    start_date=start_d,
                    end_at=end_at,
                    location=_location(ev.get("location")),
                    event_url=urljoin(page_url, url) if url else None,
                    source_page_url=page_url,
                    source_format="jsonld",
                )
            )
    return out


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _ical_value(v: str) -> str:
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _ical_when(params: str, value: str) -> tuple[Optional[datetime], Optional[date]]:
    v = value.strip()
    try:
        if "VALUE=DATE" in params.upper() or re.fullmatch(r"\d{8}", v):
            d = datetime.strptime(v[:8], "%Y%m%d").date()
            return None, d
        if v.endswith("Z"):
            dt = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")  # floating or TZID local time, kept as written
        return dt, dt.date()
    except ValueError:
        return None, None


def events_from_ical(text: str, *, ein: str, feed_url: str) -> list[OrgEvent]:
    """VEVENTs in an iCalendar feed. Recurring rules are not expanded: only the stated first date is kept."""
    out: list[OrgEvent] = []
    cur: Optional[dict[str, tuple[str, str]]] = None
    for line in _unfold(text or ""):
        if line.strip() == "BEGIN:VEVENT":
            cur = {}
            continue
        if line.strip() == "END:VEVENT":
            if cur is not None:
                title = _clean(_ical_value(cur.get("SUMMARY", ("", ""))[1]))
                start_at, start_d = _ical_when(*cur.get("DTSTART", ("", "")))
                status = cur.get("STATUS", ("", ""))[1].upper()
                if title and start_d is not None and status != "CANCELLED":
                    end_at, _ = _ical_when(*cur.get("DTEND", ("", "")))
                    url = _ical_value(cur.get("URL", ("", ""))[1]) or None
                    out.append(
                        OrgEvent(
                            ein=ein,
                            title=title[:300],
                            start_at=start_at,
                            start_date=start_d,
                            end_at=end_at,
                            location=_clean(_ical_value(cur.get("LOCATION", ("", ""))[1])),
                            event_url=url if url and url.startswith("http") else None,
                            source_page_url=feed_url,
                            source_format="ical",
                        )
                    )
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, _, params = head.partition(";")
        cur.setdefault(name.upper(), (params, value))
    return out


_HREF_RE = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"'#]+)["']""", re.I)
_ALT_ICAL_RE = re.compile(r"""<link\b[^>]*type=["']text/calendar["'][^>]*href=["']([^"']+)["']""", re.I)


def event_links(html: str, page_url: str, *, limit: int = 4) -> list[str]:
    """Same-site links that look like an events page or an iCal feed, feeds first."""
    host = (urlsplit(page_url).hostname or "").lower().removeprefix("www.")
    seen: list[str] = []
    for href in _ALT_ICAL_RE.findall(html or "") + _HREF_RE.findall(html or ""):
        href = unescape(href.strip())
        if href.lower().startswith("webcal:"):
            href = "https:" + href[7:]
        url = urljoin(page_url, href)
        h = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        if h != host or not EVENT_LINK_RE.search(href) or url in seen:
            continue
        seen.append(url)
    seen.sort(key=lambda u: 0 if (".ics" in u.lower() or "ical=1" in u.lower()) else 1)
    return seen[:limit]


def upcoming(events: Iterable[OrgEvent], today: date, *, horizon_days: int = 400) -> list[OrgEvent]:
    """Events from today on, within the horizon, one per key."""
    out: dict[str, OrgEvent] = {}
    for e in events:
        if today <= e.start_date and (e.start_date - today).days <= horizon_days:
            out.setdefault(e.event_key, e)
    return list(out.values())
