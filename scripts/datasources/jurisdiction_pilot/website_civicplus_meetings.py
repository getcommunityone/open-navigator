"""
CivicPlus Agenda Center + calendar capture for the jurisdiction pilot.

Lightweight HTML parsing (no Playwright). Writes a JSON snapshot under the
jurisdiction cache dir and returns counts for progress logging.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

from scripts.datasources.jurisdiction_pilot.http_fetch import BROWSER_USER_AGENT

_USER_AGENT = BROWSER_USER_AGENT
_TIMEOUT_S = 12

_AGENDA_VIEW_RE = re.compile(r"/AgendaCenter/ViewFile/Agenda/", re.I)
_MINUTES_VIEW_RE = re.compile(r"/AgendaCenter/ViewFile/Minutes/", re.I)
_BARE_LINK_LABEL_RE = re.compile(r"^(agenda|minutes)$", re.I)
_MEETING_TITLE_RE = re.compile(
    r"\b(meeting|agenda|hearing|workshop|session)\b",
    re.I,
)


@dataclass
class MeetingCaptureResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    agendas: int = 0
    minutes: int = 0
    pages_fetched: list[str] = field(default_factory=list)

    @property
    def events_count(self) -> int:
        return len(self.events)


def discover_civicplus_meeting_urls(
    homepage_url: str,
    *,
    html_by_url: dict[str, str] | None = None,
    session: requests.Session | None = None,
) -> list[str]:
    """Ordered unique Agenda Center / calendar URLs for a CivicPlus host."""
    if not homepage_url:
        return []
    host = urlparse(homepage_url).netloc
    out: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        u = (url or "").strip()
        if not u or u in seen:
            return
        if urlparse(u).netloc and urlparse(u).netloc != host:
            return
        seen.add(u)
        out.append(u)

    for path in ("/AgendaCenter", "/calendar.aspx"):
        _add(urljoin(homepage_url, path))

    for base, html in (html_by_url or {}).items():
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            abs_u = urljoin(base, href)
            path_l = urlparse(abs_u).path.lower()
            if "agendacenter" in path_l or "calendar.aspx" in path_l:
                _add(abs_u)

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    for page_url in (homepage_url, urljoin(homepage_url, "/Elected-Officials")):
        try:
            resp = sess.get(page_url, timeout=_TIMEOUT_S, allow_redirects=True)
            if resp.status_code != 200 or not resp.text:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                abs_u = urljoin(resp.url, href)
                path_l = urlparse(abs_u).path.lower()
                if "agendacenter" in path_l or "calendar.aspx" in path_l:
                    _add(abs_u)
        except requests.RequestException:
            continue

    return out


def extract_civicplus_agenda_center_items(
    html: str,
    page_url: str,
    *,
    max_items: int = 200,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Parse Agenda Center HTML. Returns ``(events, agenda_count, minutes_count)``.

    ``events`` holds unique meeting/agenda titles with optional document URLs.
    """
    events: list[dict[str, Any]] = []
    agendas = 0
    minutes = 0
    if not html:
        return events, agendas, minutes

    seen_titles: set[str] = set()
    seen_docs: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_u = urljoin(page_url, href)
        label = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip()
        if _BARE_LINK_LABEL_RE.match(label):
            label = ""

        if _AGENDA_VIEW_RE.search(href):
            agendas += 1
            doc_kind = "agenda"
        elif _MINUTES_VIEW_RE.search(href):
            minutes += 1
            doc_kind = "minutes"
        else:
            continue

        if abs_u in seen_docs:
            continue
        seen_docs.add(abs_u)

        if not label:
            prev = a.find_parent(["li", "div", "tr"])
            if prev is not None:
                for sib in prev.find_all_previous(["a", "span", "strong"], limit=4):
                    cand = re.sub(r"\s+", " ", sib.get_text(" ", strip=True) or "").strip()
                    if cand and not _BARE_LINK_LABEL_RE.match(cand) and _MEETING_TITLE_RE.search(cand):
                        label = cand
                        break
            if not label:
                label = f"Meeting document ({doc_kind})"

        title_key = label.lower()
        if title_key in seen_titles:
            for ev in events:
                if (ev.get("title") or "").lower() == title_key:
                    docs = ev.setdefault("documents", [])
                    docs.append({"kind": doc_kind, "url": abs_u})
                    break
            continue

        if not _MEETING_TITLE_RE.search(label) and doc_kind == "agenda":
            continue

        seen_titles.add(title_key)
        events.append(
            {
                "title": label[:512],
                "source_page_url": page_url,
                "documents": [{"kind": doc_kind, "url": abs_u}],
            }
        )

    return events[:max_items], agendas, minutes


