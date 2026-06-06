#!/usr/bin/env python3
"""Scrape municipal city-council rosters into a normalized member list.

The downstream loader (:mod:`ingestion.municipal.load_council_officials`) turns
these :class:`CouncilMember` rows into ``bronze.bronze_officials_scraped``, which
a dbt staging model (``stg_scraped__official``) unions into
``public.contact_official`` alongside the OpenStates officials. That fills the
gap where OpenStates carries a city's mayor but not its council members (e.g.
Tuscaloosa: only Mayor Maddox was present; the 7 districts were missing).

Two data paths, same output shape:

* **Curated** (default, network-free): a checked-in roster per city in
  :data:`CURATED_ROSTERS`. Reliable and immediately correct — used so the
  pipeline works without depending on a city site's HTML staying stable.
* **Live** (``get_council(slug, live=True)``): fetch + best-effort parse the
  city's council page. Selectors are heuristic; VERIFY against the live page and
  prefer refreshing the curated roster from the parsed result.

CLI::

    python -m scrapers.municipal.council_roster --city tuscaloosa            # curated
    python -m scrapers.municipal.council_roster --city tuscaloosa --live     # scrape
    python -m scrapers.municipal.council_roster --city tuscaloosa --json out.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

from loguru import logger

DEFAULT_USER_AGENT = "OpenNavigator-MunicipalScraper/1.0 (civic-research)"


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CouncilMember:
    """One current municipal official, normalized for ``contact_official``."""

    full_name: str
    title: str  # e.g. "City Councilor", "Mayor"
    jurisdiction: str  # MUST match the city's officials, e.g. "Tuscaloosa Government"
    state_code: str  # 2-letter USPS
    state: str  # full name
    district: Optional[str] = None  # e.g. "District 1"
    office: str = "government"  # mirrors OpenStates org classification
    email: Optional[str] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MunicipalCouncilConfig:
    """Where + how to scrape a city's council roster."""

    slug: str
    url: str
    jurisdiction: str
    state_code: str
    state: str
    # Title applied to scraped council members (mayor is handled separately /
    # already in OpenStates, so curated rosters here are council-only).
    member_title: str = "City Councilor"


# ---------------------------------------------------------------------------
# City configs
# ---------------------------------------------------------------------------
CONFIGS: dict[str, MunicipalCouncilConfig] = {
    "tuscaloosa": MunicipalCouncilConfig(
        slug="tuscaloosa",
        url="https://www.tuscaloosa.com/citycouncil",
        # Must equal the jurisdiction string already used for Tuscaloosa officials
        # so the API's city filter (jurisdiction ILIKE '%Tuscaloosa%' AND NOT
        # '%county%') returns these rows for ?city=Tuscaloosa.
        jurisdiction="Tuscaloosa Government",
        state_code="AL",
        state="Alabama",
    ),
    "boston": MunicipalCouncilConfig(
        slug="boston",
        url="https://www.boston.gov/departments/city-council",
        # Equals the jurisdiction string already on Boston's OpenStates official
        # (Mayor Michelle Wu) so ?city=Boston returns these council members too.
        jurisdiction="Boston Government",
        state_code="MA",
        state="Massachusetts",
    ),
}


