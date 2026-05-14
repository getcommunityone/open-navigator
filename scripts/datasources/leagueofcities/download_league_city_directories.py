#!/usr/bin/env python3
"""
Download and extract municipal league "directory" style pages.

Reads the markdown table in ``readme.md`` (State | Organization | Directory link),
fetches each league homepage, discovers primary navigation links whose labels match
patterns like "Directory", "Member Cities", "About Cities", etc., then crawls a
bounded set of HTML pages (same host as the current page for link expansion, plus
per-state ``EXTRA_DIRECTORY_SEEDS_BY_USPS`` URLs such as iMIS directories) and
heuristically extracts city / member rows into a common JSON shape under ``data/cache/leagueofcities``.

Arkansas (AR) uses ``https://www.armunileague.org/member-directory/`` (wpDataTables server-side MySQL):
the script POSTs to ``admin-ajax.php?action=get_wdtable`` with DataTables paging, then aggregates
per-official rows into one record per city. If that endpoint returns an empty body (some networks /
bot rules), it falls back to the first HTML page via WP REST ``/wp-json/wp/v2/pages?slug=member-directory``,
which yields only a partial directory; use ``--min-cities 2`` for smoke tests in that case.

This is a best-effort static HTML pass (no headless browser). JavaScript-only
directories will yield few or zero rows; the manifest records page counts and errors.

States with fewer than ``--min-cities`` extracted (default: 5) are marked
``extraction_status: "error"`` in ``cities.json`` and retried up to ``--max-attempts``.
The process exits with code 1 if any state still fails after retries.

Usage (repo root)::

  python scripts/datasources/leagueofcities/download_league_city_directories.py --all
  python scripts/datasources/leagueofcities/download_league_city_directories.py --states AL TX
  python scripts/datasources/leagueofcities/download_league_city_directories.py --all --save-html
  python scripts/datasources/leagueofcities/download_league_city_directories.py --all --max-attempts 4

If a league site fails TLS (e.g. ``SSL: UNEXPECTED_EOF_WHILE_READING``), retry with
``--openssl-legacy-workaround`` or, only if you understand the risk (MITM / broken cert),
``--insecure-tls``.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import ssl
import string
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlencode, urlunparse

import httpx
from bs4 import BeautifulSoup, Tag
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_README = Path(__file__).resolve().parent / "readme.md"
CACHE_ROOT = REPO_ROOT / "data" / "cache" / "leagueofcities"

USER_AGENT = (
    "OpenNavigatorLeagueResearch/1.0 (+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "state municipal league directory snapshots)"
)

STATE_NAME_TO_USPS: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

NAV_HINTS: tuple[str, ...] = (
    "directory",
    "member cities",
    "member city",
    "about cities",
    "city directory",
    "municipal directory",
    "our cities",
    "cities & towns",
    "cities and towns",
    "find a city",
    "city search",
    "locate a city",
    "browse cities",
    "browse members",
    "member directory",
    "municipal members",
    "all cities",
    "member listing",
    "member municipalities",
    "participating cities",
    "participating municipalities",
    "communities we serve",
    "city listing",
    "municipal listing",
    "who we serve",
)

PATH_HINTS: tuple[str, ...] = (
    "directory",
    "member",
    "members",
    "cities",
    "municipalities",
    "locator",
    "find-city",
    "city-directory",
    "city_list",
    "our-communities",
    "participating",
)

# Canonical directory URLs that are easy to miss in nav (different host, or buried path).
# Alabama iMIS uses __doPostBack pagination; without a POST crawl we only get the first grid page (~20 rows).
EXTRA_DIRECTORY_SEEDS_BY_USPS: dict[str, tuple[str, ...]] = {
    "AL": (
        "https://alm.imiscloud.com/ALALM/ALALM/About/ALM-Municipal-Directory.aspx",
    ),
    "AK": (
        "https://www.akml.org/about/municipalities/",
    ),
    # Arkansas ML hosts the live directory on armunileague.org (arml.org redirects here).
    "AR": (
        "https://www.armunileague.org/member-directory/",
    ),
}

SKIP_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".zip",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".xml",
)


def strip_tracking_params(url: str) -> str:
    p = urlparse(url)
    pairs = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]
    new_query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def clean_md_cell(s: str) -> str:
    return re.sub(r"\*+", "", s).strip()


def parse_readme_table(path: Path) -> list[dict[str, Any]]:
    """Parse pipe table: State | Organization Name | Directory link."""
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    link_re = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
    for line in text.splitlines():
        line = line.rstrip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        state_raw = parts[1]
        org = parts[2]
        link_cell = parts[3]
        if state_raw.lower() == "state" or not state_raw:
            continue
        if set(state_raw) <= {"-", " ", ":"} or re.match(r"^:?-+:?$", state_raw):
            continue
        state_name = clean_md_cell(state_raw)
        usps = STATE_NAME_TO_USPS.get(state_name)
        if not usps:
            logger.warning("No USPS for state {!r}; skip row", state_name)
            continue
        m = link_re.search(link_cell)
        if not m:
            continue
        url = strip_tracking_params(m.group(2).strip())
        rows.append(
            {
                "state_usps": usps,
                "state_name": state_name,
                "league_organization": org,
                "league_base_url": url,
            }
        )
    return rows


def host_key(netloc: str) -> str:
    h = netloc.lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def same_league_site(base_url: str, target_url: str) -> bool:
    b = urlparse(base_url).netloc
    u = urlparse(target_url).netloc
    if not b or not u:
        return False
    bk, uk = host_key(b), host_key(u)
    return uk == bk or uk.endswith("." + bk) or bk.endswith("." + uk)


def is_vendor_associate_page(url: str) -> bool:
    """League vendor / sponsor tables (not municipal members)."""
    p = urlparse(url.lower()).path
    return any(
        frag in p
        for frag in (
            "/about/associates",
            "/associates-membership",
            "/associates-directory",
        )
    )


def is_akml_municipalities_directory(url: str) -> bool:
    p = urlparse(url.lower())
    return "akml.org" in host_key(p.netloc) and "/about/municipalities" in p.path


def nav_text_score(label: str) -> int:
    t = " ".join(label.lower().split())
    if not t or len(t) > 120:
        return 0
    score = 0
    for hint in NAV_HINTS:
        if hint in t:
            score += min(len(hint), 40)
    return score


def path_score(url: str) -> int:
    path = urlparse(url).path.lower()
    segments = [p for p in path.split("/") if p]
    score = 0
    strong = (
        "directory",
        "members",
        "member-list",
        "member_list",
        "cities",
        "municipalities",
        "locator",
        "city-search",
        "citysearch",
        "find-city",
        "city-directory",
        "our-communities",
        "participating",
    )
    joined = "/".join(segments)
    for seg in segments:
        for g in strong:
            if g in seg or g in joined:
                score += 10
                break
    if "city" in path and any(x in path for x in ("list", "search", "find", "browse")):
        score += 6
    for h in PATH_HINTS:
        if h in path:
            score += 2
    return min(score, 80)


def link_visible_text(a: Tag) -> str:
    parts: list[str] = []
    for child in a.descendants:
        if isinstance(child, str):
            t = child.strip()
            if t:
                parts.append(t)
        elif child.name == "img" and child.get("alt"):
            parts.append(str(child.get("alt")).strip())
    if parts:
        return " ".join(parts)
    return (a.get_text() or "").strip()


def collect_nav_anchors(soup: BeautifulSoup) -> list[Tag]:
    tags: list[Tag] = []
    for sel in ("nav", "header"):
        for el in soup.find_all(sel):
            if isinstance(el, Tag):
                tags.extend(el.find_all("a", href=True))
    for el in soup.find_all(attrs={"role": "navigation"}):
        if isinstance(el, Tag):
            tags.extend(el.find_all("a", href=True))
    for el in soup.find_all(class_=re.compile(r"nav|menu|header", re.I)):
        if isinstance(el, Tag):
            tags.extend(el.find_all("a", href=True))
    # de-dupe preserving order
    seen: set[int] = set()
    out: list[Tag] = []
    for a in tags:
        if id(a) in seen:
            continue
        seen.add(id(a))
        out.append(a)
    return out


def discover_seed_urls(soup: BeautifulSoup, base_url: str, max_seeds: int) -> list[str]:
    scored: list[tuple[int, str]] = []
    for a in collect_nav_anchors(soup):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = strip_tracking_params(urljoin(base_url, href))
        if urlparse(full).scheme not in ("http", "https"):
            continue
        if not same_league_site(base_url, full):
            continue
        low = full.lower()
        if any(low.split("?", 1)[0].endswith(ext) for ext in SKIP_EXTENSIONS):
            continue
        label = link_visible_text(a)
        sc = nav_text_score(label) + path_score(full) // 2
        if sc > 0:
            scored.append((sc, full))

    scored.sort(key=lambda x: -x[0])
    seeds: list[str] = []
    for _, u in scored:
        if u not in seeds:
            seeds.append(u)
        if len(seeds) >= max_seeds:
            break

    if not seeds:
        # Fallback: same-site links whose URL path suggests a directory
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full = strip_tracking_params(urljoin(base_url, href))
            if urlparse(full).scheme not in ("http", "https"):
                continue
            if not same_league_site(base_url, full):
                continue
            if path_score(full) >= 10:
                seeds.append(full)
            if len(seeds) >= max_seeds:
                break

    if base_url not in seeds:
        seeds.insert(0, base_url)
    else:
        seeds.remove(base_url)
        seeds.insert(0, base_url)
    return seeds[: max_seeds + 1]


def sitemap_urls(client: httpx.Client, base_url: str, timeout: float, limit: int) -> list[str]:
    sm = urljoin(base_url, "/sitemap.xml")
    try:
        r = client.get(sm, timeout=timeout, follow_redirects=True)
        if r.status_code != 200 or not r.content:
            return []
        root = ET.fromstring(r.content)
        locs: list[str] = []
        for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if loc.text:
                locs.append(loc.text.strip())
        scored = sorted(
            ((path_score(u) + nav_text_score(u), u) for u in locs if same_league_site(base_url, u)),
            key=lambda x: -x[0],
        )
        return [u for _, u in scored[:limit]]
    except Exception as e:
        logger.debug("sitemap skip {}: {}", sm, e)
        return []


def normalize_city_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def looks_like_city_name(s: str) -> bool:
    s = s.strip()
    if len(s) < 2 or len(s) > 80:
        return False
    # Vendor rows often embed phones / "Email »" in the scraped "name" cell.
    if re.search(r"\(\d{3}\)\s*\d{3}", s):
        return False
    if re.search(r"\bemail\s*»|\bwebsite\s*»", s, re.I):
        return False
    if re.search(r"(click|read more|here|login|subscribe|privacy|cookie|menu)", s, re.I):
        return False
    if s.isdigit():
        return False
    if ";" in s:
        return False
    if "–" in s and len(s) > 40:
        return False
    if s.count(".") > 1 or (s.endswith(".") and len(s) > 25):
        return False
    if re.match(r"^(assure|accelerate|support|ensure|promote|increase|decrease|maintain|provide)\b", s, re.I):
        return False
    if re.match(r"^(municipal|member)\s+information$", s, re.I):
        return False
    if re.match(r"^municipal\s+directory$", s, re.I):
        return False
    return True


def _cell_looks_like_phone(s: str) -> bool:
    return bool(re.search(r"\(\d{3}\)\s*\d", s))


def is_armunileague_member_directory_url(url: str) -> bool:
    """Arkansas Municipal League wpDataTables member directory (per-official rows)."""
    p = urlparse(url.lower())
    return host_key(p.netloc).endswith("armunileague.org") and "/member-directory" in p.path


# wpDataTables / DataTables column binding for AR member directory (see table_1_desc on page).
ARMUNILEAGUE_DT_COLS: tuple[str, ...] = (
    "CITYNAME",
    "NAME",
    "POSITION",
    "COUNTY",
    "POPULATION",
    "SENATE",
    "HOUSE",
    "CONG",
    "CLASSIFICATION",
    "ADDRESS",
    "CITY",
    "STATE",
    "ZIP",
    "PHONE",
    "FAX",
    "MEETINGS",
    "WEBSITE",
)


def _strip_html_cell(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s or "<" not in s:
        return s
    return BeautifulSoup(s, "html.parser").get_text(" ", strip=True)


def _normalize_wdt_data_row(row: Any, colnames: tuple[str, ...]) -> list[str]:
    if isinstance(row, list):
        return [_strip_html_cell(x) for x in row]
    if isinstance(row, dict):
        return [_strip_html_cell(row.get(n, "")) for n in colnames]
    return []


def _armunileague_build_wdt_post_body(table_wp_id: str, nonce: str, start: int, length: int) -> dict[str, str]:
    names = ARMUNILEAGUE_DT_COLS
    data: dict[str, str] = {
        "action": "get_wdtable",
        "table_id": str(table_wp_id),
        f"wdtNonceFrontendServerSide_{table_wp_id}": nonce,
        "draw": "1",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
    }
    for i, nm in enumerate(names):
        data[f"columns[{i}][data]"] = str(i)
        data[f"columns[{i}][name]"] = nm
        data[f"columns[{i}][searchable]"] = "true"
        data[f"columns[{i}][orderable]"] = "true"
        data[f"columns[{i}][search][value]"] = ""
        data[f"columns[{i}][search][regex]"] = "false"
    return data


def fetch_armunileague_wpdatatables_ssr_rows(
    client: httpx.Client,
    *,
    member_page_html: str,
    referer: str,
    timeout: float,
    page_size: int = 250,
    pause_min: float = 0.15,
    pause_max: float = 0.45,
) -> list[list[str]]:
    """
    Page through wpDataTables server-side ``get_wdtable`` (MySQL) for the member directory.

    Some hosts return an empty body for this endpoint when TLS/headers do not match a browser;
    callers should fall back to :func:`fetch_armunileague_wp_rest_table_rows`.
    """
    m = re.search(r'id="wdtNonceFrontendServerSide_(\d+)"[^>]*value="([^"]+)"', member_page_html)
    if not m:
        logger.warning("AR member directory: no wdtNonceFrontendServerSide hidden input found")
        return []
    table_wp_id, nonce = m.group(1), m.group(2)
    out: list[list[str]] = []
    start = 0
    records_total: int | None = None
    draw_id = 1
    ajax = "https://www.armunileague.org/wp-admin/admin-ajax.php"
    while True:
        body = _armunileague_build_wdt_post_body(table_wp_id, nonce, start, page_size)
        body["draw"] = str(draw_id)
        draw_id += 1
        r = client.post(
            ajax,
            content=urlencode(body),
            timeout=timeout,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": referer.strip(),
                "Origin": "https://www.armunileague.org",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        if r.status_code != 200 or not (r.text or "").strip():
            if start == 0:
                logger.warning(
                    "AR wpDataTables get_wdtable returned empty (status={}); "
                    "trying WP REST fallback — if both fail, export may require a normal browser session.",
                    r.status_code,
                )
            break
        try:
            payload = r.json()
        except json.JSONDecodeError:
            logger.warning("AR wpDataTables get_wdtable non-JSON response (first 120 chars): {!r}", (r.text or "")[:120])
            break
        chunk_raw = payload.get("data") or []
        chunk = [_normalize_wdt_data_row(row, ARMUNILEAGUE_DT_COLS) for row in chunk_raw]
        out.extend(chunk)
        try:
            records_total = int(payload.get("recordsTotal") or payload.get("recordsFiltered") or 0)
        except (TypeError, ValueError):
            records_total = None
        start += len(chunk)
        if not chunk:
            break
        if records_total is not None and start >= records_total:
            break
        time.sleep(random.uniform(pause_min, pause_max))
    return out


def fetch_armunileague_wp_rest_table_rows(client: httpx.Client, timeout: float) -> list[list[str]]:
    """Fallback: WP REST ``content.rendered`` embeds the first HTML page of the table (no JS paging)."""
    try:
        r = client.get(
            "https://www.armunileague.org/wp-json/wp/v2/pages",
            params={"slug": "member-directory"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return []
        pages = r.json()
        if not isinstance(pages, list) or not pages:
            return []
        pid = pages[0].get("id")
        if pid is None:
            return []
        r2 = client.get(f"https://www.armunileague.org/wp-json/wp/v2/pages/{int(pid)}", timeout=timeout)
        if r2.status_code != 200:
            return []
        html = (r2.json() or {}).get("content", {}).get("rendered") or ""
    except Exception as e:
        logger.warning("AR WP REST table fetch failed: {}", e)
        return []
    return parse_armunileague_table_1_html_rows(html)


def parse_armunileague_table_1_html_rows(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("table", id=re.compile(r"^table_\d+$"))
    if not isinstance(t, Tag):
        t = soup.find("table")
    if not isinstance(t, Tag):
        return []
    trs = t.find_all("tr")
    if len(trs) < 2:
        return []
    out: list[list[str]] = []
    for tr in trs[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 17:
            continue
        row = [c.get_text(" ", strip=True) for c in cells[:17]]
        out.append(row)
    return out


def aggregate_armunileague_person_rows_to_cities(
    person_rows: list[list[str]],
    *,
    page_url: str,
    source_kind: str,
) -> list[dict[str, Any]]:
    """Collapse per-official rows into one record per municipality (display city name)."""
    I_CITYNAME, I_NAME, I_POS = 0, 1, 2
    I_COUNTY, I_POP, I_CLASS, I_ADDR = 3, 4, 8, 9
    I_CITY = 10
    I_PHONE, I_WEB = 13, 16

    by_norm: dict[str, dict[str, Any]] = {}
    for row in person_rows:
        if len(row) < 17:
            continue
        city_display = (row[I_CITY] or row[I_CITYNAME] or "").strip()
        if not city_display:
            continue
        if not looks_like_city_name(city_display) and looks_like_city_name(row[I_CITYNAME].strip()):
            city_display = string.capwords(row[I_CITYNAME].strip().lower())
        key = normalize_city_name(city_display)
        if not key:
            continue
        name_pretty = string.capwords(city_display.lower()) if city_display.isupper() else city_display
        pos = row[I_POS].strip()
        official = row[I_NAME].strip()
        rec = by_norm.get(key)
        if rec is None:
            rec = {
                "name": name_pretty[:200],
                "population": row[I_POP].strip() or None,
                "county": row[I_COUNTY].strip() or None,
                "mayor": None,
                "website": None,
                "phone": None,
                "email": None,
                "address": row[I_ADDR].strip() or None,
                "municipality_type": row[I_CLASS].strip() or None,
                "source_url": page_url,
                "source_kind": source_kind,
                "source_detail": "aggregated_by_city",
                "raw_row": row,
            }
            by_norm[key] = rec
        else:
            if not rec.get("population") and row[I_POP].strip():
                rec["population"] = row[I_POP].strip()
            if not rec.get("county") and row[I_COUNTY].strip():
                rec["county"] = row[I_COUNTY].strip()
            if not rec.get("address") and row[I_ADDR].strip():
                rec["address"] = row[I_ADDR].strip()
            if not rec.get("municipality_type") and row[I_CLASS].strip():
                rec["municipality_type"] = row[I_CLASS].strip()
        if official and "mayor" in pos.lower() and not rec.get("mayor"):
            rec["mayor"] = official
        if not rec.get("phone") and row[I_PHONE].strip() and _cell_looks_like_phone(row[I_PHONE]):
            rec["phone"] = row[I_PHONE].strip()
        if not rec.get("website"):
            site = row[I_WEB].strip()
            if site.startswith("http"):
                rec["website"] = strip_tracking_params(site)
            elif re.match(r"^www\.[a-z0-9.-]+\.[a-z]{2,}", site, re.I):
                rec["website"] = strip_tracking_params("https://" + site)
    return list(by_norm.values())


def extract_armunileague_member_directory(
    client: httpx.Client,
    page_url: str,
    timeout: float,
    member_page_html: str,
) -> list[dict[str, Any]]:
    if not is_armunileague_member_directory_url(page_url):
        return []
    ssr = fetch_armunileague_wpdatatables_ssr_rows(
        client, member_page_html=member_page_html, referer=page_url, timeout=timeout
    )
    if ssr:
        return aggregate_armunileague_person_rows_to_cities(ssr, page_url=page_url, source_kind="ar_member_directory")
    rest_rows = fetch_armunileague_wp_rest_table_rows(client, timeout)
    if rest_rows:
        logger.warning(
            "AR member directory: using WP REST first-page HTML fallback ({} person rows); "
            "wpDataTables AJAX returned no rows — run from a desktop network if you need the full directory.",
            len(rest_rows),
        )
        return aggregate_armunileague_person_rows_to_cities(
            rest_rows, page_url=page_url, source_kind="ar_member_directory_rest"
        )
    return []


def fix_double_scheme_url(url: str) -> str:
    """Normalize ``http://https://example.com/`` style hrefs (Iowa league table)."""
    u = url.strip()
    if not u:
        return u
    m = re.match(r"^https?://(https?://.+)$", u, re.DOTALL)
    if m:
        return m.group(1)
    return u


