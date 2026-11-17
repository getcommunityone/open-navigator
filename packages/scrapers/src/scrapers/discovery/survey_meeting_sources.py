"""Survey where the governments around each US data center publish their meetings (#460).

For every US site in ``public.data_center_site`` this finds the town (from the
address) and the county, reads each government's website, and records every
meeting platform the site links to (YouTube, Granicus, Swagit, Legistar, CivicPlus
Agenda Center, ...), with the URL, the media it carries and the page it was on.

Bot protection is respected, never worked around. A site that answers 403/429 or
a challenge page is recorded as ``blocked`` and left alone. The only retry is the
VPN-aware one in :mod:`scrapers.discovery.scrape_http`, and only for ordinary
connection failures (DNS, timeouts, resets). A real browser is used only for pages
that loaded fine but build their links with JavaScript. For governments whose site
could not be read, the survey still checks what is public elsewhere: meeting
portals on the vendors' own hosts (``<slug>.legistar.com``, ``<slug>.iqm2.com``,
...) and, with ``--youtube-search N``, a capped YouTube Data API channel search.
Both only count a hit when the page or channel names the government and its state.

Usage::

    python -m scrapers.discovery.survey_meeting_sources --data-center-sites            # dry run
    python -m scrapers.discovery.survey_meeting_sources --data-center-sites --apply --youtube-search 40
    python -m scrapers.discovery.survey_meeting_sources --jurisdiction-id abilene_4801000

``--apply`` creates and upserts ``bronze.bronze_jurisdiction_meeting_source``. A
government with nothing found gets one row with ``platform='none'`` (and its
website as ``url``, or ``''``), so its website status is still on record. Every
run also writes a JSON and a CSV report to ``data/cache/data_center_survey/``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol, Sequence
from urllib.parse import urlsplit

import httpx
from loguru import logger

from scrapers.discovery.meeting_source_fingerprints import (
    VIDEO_PLATFORMS,
    MeetingSource,
    challenge_reason,
    classify_url,
    detect_meeting_sources,
    link_count,
    meeting_page_links,
    merge_sources,
)
from scrapers.discovery.scrape_http import (
    is_scrape_transport_or_vpn_failure,
    make_scrape_async_client,
)

TABLE = "bronze.bronze_jurisdiction_meeting_source"
NONE_PLATFORM = "none"
# Platforms the pipeline already reads (so "readers to build" leaves them out).
PLATFORMS_ALREADY_READ = frozenset({"youtube", "legistar", "suiteone"})

# One ordinary desktop browser user agent, sent the same way on every request.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAX_HTML_BYTES = 3_000_000
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
_STATE_BY_NAME = {name.lower(): code for code, name in STATE_NAMES.items()}

# Census place-name suffixes and the LSAD code for census-designated places.
_PLACE_SUFFIXES = (
    "charter township", "township", "city", "town", "village", "borough", "cdp",
    "municipality", "plantation", "consolidated government", "unified government",
)
CDP_LSAD = "57"
_WORD_EXPANSIONS = {"st": "saint", "ste": "sainte", "mt": "mount", "ft": "fort"}


def repo_root() -> Path:
    """The checkout this module lives in (the folder holding ``packages/`` and ``pyproject.toml``)."""
    try:
        from core_lib.paths import repo_root as core_repo_root  # added by #459

        return Path(core_repo_root())
    except ImportError:
        pass
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


# --------------------------------------------------------------------------------
# Address parsing and place matching
# --------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedAddress:
    place_text: str
    state_code: str
    zip_code: Optional[str]
    has_street: bool  # the place segment still carries a street (no comma before the city)


_TAIL_RE = re.compile(r"(?:,\s*|\s+)([A-Za-z]{2})(?:\s+(\d{5})(?:-\d{4})?)?\s*$")


def parse_address(address: Optional[str]) -> Optional[ParsedAddress]:
    """Split ``"..., City, ST 12345"`` into the city text, state and ZIP.

    Handles a trailing ``, USA``, full state names (``Ridgeland, Mississippi``) and a
    missing comma before the city (``5800 EDGEWOOD RD SW CEDAR RAPIDS, IA``), in
    which case ``place_text`` keeps the street words and ``has_street`` is True.
    """
    if not address:
        return None
    s = " ".join(address.replace("\n", " ").split())
    s = re.sub(r",?\s*(USA|U\.S\.A\.|United States)\.?$", "", s, flags=re.I).strip(" ,")
    state_code: Optional[str] = None
    zip_code: Optional[str] = None
    before = ""
    m = _TAIL_RE.search(s)
    if m and m.group(1).upper() in STATE_NAMES:
        state_code, zip_code = m.group(1).upper(), m.group(2)
        before = s[: m.start()]
    else:
        low = s.lower()
        tail_zip = re.search(r"\s+(\d{5})(?:-\d{4})?$", s)
        core = s[: tail_zip.start()] if tail_zip else s
        low = core.lower()
        for name in sorted(_STATE_BY_NAME, key=len, reverse=True):
            if low.endswith(name):
                state_code = _STATE_BY_NAME[name]
                zip_code = tail_zip.group(1) if tail_zip else None
                before = core[: len(core) - len(name)]
                break
    if not state_code:
        return None
    before = before.strip(" ,")
    if not before:
        return None
    segments = [seg.strip() for seg in before.split(",") if seg.strip()]
    place = segments[-1]
    has_street = len(segments) == 1 and bool(re.search(r"\d", place))
    return ParsedAddress(place_text=place, state_code=state_code, zip_code=zip_code, has_street=has_street)


def normalize_place_name(name: str) -> str:
    """Lowercase, expand St/Mt/Ft, drop punctuation and Census suffixes like ``city`` or ``village``."""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [_WORD_EXPANSIONS.get(w, w) for w in s.split()]
    s = " ".join(words)
    changed = True
    while changed:
        changed = False
        for suffix in _PLACE_SUFFIXES:
            if s.endswith(" " + suffix):
                s = s[: -len(suffix) - 1].strip()
                changed = True
    for prefix in ("city of ", "town of ", "village of ", "borough of "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def match_place(parsed: ParsedAddress, places: Sequence[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The municipality in ``places`` (one state's rows) that ``parsed.place_text`` names.

    Exact name first. When the segment still carries the street (no comma before the
    city), try its trailing words, longest first. Incorporated places win over
    census-designated places with the same name.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    for row in places:
        key = normalize_place_name(str(row.get("name") or ""))
        if key:
            index.setdefault(key, []).append(row)

    def pick(key: str) -> Optional[dict[str, Any]]:
        rows = index.get(key)
        if not rows:
            return None
        return sorted(rows, key=lambda r: (str(r.get("lsad") or "") == CDP_LSAD, str(r.get("geoid") or "")))[0]

    text = normalize_place_name(parsed.place_text)
    hit = pick(text)
    if hit or not parsed.has_street:
        return hit
    words = text.split()
    for start in range(1, len(words)):
        cand = " ".join(words[start:])
        if re.search(r"\d", cand):
            continue
        hit = pick(cand)
        if hit:
            return hit
    return None


# --------------------------------------------------------------------------------
# Warehouse access
# --------------------------------------------------------------------------------


class Warehouse(Protocol):
    def data_center_sites(self) -> list[dict[str, Any]]: ...
    def places(self, state_code: str) -> list[dict[str, Any]]: ...
    def county_for_place(self, geoid: str) -> Optional[dict[str, Any]]: ...
    def county_for_zip(self, zip_code: str) -> Optional[dict[str, Any]]: ...
    def jurisdiction(self, jurisdiction_id: str) -> Optional[dict[str, Any]]: ...
    def websites(self, jurisdiction_id: str) -> list[dict[str, Any]]: ...


def warehouse_dsn() -> str:
    """Local warehouse DSN (``SURVEY_DATABASE_URL`` overrides). Never a Neon URL by default."""
    explicit = (os.getenv("SURVEY_DATABASE_URL") or "").strip()
    if explicit:
        return explicit
    pwd = os.getenv("POSTGRES_PASSWORD") or "password"
    return f"postgresql://postgres:{pwd}@localhost:5433/open_navigator"


_JURISDICTION_COLS = "jurisdiction_id, geoid, name, jurisdiction_type, state_code, state, lsad"


class PgWarehouse:
    """Reads the local warehouse with psycopg2."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        import psycopg2
        import psycopg2.extras

        self._conn = psycopg2.connect(dsn or warehouse_dsn())
        self._conn.autocommit = True
        self._cursor_factory = psycopg2.extras.RealDictCursor
        self._places: dict[str, list[dict[str, Any]]] = {}

    def _all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._conn.cursor(cursor_factory=self._cursor_factory) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def _one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict[str, Any]]:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def data_center_sites(self) -> list[dict[str, Any]]:
        return self._all(
            "SELECT data_center_site_id, site_name, address, state_code, state "
            "FROM public.data_center_site WHERE state_code IS NOT NULL ORDER BY data_center_site_id"
        )

    def places(self, state_code: str) -> list[dict[str, Any]]:
        if state_code not in self._places:
            self._places[state_code] = self._all(
                f"SELECT {_JURISDICTION_COLS} FROM intermediate.int_jurisdictions "
                "WHERE state_code = %s AND jurisdiction_type = 'municipality'",
                (state_code,),
            )
        return self._places[state_code]

    def _county(self, county_fips: str) -> Optional[dict[str, Any]]:
        return self._one(
            f"SELECT {_JURISDICTION_COLS} FROM intermediate.int_jurisdictions "
            "WHERE jurisdiction_type = 'county' AND geoid = %s",
            (county_fips,),
        )

    def county_for_place(self, geoid: str) -> Optional[dict[str, Any]]:
        row = self._one(
            "SELECT county_fips FROM public.jurisdiction_county_crosswalk WHERE geoid = %s LIMIT 1", (geoid,)
        )
        return self._county(row["county_fips"]) if row and row.get("county_fips") else None

    def county_for_zip(self, zip_code: str) -> Optional[dict[str, Any]]:
        row = self._one(
            "SELECT county, bus_ratio FROM bronze.bronze_jurisdictions_zip_county "
            "WHERE zip = %s ORDER BY bus_ratio DESC NULLS LAST, tot_ratio DESC NULLS LAST LIMIT 1",
            (zip_code,),
        )
        if not row or row.get("bus_ratio") is None or float(row["bus_ratio"]) < 0.5:
            return None
        return self._county(str(row["county"]).strip())

    def jurisdiction(self, jurisdiction_id: str) -> Optional[dict[str, Any]]:
        return self._one(
            f"SELECT {_JURISDICTION_COLS} FROM intermediate.int_jurisdictions WHERE jurisdiction_id = %s LIMIT 1",
            (jurisdiction_id,),
        )

    def websites(self, jurisdiction_id: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT website_url, domain_name, website_source, agency FROM intermediate.int_jurisdiction_websites "
            "WHERE jurisdiction_id = %s AND website_url IS NOT NULL",
            (jurisdiction_id,),
        )
        for table in (
            "bronze.bronze_jurisdictions_municipalities_scraped",
            "bronze.bronze_jurisdictions_counties_scraped",
        ):
            rows += self._all(
                f"SELECT COALESCE(NULLIF(homepage_final_url, ''), homepage_url) AS website_url, "
                f"NULL AS domain_name, 'scraped' AS website_source, NULL AS agency FROM {table} "
                "WHERE jurisdiction_id = %s AND COALESCE(NULLIF(homepage_final_url, ''), homepage_url) IS NOT NULL",
                (jurisdiction_id,),
            )
        return rows

    def write_rows(self, rows: Sequence[dict[str, Any]]) -> int:
        """Create the bronze table if needed and upsert ``rows``."""
        import psycopg2.extras

        with self._conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    jurisdiction_id     text        NOT NULL,
                    geoid               text,
                    state_code          text,
                    jurisdiction_type   text,
                    platform            text        NOT NULL,
                    url                 text        NOT NULL,
                    media               text,
                    found_on            text,
                    website_status      text,
                    data_center_site_id text        NULL,
                    surveyed_at         timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT bronze_jurisdiction_meeting_source_pkey PRIMARY KEY (jurisdiction_id, platform, url),
                    CONSTRAINT bronze_jurisdiction_meeting_source_media_chk
                        CHECK (media IS NULL OR media IN ('video', 'documents', 'both'))
                )
                """
            )
            if not rows:
                return 0
            cols = [
                "jurisdiction_id", "geoid", "state_code", "jurisdiction_type", "platform", "url", "media",
                "found_on", "website_status", "data_center_site_id", "surveyed_at",
            ]
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES %s "
                "ON CONFLICT (jurisdiction_id, platform, url) DO UPDATE SET "
                + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("jurisdiction_id", "platform", "url")),
                [tuple(r[c] for c in cols) for r in rows],
            )
            # A government that now has sources no longer needs its "nothing found" row.
            with_sources = sorted({r["jurisdiction_id"] for r in rows if r["platform"] != NONE_PLATFORM})
            if with_sources:
                cur.execute(
                    f"DELETE FROM {TABLE} WHERE platform = %s AND jurisdiction_id = ANY(%s)",
                    (NONE_PLATFORM, with_sources),
                )
        return len(rows)

    def close(self) -> None:
        self._conn.close()


# --------------------------------------------------------------------------------
# Governments around the sites
# --------------------------------------------------------------------------------


@dataclass
class Government:
    jurisdiction_id: str
    geoid: Optional[str]
    name: str
    state_code: str
    state: str
    jurisdiction_type: str
    site_ids: list[str] = field(default_factory=list)


@dataclass
class SiteMatch:
    data_center_site_id: str
    site_name: Optional[str]
    address: Optional[str]
    state_code: str
    city_text: Optional[str]
    city_jurisdiction_id: Optional[str]
    city_status: str  # matched | cdp | unmatched | unparsed
    county_jurisdiction_id: Optional[str]
    county_match: str  # crosswalk | zip | unmatched


def _government(row: dict[str, Any]) -> Government:
    return Government(
        jurisdiction_id=str(row["jurisdiction_id"]),
        geoid=row.get("geoid"),
        name=str(row.get("name") or ""),
        state_code=str(row.get("state_code") or ""),
        state=str(row.get("state") or STATE_NAMES.get(str(row.get("state_code") or ""), "")),
        jurisdiction_type=str(row.get("jurisdiction_type") or ""),
    )


def resolve_site_governments(
    sites: Iterable[dict[str, Any]], wh: Warehouse
) -> tuple[list[Government], list[SiteMatch]]:
    """The city and county governments around each site, de-duplicated, plus one match record per site.

    A census-designated place has no municipal government, so only its county is
    surveyed. When the city can't be matched, the county comes from the address ZIP
    (HUD ZIP-county crosswalk, the county holding most of the ZIP's business addresses).
    """
    governments: dict[str, Government] = {}
    matches: list[SiteMatch] = []

    def add(row: dict[str, Any], site_id: str) -> str:
        gov = governments.setdefault(str(row["jurisdiction_id"]), _government(row))
        if site_id not in gov.site_ids:
            gov.site_ids.append(site_id)
        return gov.jurisdiction_id

    for site in sites:
        site_id = str(site["data_center_site_id"])
        state_code = str(site.get("state_code") or "").upper()
        parsed = parse_address(site.get("address"))
        if parsed and parsed.state_code != state_code:
            parsed = ParsedAddress(parsed.place_text, state_code, parsed.zip_code, parsed.has_street)
        city_id: Optional[str] = None
        county_id: Optional[str] = None
        county_match = "unmatched"
        city_status = "unparsed" if parsed is None else "unmatched"
        place = match_place(parsed, wh.places(state_code)) if parsed else None
        if place:
            city_status = "cdp" if str(place.get("lsad") or "") == CDP_LSAD else "matched"
            if city_status == "matched":
                city_id = add(place, site_id)
            county = wh.county_for_place(str(place["geoid"])) if place.get("geoid") else None
            if county:
                county_id, county_match = add(county, site_id), "crosswalk"
        if county_id is None and parsed and parsed.zip_code:
            county = wh.county_for_zip(parsed.zip_code)
            if county and str(county.get("state_code") or "") == state_code:
                county_id, county_match = add(county, site_id), "zip"
        matches.append(
            SiteMatch(
                data_center_site_id=site_id,
                site_name=site.get("site_name"),
                address=site.get("address"),
                state_code=state_code,
                city_text=parsed.place_text if parsed else None,
                city_jurisdiction_id=city_id,
                city_status=city_status,
                county_jurisdiction_id=county_id,
                county_match=county_match,
            )
        )
    return list(governments.values()), matches


_SOURCE_RANK = {"override": 0, "gsa": 1, "naco": 2, "uscm": 3, "league": 4, "scraped": 5, "wikidata": 6}
# Hosts of a department or side project rather than the government's main site.
_SIDE_SITE_RE = re.compile(
    r"(sheriff|911|court|attorney|probate|health|workforce|jobs|police|library|election|vote|"
    r"conversations|ready|tourism|visit|chamber|pd[a-z]{0,2}\.)",
    re.I,
)


def name_tokens(gov: Government) -> list[str]:
    """Strings a government's own domain usually contains (``racine``, ``sanantonio``, ``mtpleasant``)."""
    words = re.sub(r"[^a-z0-9 ]", "", _core_name(gov).lower()).split()
    if not words:
        return []
    tokens = {"".join(words)}
    short = {"mount": "mt", "saint": "st", "fort": "ft", "st": "saint", "mt": "mount", "ft": "fort"}
    if words[0] in short:
        tokens.add(short[words[0]] + "".join(words[1:]))
    return sorted(tokens)


def rank_websites(rows: Iterable[dict[str, Any]], gov: Government, limit: int = 3) -> list[str]:
    """Candidate homepages for ``gov``, best first.

    Order: curated overrides, hosts that carry the government's name, ``.gov``, source,
    shorter domains. Dropped: department side-sites (sheriff, 911, courts ...), GSA rows
    registered by a different agency, and Wikidata rows whose host doesn't carry the
    name (Wikidata county websites are sometimes another state's county).
    """
    tokens = name_tokens(gov)
    core = _core_name(gov).lower()
    best: dict[str, tuple[tuple[int, int, int, int, int], str]] = {}
    for row in rows:
        url = str(row.get("website_url") or "").strip()
        if not url:
            continue
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        host = (urlsplit(url).hostname or "").lower()
        if not host or "." not in host or _SIDE_SITE_RE.search(host):
            continue
        bare = host[4:] if host.startswith("www.") else host
        source = str(row.get("website_source") or "")
        named = any(t in bare.replace("-", "") for t in tokens)
        agency = str(row.get("agency") or "").lower()
        if source == "gsa" and agency and core not in agency:
            continue
        if source == "wikidata" and not named:
            continue
        key = (
            0 if source == "override" else 1,
            0 if named else 1,
            0 if bare.endswith(".gov") else 1,
            _SOURCE_RANK.get(source, 9),
            len(bare),
        )
        if bare not in best or key < best[bare][0]:
            best[bare] = (key, url)
    return [url for _, url in sorted(best.values())][:limit]


# --------------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------------


@dataclass
class Page:
    url: str
    final_url: str
    status_code: int
    html: str
    outcome: str  # ok | blocked | unreachable
    reason: Optional[str] = None


class Fetcher:
    """Polite page fetcher: bounded concurrency, timeouts, no bot-block evasion."""

    def __init__(self, concurrency: int = 4, timeout_s: float = 20.0, use_browser: bool = True) -> None:
        self._sem = asyncio.Semaphore(concurrency)
        self._timeout = timeout_s
        self._use_browser = use_browser
        self._client = make_scrape_async_client(
            timeout=timeout_s, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        )
        self._pw: Any = None
        self._browser: Any = None
        self._browser_lock = asyncio.Lock()
        self._browser_sem = asyncio.Semaphore(2)
        self._browser_broken = False

    async def _get(self, url: str) -> httpx.Response:
        try:
            return await self._client.get(url)
        except Exception as exc:
            if not is_scrape_transport_or_vpn_failure(exc=exc):
                raise
            # Ordinary connection failure: one retry outside the VPN/proxy. Never for an HTTP status.
            async with make_scrape_async_client(
                timeout=self._timeout, headers={"User-Agent": USER_AGENT}, direct_egress=True
            ) as direct:
                return await direct.get(url)

    async def fetch(self, url: str) -> Page:
        async with self._sem:
            try:
                resp = await self._get(url)
            except Exception as exc:  # noqa: BLE001 - every failure is an outcome to record
                return Page(url, url, 0, "", "unreachable", f"{type(exc).__name__}: {exc}"[:200])
        final_url = str(resp.url)
        ctype = resp.headers.get("content-type", "").lower()
        html = resp.text[:MAX_HTML_BYTES] if ("html" in ctype or not ctype) else ""
        reason = challenge_reason(html, resp.status_code)
        if reason:
            return Page(url, final_url, resp.status_code, "", "blocked", reason)
        if resp.status_code >= 400:
            return Page(url, final_url, resp.status_code, "", "unreachable", f"http_{resp.status_code}")
        page = Page(url, final_url, resp.status_code, html, "ok")
        if self._use_browser and html and "<script" in html.lower() and link_count(html) < 8:
            rendered = await self._render(final_url)
            if rendered and not challenge_reason(rendered, 200) and link_count(rendered) > link_count(html):
                page.html = rendered
                page.reason = "rendered_with_browser"
        return page

    async def _render(self, url: str) -> Optional[str]:
        """Render a page whose links are built by JavaScript. Not used for blocked pages."""
        if self._browser_broken:
            return None
        async with self._browser_lock:
            if self._browser is None:
                try:
                    from playwright.async_api import async_playwright

                    self._pw = await async_playwright().start()
                    self._browser = await self._pw.chromium.launch(headless=True)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Browser unavailable, JavaScript-built links will be missed: {}", exc)
                    self._browser_broken = True
                    return None
        async with self._browser_sem:
            context = await self._browser.new_context(user_agent=USER_AGENT)
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=int(self._timeout * 1000))
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:  # noqa: BLE001 - pages that never go idle still have their DOM
                    pass
                return (await page.content())[:MAX_HTML_BYTES]
            except Exception as exc:  # noqa: BLE001
                logger.debug("browser render failed url={} detail={}", url, exc)
                return None
            finally:
                await context.close()

    async def close(self) -> None:
        await self._client.aclose()
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()