def extract_civicplus_calendar_events(
    html: str,
    page_url: str,
    *,
    max_events: int = 80,
) -> list[dict[str, Any]]:
    """Parse CivicEngage calendar list markup (``eventTitle_*`` anchors)."""
    out: list[dict[str, Any]] = []
    if not html:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()

    for a in soup.find_all("a", href=True, id=re.compile(r"^eventTitle_", re.I)):
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        href = urljoin(page_url, (a.get("href") or "").strip())
        date_text = ""
        parent = a.find_parent(["div", "li", "article"])
        if parent is not None:
            date_el = parent.find(class_=re.compile(r"date", re.I))
            if date_el is not None:
                date_text = re.sub(r"\s+", " ", date_el.get_text(" ", strip=True) or "").strip()
        out.append(
            {
                "title": title[:512],
                "event_date_text": date_text[:128] or None,
                "event_url": href,
                "source_page_url": page_url,
                "documents": [],
            }
        )
        if len(out) >= max_events:
            break
    return out


def scrape_civicplus_meetings(
    homepage_url: str,
    session: requests.Session,
    *,
    html_by_url: dict[str, str] | None = None,
    extra_urls: list[str] | None = None,
) -> MeetingCaptureResult:
    """Fetch and parse CivicPlus meeting surfaces; aggregate counts."""
    result = MeetingCaptureResult()
    urls = discover_civicplus_meeting_urls(homepage_url, html_by_url=html_by_url, session=session)
    for u in extra_urls or []:
        if u and u not in urls:
            urls.append(u)

    all_events: list[dict[str, Any]] = []
    seen_event_keys: set[str] = set()
    total_agendas = 0
    total_minutes = 0

    for url in urls[:8]:
        html = (html_by_url or {}).get(url)
        if not html:
            try:
                resp = session.get(url, timeout=_TIMEOUT_S, allow_redirects=True)
                if resp.status_code != 200 or not resp.text:
                    continue
                html = resp.text
            except requests.RequestException:
                continue
        result.pages_fetched.append(url)

        if "calendar.aspx" in urlparse(url).path.lower():
            for ev in extract_civicplus_calendar_events(html, url):
                key = (ev.get("title") or "").lower()
                if key in seen_event_keys:
                    continue
                seen_event_keys.add(key)
                all_events.append(ev)
        else:
            events, ag, mn = extract_civicplus_agenda_center_items(html, url)
            total_agendas += ag
            total_minutes += mn
            for ev in events:
                key = (ev.get("title") or "").lower()
                if key in seen_event_keys:
                    continue
                seen_event_keys.add(key)
                all_events.append(ev)

    result.events = all_events
    result.agendas = total_agendas
    result.minutes = total_minutes
    return result


def write_meetings_snapshot(
    out_path: Path,
    *,
    jurisdiction_id: str,
    homepage_url: str,
    capture: MeetingCaptureResult,
    scrape_batch_id: str,
) -> None:
    payload = {
        "jurisdiction_id": jurisdiction_id,
        "homepage_url": homepage_url,
        "scrape_batch_id": scrape_batch_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "pages_fetched": capture.pages_fetched,
        "events_count": capture.events_count,
        "agendas_count": capture.agendas,
        "minutes_count": capture.minutes,
        "events": capture.events,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
