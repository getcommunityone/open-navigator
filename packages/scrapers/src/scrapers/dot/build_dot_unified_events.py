#!/usr/bin/env python3
"""
Build a **consistent** per-event JSON model for state DOT public meetings / hearings.

This complements ``extract_dot_event_candidates_from_cache.py`` (link discovery + heuristics)
with **structured parsers** where we know the HTML shape.

Current adapters
----------------
* **WY** — ``public-meeting-schedule.html`` list (``div.news`` blocks).
* **AL** — ``pi_schedule.html`` table ``#meetings``.

Output
------
* ``{cache_root}/unified_events.jsonl`` — one JSON object per line (all selected states).
* ``{cache_root}/{USPS}/unified_events.json`` — array for that state.

Usage (repo root)::

  .venv/bin/python packages/scrapers/src/scrapers/dot/build_dot_unified_events.py --states WY AL
  .venv/bin/python packages/scrapers/src/scrapers/dot/build_dot_unified_events.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = REPO_ROOT / "data" / "cache" / "dot_public_involvement"

USER_AGENT = (
    "OpenNavigatorDotResearch/1.0 (+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "DOT unified events)"
)

SCHEMA_VERSION = 1

# Canonical list URLs we parse with dedicated adapters (extend per state).
DOT_ADAPTER_SOURCES: dict[str, list[tuple[str, str]]] = {
    "WY": [
        (
            "wy_dot_public_meeting_schedule_v1",
            "https://www.dot.state.wy.us/home/news_info/public-meeting-schedule.html",
        )
    ],
    "AL": [
        ("al_dot_pi_schedule_table_v1", "https://www.dot.state.al.us/news/pi_schedule.html"),
    ],
}

_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _event_fingerprint(state_usps: str, payload: dict[str, Any]) -> str:
    key = json.dumps(
        {
            "state": state_usps.upper(),
            "adapter": payload.get("adapter"),
            "title": (payload.get("title") or "").strip(),
            "list_page_url": (payload.get("list_page_url") or "").strip(),
            "detail_url": (payload.get("detail_url") or "").strip(),
            "meeting_date_raw": (payload.get("meeting_date_raw") or "").strip(),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_us_slash_dates(text: str) -> list[date]:
    out: list[date] = []
    for m in _SLASH_DATE.finditer(text or ""):
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out.append(date(y, mo, d))
        except ValueError:
            continue
    return out


def _parse_month_day_year(month: str, day: str, year: str) -> tuple[date | None, str]:
    raw = f"{month.strip()} {day.strip()} {year.strip()}"
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt).date(), raw
        except ValueError:
            continue
    return None, raw


def fetch_html(url: str, timeout_s: float) -> str:
    with httpx.Client(
        timeout=timeout_s,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def parse_wy_schedule(html: str, list_url: str, adapter: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for div in soup.select("div.news"):
        h2 = div.select_one("h2.news-heading")
        if not h2:
            continue
        title = h2.get_text(" ", strip=True)
        if not title:
            continue
        holder = div.select_one(".news-date-holder")
        month = day = year = ""
        if holder:
            sm = holder.select_one(".month")
            sd = holder.select_one(".day")
            sy = holder.select_one(".year")
            month = sm.get_text(strip=True) if sm else ""
            day = sd.get_text(strip=True) if sd else ""
            year = sy.get_text(strip=True) if sy else ""
        meeting_date: date | None = None
        meeting_date_raw = ""
        if month and day and year:
            meeting_date, meeting_date_raw = _parse_month_day_year(month, day, year)
        teaser = ""
        p = div.find("p")
        if p:
            teaser = p.get_text(" ", strip=True)
        detail_url = ""
        rm = None
        for a in div.find_all("a", href=True):
            if "read more" in (a.get_text(" ", strip=True) or "").lower():
                rm = a
                break
        if rm:
            detail_url = urljoin(list_url, rm["href"])
        collateral: list[dict[str, Any]] = []
        if detail_url:
            collateral.append({"url": detail_url, "kind": "detail_page", "label": "Read More"})
        for a in div.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.lower().startswith("javascript:"):
                continue
            if href.lower().endswith(".pdf"):
                collateral.append(
                    {
                        "url": urljoin(list_url, href),
                        "kind": "pdf",
                        "label": (a.get_text(" ", strip=True) or "")[:240],
                    }
                )
        rows.append(
            {
                "adapter": adapter,
                "title": title,
                "summary_text": teaser[:8000] if teaser else None,
                "list_page_url": list_url,
                "detail_url": detail_url or None,
                "meeting_date": meeting_date.isoformat() if meeting_date else None,
                "meeting_date_raw": meeting_date_raw or None,
                "collateral": collateral,
            }
        )
    return rows


def parse_al_pi_schedule(html: str, list_url: str, adapter: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("table", id="meetings")
    if not t:
        return []
    tbody = t.find("tbody")
    if not tbody:
        return []
    out: list[dict[str, Any]] = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        loc = tds[0].get_text(" ", strip=True)
        desc_td = tds[1]
        title = desc_td.get_text(" ", strip=True)
        link = desc_td.find("a", href=True)
        detail_url = urljoin(list_url, link["href"]) if link else None
        meeting_type = tds[2].get_text(" ", strip=True)
        in_person = tds[3].get_text(" ", strip=True)
        comment_period = tds[4].get_text(" ", strip=True)
        comment_end = tds[5].get_text(" ", strip=True)
        parts = [loc, meeting_type, in_person, comment_period, comment_end]
        summary = " | ".join(p for p in parts if p)
        dates = _parse_us_slash_dates(" ".join([in_person, comment_end]))
        meeting_date = min(dates) if dates else None
        meeting_date_raw = None
        if dates:
            meeting_date_raw = min(dates).strftime("%m/%d/%Y")
        collateral: list[dict[str, Any]] = []
        if detail_url:
            collateral.append(
                {"url": detail_url, "kind": "detail_page", "label": (title or "project")[:200]}
            )
        out.append(
            {
                "adapter": adapter,
                "title": title or "(no title)",
                "summary_text": summary[:8000] if summary else None,
                "list_page_url": list_url,
                "detail_url": detail_url,
                "meeting_date": meeting_date.isoformat() if meeting_date else None,
                "meeting_date_raw": meeting_date_raw,
                "collateral": collateral,
            }
        )
    return out


def parse_for_state(state_usps: str, adapter: str, list_url: str, html: str) -> list[dict[str, Any]]:
    host = urlparse(list_url).netloc.lower()
    if state_usps.upper() == "WY" or "public-meeting-schedule" in list_url.lower():
        return parse_wy_schedule(html, list_url, adapter)
    if state_usps.upper() == "AL" and "pi_schedule" in list_url.lower():
        return parse_al_pi_schedule(html, list_url, adapter)
    if "dot.state.al.us" in host and "pi_schedule" in list_url.lower():
        return parse_al_pi_schedule(html, list_url, adapter)
    logger.warning("No parser for {} list_url={}", state_usps, list_url)
    return []


def _finalize_row(state_usps: str, row: dict[str, Any]) -> dict[str, Any]:
    fp = _event_fingerprint(state_usps, row)
    scraped_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "state_usps": state_usps.upper(),
        "event_fingerprint": fp,
        "scraped_at": scraped_at,
        **row,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE,
        help=f"Cache directory (default: {DEFAULT_CACHE})",
    )
    ap.add_argument("--states", nargs="*", help="USPS codes, e.g. WY AL")
    ap.add_argument("--all", action="store_true", help="Run every state in DOT_ADAPTER_SOURCES")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args()
    cache_root: Path = args.cache_root

    if args.all:
        states = sorted(DOT_ADAPTER_SOURCES.keys())
    elif args.states:
        states = [s.strip().upper() for s in args.states if s.strip()]
    else:
        ap.error("Pass --states … or --all")

    all_lines: list[dict[str, Any]] = []
    for usps in states:
        sources = DOT_ADAPTER_SOURCES.get(usps)
        if not sources:
            logger.warning("No adapter sources configured for {}", usps)
            continue
        state_rows: list[dict[str, Any]] = []
        for adapter, list_url in sources:
            logger.info("Fetch {} {}", usps, list_url)
            html = fetch_html(list_url, args.timeout)
            parsed = parse_for_state(usps, adapter, list_url, html)
            for row in parsed:
                state_rows.append(_finalize_row(usps, row))
        all_lines.extend(state_rows)
        out_state = cache_root / usps / "unified_events.json"
        out_state.parent.mkdir(parents=True, exist_ok=True)
        out_state.write_text(json.dumps(state_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        logger.info("Wrote {} events to {}", len(state_rows), out_state)

    jsonl_path = cache_root / "unified_events.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for obj in all_lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    logger.info("Wrote {} lines to {}", len(all_lines), jsonl_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