# --------------------------------------------------------------------------------
# Name checks (vendor pages and YouTube channels)
# --------------------------------------------------------------------------------

_GOV_WORDS = "city|town|village|borough|township"
_NOT_GOVERNMENT_WORDS = re.compile(
    r"\b(school|schools|isd|usd|district|chamber|news|church|library|police|sheriff|fire|tourism|visit|"
    r"university|college|historical|museum|realtor|real estate|fan|fans|radio|tv news)\b",
    re.I,
)


def _core_name(gov: Government) -> str:
    name = gov.name.strip()
    if gov.jurisdiction_type == "county":
        name = re.sub(r"\s+(county|parish|borough|census area|municipality)$", "", name, flags=re.I)
    return name


def names_government(text: str, gov: Government) -> bool:
    """``text`` names this government the way an official page or channel would.

    Municipality: "City of X", "Town of X", "X City" ... County: "X County" / "X Parish".
    """
    core = re.escape(" ".join(_core_name(gov).lower().split()))
    low = " ".join(text.lower().split())
    if gov.jurisdiction_type == "county":
        return bool(re.search(rf"\b{core} (county|parish)\b", low))
    return bool(re.search(rf"\b({_GOV_WORDS}) of {core}\b", low) or re.search(rf"\b{core},? ({_GOV_WORDS})\b", low))


