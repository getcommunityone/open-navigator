"""
SuiteOne Media portal fetch + parse (pure, testable).

The portal renders meetings as table rows. Each row carries:
- an event link ``<a href="/event/?id=11169" title="Navigate to <body>">``,
- a date cell ``<td data-sort=...>Jun 09, 2026 | 02:30 PM</td>``,
- and, when published, an agenda link ``GetAgendaFile/Agenda?aid=N`` and/or a
  minutes link ``GetMinutesFile/Synopsis?mid=N``.

``parse_listing`` turns that into one :class:`MeetingDoc` per *document* (a
meeting with both an agenda and minutes yields two records; a meeting with
neither yields none — we only emit rows we can link to a real document).
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

# Leading "2:30 p.m. " / "10 a.m. " style time prefix on a meeting title; stripped
# to recover a clean body name ("Finance Committee") while the full title is kept.
_TIME_PREFIX = re.compile(r"^\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?\s+", re.IGNORECASE)
_NAVIGATE_PREFIX = re.compile(r"^\s*Navigate to\s+", re.IGNORECASE)
# "Jun 09, 2026" (optionally trailed by "| 02:30 PM")
_DATE_RE = re.compile(r"([A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2})")


@dataclass
class MeetingDoc:
    """One agenda or minutes document for a single meeting."""

    doc_type: str  # 'agenda' | 'minutes'
    url: str
    meeting_date: Optional[date]
    body_name: str  # cleaned body ("Finance Committee")
    meeting_title: str  # full listing title ("3:00 p.m. Finance Committee")
    event_id: Optional[str]
    ref_id: Optional[str]  # aid (agenda) or mid (minutes)
    scheduled_time: Optional[str] = None
    raw: dict = field(default_factory=dict)


# SuiteOne serves a document purely by its ``aid``/``mid`` query param; the path
# segment between ``GetXFile/`` and ``?`` is a decorative title that older portal
# rows pollute with the meeting date — e.g. ``GetAgendaFile/11/2/21 Agenda?aid=N``
# or ``GetMinutesFile/Synopsis ?mid=N``. Spaces (``%20``) and especially embedded
# slashes (extra path segments) make the link 404 even though the file is fine.
# Collapse the label down to its canonical keyword (preserving Minutes vs Synopsis)
# so the link routes; this also subsumes the older trailing-whitespace fix.
_DOC_URL_LABEL = re.compile(
    r"(/event/Get(?:Agenda|Minutes|Document)File/)[^?]*?"
    r"(Agenda|Minutes|Synopsis|Packet)[^?]*(\?|$)",
    re.IGNORECASE,
)
# Fallback: bare trailing whitespace before the query when no keyword is present.
_DOC_URL_TRAILING_WS = re.compile(r"(?:%20|\s)+(\?|$)", re.IGNORECASE)


def _normalize_doc_url(url: str) -> str:
    url = (url or "").strip()
    if _DOC_URL_LABEL.search(url):
        return _DOC_URL_LABEL.sub(r"\1\2\3", url)
    return _DOC_URL_TRAILING_WS.sub(r"\1", url)


def _clean_title(raw_title: str) -> str:
    return _NAVIGATE_PREFIX.sub("", raw_title or "").strip()


def _body_name(title: str) -> str:
    return _TIME_PREFIX.sub("", title or "").strip() or title.strip()


def _parse_date(text: str) -> Optional[date]:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%b %d, %Y").date()
    except ValueError:
        return None


def parse_listing(html: str, base_url: str) -> list[MeetingDoc]:
    """Parse a SuiteOne listing page into agenda/minutes :class:`MeetingDoc`s."""
    soup = BeautifulSoup(html, "html.parser")
    docs: list[MeetingDoc] = []
    seen_urls: set[str] = set()

    for tr in soup.find_all("tr"):
        event_a = tr.find("a", href=re.compile(r"/event/\?id=\d+"))
        if not event_a:
            continue
        raw_title = event_a.get("title") or event_a.get_text(" ", strip=True)
        title = _clean_title(raw_title)
        body = _body_name(title)

        eid_m = re.search(r"/event/\?id=(\d+)", event_a.get("href", ""))
        event_id = eid_m.group(1) if eid_m else None

        date_td = tr.find("td", attrs={"data-sort": True})
        date_text = date_td.get_text(" ", strip=True) if date_td else ""
        meeting_date = _parse_date(date_text)
        time_m = re.search(r"\|\s*([0-9:]+\s*[AP]M)", date_text)
        scheduled_time = time_m.group(1).strip() if time_m else None

        for doc_type, pattern, ref_param in (
            ("agenda", "GetAgendaFile", "aid"),
            ("minutes", "GetMinutesFile", "mid"),
        ):
            link = tr.find("a", href=re.compile(pattern))
            if not link:
                continue
            href = link.get("href", "")
            url = _normalize_doc_url(urljoin(base_url, href))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            ref_m = re.search(rf"{ref_param}=(\d+)", href)
            docs.append(
                MeetingDoc(
                    doc_type=doc_type,
                    url=url,
                    meeting_date=meeting_date,
                    body_name=body,
                    meeting_title=title,
                    event_id=event_id,
                    ref_id=ref_m.group(1) if ref_m else None,
                    scheduled_time=scheduled_time,
                    raw={
                        "source": "suiteone",
                        "event_id": event_id,
                        "ref_id": ref_m.group(1) if ref_m else None,
                        "scheduled_time": scheduled_time,
                        "body": body,
                        "date_text": date_text or None,
                    },
                )
            )
    return docs


def fetch_listing(portal_url: str, *, timeout: float = 30.0) -> str:
    """GET the SuiteOne portal listing HTML."""
    logger.info("Fetching SuiteOne listing: {}", portal_url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; open-navigator/1.0; civic-data; "
            "+https://github.com/open-navigator)"
        )
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        resp = client.get(portal_url)
        resp.raise_for_status()
        return resp.text


def scrape_portal(portal_url: str) -> list[MeetingDoc]:
    """Fetch + parse a SuiteOne portal into agenda/minutes documents."""
    docs = parse_listing(fetch_listing(portal_url), portal_url)
    logger.success(
        "Parsed {} documents ({} agenda, {} minutes) from {}",
        len(docs),
        sum(1 for d in docs if d.doc_type == "agenda"),
        sum(1 for d in docs if d.doc_type == "minutes"),
        portal_url,
    )
    return docs


# The portal root only renders the current + prior calendar year. Each meeting
# body carries an "Older Meetings.." control whose data-* attributes drive a
# ``POST /Home/GetRecentEventsGroup`` that returns the body's FULL event history
# (one HTML fragment of the same <tr> shape ``parse_listing`` already reads).
_OLDER_GROUP_RE = re.compile(
    r'<a[^>]*class="[^"]*older_meetings_click[^"]*"[^>]*>', re.IGNORECASE
)
_EVENTS_GROUP_PATH = "/Home/GetRecentEventsGroup"


@dataclass
class _OlderGroup:
    group_name: str
    group_id: str
    unique_id: str
    category_id: str
    year_from: str


def _attr(tag: str, name: str) -> Optional[str]:
    m = re.search(rf'data-{name}="([^"]*)"', tag, re.IGNORECASE)
    return _html.unescape(m.group(1)) if m else None


def parse_older_groups(html: str) -> list[_OlderGroup]:
    """Extract the per-body "Older Meetings.." groups from a portal listing."""
    groups: list[_OlderGroup] = []
    for tag in _OLDER_GROUP_RE.findall(html):
        gid = _attr(tag, "groupId")
        cat = _attr(tag, "categoryId")
        uid = _attr(tag, "uniqueId")
        if not (gid and cat and uid):
            continue
        groups.append(
            _OlderGroup(
                group_name=_attr(tag, "groupName") or "",
                group_id=gid,
                unique_id=uid,
                category_id=cat,
                year_from=_attr(tag, "yearFrom") or "",
            )
        )
    return groups


def fetch_events_group(
    client: "httpx.Client", base_url: str, group: _OlderGroup
) -> str:
    """POST the older-events endpoint for one body; returns the HTML fragment."""
    resp = client.post(
        urljoin(base_url, _EVENTS_GROUP_PATH),
        data={
            "yearFrom": group.year_from,
            "groupName": group.group_name,
            "groupId": group.group_id,
            "uniqueId": group.unique_id,
            "categoryId": group.category_id,
            "psize": 10,
            "page": 0,
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    resp.raise_for_status()
    return resp.text


def scrape_portal_history(
    portal_url: str, *, since_year: int | None = None, timeout: float = 60.0
) -> list[MeetingDoc]:
    """Fetch the full meeting history of a SuiteOne portal (all bodies, all years).

    Walks every body's "Older Meetings.." group, merges with the root listing,
    and de-dupes by document URL. ``since_year`` keeps only documents whose real
    meeting date falls in that year or later (undated rows are dropped when set).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; open-navigator/1.0; civic-data; "
            "+https://github.com/open-navigator)"
        )
    }
    by_url: dict[str, MeetingDoc] = {}
    with httpx.Client(
        follow_redirects=True, timeout=timeout, headers=headers
    ) as client:
        root_resp = client.get(portal_url)
        root_resp.raise_for_status()
        root_html = root_resp.text
        for d in parse_listing(root_html, portal_url):
            by_url.setdefault(d.url, d)

        groups = parse_older_groups(root_html)
        logger.info("Found {} meeting bodies with older-meeting history", len(groups))
        for g in groups:
            try:
                fragment = fetch_events_group(client, portal_url, g)
            except Exception as exc:  # noqa: BLE001 — one body failing must not abort the rest
                logger.warning("Older-events fetch failed for {}: {}", g.group_name, exc)
                continue
            new = 0
            for d in parse_listing(fragment, portal_url):
                if d.url not in by_url:
                    by_url[d.url] = d
                    new += 1
            logger.info("  {:<48} +{} docs", g.group_name, new)

    docs = list(by_url.values())
    if since_year is not None:
        docs = [d for d in docs if d.meeting_date and d.meeting_date.year >= since_year]

    years = sorted({d.meeting_date.year for d in docs if d.meeting_date})
    logger.success(
        "History: {} documents ({} agenda, {} minutes) spanning {}",
        len(docs),
        sum(1 for d in docs if d.doc_type == "agenda"),
        sum(1 for d in docs if d.doc_type == "minutes"),
        f"{years[0]}–{years[-1]}" if years else "no dates",
    )
    return docs