_LOOSE_DOMAIN = re.compile(
    r"^([a-z0-9][a-z0-9.-]*\.(?:gov|org|net|com|us|edu|io|co))(?:/[^\s]*)?/?$",
    re.I,
)


def official_url_from_website_cell(cell: Tag, page_url: str) -> str | None:
    """
    Municipal site from the **Website** column only (not the City column's
    ``/cities/{id}`` league profile link).
    """
    ph = host_key(urlparse(page_url).netloc)
    candidates: list[str] = []
    for a in cell.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href_raw = (a.get("href") or "").strip()
        if label:
            candidates.append(label)
        if href_raw and href_raw not in candidates:
            candidates.append(href_raw)
    txt = cell.get_text(" ", strip=True)
    if txt and txt not in candidates:
        candidates.append(txt)

    for raw in candidates:
        c = fix_double_scheme_url(raw.strip())
        if not c or c in (")", "http://)", "https://)"):
            continue
        if c.startswith("//"):
            c = "https:" + c
        if not re.match(r"^https?://", c, re.I):
            if re.match(r"^www\.[a-z0-9.-]+\.[a-z]{2,}(/.*)?$", c, re.I):
                c = "https://" + c
            elif _LOOSE_DOMAIN.match(c):
                c = "https://" + c.lstrip("/")
            else:
                continue
        try:
            full = strip_tracking_params(c)
        except Exception:
            continue
        if urlparse(full).scheme not in ("http", "https"):
            continue
        nh = host_key(urlparse(full).netloc)
        if nh == ph and "/cities/" in full:
            continue
        if nh == ph:
            continue
        if full.startswith("http://"):
            full = "https://" + full[len("http://") :]
        return full
    return None