def names_state(text: str, gov: Government) -> bool:
    if gov.state and gov.state.lower() in text.lower():
        return True
    return bool(re.search(rf"(^|[\s,(]){re.escape(gov.state_code)}(\b|$)", text))


# --------------------------------------------------------------------------------
# Off-site checks: vendor URL patterns and YouTube search
# --------------------------------------------------------------------------------


def vendor_slugs(gov: Government) -> list[str]:
    base = re.sub(r"[^a-z0-9]", "", _core_name(gov).lower())
    st = gov.state_code.lower()
    if not base:
        return []
    if gov.jurisdiction_type == "county":
        return [f"{base}county{st}", f"{base}county", f"{base}co{st}"]
    return [f"{base}{st}", base, f"cityof{base}"]


def vendor_probe_urls(gov: Government) -> list[str]:
    """Portal URLs on the vendors' own hosts where this government's meetings would be."""
    st = gov.state_code.lower()
    urls: list[str] = []
    for slug in vendor_slugs(gov):
        urls += [
            f"https://{slug}.legistar.com/Calendar.aspx",
            f"https://{slug}.granicus.com/ViewPublisher.php?view_id=1",
            f"https://{slug}.iqm2.com/Citizens/Default.aspx",
            f"https://{slug}.primegov.com/public/portal",
            f"https://pub-{slug}.escribemeetings.com/",
            f"https://{slug}.suiteonemedia.com/",
            f"https://{slug}.new.swagit.com/views/",
            f"https://go.boarddocs.com/{st}/{slug}/Board.nsf/Public",
        ]
    base = re.sub(r"[^a-z0-9]", "", _core_name(gov).lower())
    if base:
        urls.append(f"https://{base}-{st}.municodemeetings.com/")
    return urls