# Curated, checked-in rosters (council members only — the mayor is already in
# OpenStates/contact_official, so adding one here would duplicate). Refresh these
# from a verified live scrape; they are the reliable default.
CURATED_ROSTERS: dict[str, list[CouncilMember]] = {
    "tuscaloosa": [
        CouncilMember("Joseph Eatmon, Sr.", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 1"),
        CouncilMember("Raevan Howard", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 2"),
        CouncilMember("Richard Henry", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 3"),
        CouncilMember("Lee Busby", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 4"),
        CouncilMember("Kip Tyner", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 5"),
        CouncilMember("John Faile", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 6"),
        CouncilMember("Cassius Lanier", "City Councilor", "Tuscaloosa Government", "AL", "Alabama", "District 7"),
    ],
    # Boston City Council: 4 at-large + 9 district seats (no mayor — Michelle Wu
    # is already in OpenStates/contact_official). District 9's holder also chairs
    # the body, so her title carries the "City Council President" role.
    # Source: https://www.boston.gov/departments/city-council
    "boston": [
        CouncilMember("Liz Breadon", "City Council President", "Boston Government", "MA", "Massachusetts", "District 9"),
        CouncilMember("Ruthzee Louijeune", "City Councilor", "Boston Government", "MA", "Massachusetts", "At-Large"),
        CouncilMember("Julia M. Mejia", "City Councilor", "Boston Government", "MA", "Massachusetts", "At-Large"),
        CouncilMember("Erin J. Murphy", "City Councilor", "Boston Government", "MA", "Massachusetts", "At-Large"),
        CouncilMember("Henry Santana", "City Councilor", "Boston Government", "MA", "Massachusetts", "At-Large"),
        CouncilMember("Gabriela Coletta Zapata", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 1"),
        CouncilMember("Edward M. Flynn", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 2"),
        CouncilMember("John FitzGerald", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 3"),
        CouncilMember("Brian Worrell", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 4"),
        CouncilMember("Enrique J. Pepén", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 5"),
        CouncilMember("Benjamin J. Weber", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 6"),
        CouncilMember("Miniard Culpepper", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 7"),
        CouncilMember("Sharon Durkan", "City Councilor", "Boston Government", "MA", "Massachusetts", "District 8"),
    ],
}


# ---------------------------------------------------------------------------
# Live scrape (best-effort)
# ---------------------------------------------------------------------------
def fetch_html(url: str, *, timeout: int = 20) -> str:
    """GET a page as text with an identifiable UA. Requires network."""
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted civic URL)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


class _TextHarvester(HTMLParser):
    """Collect visible text chunks + member headshots; skip script/style.

    Also records ``(alt, src)`` for every ``<img>`` so the parser can pair a
    member with their headshot — city sites label these ``alt="<Name> headshot"``.
    """

    _SKIP = {"script", "style", "noscript", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []
        self.images: list[tuple[str, str, str]] = []  # (alt, src, title)

    def handle_starttag(self, tag, attrs):  # noqa: D102
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "img":
            a = dict(attrs)
            src = (a.get("src") or "").strip()
            alt = (a.get("alt") or "").strip()
            title = (a.get("title") or "").strip()
            if src and (alt or title):
                self.images.append((alt, src, title))

    def handle_endtag(self, tag):  # noqa: D102
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):  # noqa: D102
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.chunks.append(text)


def _name_key(name: str) -> str:
    """Normalized key for matching a member name to their headshot alt text."""
    return re.sub(r"\s+", " ", name or "").strip().lower()


def _headshots_by_name(harv: _TextHarvester, base_url: str) -> dict[str, str]:
    """Map normalized member name -> absolute headshot URL from img alt/src.

    City sites label member photos ``alt="<Name> headshot"``; strip that suffix
    to recover the name and resolve the (often relative) src against the page URL.
    """
    out: dict[str, str] = {}
    for alt, src, _title in harv.images:
        name = re.sub(r"\s+headshot$", "", alt, flags=re.IGNORECASE).strip()
        key = _name_key(name)
        if key and key not in out:
            out[key] = urljoin(base_url, src)
    return out


# Mayors / executives whose photo isn't on the council page and whom OpenStates
# carries with no image. Their headshots live on a department page; scraping it
# lets us overlay a photo onto the existing contact_official row (matched by
# name, so we never duplicate the OpenStates official).
OFFICIAL_PHOTO_SOURCES: dict[str, list[str]] = {
    "boston": ["https://www.boston.gov/departments/mayors-office"],
}

# alt text like "A headshot of Mayor Michelle Wu smiling." -> the bare name.
_HEADSHOT_OF_RE = re.compile(
    r"headshot of\s+(?:mayor|councilor|councill?or|councilman|councilwoman|"
    r"commissioner|chief|president|director)?\s*(.+?)(?:\s+smiling)?\.?$",
    re.IGNORECASE,
)


def scrape_official_photos(url: str) -> dict[str, str]:
    """Scrape ``name -> absolute headshot URL`` from an arbitrary department page.

    Handles the two headshot labellings city sites use: ``alt="<Name> headshot"``
    and ``alt="A headshot of <Title> <Name> ..." title="<Name>"`` (the mayor's
    office page). Prefers the clean ``title`` attribute for the name.
    """
    harv = _TextHarvester()
    harv.feed(fetch_html(url))
    out: dict[str, str] = {}
    for alt, src, title in harv.images:
        if "headshot" not in alt.lower() and "headshot" not in title.lower():
            continue
        name = ""
        if title and "headshot" in alt.lower():
            name = title.strip()
        if not name:
            m = _HEADSHOT_OF_RE.search(alt)
            if m:
                name = m.group(1)
            else:
                name = re.sub(r"\s*headshot.*$", "", alt, flags=re.IGNORECASE)
        key = _name_key(name)
        if key and key not in out:
            out[key] = urljoin(url, src)
    return out


_DISTRICT_RE = re.compile(r"\bDistrict\s+(\d+)\b", re.IGNORECASE)
_ATLARGE_RE = re.compile(r"\bAt[-\s]?Large\b", re.IGNORECASE)
# A "role" line that identifies a council seat: "City Councilor, At-Large",
# "City Council President; City Councilor, District 9", "City Council Member".
_ROLE_RE = re.compile(r"\bCity\s+Council(?:\s*(?:or|man|woman|member|President))?\b", re.IGNORECASE)
_PRESIDENT_RE = re.compile(r"\bCouncil\s+President\b", re.IGNORECASE)
# A name line: "Councilor Joseph Eatmon, Sr." / "Councilman Lee Busby" etc.
_NAME_RE = re.compile(
    r"^(?:Councilor|Councilman|Councilwoman|Council\s*Member)\s+(.+)$",
    re.IGNORECASE,
)


def _looks_like_name(chunk: str) -> bool:
    """Heuristic: a short, capitalized line that isn't itself a role/district label."""
    text = re.sub(r"\s+headshot$", "", chunk, flags=re.IGNORECASE).strip()
    if not text or len(text) > 60:
        return False
    if _ROLE_RE.search(text) or _DISTRICT_RE.search(text) or _ATLARGE_RE.search(text):
        return False
    if not (1 <= len(text.split()) <= 6):
        return False
    return bool(re.match(r"[A-ZÀ-Þ]", text))


def _make_member(
    name: str,
    district: Optional[str],
    title: str,
    config: MunicipalCouncilConfig,
    photos: Optional[dict[str, str]] = None,
) -> CouncilMember:
    full_name = re.sub(r"\s+", " ", name).strip()
    photo_url = (photos or {}).get(_name_key(full_name))
    return CouncilMember(
        full_name=full_name,
        title=title,
        jurisdiction=config.jurisdiction,
        state_code=config.state_code,
        state=config.state,
        district=district,
        photo_url=photo_url,
    )


def parse_council_html(html: str, config: MunicipalCouncilConfig) -> list[CouncilMember]:
    """Best-effort parse of a council page into members.

    Handles two common layouts, both keying off the seat label so we never emit a
    member without a confirmed council role:

    * **Prefixed name** (Tuscaloosa): a "Councilor <Name>" line followed by a
      "District N" line.
    * **Name-then-role** (Boston): a bare "<Name>" line followed by a
      "City Councilor, At-Large" / "City Councilor, District N" role line.

    City sites vary wildly — treat a low/zero yield as "verify selectors" and fall
    back to the curated roster, not as an authoritative empty result.
    """
    harv = _TextHarvester()
    harv.feed(html)
    chunks = harv.chunks
    photos = _headshots_by_name(harv, config.url)

    members: list[CouncilMember] = []
    pending_name: Optional[str] = None
    for chunk in chunks:
        nm = _NAME_RE.match(chunk)
        if nm:
            pending_name = re.sub(r"\s+", " ", nm.group(1)).strip()
            continue

        # A role line resolves the most-recent candidate name into a member
        # (Boston layout, and also covers Tuscaloosa rows whose label happens to
        # carry the "City Council" prefix).
        if _ROLE_RE.search(chunk) and pending_name:
            dm = _DISTRICT_RE.search(chunk)
            if dm:
                district: Optional[str] = f"District {dm.group(1)}"
            elif _ATLARGE_RE.search(chunk):
                district = "At-Large"
            else:
                district = None
            title = "City Council President" if _PRESIDENT_RE.search(chunk) else config.member_title
            members.append(_make_member(pending_name, district, title, config, photos))
            pending_name = None
            continue

        # A bare "District N" line resolves a prefixed-name candidate (Tuscaloosa).
        dm = _DISTRICT_RE.search(chunk)
        if dm and pending_name:
            members.append(_make_member(pending_name, f"District {dm.group(1)}", config.member_title, config, photos))
            pending_name = None
            continue

        # Otherwise, remember this line as a possible name for the next role line.
        if _looks_like_name(chunk):
            pending_name = re.sub(r"\s+headshot$", "", chunk, flags=re.IGNORECASE).strip()
    return members


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def _overlay_live_photos(members: list[CouncilMember], config: MunicipalCouncilConfig) -> list[CouncilMember]:
    """Attach live headshot URLs to a curated roster, matched by name.

    Keeps the curated names/districts/titles authoritative (the raw parse is too
    noisy to trust for membership) while filling the one thing the curated roster
    can't carry offline: a current headshot URL. Network failure -> unchanged.
    """
    try:
        harv = _TextHarvester()
        harv.feed(fetch_html(config.url))
        photos = _headshots_by_name(harv, config.url)
    except Exception as exc:
        logger.warning("headshot enrichment for {} failed ({}); keeping curated photos", config.slug, exc)
        return members

    enriched: list[CouncilMember] = []
    filled = 0
    for m in members:
        url = photos.get(_name_key(m.full_name))
        if url and not m.photo_url:
            enriched.append(dataclasses.replace(m, photo_url=url))
            filled += 1
        else:
            enriched.append(m)
    logger.success("attached {}/{} headshots for {} from {}", filled, len(members), config.slug, config.url)
    return enriched


def get_council(
    slug: str,
    *,
    live: bool = False,
    json_path: Optional[str] = None,
) -> list[CouncilMember]:
    """Return council members for a city.

    Precedence: explicit ``json_path`` > curated roster (enriched with live
    headshots when ``live``) > best-effort live parse for cities with no curated
    roster.

    With ``live=True`` and a curated roster present, the curated names/districts
    are authoritative and only the headshot URLs are pulled live (the raw page
    parse is too noisy to trust for membership). Cities with no curated roster
    fall back to the best-effort parse.
    """
    slug = slug.lower().strip()

    if json_path:
        with open(json_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return [CouncilMember(**r) for r in raw]

    curated = CURATED_ROSTERS.get(slug)

    if live:
        cfg = CONFIGS.get(slug)
        if not cfg:
            raise ValueError(f"no scrape config for city {slug!r}")
        if curated is not None:
            return _overlay_live_photos(list(curated), cfg)
        # No curated roster: best-effort parse of the live page.
        try:
            parsed = parse_council_html(fetch_html(cfg.url), cfg)
        except Exception as exc:
            logger.warning("live scrape of {} failed ({})", slug, exc)
            parsed = []
        if parsed:
            logger.success("scraped {} council members from {}", len(parsed), cfg.url)
            return parsed
        logger.warning("live parse yielded 0 members and no curated roster exists for {}", slug)

    if curated is None:
        raise ValueError(f"no curated roster for city {slug!r}")
    return list(curated)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="tuscaloosa", help="City slug (default: tuscaloosa)")
    p.add_argument("--live", action="store_true", help="Scrape the live page instead of the curated roster")
    p.add_argument("--json", dest="json_out", default=None, help="Write the roster to this JSON file")
    args = p.parse_args(argv)

    members = get_council(args.city, live=args.live)
    logger.info("{}: {} council members", args.city, len(members))
    for m in members:
        logger.info("  {} — {} ({})", m.full_name, m.district or "?", m.title)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump([m.to_dict() for m in members], fh, indent=2)
        logger.success("wrote {}", args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