def _imis_roster_http_url(href: str) -> str | None:
    """Pull ``https://...ORGpublicProfileRoster.aspx?...`` out of ``javascript:ShowDialog...`` hrefs."""
    raw = href.strip()
    m = re.search(
        r"(https?://[^\s'\"]+ORGpublicProfileRoster\.aspx[^\s'\"]*)",
        raw,
        re.I,
    )
    if m:
        return strip_tracking_params(m.group(1))
    return None


def league_profile_url_from_name_cell(name_cell: Tag, page_url: str) -> str | None:
    """League city profile URL from the name / City column (e.g. ``/cities/101`` or iMIS roster)."""
    for a in name_cell.find_all("a", href=True):
        href_raw = (a.get("href") or "").strip()
        if not href_raw:
            continue
        if href_raw.lower().startswith("javascript:"):
            imis = _imis_roster_http_url(href_raw)
            if imis and same_league_site(page_url, imis):
                return imis
            continue
        u = strip_tracking_params(urljoin(page_url, fix_double_scheme_url(href_raw)))
        if urlparse(u).scheme not in ("http", "https"):
            continue
        low = u.lower()
        if same_league_site(page_url, u) and ("/cities/" in low or "orgpublicprofileroster.aspx" in low):
            return u
    return None


def municipality_site_from_cells(cells: list[str], page_url: str) -> str | None:
    """Pick an official municipal web address from table cells (not league profile)."""
    ph = host_key(urlparse(page_url).netloc)
    for cell in cells:
        c = cell.strip()
        if not c or len(c) > 200 or _cell_looks_like_phone(c):
            continue
        if re.fullmatch(r"[\d,.\s]+", c):
            continue
        cand: str | None = None
        if c.startswith("http://") or c.startswith("https://"):
            cand = strip_tracking_params(c)
        elif re.match(r"^www\.[a-z0-9.-]+\.[a-z]{2,}(/.*)?$", c, re.I):
            cand = strip_tracking_params("https://" + c)
        elif re.search(r"^[a-z0-9][a-z0-9.-]*\.(gov|org|net|com|us)(/[^\s]*)?$", c, re.I):
            cand = strip_tracking_params("https://" + c)
        if not cand:
            continue
        try:
            ch = host_key(urlparse(cand).netloc)
        except Exception:
            continue
        if ch == ph:
            continue
        if "/cities/" in cand:
            continue
        return cand
    return None