def vendor_page_matches(html: str, probe_url: str, gov: Government) -> bool:
    """A vendor page is this government's when it names the government and its state.

    The state may also be carried by the slug itself (``abilenetx``).
    """
    text = re.sub(r"<[^>]+>", " ", html)
    if not names_government(text, gov):
        return False
    host = (urlsplit(probe_url).hostname or "").split(".")[0]
    return names_state(text, gov) or host.endswith(gov.state_code.lower())


async def probe_vendor_hosts(gov: Government, fetcher: Fetcher) -> list[MeetingSource]:
    found: list[MeetingSource] = []
    for url in vendor_probe_urls(gov):
        page = await fetcher.fetch(url)
        if page.outcome != "ok" or not page.html:
            continue
        hit = classify_url(page.final_url)  # a redirect to the vendor's own site is not a portal
        if hit and vendor_page_matches(page.html, url, gov):
            platform, canonical, media = hit
            found.append(MeetingSource(platform, canonical, media, "url_pattern"))
    return found


def youtube_query(gov: Government) -> str:
    if gov.jurisdiction_type == "county":
        return f"{gov.name} {gov.state}"
    return f"City of {gov.name} {gov.state}"


def accept_youtube_channel(title: str, description: str, gov: Government) -> bool:
    """Only a channel whose title names the government (and the state, in title or description)."""
    if _NOT_GOVERNMENT_WORDS.search(title):
        return False
    return names_government(title, gov) and (names_state(title, gov) or names_state(description, gov))


