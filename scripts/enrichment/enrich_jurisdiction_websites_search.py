#!/usr/bin/env python3
"""
Suggest (or optionally append) ``jurisdiction_website_url_overrides`` rows when a jurisdiction's
meetings scrape was **missing**, **failed** (zero HTML pages), or **shallow** (few pages).

Supports **county**, **municipality** (cities / places), and **school_district** via
``--jurisdiction-type`` (cache layout matches ``comprehensive_discovery_pipeline_jurisdiction``:
``{STATE}/{type}/{type}_{geoid}/``).

Strategy (free tier, no paid APIs required for the core path):

1. Read targets from ``data/cache/scraped_meetings/{STATE}/{jurisdiction_type}/*/`` manifests, and/or
   ``missing``: no scrape folder — AL counties still use the static 67-FIPS list; other types/states
   use ``intermediate.int_jurisdictions`` GEOIDs minus folders on disk.
2. Load display names from Postgres ``intermediate.int_jurisdictions``.
3. ``ddgs`` metasearch (DuckDuckGo and other backends) for an official-site style query.
4. Rank ``.gov`` / ``.org`` hits with **host + title heuristics**: penalize census, courts, state
   revenue/tax portals, IRS/CDC, and other common false positives; boost local-looking hosts and
   titles that match the jurisdiction type (county / city / school).
5. For the top HEAD-reachable candidates, optionally **GET** a short HTML slice and add a **page
   score** (jurisdiction name + state, optional **ZIP** from ``int_jurisdictions``, simple US
   street-line patterns). The script picks the **best combined score**, not the first DDG hit.
6. Validate with ``httpx`` **HEAD** (fallback **GET** stream if HEAD is unsupported), optionally via
   ``WIKIDATA_HTTPS_PROXY`` (SOCKS5) when set — same knob as Wikidata loaders.
7. Optionally call **YouTube Data API v3** search when ``YOUTUBE_DATA_API_KEY`` is set (free quota)
   to capture a top meeting-ish video id/title for manual review context — not written to dbt.

Outputs a CSV under ``data/cache/enrichment/`` and optionally **appends** unique rows to
``dbt_project/seeds/jurisdiction_website_url_overrides.csv``. After append: run dbt seed + rebuild
``int_jurisdiction_websites`` (see repo dbt docs).

Examples::

    .venv/bin/python scripts/enrichment/enrich_jurisdiction_websites_search.py --state AL --dry-run

    # Cities (7-digit place GEOID) in Alabama — missing + failed + shallow from cache + DB
    .venv/bin/python scripts/enrichment/enrich_jurisdiction_websites_search.py \\
      --state AL --jurisdiction-type municipality --mode failed,missing,shallow --dry-run

    WIKIDATA_HTTPS_PROXY=socks5h://127.0.0.1:9091 \\
      .venv/bin/python scripts/enrichment/enrich_jurisdiction_websites_search.py \\
      --state AL --apply-seed --skip-existing-seed
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse, urlunparse

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from scripts.discovery.jurisdiction_discovery_pipeline import (
    jurisdiction_pk_from_geoid,
    resolve_database_url,
)

# Official AL county FIPS (01 + 3-digit county) — 67 counties.
_AL_COUNTY_3 = (
    "001,003,005,007,009,011,013,015,017,019,021,023,025,027,029,031,033,035,037,039,041,043,"
    "045,047,049,051,053,055,057,059,061,063,065,067,069,071,073,075,077,079,081,083,085,087,089,"
    "091,093,095,097,099,101,103,105,107,109,111,113,115,117,119,121,123,125,127,129,131,133"
).split(",")
AL_COUNTY_GEOIDS = [f"01{c}" for c in _AL_COUNTY_3]

# Matches ``ComprehensiveDiscoveryPipelineMeetings`` output dirs under ``{STATE}/{segment}/``.
_JTYPE_FOLDER_SEGMENT: Dict[str, str] = {
    "county": "county",
    "municipality": "municipality",
    "school_district": "school_district",
}

_JTYPE_ID_PREFIX: Dict[str, str] = {
    "county": "county",
    "municipality": "municipality",
    "school_district": "school_district",
}

_JTYPE_GEOID_WIDTH: Dict[str, int] = {
    "county": 5,
    "municipality": 7,
    "school_district": 7,
}


def _normalize_jurisdiction_type(raw: str) -> str:
    """Return ``county`` | ``municipality`` | ``school_district`` for CLI / SQL."""
    s = (raw or "").strip().lower()
    if s in ("county",):
        return "county"
    if s in ("municipality", "city", "place", "town", "village"):
        return "municipality"
    if s in ("school_district", "school", "sd"):
        return "school_district"
    raise ValueError(
        f"Unsupported --jurisdiction-type {raw!r}; use county, municipality, or school_district"
    )


def _id_prefix(jtype: str) -> str:
    return f"{_JTYPE_ID_PREFIX[_normalize_jurisdiction_type(jtype)]}_"


def _folder_segment(jtype: str) -> str:
    return _JTYPE_FOLDER_SEGMENT[_normalize_jurisdiction_type(jtype)]


def _geoid_digit_width(jtype: str) -> int:
    return _JTYPE_GEOID_WIDTH[_normalize_jurisdiction_type(jtype)]


def _canonical_geoid_str(geoid: str, jtype: str) -> str:
    g = (geoid or "").strip().replace("-", "")
    if not g.isdigit():
        return ""
    return g.zfill(_geoid_digit_width(jtype))


def _normalize_cli_geoid_token(token: str, jtype: str) -> Optional[str]:
    """Parse one ``--geoids`` CSV token into a padded GEOID string, or None if invalid."""
    t = (token or "").strip()
    if not t:
        return None
    c = _canonical_geoid_str(t, jtype)
    return c or None


_BLOCKLIST_HOST_FRAGMENTS = (
    "wikipedia.org",
    "wikimedia.org",
    "facebook.com",
    "fb.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "yelp.com",
    "google.com/maps",
    "bing.com/maps",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "pinterest.com",
    "reddit.com",
    "amazon.com",
)


def _load_dotenv() -> None:
    load_dotenv(_root / ".env", override=False)


def _slug_from_place_name(name: str, jtype: str) -> str:
    """Host-matching slug from ``int_jurisdictions.name`` (best-effort)."""
    base = (name or "").lower()
    for noise in (
        "county",
        "parish",
        "borough",
        "city of",
        "city",
        "town of",
        "town",
        "village",
        "school district",
        "public schools",
        "schools",
    ):
        base = base.replace(noise, " ")
    base = re.sub(r"[^a-z0-9]+", "", base.strip())
    return base[:32]


def _host_blocked(host: str) -> bool:
    h = (host or "").lower()
    return any(b in h for b in _BLOCKLIST_HOST_FRAGMENTS)


# (substring in host, penalty) — applied as sum of matches (capped per row).
_NEGATIVE_GOV_ORG_HOST: Tuple[Tuple[str, int], ...] = (
    ("census.gov", 120),
    ("data.census", 120),
    ("factfinder", 80),
    ("uscourts.gov", 120),
    (".uscourts.", 100),
    ("alacourt.gov", 120),
    ("pacer.gov", 100),
    ("irs.gov", 100),
    ("cdc.gov", 80),
    ("nih.gov", 60),
    ("usa.gov", 70),
    ("acf.hhs.gov", 70),
    ("cms.gov", 60),
    ("sam.gov", 60),
    ("grants.gov", 60),
    ("federalregister.gov", 70),
    ("justice.gov", 70),
    ("supremecourt", 90),
    ("revenue.", 95),
    ("dor.", 85),
    ("taxation.", 85),
    ("comptroller.", 70),
    ("treasurer.", 65),
    ("judicial.", 90),
    (".courts.", 85),
    ("courtinfo", 85),
    ("clerkofcourt", 85),
    ("probatecourt", 85),
    ("sos.state", 75),
    ("secretaryofstate", 75),
)

_NEGATIVE_RESULT_TITLE: Tuple[Tuple[str, int], ...] = (
    ("census bureau", 100),
    ("u.s. census", 100),
    ("american community survey", 80),
    ("department of revenue", 90),
    ("division of taxation", 90),
    ("tax commission", 85),
    ("internal revenue", 90),
    ("tax court", 95),
    ("supreme court", 70),
    ("circuit court", 75),
    ("district court", 75),
    ("probate court", 80),
    ("clerk of court", 80),
    ("public health", 55),
    ("department of public health", 65),
)


def _state_host_penalty(host: str, place_slug: str, state_usps: str) -> int:
    """Penalize bare state portal hosts when they lack a local slug (common wrong pick for counties)."""
    h = (host or "").lower().split(":")[-1]
    if not h.startswith("www."):
        h_norm = h
    else:
        h_norm = h[4:]
    st = (state_usps or "").strip().lower()
    if len(st) != 2:
        return 0
    bare = (f"{st}.gov", f"www.{st}.gov")
    # e.g. alabama.gov / www.alabama.gov
    long_names = {
        "al": "alabama.gov",
    }
    candidates = {bare[0], bare[1], f"{long_names.get(st, '')}"}
    candidates.discard("")
    if h_norm in candidates or h in candidates:
        if place_slug and place_slug in re.sub(r"[^a-z0-9]", "", h):
            return 0
        return 55
    return 0


def _ddg_title_and_body_score(title: str, body: str, jtype: str) -> int:
    """Light bonus when DDG title reads like the right level of government."""
    jt = _normalize_jurisdiction_type(jtype)
    t = f"{title or ''} {body or ''}".lower()
    score = 0
    if jt == "county":
        if "county" in t:
            score += 6
        if any(x in t for x in ("commission", "county government", "county office")):
            score += 5
    elif jt == "municipality":
        if any(x in t for x in ("city of", "town of", "municipal", "city government", "mayor")):
            score += 8
    elif jt == "school_district":
        if any(x in t for x in ("school district", "schools", "k-12", "board of education", "usd ", "isd ")):
            score += 10
    return score


def _score_ddg_row(
    row: Dict[str, Any],
    *,
    place_slug: str,
    display_name: str,
    jtype: str,
    state_usps: str,
) -> Optional[Tuple[str, int]]:
    """
    One DDG row → ``(href, score)`` or None if not a usable .gov/.org candidate.
    Higher score is better.
    """
    href = (row.get("href") or "").strip()
    if not href.startswith("http"):
        return None
    try:
        host = urlparse(href).netloc.lower()
    except ValueError:
        return None
    if _host_blocked(host):
        return None
    if not (host.endswith(".gov") or host.endswith(".org")):
        return None
    title = (row.get("title") or "").strip()
    body = (row.get("body") or "").strip()
    score = 0
    if host.endswith(".gov"):
        score += 5
    else:
        score += 3
    host_alnum = re.sub(r"[^a-z0-9]", "", host)
    if place_slug and place_slug in host_alnum:
        score += 14
    for frag, pen in _NEGATIVE_GOV_ORG_HOST:
        if frag in host:
            score -= pen
    tl = title.lower()
    for frag, pen in _NEGATIVE_RESULT_TITLE:
        if frag in tl:
            score -= pen
    blob = f"{title} {body}".lower()
    if "u.s. census" in blob or "census data" in blob or "american community survey" in blob:
        score -= 30
    score -= _state_host_penalty(host, place_slug, state_usps)
    score += _ddg_title_and_body_score(title, body, jtype)
    # Prefer hosts that echo the place name (beyond slug), e.g. "jefferson" in jeffersoncountyal.gov
    tokens = _page_match_tokens(display_name, jtype)
    for tok in tokens[:2]:
        if len(tok) >= 4 and tok in host_alnum:
            score += 6
    return (href, score)


def _rank_gov_org_candidates(
    results: Sequence[Dict[str, Any]],
    *,
    place_slug: str,
    display_name: str,
    jtype: str,
    state_usps: str,
    max_scan: int,
) -> List[Tuple[int, str, int]]:
    """``(ddg_index, href, ddg_score)`` sorted by ``ddg_score`` descending."""
    out: List[Tuple[int, str, int]] = []
    for i, row in enumerate(results[:max_scan]):
        scored = _score_ddg_row(
            row,
            place_slug=place_slug,
            display_name=display_name,
            jtype=jtype,
            state_usps=state_usps,
        )
        if not scored:
            continue
        href, sc = scored
        out.append((i, href, sc))
    out.sort(key=lambda t: -t[2])
    return out


def _page_match_tokens(display_name: str, jtype: str) -> List[str]:
    """Lowercase tokens from Census-style ``name`` for substring checks on-page."""
    jt = _normalize_jurisdiction_type(jtype)
    n = (display_name or "").lower()
    for noise in (
        " consolidated",
        " school district",
        " public schools",
        "public schools",
        " schools",
        "borough of ",
        "city of ",
        "town of ",
        "village of ",
        "county",
        " parish",
        " borough",
    ):
        n = n.replace(noise, " ")
    n = re.sub(r"[^a-z0-9\s]+", " ", n)
    parts = [p for p in n.split() if len(p) > 2]
    seen: Set[str] = set()
    out: List[str] = []
    for p in parts[:8]:
        if p not in seen:
            seen.add(p)
            out.append(p)
    if jt == "school_district" and display_name:
        raw = display_name.lower()
        for keep in ("cisd", "isd", "usd", "csd", "ssd", "rsu"):
            if keep in raw.replace(" ", ""):
                out.append(keep)
                break
    return out


def _visible_text_sample(html: str, *, max_chars: int = 220_000) -> str:
    try:
        soup = BeautifulSoup(html[: min(len(html), max_chars + 80_000)], "html.parser")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        t = soup.get_text(" ", strip=True)
        return " ".join(t.split()).lower()[:max_chars]
    except Exception:
        return ""


def _page_locality_score(
    html: str,
    *,
    display_name: str,
    jtype: str,
    state_usps: str,
    state_long: str,
    zip_code: Optional[str],
) -> int:
    """
    Heuristic match of homepage text to the jurisdiction (name, state, optional ZCTA zip).
    Not authoritative — used only to rank DDG candidates against each other.
    """
    jt = _normalize_jurisdiction_type(jtype)
    text = _visible_text_sample(html)
    if not text:
        return 0
    score = 0
    if "census bureau" in text or "u.s. census bureau" in text:
        score -= 45
    if "department of revenue" in text or "taxation division" in text:
        score -= 35
    tokens = _page_match_tokens(display_name, jtype)
    hit = 0
    for tok in tokens:
        if len(tok) > 2 and tok in text:
            hit += 1
            score += min(10, 4 + len(tok) // 4)
    if jt == "county" and "county" in text and hit > 0:
        score += 12
    if jt == "municipality" and hit > 0:
        if any(x in text for x in (" city", "municipal", "town of", "mayor", "council")):
            score += 10
    if jt == "school_district" and hit > 0:
        if any(x in text for x in ("school board", "board of education", "superintendent", "student", "k-12", "kindergarten")):
            score += 12
    st = (state_usps or "").strip().lower()
    if len(st) == 2:
        if re.search(rf"\b{re.escape(st)}\b", text):
            score += 5
    sl = (state_long or "").strip().lower()
    if len(sl) > 3 and sl in text:
        score += 4
    z = re.sub(r"\D", "", zip_code or "")[:5]
    if len(z) == 5:
        if z in re.sub(r"\D", "", text):
            score += 22
        elif z in text:
            score += 22
    if re.search(
        r"\b\d{2,5}\s+[a-z0-9.\s]{1,48}\s+(?:street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|lane|ln|way|circle|cir)\b",
        text,
    ):
        score += 7
    return score


def _get_homepage_html(
    url: str,
    *,
    proxy: Optional[str],
    timeout_s: float = 22.0,
) -> Tuple[int, str, str]:
    """``(status, final_url, html_or_empty)`` — html truncated client-side."""
    u = _canonical_https(url)
    if not u:
        return 0, "", ""
    headers = {
        "User-Agent": (
            "OpenNavigatorJurisdictionEnrichment/1.1 (+https://github.com/getcommunityone/open-navigator)"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(
            proxy=proxy,
            timeout=timeout_s,
            follow_redirects=True,
            headers=headers,
        ) as client:
            r = client.get(u)
            html = ""
            ct = (r.headers.get("content-type") or "").lower()
            if r.status_code == 200 and ("html" in ct or ct.startswith("text/") or not ct):
                html = (r.text or "")[:650_000]
            return r.status_code, str(r.url), html
    except httpx.RequestError:
        return 0, u, ""


def _canonical_https(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    if u.lower().startswith("http://"):
        p = urlparse(u)
        u = urlunparse(("https", p.netloc, p.path, p.params, p.query, p.fragment))
    return u.rstrip("/")


def _httpx_proxy() -> Optional[str]:
    return (os.getenv("WIKIDATA_HTTPS_PROXY") or os.getenv("ALL_PROXY") or "").strip() or None


def _validate_url(url: str, *, timeout_s: float = 20.0) -> Tuple[int, str, str]:
    """
    Return ``(status_or_0, final_url, detail)``. ``detail`` empty on success (2xx/3xx we treat as
    reachable for a government homepage — some sites 302 to CDN).
    """
    u = _canonical_https(url)
    if not u:
        return 0, "", "empty_url"
    headers = {
        "User-Agent": (
            "OpenNavigatorJurisdictionEnrichment/1.0 (+https://github.com/getcommunityone/open-navigator)"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    proxy = _httpx_proxy()
    try:
        with httpx.Client(
            proxy=proxy,
            timeout=timeout_s,
            follow_redirects=True,
            headers=headers,
        ) as client:
            r = client.head(u)
            if r.status_code in (405, 501):
                r = client.get(u)
            return r.status_code, str(r.url), ""
    except httpx.RequestError as exc:
        return 0, u, f"request_error:{type(exc).__name__}:{exc!r}"


def _extract_contact_hint(html: str, page_url: str) -> str:
    """Short text snippet: first mailto + stripped title (best-effort, not authoritative)."""
    try:
        soup = BeautifulSoup(html[:800_000], "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""
        mail = ""
        for a in soup.find_all("a", href=True):
            h = a.get("href") or ""
            if h.lower().startswith("mailto:"):
                mail = h.split(":", 1)[-1].split("?")[0][:120]
                break
        bits = [b for b in (title, mail) if b]
        return " | ".join(bits)[:500]
    except Exception as exc:
        return f"(parse_error:{type(exc).__name__})"


def _youtube_top_video(
    query: str,
    *,
    api_key: Optional[str],
    timeout_s: float = 15.0,
) -> Tuple[Optional[str], Optional[str], str]:
    if not api_key:
        return None, None, "no_api_key"
    try:
        from googleapiclient.discovery import build

        yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        req = yt.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=3,
        )
        res = req.execute()
        items = res.get("items") or []
        if not items:
            return None, None, "empty_results"
        vid = (items[0].get("id") or {}).get("videoId")
        sn = items[0].get("snippet") or {}
        title = (sn.get("title") or "").strip()
        return vid, title, ""
    except Exception as exc:
        return None, None, f"youtube_error:{type(exc).__name__}:{exc!r}"


def _manifest_paths(state: str, scraped_root: Path, jtype: str) -> List[Path]:
    jt = _normalize_jurisdiction_type(jtype)
    seg = _folder_segment(jt)
    pref = _id_prefix(jt)
    d = scraped_root / state.upper() / seg
    if not d.is_dir():
        return []
    return sorted(d.glob(f"{pref}*/_manifest.json"))


def _present_scrape_geoids(state: str, scraped_root: Path, jtype: str) -> Set[str]:
    """GEOID suffixes (zero-padded) that have a scrape folder under ``{STATE}/{segment}/``."""
    jt = _normalize_jurisdiction_type(jtype)
    seg = _folder_segment(jt)
    pref = _id_prefix(jt)
    out: Set[str] = set()
    if not scraped_root.is_dir():
        return out
    d = scraped_root / state.upper() / seg
    if not d.is_dir():
        return out
    for p in d.glob(f"{pref}*"):
        if p.is_dir():
            out.add(p.name[len(pref) :])
    return out


def _read_manifest_pages(path: Path) -> int:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return len(d.get("pages_fetched") or [])
    except Exception:
        return -1


def _load_missing_geoids_from_int_jurisdictions(
    state: str, jtype: str, present_dirs: Set[str]
) -> Set[str]:
    """GEOIDs in ``int_jurisdictions`` for this state/type with no scrape folder on disk."""
    jt = _normalize_jurisdiction_type(jtype)
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for missing-from-db mode")
    db = resolve_database_url()
    sql = """
        SELECT trim(geoid::text) AS geoid
        FROM intermediate.int_jurisdictions
        WHERE upper(trim(state_code)) = %s
          AND lower(trim(jurisdiction_type)) = %s
          AND geoid IS NOT NULL
    """
    out: Set[str] = set()
    with psycopg2.connect(db) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (state.upper(), jt))
            for row in cur.fetchall():
                raw = str(row[0] or "").strip()
                if not raw or not raw.replace("-", "").isdigit():
                    continue
                pad = _canonical_geoid_str(raw, jt)
                if pad and pad not in present_dirs:
                    out.add(pad)
    return out


def _collect_targets(
    *,
    state: str,
    scraped_root: Path,
    modes: Set[str],
    shallow_max_pages: int,
    extra_geoids: Sequence[str],
    jtype: str,
) -> List[str]:
    """Return padded GEOID strings to enrich for the given jurisdiction type."""
    jt = _normalize_jurisdiction_type(jtype)
    want: Set[str] = set()
    present_dirs = _present_scrape_geoids(state, scraped_root, jt)

    if "missing" in modes:
        if jt == "county" and state.upper() == "AL":
            for g in AL_COUNTY_GEOIDS:
                if g not in present_dirs:
                    want.add(g)
        else:
            want.update(_load_missing_geoids_from_int_jurisdictions(state, jt, present_dirs))

    pref = _id_prefix(jt)
    for mf in _manifest_paths(state, scraped_root, jt):
        geoid = mf.parent.name[len(pref) :]
        n = _read_manifest_pages(mf)
        if n < 0:
            continue
        if "failed" in modes and n == 0:
            want.add(geoid)
        if "shallow" in modes and 0 < n < shallow_max_pages:
            want.add(geoid)

    for tok in extra_geoids:
        ng = _normalize_cli_geoid_token(tok, jt)
        if ng:
            want.add(ng)

    def _sort_key(x: str) -> Tuple[int, int]:
        return (len(x), int(x)) if x.isdigit() else (len(x), 0)

    return sorted(want, key=_sort_key)


def _load_jurisdiction_names(
    geoids: Sequence[str], jtype: str
) -> Dict[str, Tuple[str, str, Optional[str]]]:
    """Canonical padded geoid -> (jurisdiction_id, display name, zip or None)."""
    jt = _normalize_jurisdiction_type(jtype)
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for --state DB name lookup")
    out: Dict[str, Tuple[str, str, Optional[str]]] = {}
    if not geoids:
        return out
    want = {_canonical_geoid_str(g, jt) for g in geoids}
    want.discard("")
    if not want:
        return out
    db = resolve_database_url()
    sql = """
        SELECT jurisdiction_id, name, trim(geoid::text) AS geoid_raw, NULLIF(trim(zip::text), '') AS zip
        FROM intermediate.int_jurisdictions
        WHERE upper(trim(state_code)) = %s
          AND lower(trim(jurisdiction_type)) = %s
    """
    with psycopg2.connect(db) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (state.upper(), jt))
            for jid, name, g_raw, zip_c in cur.fetchall():
                g = _canonical_geoid_str(str(g_raw or ""), jt)
                if not g or g not in want:
                    continue
                z = str(zip_c).strip() if zip_c is not None else ""
                out[g] = (str(jid), str(name or "").strip(), z or None)
    return out


def _existing_override_geoids(seed_path: Path, jtype: str) -> Set[str]:
    """Padded GEOIDs already present in the overrides seed for this ``jurisdiction_id`` prefix."""
    pref = _id_prefix(_normalize_jurisdiction_type(jtype))
    if not seed_path.is_file():
        return set()
    seen: Set[str] = set()
    rx = re.compile(rf"^{re.escape(pref)}(.+)$", re.I)
    with seed_path.open(newline="", encoding="utf-8") as fp:
        r = csv.DictReader(fp)
        for row in r:
            jid = (row.get("jurisdiction_id") or "").strip()
            m = rx.match(jid)
            if m:
                seen.add(m.group(1))
    return seen


def _ddg_and_youtube_queries(
    cname: str, state_long: str, state_usps: str, jtype: str
) -> Tuple[str, str]:
    jt = _normalize_jurisdiction_type(jtype)
    # Negative site clauses (best-effort) reduce census / federal / state tax portal noise in DDG.
    neg = "-site:census.gov -site:data.census.gov -site:cdc.gov -site:irs.gov -site:uscourts.gov"
    if jt == "county":
        return (
            f'"{cname}" {state_long} official county government website {neg}',
            f"{cname} county commission meeting {state_usps}",
        )
    if jt == "municipality":
        return (
            f'"{cname}" {state_long} official city government website {neg}',
            f"{cname} city council meeting {state_usps}",
        )
    return (
        f'"{cname}" {state_long} official school district website {neg}',
        f"{cname} school board meeting {state_usps}",
    )


@dataclass
class EnrichmentRow:
    jurisdiction_id: str
    geoid: str
    county_name: str
    state_code: str
    search_query: str
    chosen_url: str
    chosen_rank: str
    ddg_href: str
    ddg_title: str
    head_status: str
    head_final_url: str
    validation_detail: str
    relevance_scores: str
    contact_hint: str
    youtube_video_id: str
    youtube_title: str
    youtube_detail: str
    manual_review: str
    notes: str


def _run_ddg(query: str, *, max_results: int, proxy: Optional[str]) -> List[Dict[str, Any]]:
    from ddgs import DDGS

    kwargs: Dict[str, Any] = {"timeout": 25}
    if proxy:
        kwargs["proxy"] = proxy
    return list(DDGS(**kwargs).text(query, max_results=max_results))


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(
        description="Suggest jurisdiction website URLs (county / city / school district) via DDG + HEAD for dbt overrides.",
    )
    parser.add_argument(
        "--jurisdiction-type",
        default="county",
        metavar="TYPE",
        help="county | municipality (cities/places) | school_district — must match meetings scrape folders",
    )
    parser.add_argument("--state", default="AL", help="USPS state code (default AL)")
    parser.add_argument(
        "--scraped-root",
        type=Path,
        default=None,
        help="Root of scraped meetings cache (default: repo data/cache/scraped_meetings)",
    )
    parser.add_argument(
        "--mode",
        default="failed,missing,shallow",
        help=(
            "Comma list: failed (0 pages), shallow (1..N-1 pages), missing (no scrape folder: AL counties "
            "use static 67 FIPS; cities/schools use int_jurisdictions). --geoids is always merged."
        ),
    )
    parser.add_argument("--shallow-max-pages", type=int, default=5)
    parser.add_argument(
        "--geoids",
        default="",
        help="Comma-separated GEOIDs (padded width for type: county 5, place/school 7). Unioned into targets.",
    )
    parser.add_argument(
        "--apply-seed",
        action="store_true",
        help="Append validated rows (manual_review=false after locality scoring) to "
        "dbt_project/seeds/jurisdiction_website_url_overrides.csv (use --append-seed PATH for a different file)",
    )
    parser.add_argument("--max-ddg-results", type=int, default=12)
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds between DDG queries (politeness)")
    parser.add_argument("--output", type=Path, default=None, help="CSV output path")
    parser.add_argument(
        "--append-seed",
        type=Path,
        default=None,
        help="Append high-confidence rows (manual_review=false after locality scoring, HEAD ok) to this overrides CSV",
    )
    parser.add_argument("--skip-existing-seed", action="store_true", help="Skip GEOIDs already in overrides seed")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fetch-contact-hint", action="store_true", help="GET homepage and extract title/mailto")
    parser.add_argument(
        "--no-fetch-page-signals",
        action="store_true",
        help="Disable GET-based homepage scoring (faster; first DDG-ranked .gov/.org that passes HEAD wins).",
    )
    parser.add_argument(
        "--max-signal-fetches",
        type=int,
        default=5,
        metavar="N",
        help="Max HEAD-OK homepages to GET for locality scoring (name/state/ZIP/street heuristics; default 5).",
    )
    args = parser.parse_args()

    try:
        jt = _normalize_jurisdiction_type(args.jurisdiction_type)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    state = args.state.strip().upper()
    scraped_root = (
        args.scraped_root.expanduser()
        if args.scraped_root
        else _root / "data/cache/scraped_meetings"
    )
    modes = {m.strip().lower() for m in args.mode.split(",") if m.strip()}
    if "manual" in modes:
        modes.add("manual")
    extra_geoids = [x.strip() for x in args.geoids.split(",") if x.strip()]

    targets = _collect_targets(
        state=state,
        scraped_root=scraped_root,
        modes=modes,
        shallow_max_pages=max(2, args.shallow_max_pages),
        extra_geoids=extra_geoids,
        jtype=jt,
    )

    seed_default = _root / "dbt_project" / "seeds" / "jurisdiction_website_url_overrides.csv"
    seed_write: Optional[Path] = None
    if args.append_seed:
        seed_write = args.append_seed.expanduser()
    elif args.apply_seed:
        seed_write = seed_default
    existing_seed = (
        _existing_override_geoids(seed_write or seed_default, jt) if args.skip_existing_seed else set()
    )

    if not targets:
        logger.warning("No target jurisdictions after mode filter — nothing to do.")
        return

    names = _load_jurisdiction_names(targets, jt)
    proxy = _httpx_proxy()
    yt_key = (os.getenv("YOUTUBE_DATA_API_KEY") or "").strip()

    out_path = args.output
    if out_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = _root / "data/cache/enrichment"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"jurisdiction_website_enrichment_{state.lower()}_{jt}_{ts}.csv"

    shallow_cap = max(2, int(args.shallow_max_pages))
    total_targets = len(targets)
    named = sum(1 for g in targets if g in names)
    logger.info(
        "enrichment_start jurisdiction_type={} state={} modes={} shallow_lt_pages={} targets_total={} "
        "int_jurisdictions_named={} scraped_root={} dry_run={} apply_seed={} sleep_s={} proxy={} csv_out={}",
        jt,
        state,
        ",".join(sorted(modes)),
        shallow_cap,
        total_targets,
        named,
        scraped_root,
        args.dry_run,
        bool(args.apply_seed or args.append_seed),
        args.sleep,
        "set" if proxy else "none",
        out_path,
    )
    rows_out: List[EnrichmentRow] = []
    append_rows: List[Tuple[str, str]] = []

    for idx, geoid in enumerate(targets, start=1):
        if geoid in existing_seed:
            logger.info(
                "enrichment_progress {}/{} geoid={} action=skip_existing_seed",
                idx,
                total_targets,
                geoid,
            )
            continue
        meta = names.get(geoid)
        place_name = (meta or {}).get("name") if meta else None
        if not meta:
            rows_out.append(
                EnrichmentRow(
                    jurisdiction_id=jurisdiction_pk_from_geoid(geoid, jt, name=place_name)
                    or f"{_id_prefix(jt)}{geoid}",
                    geoid=geoid,
                    county_name="",
                    state_code=state,
                    search_query="",
                    chosen_url="",
                    chosen_rank="",
                    ddg_href="",
                    ddg_title="",
                    head_status="",
                    head_final_url="",
                    validation_detail="no_int_jurisdictions_row",
                    relevance_scores="",
                    contact_hint="",
                    youtube_video_id="",
                    youtube_title="",
                    youtube_detail="",
                    manual_review="true",
                    notes="Add row to int_jurisdictions or fix GEOID / --jurisdiction-type",
                )
            )
            logger.warning(
                "enrichment_progress {}/{} geoid={} action=no_int_jurisdictions_row",
                idx,
                total_targets,
                geoid,
            )
            continue

        jid, cname, zip_c = meta
        slug = _slug_from_place_name(cname, jt)
        state_long = "Alabama" if state == "AL" else state
        query, yt_query = _ddg_and_youtube_queries(cname, state_long, state, jt)
        fetch_page_signals = not args.no_fetch_page_signals
        max_sig = max(1, int(args.max_signal_fetches))

        manual = "true"
        notes: List[str] = []
        chosen = ""
        rank_s = ""
        dhref = ""
        dtitle = ""
        st_s = ""
        fin = ""
        val_detail = ""
        rel_scores = ""
        contact = ""
        yid = ""
        ytitle = ""
        ydetail = ""
        chosen_html = ""

        ddg_results: List[Dict[str, Any]] = []
        ranked: List[Tuple[int, str, int]] = []
        qdisp = (query[:140] + "...") if len(query) > 140 else query
        logger.info(
            "enrichment_progress {}/{} geoid={} step=ddg_search sleep_after_county_s={} query={}",
            idx,
            total_targets,
            geoid,
            args.sleep,
            qdisp,
        )
        try:
            ddg_results = _run_ddg(query, max_results=args.max_ddg_results, proxy=proxy)
        except Exception as exc:
            val_detail = f"ddg_error:{type(exc).__name__}:{exc!r}"
            notes.append("duckduckgo_failed")
        else:
            ranked = _rank_gov_org_candidates(
                ddg_results,
                place_slug=slug,
                display_name=cname,
                jtype=jt,
                state_usps=state,
                max_scan=args.max_ddg_results,
            )
            if not ranked:
                notes.append("no_gov_org_in_results")
            else:
                validated: List[Tuple[int, str, int, int, str, str]] = []
                last_vd = ""
                for rnk, href, ddg_sc in ranked:
                    if len(validated) >= max_sig:
                        break
                    st, fin_u, vd = _validate_url(href)
                    last_vd = vd
                    if 200 <= st < 400:
                        validated.append((rnk, href, ddg_sc, st, fin_u, vd))

                if not validated:
                    val_detail = last_vd or "no_reachable_candidate"
                    notes.append("no_head_ok_candidate")
                elif fetch_page_signals:
                    best: Optional[Tuple[int, int, int, str, str, str, str, str]] = None
                    # combined, ddg_sc, page_sc, rnk, href, fin, vd, canonical
                    for rnk, href, ddg_sc, st, fin_u, vd in validated:
                        canon = _canonical_https(fin_u or href)
                        gst, _gfin, html = _get_homepage_html(canon, proxy=proxy)
                        page_sc = 0
                        if gst == 200 and html:
                            page_sc = _page_locality_score(
                                html,
                                display_name=cname,
                                jtype=jt,
                                state_usps=state,
                                state_long=state_long,
                                zip_code=zip_c,
                            )
                        comb = ddg_sc + page_sc
                        if best is None or comb > best[0]:
                            best = (comb, ddg_sc, page_sc, str(rnk), href, fin_u, vd, canon)
                            if gst == 200 and html:
                                chosen_html = html
                            else:
                                chosen_html = ""
                    assert best is not None
                    comb, ddg_sc, page_sc, rank_s, href, fin_u, vd, canon = best
                    dhref = href
                    fin = fin_u or ""
                    val_detail = vd
                    st_s = "200"
                    chosen = canon
                    rel_scores = f"ddg={ddg_sc} page={page_sc} combined={comb}"
                    for row in ddg_results:
                        if (row.get("href") or "").strip() == href:
                            dtitle = (row.get("title") or "")[:300]
                            break
                    if page_sc < 5 and ddg_sc < 18:
                        manual = "true"
                        notes.append("weak_local_signals")
                    else:
                        manual = "false"
                else:
                    rnk, href, ddg_sc, st, fin_u, vd = validated[0]
                    dhref = href
                    fin = fin_u or ""
                    val_detail = vd
                    st_s = str(st)
                    chosen = _canonical_https(fin_u or href)
                    rank_s = str(rnk)
                    rel_scores = f"ddg={ddg_sc} page=skipped combined={ddg_sc}"
                    manual = "false"
                    for row in ddg_results:
                        if (row.get("href") or "").strip() == href:
                            dtitle = (row.get("title") or "")[:300]
                            break

        if chosen and args.fetch_contact_hint:
            try:
                if chosen_html:
                    contact = _extract_contact_hint(chosen_html, chosen)
                else:
                    with httpx.Client(
                        proxy=proxy,
                        timeout=30.0,
                        follow_redirects=True,
                        headers={
                            "User-Agent": (
                                "OpenNavigatorJurisdictionEnrichment/1.1 "
                                "(+https://github.com/getcommunityone/open-navigator)"
                            ),
                        },
                    ) as c:
                        r = c.get(chosen)
                        if r.status_code == 200 and "text/html" in (r.headers.get("content-type") or "").lower():
                            contact = _extract_contact_hint(r.text, chosen)
            except Exception as exc:
                contact = f"(get_error:{type(exc).__name__})"

        yid, ytitle, ydetail = _youtube_top_video(yt_query, api_key=yt_key or None)

        if manual == "true" and not notes:
            notes.append("needs_manual_pick")

        n_ddg = len(ddg_results)
        n_ranked = len(ranked)
        chosen_disp = (chosen[:120] + "...") if len(chosen) > 120 else (chosen or "(none)")
        val_disp = (val_detail[:160] + "...") if len(val_detail) > 160 else (val_detail or "-")
        logger.info(
            "enrichment_progress {}/{} geoid={} county={} ddg_raw_hits={} gov_org_ranked={} "
            "chosen={} head_http={} manual_review={} val_detail={} notes={}",
            idx,
            total_targets,
            geoid,
            (cname or "")[:60],
            n_ddg,
            n_ranked,
            chosen_disp,
            st_s or "-",
            manual,
            val_disp,
            ";".join(notes) if notes else "-",
        )

        rows_out.append(
            EnrichmentRow(
                jurisdiction_id=jid,
                geoid=geoid,
                county_name=cname,
                state_code=state,
                search_query=query,
                chosen_url=chosen,
                chosen_rank=rank_s,
                ddg_href=dhref,
                ddg_title=dtitle,
                head_status=st_s,
                head_final_url=fin,
                validation_detail=val_detail,
                relevance_scores=rel_scores,
                contact_hint=contact,
                youtube_video_id=yid or "",
                youtube_title=ytitle or "",
                youtube_detail=ydetail,
                manual_review=manual,
                notes=";".join(notes),
            )
        )

        if seed_write and manual == "false" and chosen and not args.dry_run:
            append_rows.append((jid, chosen))

        time.sleep(max(0.0, float(args.sleep)))

    fieldnames = [f.name for f in fields(EnrichmentRow)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        for row in rows_out:
            w.writerow(row.__dict__)

    n_auto = sum(1 for r in rows_out if (r.manual_review or "").strip().lower() == "false")
    n_manual = len(rows_out) - n_auto
    logger.success("Wrote {} suggestion rows → {}", len(rows_out), out_path)
    logger.info(
        "enrichment_summary rows_written={} high_confidence_manual_review_false={} needs_manual_or_review_true={} "
        "would_append_seed_rows={} dry_run={}",
        len(rows_out),
        n_auto,
        n_manual,
        len(append_rows),
        args.dry_run,
    )

    if append_rows and seed_write and not args.dry_run:
        with seed_write.open("a", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            for jid, url in append_rows:
                w.writerow([jid, url])
        logger.success("Appended {} rows → {}", len(append_rows), seed_write)
        logger.info(
            "Next: cd dbt_project && dbt seed --select jurisdiction_website_url_overrides && "
            "dbt run --select int_jurisdiction_websites",
        )


if __name__ == "__main__":
    main()