def header_map(cells: list[str]) -> dict[str, int]:
    """Map canonical field -> column index from header row."""
    canon: dict[str, int] = {}
    aliases: dict[str, tuple[str, ...]] = {
        "name": ("city", "municipality", "town", "member", "name", "community", "village", "borough"),
        "population": ("population", "pop.", "pop", "2020", "2023", "2024", "census"),
        "county": ("county", "parish", "borough"),
        "mayor": ("mayor", "manager", "administrator"),
        "website": ("website", "web", "url", "link", "home page", "homepage"),
        "phone": ("phone", "telephone", "tel", "fax"),
        "email": ("email", "e-mail", "contact"),
        "address": ("address", "location", "mailing"),
        "municipality_type": ("type", "class", "form of government", "government"),
    }
    lowered = [re.sub(r"\s+", " ", c.lower().strip()) for c in cells]
    for canon_key, keys in aliases.items():
        for i, h in enumerate(lowered):
            for k in keys:
                if k == h or (len(k) > 3 and k in h):
                    if canon_key not in canon:
                        canon[canon_key] = i
                    break
    return canon


def extract_from_tables(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    if is_vendor_associate_page(page_url):
        return []
    out: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        if not header_cells:
            continue
        cmap = header_map(header_cells)
        # require a plausible name column or use first column as name if many rows
        start = 1
        if "name" not in cmap and len(header_cells) >= 2:
            cmap = {"name": 0}
            start = 0
        if "name" not in cmap:
            continue
        for ri, tr in enumerate(rows[start:], start=1):
            cell_tags = tr.find_all(["td", "th"], recursive=False)
            if not cell_tags:
                continue
            max_col = max(cmap.values())
            if len(cell_tags) <= max_col:
                continue
            name_col = cmap["name"]
            name_cell = cell_tags[name_col]
            name = name_cell.get_text(" ", strip=True)
            if not looks_like_city_name(name):
                continue
            cells = [c.get_text(" ", strip=True) for c in cell_tags]
            rec: dict[str, Any] = {
                "name": name,
                "population": cells[cmap["population"]] if "population" in cmap and cmap["population"] < len(cells) else None,
                "county": cells[cmap["county"]] if "county" in cmap and cmap["county"] < len(cells) else None,
                "mayor": cells[cmap["mayor"]] if "mayor" in cmap and cmap["mayor"] < len(cells) else None,
                "website": None,
                "phone": cells[cmap["phone"]] if "phone" in cmap and cmap["phone"] < len(cells) else None,
                "email": cells[cmap["email"]] if "email" in cmap and cmap["email"] < len(cells) else None,
                "address": cells[cmap["address"]] if "address" in cmap and cmap["address"] < len(cells) else None,
                "municipality_type": cells[cmap["municipality_type"]]
                if "municipality_type" in cmap and cmap["municipality_type"] < len(cells)
                else None,
                "source_url": page_url,
                "source_kind": "table",
                "source_detail": f"table_row_{ri}",
                "raw_row": cells,
            }
            official: str | None = None
            if "website" in cmap and cmap["website"] < len(cell_tags):
                official = official_url_from_website_cell(cell_tags[cmap["website"]], page_url)
            if not official:
                official = municipality_site_from_cells(cells, page_url)
            rec["website"] = official
            prof = league_profile_url_from_name_cell(name_cell, page_url)
            if prof:
                rec["league_profile_url"] = prof
            out.append(rec)
    return out


def extract_from_definition_lists(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    if is_vendor_associate_page(page_url):
        return []
    out: list[dict[str, Any]] = []
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt", recursive=False)
        dds = dl.find_all("dd", recursive=False)
        for dt, dd in zip(dts, dds):
            label = dt.get_text(" ", strip=True)
            val = dd.get_text(" ", strip=True)
            if not label or not val:
                continue
            if any(k in label.lower() for k in ("city", "municipality", "town", "member")):
                if looks_like_city_name(val):
                    rec = {
                        "name": val,
                        "population": None,
                        "county": None,
                        "mayor": None,
                        "website": None,
                        "phone": None,
                        "email": None,
                        "address": None,
                        "municipality_type": None,
                        "source_url": page_url,
                        "source_kind": "dl",
                        "source_detail": label[:80],
                        "raw_row": [label, val],
                    }
                    la = dd.find("a", href=True)
                    if la and la["href"].strip().startswith("http"):
                        rec["website"] = strip_tracking_params(la["href"].strip())
                    out.append(rec)
    return out


def extract_from_member_lists(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    """List items that are mostly a short place name with optional external link."""
    out: list[dict[str, Any]] = []
    if is_vendor_associate_page(page_url):
        return out
    if path_score(page_url) < 10:
        return out
    main = soup.find("main") or soup.find(id=re.compile(r"content|main", re.I)) or soup.body
    if not isinstance(main, Tag):
        return out
    for li in main.find_all("li"):
        if li.find_parent("nav"):
            continue
        a = li.find("a", href=True)
        text = li.get_text(" ", strip=True)
        name = (a.get_text(strip=True) if a else text) or ""
        if not looks_like_city_name(name):
            continue
        if len(text) > 200:
            continue
        href = a["href"].strip() if a else ""
        website = None
        if href.startswith("http"):
            website = strip_tracking_params(href)
        elif href and not href.startswith("#"):
            website = strip_tracking_params(urljoin(page_url, href))
        out.append(
            {
                "name": name[:200],
                "population": None,
                "county": None,
                "mayor": None,
                "website": website,
                "phone": None,
                "email": None,
                "address": None,
                "municipality_type": None,
                "source_url": page_url,
                "source_kind": "list_item",
                "source_detail": None,
                "raw_row": [text],
            }
        )
    return out


def extract_akml_municipal_directory_links(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    """
    Alaska ML lists members as ``<a href=\"...pdf\">City</a>`` blocks (Divi), not tables or ``<li>``.
    """
    if not is_akml_municipalities_directory(page_url):
        return []
    root = soup.find(id="main-content") or soup.find(id=re.compile(r"et-main-area", re.I)) or soup.find("article")
    if not isinstance(root, Tag):
        root = soup.body if isinstance(soup.body, Tag) else None
    if not isinstance(root, Tag):
        return []
    out: list[dict[str, Any]] = []
    ph = host_key(urlparse(page_url).netloc)
    i = 0
    for a in root.find_all("a", href=True):
        if a.find_parent("nav"):
            continue
        if a.find_parent(class_=re.compile(r"tb_footer|tb_header", re.I)):
            continue
        name = a.get_text(" ", strip=True)
        if not looks_like_city_name(name):
            continue
        href = strip_tracking_params(urljoin(page_url, fix_double_scheme_url(a["href"].strip())))
        if urlparse(href).scheme not in ("http", "https"):
            continue
        nh = host_key(urlparse(href).netloc)
        if nh != ph:
            continue
        low = href.lower()
        website = href if ("/wp-content/uploads/" in low or low.endswith(".pdf")) else None
        i += 1
        out.append(
            {
                "name": name[:200],
                "population": None,
                "county": None,
                "mayor": None,
                "website": website,
                "phone": None,
                "email": None,
                "address": None,
                "municipality_type": None,
                "source_url": page_url,
                "source_kind": "akml_pdf_directory",
                "source_detail": f"pdf_link_{i}",
                "raw_row": [name, href],
            }
        )
    return out


def merge_city_records(records: list[dict[str, Any]], state_usps: str) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for r in records:
        key = normalize_city_name(r["name"])
        if not key:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = dict(r)
            continue
        # merge: prefer non-null fields from either; prefer table over list_item
        rank = {"table": 3, "dl": 2, "list_item": 1, "akml_pdf_directory": 3, "ar_member_directory": 3, "ar_member_directory_rest": 2}
        pr, rr = rank.get(prev.get("source_kind"), 0), rank.get(r.get("source_kind"), 0)
        base, other = (prev, r) if pr >= rr else (r, prev)
        merged = dict(base)
        for f in (
            "population",
            "county",
            "mayor",
            "website",
            "league_profile_url",
            "phone",
            "email",
            "address",
            "municipality_type",
        ):
            if not merged.get(f) and other.get(f):
                merged[f] = other[f]
        by_key[key] = merged

    final: list[dict[str, Any]] = []
    for r in by_key.values():
        r["state_usps"] = state_usps
        final.append(r)
    final.sort(key=lambda x: normalize_city_name(x["name"]))
    return final


def _openssl_legacy_cipher_context() -> ssl.SSLContext:
    """
    Some regional sites use older TLS stacks; OpenSSL 3 defaults (SECLEVEL=2) can
    fail handshakes that browsers still accept. Lower cipher constraints as a last
    resort before --insecure-tls.
    """
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return ctx


def fetch_html(client: httpx.Client, url: str, timeout: float) -> tuple[int | None, str | None, bytes]:
    """
    GET with retries for transient TLS / connection resets (e.g. UNEXPECTED_EOF_WHILE_READING).
    """
    last_exc: BaseException | None = None
    for attempt in range(1, 4):
        try:
            r = client.get(url, timeout=timeout, follow_redirects=True)
            return (
                r.status_code,
                r.headers.get("content-type", "").split(";")[0].strip().lower() or None,
                r.content,
            )
        except (
            ssl.SSLError,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.RemoteProtocolError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
        ) as e:
            last_exc = e
            if attempt < 3:
                delay = 0.6 * attempt + random.uniform(0, 0.35)
                logger.warning(
                    "GET attempt {}/{} failed {} ({}); retrying in {:.1f}s",
                    attempt,
                    3,
                    url,
                    e,
                    delay,
                )
                time.sleep(delay)
        except Exception as e:
            logger.warning("GET failed {}: {}", url, e)
            return None, None, b""
    if last_exc is not None:
        logger.warning("GET failed {} after 3 attempts: {}", url, last_exc)
    return None, None, b""


def crawl_state_league(
    client: httpx.Client,
    rec: dict[str, Any],
    *,
    timeout: float,
    max_pages: int,
    max_seeds: int,
    delay_min: float,
    delay_max: float,
    save_html: bool,
    cache_usps: Path,
    sitemap_extra: int,
    min_cities: int,
) -> dict[str, Any]:
    base = rec["league_base_url"]
    usps = rec["state_usps"]
    errors: list[str] = []
    pages_meta: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    def pause() -> None:
        time.sleep(random.uniform(delay_min, delay_max))

    status, ctype, body = fetch_html(client, base, timeout)
    pause()

    def finalize(merged_in: list[dict[str, Any]], pages_meta_in: list[dict[str, Any]], errors_in: list[str]) -> dict[str, Any]:
        merged = merge_city_records(merged_in, usps)
        extracted_at = datetime.now(timezone.utc).isoformat()
        for c in merged:
            c["alternate_names"] = []
            c.setdefault("state_usps", usps)
        all_errs = list(errors_in)
        n = len(merged)
        extraction_status = "ok"
        if n < min_cities:
            extraction_status = "error"
            all_errs.append(f"too_few_cities:{n}<{min_cities}")
        out_doc = {
            "state_usps": usps,
            "state_name": rec["state_name"],
            "league_organization": rec["league_organization"],
            "league_base_url": base,
            "extracted_at": extracted_at,
            "extraction_status": extraction_status,
            "extraction_errors": all_errs,
            "min_cities_expected": min_cities,
            "cities": merged,
        }
        (cache_usps / "cities.json").write_text(json.dumps(out_doc, indent=2), encoding="utf-8")
        (cache_usps / "pages_index.json").write_text(json.dumps({"pages": pages_meta_in}, indent=2), encoding="utf-8")
        return {
            "seed_urls": list(dict.fromkeys([p["url"] for p in pages_meta_in])),
            "pages_fetched": len(pages_meta_in),
            "cities_extracted": n,
            "extraction_status": extraction_status,
            "errors": all_errs,
            "pages": pages_meta_in,
        }

    if status != 200 or not body:
        errors.append(f"homepage_http_{status}")
        return finalize([], pages_meta, errors)

    soup = BeautifulSoup(body, "html.parser")
    queue: list[str] = []
    seen: set[str] = set()

    for u in discover_seed_urls(soup, base, max_seeds):
        if u not in seen:
            seen.add(u)
            queue.append(u)

    for u in EXTRA_DIRECTORY_SEEDS_BY_USPS.get(usps, ()):
        u = strip_tracking_params(u.strip())
        if urlparse(u).scheme not in ("http", "https") or u in seen:
            continue
        seen.add(u)
        if queue and queue[0] == base:
            queue.insert(1, u)
        else:
            queue.insert(0, u)

    if sitemap_extra > 0:
        for u in sitemap_urls(client, base, timeout, sitemap_extra):
            if u not in seen and same_league_site(base, u):
                seen.add(u)
                queue.append(u)
        pause()

    if save_html:
        (cache_usps / "snapshots").mkdir(parents=True, exist_ok=True)
        safe = "index_home.html"
        (cache_usps / "snapshots" / safe).write_bytes(body)

    # process queue
    while queue and len(pages_meta) < max_pages:
        url = queue.pop(0)
        if url in {p["url"] for p in pages_meta}:
            continue
        st, ct, raw = (
            (status, ctype, body)
            if url == base and pages_meta == []
            else fetch_html(client, url, timeout)
        )
        if url != base or pages_meta:
            pause()
        if st != 200 or not raw:
            pages_meta.append({"url": url, "http_status": st, "bytes": 0, "error": "fetch_failed"})
            continue
        if ct and "html" not in ct and "text" not in ct:
            pages_meta.append({"url": url, "http_status": st, "bytes": len(raw), "content_type": ct, "skipped": True})
            continue

        if raw.lstrip()[:120].decode("utf-8", errors="ignore").lstrip().startswith("<?xml"):
            pages_meta.append(
                {"url": url, "http_status": st, "bytes": len(raw), "content_type": ct, "skipped": "xml_not_html"}
            )
            continue

        psoup = BeautifulSoup(raw, "html.parser")
        if save_html:
            slug = re.sub(r"[^\w.\-]+", "_", urlparse(url).path)[:120] or "page"
            if not slug.endswith(".html"):
                slug += ".html"
            (cache_usps / "snapshots" / f"{len(pages_meta):03d}_{slug}").write_bytes(raw)

        html_text = raw.decode("utf-8", errors="replace")
        if usps == "AR" and is_armunileague_member_directory_url(url):
            rows = extract_armunileague_member_directory(client, url, timeout, html_text)
            if not rows:
                rows = (
                    extract_from_tables(psoup, url)
                    + extract_from_definition_lists(psoup, url)
                    + extract_from_member_lists(psoup, url)
                    + extract_akml_municipal_directory_links(psoup, url)
                )
        else:
            rows = (
                extract_from_tables(psoup, url)
                + extract_from_definition_lists(psoup, url)
                + extract_from_member_lists(psoup, url)
                + extract_akml_municipal_directory_links(psoup, url)
            )
        all_rows.extend(rows)
        pages_meta.append(
            {
                "url": url,
                "http_status": st,
                "bytes": len(raw),
                "content_type": ct,
                "rows_extracted": len(rows),
            }
        )

        # Stop after a configured canonical directory page returns enough rows (avoids
        # enqueuing dozens of nav/member-service URLs + ~0.5s delay per fetch, e.g. AKML).
        extra_norm = {
            strip_tracking_params(u).rstrip("/").lower() for u in EXTRA_DIRECTORY_SEEDS_BY_USPS.get(usps, ())
        }
        hit_canonical = bool(extra_norm) and len(rows) >= min_cities and strip_tracking_params(url).rstrip("/").lower() in extra_norm
        if hit_canonical:
            queue.clear()

        # expand queue with same-site links on directory-like pages
        page_title = psoup.title.get_text(strip=True) if psoup.title else ""
        if (
            len(pages_meta) < max_pages
            and (path_score(url) > 0 or nav_text_score(page_title) > 0)
            and not hit_canonical
        ):
            for a in psoup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                full = strip_tracking_params(urljoin(url, href))
                if urlparse(full).scheme not in ("http", "https"):
                    continue
                if not same_league_site(url, full):
                    continue
                low = full.lower().split("?", 1)[0]
                if any(low.endswith(ext) for ext in SKIP_EXTENSIONS):
                    continue
                if full in seen:
                    continue
                if path_score(full) + nav_text_score(link_visible_text(a)) == 0:
                    continue
                seen.add(full)
                queue.append(full)

    return finalize(all_rows, pages_meta, errors)


def main() -> int:
    ap = argparse.ArgumentParser(description="Download state league directory pages and extract city rows.")
    ap.add_argument("--readme", type=Path, default=DEFAULT_README, help="Markdown table path")
    ap.add_argument("--cache", type=Path, default=CACHE_ROOT, help="Output cache root")
    ap.add_argument("--states", nargs="*", help="USPS codes (e.g. AL TX)")
    ap.add_argument("--all", action="store_true", help="All states in the table")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--max-pages", type=int, default=42, help="Max HTML pages per state")
    ap.add_argument("--max-seeds", type=int, default=14, help="Max nav/sitemap seed URLs from homepage")
    ap.add_argument("--sitemap-extra", type=int, default=8, help="Extra URLs from /sitemap.xml (0=disable)")
    ap.add_argument("--delay-min", type=float, default=0.35, help="Polite delay lower bound (seconds)")
    ap.add_argument("--delay-max", type=float, default=1.1, help="Polite delay upper bound (seconds)")
    ap.add_argument("--save-html", action="store_true", help="Save fetched HTML under each state's snapshots/")
    ap.add_argument(
        "--min-cities",
        type=int,
        default=5,
        help="Fewer unique cities than this after a run marks extraction_status=error (default: 5)",
    )
    ap.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum crawl attempts per state when below --min-cities (default: 3)",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--insecure-tls",
        action="store_true",
        help="Disable TLS certificate verification (insecure; for broken certs or certain intercept proxies only)",
    )
    ap.add_argument(
        "--openssl-legacy-workaround",
        action="store_true",
        help="Relax OpenSSL cipher/SECLEVEL (DEFAULT:@SECLEVEL=1) for legacy TLS stacks",
    )
    args = ap.parse_args()

    if not args.readme.is_file():
        logger.error("Missing readme: {}", args.readme)
        return 1

    registry = parse_readme_table(args.readme)
    if not registry:
        logger.error("No rows parsed from {}", args.readme)
        return 1

    by_usps = {r["state_usps"]: r for r in registry}
    want = set(by_usps)
    if args.all:
        selected = sorted(want)
    elif args.states:
        selected = [s.strip().upper() for s in args.states if s.strip()]
        bad = [s for s in selected if s not in want]
        if bad:
            logger.error("Unknown USPS (not in readme): {}", bad)
            return 1
    else:
        logger.error("Specify --all or --states AL ...")
        return 1

    args.cache.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        for u in selected:
            r = by_usps[u]
            logger.info("[dry-run] {} {} -> {}", u, r["league_organization"], r["league_base_url"])
        return 0

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    if args.insecure_tls:
        logger.warning(
            "TLS certificate verification is OFF (--insecure-tls). "
            "Only use on trusted networks or for known-broken league hosts."
        )
        verify: bool | ssl.SSLContext = False
    elif args.openssl_legacy_workaround:
        logger.warning(
            "Using relaxed TLS cipher policy (--openssl-legacy-workaround); weaker than defaults."
        )
        verify = _openssl_legacy_cipher_context()
    else:
        verify = True

    manifest_rows: list[dict[str, Any]] = []
    failed_states: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()

    with httpx.Client(headers=headers, verify=verify, http2=False) as client:
        for usps in selected:
            rec = by_usps[usps]
            cache_usps = args.cache / usps
            cache_usps.mkdir(parents=True, exist_ok=True)
            summary: dict[str, Any] | None = None
            for attempt in range(1, args.max_attempts + 1):
                if attempt > 1:
                    backoff = random.uniform(1.0, 3.0) * attempt
                    logger.warning(
                        "{} still below {} cities (or crawl error); sleeping {:.1f}s before attempt {}/{}",
                        usps,
                        args.min_cities,
                        backoff,
                        attempt,
                        args.max_attempts,
                    )
                    time.sleep(backoff)
                logger.info("Crawling {} {} (attempt {}/{}) ...", usps, rec["league_base_url"], attempt, args.max_attempts)
                summary = crawl_state_league(
                    client,
                    rec,
                    timeout=args.timeout,
                    max_pages=args.max_pages,
                    max_seeds=args.max_seeds,
                    delay_min=args.delay_min,
                    delay_max=args.delay_max,
                    save_html=args.save_html,
                    cache_usps=cache_usps,
                    sitemap_extra=args.sitemap_extra,
                    min_cities=args.min_cities,
                )
                if summary["extraction_status"] == "ok":
                    break
            assert summary is not None
            if summary["extraction_status"] != "ok":
                failed_states.append(usps)
            manifest_rows.append(
                {
                    "state_usps": usps,
                    "state_name": rec["state_name"],
                    "league_organization": rec["league_organization"],
                    "league_base_url": rec["league_base_url"],
                    "generated_at": generated_at,
                    "attempts_used": attempt,
                    "max_attempts": args.max_attempts,
                    "min_cities": args.min_cities,
                    "extraction_status": summary["extraction_status"],
                    "pages_fetched": summary["pages_fetched"],
                    "cities_extracted": summary["cities_extracted"],
                    "errors": summary["errors"],
                    "cities_json": str((cache_usps / "cities.json").relative_to(REPO_ROOT)),
                }
            )
            logger.info(
                "{} done (status={}): {} pages, {} cities -> {}",
                usps,
                summary["extraction_status"],
                summary["pages_fetched"],
                summary["cities_extracted"],
                cache_usps / "cities.json",
            )

    manifest = {
        "generated_at": generated_at,
        "source_readme": str(args.readme.relative_to(REPO_ROOT)),
        "cache_root": str(args.cache.relative_to(REPO_ROOT)),
        "min_cities": args.min_cities,
        "max_attempts_per_state": args.max_attempts,
        "failed_states": sorted(failed_states),
        "all_states_ok": len(failed_states) == 0,
        "rows": manifest_rows,
    }
    man_path = args.cache / "_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Wrote {}", man_path)
    if failed_states:
        logger.error("Failed states (after retries): {}", sorted(failed_states))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