async def youtube_channel_search(gov: Government, api_key: str, client: httpx.AsyncClient) -> list[MeetingSource]:
    """One YouTube Data API search (100 quota units) for this government's official channel."""
    resp = await client.get(
        YOUTUBE_SEARCH_URL,
        params={"part": "snippet", "type": "channel", "maxResults": 10, "q": youtube_query(gov), "key": api_key},
    )
    if resp.status_code != 200:
        logger.warning("YouTube search failed for {}: HTTP {}", gov.jurisdiction_id, resp.status_code)
        return []
    out: list[MeetingSource] = []
    for item in resp.json().get("items", []):
        snippet = item.get("snippet") or {}
        channel_id = (item.get("id") or {}).get("channelId") or snippet.get("channelId")
        if channel_id and accept_youtube_channel(snippet.get("title", ""), snippet.get("description", ""), gov):
            out.append(MeetingSource("youtube", f"https://www.youtube.com/channel/{channel_id}", "video", "youtube_search"))
    return out[:1]


# --------------------------------------------------------------------------------
# Survey
# --------------------------------------------------------------------------------


@dataclass
class GovernmentResult:
    government: Government
    website_url: Optional[str]
    website_status: str  # ok | blocked | unreachable | missing
    website_reason: Optional[str]
    pages_read: int
    sources: list[MeetingSource]
    youtube_searched: bool = False


async def survey_government(gov: Government, websites: Sequence[str], fetcher: Fetcher, max_pages: int) -> GovernmentResult:
    if not websites:
        result = GovernmentResult(gov, None, "missing", None, 0, [])
    else:
        status, reason, home, used = "unreachable", None, None, websites[0]
        for url in websites:
            page = await fetcher.fetch(url)
            used = url
            if page.outcome == "ok":
                status, reason, home = "ok", page.reason, page
                break
            if page.outcome == "blocked":
                status, reason = "blocked", page.reason
                break  # respect the block; don't try the government's other addresses
            reason = page.reason
        sources: list[MeetingSource] = []
        pages_read = 0
        if home is not None:
            pages_read = 1
            sources += detect_meeting_sources(home.html, home.final_url)
            for link in meeting_page_links(home.html, home.final_url, home.final_url, limit=max_pages):
                await asyncio.sleep(0.3)
                sub = await fetcher.fetch(link)
                if sub.outcome == "ok" and sub.html:
                    pages_read += 1
                    sources += detect_meeting_sources(sub.html, sub.final_url)
        result = GovernmentResult(gov, used, status, reason, pages_read, sources)
    if result.website_status != "ok":
        result.sources += await probe_vendor_hosts(gov, fetcher)
    result.sources = merge_sources(result.sources)
    logger.info(
        "{} ({}): website {} — {} source(s)",
        gov.name, gov.state_code, result.website_status, len(result.sources),
    )
    return result


def youtube_search_order(results: Sequence[GovernmentResult]) -> list[GovernmentResult]:
    """Governments without a video source: nothing found first (blocked sites first), then documents-only."""
    status_rank = {"blocked": 0, "unreachable": 1, "missing": 2, "ok": 3}
    pending = [r for r in results if not any(s.platform in VIDEO_PLATFORMS for s in r.sources)]
    return sorted(pending, key=lambda r: (bool(r.sources), status_rank.get(r.website_status, 9), r.government.jurisdiction_id))


async def run_youtube_searches(results: Sequence[GovernmentResult], cap: int, api_key: Optional[str]) -> int:
    if cap <= 0:
        return 0
    if not api_key:
        logger.warning("--youtube-search set but YOUTUBE_API_KEY is missing; skipping")
        return 0
    used = 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        for result in youtube_search_order(results)[:cap]:
            used += 1
            result.youtube_searched = True
            try:
                result.sources = merge_sources(result.sources + await youtube_channel_search(result.government, api_key, client))
            except httpx.HTTPError as exc:
                logger.warning("YouTube search error for {}: {}", result.government.jurisdiction_id, exc)
    logger.success("Ran {} YouTube channel searches ({} quota units)", used, used * 100)
    return used


def bronze_rows(results: Sequence[GovernmentResult], surveyed_at: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in results:
        gov = r.government
        base = {
            "jurisdiction_id": gov.jurisdiction_id,
            "geoid": gov.geoid,
            "state_code": gov.state_code,
            "jurisdiction_type": gov.jurisdiction_type,
            "website_status": r.website_status,
            "data_center_site_id": sorted(gov.site_ids)[0] if gov.site_ids else None,
            "surveyed_at": surveyed_at,
        }
        if not r.sources:
            rows.append({**base, "platform": NONE_PLATFORM, "url": r.website_url or "", "media": None, "found_on": None})
        for s in r.sources:
            rows.append({**base, "platform": s.platform, "url": s.url, "media": s.media, "found_on": s.found_on})
    return rows


def summarize(results: Sequence[GovernmentResult], matches: Sequence[SiteMatch]) -> dict[str, Any]:
    per_platform: Counter[str] = Counter()
    for r in results:
        for platform in {s.platform for s in r.sources}:
            per_platform[platform] += 1
    nothing = [r for r in results if not r.sources]
    blocked = [r for r in results if r.website_status == "blocked"]
    return {
        "sites": len(matches),
        "sites_city_unmatched": [asdict(m) for m in matches if m.city_status in ("unmatched", "unparsed")],
        "sites_city_cdp": [asdict(m) for m in matches if m.city_status == "cdp"],
        "sites_county_unmatched": [asdict(m) for m in matches if m.county_match == "unmatched"],
        "sites_county_from_zip": [asdict(m) for m in matches if m.county_match == "zip"],
        "governments": len(results),
        "governments_by_type": dict(Counter(r.government.jurisdiction_type for r in results)),
        "website_status": dict(Counter(r.website_status for r in results)),
        "governments_per_platform": dict(per_platform.most_common()),
        "governments_with_video_source": sum(any(s.platform in VIDEO_PLATFORMS for s in r.sources) for r in results),
        "governments_with_no_source": [f"{r.government.name}, {r.government.state_code} ({r.website_status})" for r in nothing],
        "blocked": [
            f"{r.government.name}, {r.government.state_code}: {r.website_url} ({r.website_reason})" for r in blocked
        ],
        "youtube_searches": sum(r.youtube_searched for r in results),
        "readers_to_build": [p for p, _ in per_platform.most_common() if p not in PLATFORMS_ALREADY_READ],
    }


def write_report(results: Sequence[GovernmentResult], matches: Sequence[SiteMatch], summary: dict[str, Any],
                 rows: Sequence[dict[str, Any]], out_dir: Path, stamp: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"survey_{stamp}.json"
    csv_path = out_dir / f"survey_{stamp}.csv"
    payload = {
        "summary": summary,
        "sites": [asdict(m) for m in matches],
        "governments": [
            {
                **asdict(r.government),
                "website_url": r.website_url,
                "website_status": r.website_status,
                "website_reason": r.website_reason,
                "pages_read": r.pages_read,
                "youtube_searched": r.youtube_searched,
                "sources": [asdict(s) for s in r.sources],
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    with csv_path.open("w", newline="") as fh:
        cols = ["jurisdiction_id", "geoid", "state_code", "jurisdiction_type", "platform", "url", "media",
                "found_on", "website_status", "data_center_site_id", "surveyed_at"]
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def print_summary(results: Sequence[GovernmentResult], summary: dict[str, Any]) -> None:
    print(f"\n{'government':<34} {'st':<3} {'type':<13} {'website':<12} sources")
    for r in sorted(results, key=lambda x: (x.government.state_code, x.government.name)):
        plats = ", ".join(sorted({s.platform for s in r.sources})) or "-"
        print(f"{r.government.name[:33]:<34} {r.government.state_code:<3} {r.government.jurisdiction_type[:12]:<13} "
              f"{r.website_status:<12} {plats}")
    print(f"\nGovernments surveyed: {summary['governments']}  website status: {summary['website_status']}")
    print(f"Governments per platform: {summary['governments_per_platform']}")
    print(f"No source found: {len(summary['governments_with_no_source'])}  blocked: {len(summary['blocked'])}")


async def run(args: argparse.Namespace, wh: Warehouse) -> dict[str, Any]:
    matches: list[SiteMatch] = []
    if args.data_center_sites:
        governments, matches = resolve_site_governments(wh.data_center_sites(), wh)
    else:
        governments = []
    for jid in args.jurisdiction_id or []:
        row = wh.jurisdiction(jid)
        if row is None:
            logger.warning("Unknown jurisdiction_id {}", jid)
        elif all(g.jurisdiction_id != jid for g in governments):
            governments.append(_government(row))
    if args.limit:
        governments = governments[: args.limit]
    logger.info("Surveying {} governments", len(governments))

    fetcher = Fetcher(concurrency=args.concurrency, timeout_s=args.timeout, use_browser=not args.no_browser)
    gov_sem = asyncio.Semaphore(args.concurrency)

    async def one(gov: Government) -> GovernmentResult:
        async with gov_sem:
            return await survey_government(gov, rank_websites(wh.websites(gov.jurisdiction_id), gov), fetcher, args.max_pages)

    try:
        results = list(await asyncio.gather(*(one(g) for g in governments)))
    finally:
        await fetcher.close()
    await run_youtube_searches(results, args.youtube_search, os.getenv("YOUTUBE_API_KEY"))

    surveyed_at = datetime.now(timezone.utc)
    rows = bronze_rows(results, surveyed_at)
    summary = summarize(results, matches)
    print_summary(results, summary)
    out_dir = Path(args.report_dir) if args.report_dir else repo_root() / "data" / "cache" / "data_center_survey"
    json_path, csv_path = write_report(results, matches, summary, rows, out_dir, surveyed_at.strftime("%Y%m%dT%H%M%SZ"))
    logger.success("Report written: {} and {}", json_path, csv_path)
    if args.apply:
        written = wh.write_rows(rows)  # type: ignore[attr-defined]
        logger.success("Upserted {} rows into {}", written, TABLE)
    else:
        logger.info("Dry run: {} rows not written (use --apply)", len(rows))
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-center-sites", action="store_true", help="survey the governments around every US data center site")
    p.add_argument("--jurisdiction-id", action="append", help="survey this jurisdiction (repeatable)")
    p.add_argument("--youtube-search", type=int, default=0, metavar="N",
                   help="at most N YouTube Data API channel searches (100 units each; default 0)")
    p.add_argument("--apply", action="store_true", help=f"write {TABLE} (dry run by default)")
    p.add_argument("--max-pages", type=int, default=10, help="meeting-ish pages to read per site besides the homepage")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--timeout", type=float, default=20.0, help="seconds per request")
    p.add_argument("--no-browser", action="store_true", help="never render JavaScript-built pages in a browser")
    p.add_argument("--limit", type=int, default=0, help="survey only the first N governments")
    p.add_argument("--report-dir", help="report folder (default data/cache/data_center_survey under the repo root)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.data_center_sites and not args.jurisdiction_id:
        build_parser().error("give --data-center-sites or --jurisdiction-id")
    try:
        from dotenv import load_dotenv

        load_dotenv(repo_root() / ".env")
    except ImportError:
        pass
    wh = PgWarehouse()
    try:
        asyncio.run(run(args, wh))
    finally:
        wh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
