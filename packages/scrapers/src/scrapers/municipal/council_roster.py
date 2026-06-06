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
    python -m scrapers.municipal.council_roster --city northport --live      # CivicPlus dir + bios
    python -m scrapers.municipal.council_roster --profiles atlanta           # mayor photo + bio
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
    # Biography prose scraped from the member's detail / "more information" page
    # (e.g. a CivicPlus directory.aspx entry). Newline-separated sections; flows
    # bronze_officials_scraped.biography -> contact_official.biography -> the
    # PersonDetail page. None when the source page carries no bio.
    biography: Optional[str] = None

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
    # Optional per-member detail-page URL template for sites that don't put
    # headshots on the roster page. "{district}" is filled with the member's
    # district number. caboosecms sites (e.g. Tuscaloosa) render the headshot as
    # a CSS background-image on this page, not as an <img> on the roster.
    member_page_template: Optional[str] = None
    # CivicPlus sites (e.g. Northport) link each member to a `directory.aspx?eid=N`
    # detail page that carries the name, title/district, headshot AND biography.
    # When True, `--live` discovers those eids off the roster page and parses each
    # detail page in full (see scrape_civicplus_directory) rather than the roster.
    civicplus_directory: bool = False


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
        # Headshots live on per-district pages as a CSS background-image, not on
        # the roster page — e.g. /citycouncil/district-5 for Kip Tyner.
        member_page_template="https://www.tuscaloosa.com/citycouncil/district-{district}",
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
    "atlanta": MunicipalCouncilConfig(
        slug="atlanta",
        url="https://www.atlantaga.gov/government/city-council",
        # Matches the jurisdiction string on Atlanta's OpenStates mayor (Andre
        # Dickens) so the seed override join + ?city=Atlanta line up. NOTE: the
        # council roster is not curated yet — Atlanta is wired here primarily for
        # mayor profile scraping (OFFICIAL_PROFILE_SOURCES below), which carries
        # the state metadata the official_photo_override seed needs.
        jurisdiction="Atlanta Government",
        state_code="GA",
        state="Georgia",
    ),
    "kingsport": MunicipalCouncilConfig(
        slug="kingsport",
        # Board of Mayor and Aldermen (BMA) — Kingsport's governing body.
        url="https://www.kingsporttn.gov/government/bma/",
        # No OpenStates officials exist for Kingsport at all (mayor included), so
        # ?city=Kingsport returns ONLY these scraped rows. Uses the "<City>
        # Government" convention shared by the other TN cities in contact_official.
        jurisdiction="Kingsport Government",
        state_code="TN",
        state="Tennessee",
        member_title="Alderman",
    ),
    "northport": MunicipalCouncilConfig(
        slug="northport",
        # CivicPlus site. The roster page links each member ("More Information") to
        # a directory.aspx?eid=N detail page carrying name/title/district/headshot
        # AND a full biography.
        url="https://www.northportal.gov/220/City-Council",
        # No OpenStates officials exist for Northport (mayor included), so
        # ?city=Northport returns ONLY these scraped rows. Uses the "<City>
        # Government" convention shared by the other AL cities in contact_official.
        # The mayor is therefore INCLUDED here (nothing to duplicate), like Kingsport.
        jurisdiction="Northport Government",
        state_code="AL",
        state="Alabama",
        civicplus_directory=True,
    ),
}


# Northport, AL council biographies, scraped from each member's CivicPlus
# directory.aspx detail page ("More Information"). Kept here so the curated roster
# below stays readable; refresh with `--live` (scrape_civicplus_directory).
_NORTHPORT_BIOS: dict[str, str] = {
    "Dale Phillips": (
        "Mayor Phillips was elected in August of 2025 and sworn in as Mayor on November 3, 2025, replacing John Hinton."
    ),
    "Turnley Smith": (
        "Personal Profile\n"
        "Turnley Smith was born in Florence, Alabama, and raised in Hohenwald, Tennessee. He has been a proud resident of Northport since 2006.\n"
        "He has been married since 1999. He and his wife are blessed with two wonderful children. Together, they enjoy biking, playing pickleball, and traveling.\n"
        "His favorite pastime is golf.\n"
        "\n"
        "Education\n"
        "He holds a Bachelor of Architecture, a Bachelor of Interior Architecture, and a Bachelor of Science in Environmental Design from Auburn University's College of Architecture, Design and Construction. He completed his thesis in Auburn's renowned Rural Studio in Newbern, Alabama.\n"
        "After graduation, Mr. Smith joined Ellis Architects in Tuscaloosa, where he completed the Architect Intern Program. He later founded and operated his own Design-Build firm for more than 17 years, during which he also became a Licensed Homebuilder.\n"
        "He currently serves as Deputy Director of Building and Inspections for the City of Tuscaloosa Department of Urban Development.\n"
        "\n"
        "Overall Goals\n"
        "Turnley Smith chose to run for Northport City Council to share his expertise in community planning and to help ensure that all residents have a voice in building a better Northport.\n"
        "Poll Location: District 1 - Northport Civic Center\n"
        "\n"
        "Voting District Information\n"
        "Mr. Smith was elected to the City Council in August 2025."
    ),
    "Woodrow Washington III": (
        "Personal Profile\n"
        "Married to Marie J. Washington\n"
        "Two sons, Kerry Matthew Jr., and Woodrow Washington IV\n"
        "Five grandchildren: Tristan Williams, Jordan Scruggs, Treasure Anderson, Kerry Matthews III, and Damon Bishop\n"
        "Retired Fire Captain from Tuscaloosa Fire Service\n"
        "Retired MSGT. United Air Force Reserve\n"
        "Owner of Archibald BBQ, Archibald and Archibald and Woodrow's BBQ\n"
        "Owner of New Life CRF (State Contractor for the Department of Intellectual Disability)\n"
        "Member of Alpha Tau Chapter of Omega Psi Phi Fraternity, Inc. Tuscaloosa, AL\n"
        "Member of Beulah Baptist Church, Northport, AL\n"
        "\n"
        "Education\n"
        "Graduate of Tuscaloosa County High School\n"
        "Graduate of Stillman College with a Bachelor of Science Degree in Business Administration\n"
        "\n"
        "Areas of Interest\n"
        "Spending time with family and friends\n"
        "Community Service\n"
        "Developing our youth through sports\n"
        "\n"
        "Overall Goals\n"
        "Ensure every citizen of District 2 voice is heard\n"
        "Meet the needs of all citizens in District 2\n"
        "Bridge the gap from City Hall and the community\n"
        "Poll Location: District 2 - New Zion Baptist Church\n"
        "\n"
        "Voting District Information\n"
        "Councilman Washington was elected to the City Council in October 2020 and re-elected in August 2025. He represents District 2 and is serving his second term. Councilman Washington was elected President Pro Tempore on November 3, 2025."
    ),
    "Jaime Conger": (
        "Personal Profile\n"
        "Born and raised in Montgomery, Alabama. Jaime has been a proud resident of Northport since 2008. She has been married to John Conger since 2009, and they are blessed with two children, Vivian and Henry.\n"
        "Served with many local organizations since moving to Tuscaloosa County, and is the past president of the Tuscaloosa County Bar Association and the Junior League of Tuscaloosa.\n"
        "Graduate of the Alabama State Bar Leadership Forum\n"
        "Previously served Northport as chair of the Northport Redevelopment Authority.\n"
        "\n"
        "Education\n"
        "Graduated from Saint James School in Montgomery, Alabama, in 2000.\n"
        "Bachelor of Arts in both economics and political science from Furman University in Greenville, South Carolina, in 2004.\n"
        "Councilor Conger received her J.D. from Tulane University School of Law in New Orleans, Louisiana, in 2007. Before graduating, she attended the University of Alabama School of Law for the fall 2005 semester due to Hurricane Katrina.\n"
        "After graduation, she practiced law for one year in Montgomery, Alabama, before making Northport her home in 2008.\n"
        "Practiced law with the firm Smith & Staggs, LLP since 2012, and her main areas of practice are domestic relations, criminal defense, and juvenile delinquency and dependency.\n"
        "\n"
        "Overall Goals\n"
        "Jaime Conger ran on the platform of restoring trust to the Northport City Council. Her main objectives are to unify the community, promote transparency, support small businesses, address outstanding infrastructure issues, and advocate for the citizens of Northport.\n"
        "Poll Location: District 3 - Daystar Family Church\n"
        "\n"
        "Voting District Information\n"
        "Councilwoman Conger was elected in August of 2025 to represent District 3."
    ),
    "Jamie Dykes": (
        "Personal Profile\n"
        "Daughter, Emma Katharine, 2020 Graduate of TCHS\n"
        "Parents, Linda and Frank Dykes\n"
        "\n"
        "Education\n"
        "Graduate of The University of Alabama with a BS and MA in Elementary Education\n"
        "\n"
        "Areas of Interest\n"
        "Spending time with family\n"
        "Grilling or eating out with friends\n"
        "Playing tennis\n"
        "Working in her yard\n"
        "Alabama Softball\n"
        "Being anywhere on the water, especially Lake Tuscaloosa\n"
        "\n"
        "Overall Goals\n"
        "Meet the needs of all District 4 citizens\n"
        "Paving schedule\n"
        "Create a Citizens Advisory group\n"
        "Enhance the positivity of Northport\n"
        "Poll Location: District 4 - Northport Fire and Rescue Station 2\n"
        "\n"
        "Voting District Information\n"
        "Councilwoman Dykes was elected to the City Council in October 2020 and re-elected in August 2025. She represents District 4 and is serving her second term on the Northport City Council. Councilwoman Dykes was elected Council President on November 3, 2025."
    ),
    "Danny Higdon": (
        "Personal Profile\n"
        "Councilman Higdon has been a proud resident of Northport for over fifty years. He and his wife, Mitzi, have been married for 39 years and are the parents of three sons, all of whom are married and reside in Northport. Two of their sons are educators, and the third serves as Marketing Director for a mission organization. Danny and Mitzi are blessed with six grandchildren.\n"
        "\n"
        "Education\n"
        "Attended Crestmont Elementary, Northport Junior High, and graduated from Tuscaloosa County High School.\n"
        "Bachelor's degree in Commerce and Business Administration with a major in Accounting from the University of Alabama.\n"
        "\n"
        "Areas of Interest\n"
        "Worked as an Auditor with the City of Tuscaloosa from 1991 to 1994.\n"
        "Worked as an Auditor at the City of Northport, where he later advanced to the position of Auditor/Assistant Finance Director, serving from 1994 to 2005.\n"
        "Worked at the Tuscaloosa County Board of Education, where he held several administrative roles before being appointed Chief School Finance Officer (CSFO) in 2012. Danny served as CSFO until his retirement in 2020. He returned to the position in 2021 and remained in that role until his retirement in April 2025.\n"
        "In addition to his professional accomplishments, Danny served in the Alabama National Guard in Northport, first with Company A of the 31st Support Battalion and later with Headquarters Company of the 31st Armor Brigade, achieving the rank of Captain.\n"
        "\n"
        "Overall Goals\n"
        "Danny Higdon chose to run for the Northport City Council to serve the citizens with integrity, transparency, and fiscal responsibility. His goal is to ensure that the voices of Northport residents are heard and represented in every decision that impacts the community.\n"
        "Poll Location: District 5 - Flatwoods Baptist Church\n"
        "\n"
        "Voting District Information\n"
        "Councilman Higdon was elected in August of 2025 to represent District 5."
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
    # Kingsport, TN — Board of Mayor and Aldermen (BMA): mayor + vice mayor + 5
    # aldermen, all elected AT-LARGE (no districts). Unlike Tuscaloosa/Boston, this
    # roster INCLUDES the mayor and vice mayor because OpenStates carries no
    # Kingsport officials at all — so there is nothing to duplicate. Photos/emails
    # are taken straight off the BMA page (the curated roster is the reliable
    # default; `--live` re-pulls the headshots by name).
    # Source: https://www.kingsporttn.gov/government/bma/
    "kingsport": [
        CouncilMember(
            "Paul W. Montgomery", "Mayor", "Kingsport Government", "TN", "Tennessee",
            district=None, email="PaulMontgomery@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/2024/09/Mayor_Paul-Montgomery-scaled.jpg",
        ),
        CouncilMember(
            "Darrell Duncan", "Vice Mayor", "Kingsport Government", "TN", "Tennessee",
            district=None, email="DarrellDuncan@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/2024/09/darrell-web.png",
        ),
        CouncilMember(
            "Morris Baker", "Alderman", "Kingsport Government", "TN", "Tennessee",
            district="At-Large", email="MorrisBaker@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/2024/09/morris-web.png",
        ),
        CouncilMember(
            "Betsy Cooper", "Alderman", "Kingsport Government", "TN", "Tennessee",
            district="At-Large", email="BetsyCooper@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/Alderman_Betsy-Cooper.jpg",
        ),
        CouncilMember(
            "Colette George", "Alderman", "Kingsport Government", "TN", "Tennessee",
            district="At-Large", email="ColetteGeorge@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/Colette-George.jpeg",
        ),
        CouncilMember(
            "Gary Mayes", "Alderman", "Kingsport Government", "TN", "Tennessee",
            district="At-Large", email="GaryMayes@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/2024/10/mayes-web.png",
        ),
        CouncilMember(
            "James Phillips", "Alderman", "Kingsport Government", "TN", "Tennessee",
            district="At-Large", email="JamesPhillips@kingsporttn.gov",
            photo_url="https://www.kingsporttn.gov/wp-content/uploads/2021/07/james-web.jpg",
        ),
    ],
    # Northport, AL — Mayor + 5 single-member-district council seats. Like
    # Kingsport, OpenStates carries no Northport officials at all, so this roster
    # INCLUDES the mayor (nothing to duplicate). Names/titles/districts, headshots,
    # and biographies were scraped from each member's CivicPlus directory.aspx
    # detail page; `--live` (scrape_civicplus_directory) re-pulls all of it.
    # Source: https://www.northportal.gov/220/City-Council
    "northport": [
        CouncilMember(
            "Dale Phillips", "Mayor", "Northport Government", "AL", "Alabama",
            district=None, phone="205-394-1476",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1771",
            biography=_NORTHPORT_BIOS["Dale Phillips"],
        ),
        CouncilMember(
            "Turnley Smith", "City Councilor", "Northport Government", "AL", "Alabama",
            district="District 1",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1779",
            biography=_NORTHPORT_BIOS["Turnley Smith"],
        ),
        CouncilMember(
            "Woodrow Washington III", "City Councilor (Mayor Pro Tempore)", "Northport Government", "AL", "Alabama",
            district="District 2",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1780",
            biography=_NORTHPORT_BIOS["Woodrow Washington III"],
        ),
        CouncilMember(
            "Jaime Conger", "City Councilor", "Northport Government", "AL", "Alabama",
            district="District 3",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1777",
            biography=_NORTHPORT_BIOS["Jaime Conger"],
        ),
        CouncilMember(
            "Jamie Dykes", "City Council President", "Northport Government", "AL", "Alabama",
            district="District 4",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1778",
            biography=_NORTHPORT_BIOS["Jamie Dykes"],
        ),
        CouncilMember(
            "Danny Higdon", "City Councilor", "Northport Government", "AL", "Alabama",
            district="District 5",
            photo_url="https://www.northportal.gov/ImageRepository/Document?documentID=1776",
            biography=_NORTHPORT_BIOS["Danny Higdon"],
        ),
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


# CSS `background-image:url(...)` — caboosecms sites render member headshots this
# way (not as <img>), so the <img>-only harvester never sees them.
_BG_IMAGE_RE = re.compile(
    r"background-image:\s*url\(\s*['\"]?([^'\")]+?)['\"]?\s*\)", re.IGNORECASE
)
# Site chrome to ignore when picking the member photo off a detail page.
_PHOTO_CHROME = ("banner", "seal", "logo", "header", "favicon", "icon", "arrows")


def _member_photo_from_page(html: str, base_url: str) -> Optional[str]:
    """Pull a single member headshot from a per-member detail page.

    Returns the first CSS ``background-image`` that points at a CMS media asset,
    skipping site chrome (banner/seal/logo). Resolves protocol-relative
    (``//assets...``) and relative URLs against ``base_url``. ``None`` if none.
    """
    for raw in _BG_IMAGE_RE.findall(html):
        url = raw.strip()
        low = url.lower()
        if "/media/" not in low and "/assets/" not in low:
            continue
        if any(chrome in low for chrome in _PHOTO_CHROME):
            continue
        if url.startswith("//"):
            url = "https:" + url
        return urljoin(base_url, url)
    return None


def _detail_page_photo(config: MunicipalCouncilConfig, district: Optional[str]) -> Optional[str]:
    """Headshot URL from a member's per-district detail page, or ``None``.

    Only fires for configs with a ``member_page_template``; the district number is
    extracted from ``district`` ("District 5" -> "5"). Network failure -> ``None``.
    """
    if not config.member_page_template or not district:
        return None
    dm = _DISTRICT_RE.search(district)
    if not dm:
        return None
    page_url = config.member_page_template.format(district=dm.group(1))
    try:
        return _member_photo_from_page(fetch_html(page_url), page_url)
    except Exception as exc:
        logger.warning("detail-page headshot fetch failed for {} ({})", page_url, exc)
        return None


# Mayors / executives whom OpenStates carries with no image *and* no biography.
# Their headshot and bio live on a city department / "meet the <office>" page;
# scraping it lets us overlay BOTH onto the existing contact_official row
# (matched by name, so we never duplicate the OpenStates official). The scraped
# values are curated into the seed `official_photo_override` (which also carries
# the biography) and coalesced in by the contact_official mart.
OFFICIAL_PROFILE_SOURCES: dict[str, list[str]] = {
    "boston": ["https://www.boston.gov/departments/mayors-office"],
    # Atlanta's mayor (Andre Dickens) is in OpenStates with no photo/bio; both
    # live on the "Meet the Mayor" page. It is a single-official profile page, so
    # scrape_official_profile attaches the page's bio to that one official.
    "atlanta": ["https://www.atlantaga.gov/government/mayor-s-office/meet-the-mayor"],
}


@dataclass(frozen=True)
class OfficialProfile:
    """A scraped mayor/executive profile, overlaid onto contact_official by name."""

    full_name: str
    photo_url: Optional[str] = None
    biography: Optional[str] = None
    source_url: Optional[str] = None


# alt text like "A headshot of Mayor Michelle Wu smiling." -> the bare name.
_HEADSHOT_OF_RE = re.compile(
    r"headshot of\s+(?:mayor|councilor|councill?or|councilman|councilwoman|"
    r"commissioner|chief|president|director)?\s*(.+?)(?:\s+smiling)?\.?$",
    re.IGNORECASE,
)

# Min word count for a text chunk to read as biography prose (vs. a nav label,
# button, or heading), and a sanity cap on the joined bio length.
_BIO_MIN_WORDS = 12
_BIO_MAX_CHARS = 4000


def _name_from_headshot(alt: str, title: str) -> str:
    """Recover an official's bare name from a headshot's ``alt``/``title``.

    Handles the two labellings city sites use: ``alt="<Name> headshot"`` and
    ``alt="A headshot of <Title> <Name> ..." title="<Name>"`` (mayor's-office
    style). Prefers the clean ``title`` when present.
    """
    if title and "headshot" in alt.lower():
        return title.strip()
    m = _HEADSHOT_OF_RE.search(alt)
    if m:
        return m.group(1).strip()
    return re.sub(r"\s*headshot.*$", "", alt, flags=re.IGNORECASE).strip()


def _extract_biography(chunks: list[str]) -> Optional[str]:
    """Best-effort biography: the page's prose chunks, joined.

    A "meet the mayor" page's bio is its body prose — long, sentence-like text
    nodes — as opposed to nav items / labels / buttons (short fragments). Keep
    chunks of >= ``_BIO_MIN_WORDS`` words, join them, and cap the length. Returns
    ``None`` when the page has no prose block. Heuristic — ALWAYS verify the live
    result and prefer curating the seed from it.
    """
    prose = [c for c in chunks if len(c.split()) >= _BIO_MIN_WORDS]
    if not prose:
        return None
    bio = re.sub(r"\s+", " ", " ".join(prose)).strip()
    return bio[:_BIO_MAX_CHARS].rstrip() or None


def scrape_official_profile(url: str) -> dict[str, OfficialProfile]:
    """Scrape ``name_key -> OfficialProfile`` (photo + bio) from a profile page.

    Photos are matched off each headshot's ``alt``/``title`` (see
    :func:`_name_from_headshot`). The biography is attached ONLY when the page
    carries exactly one official's headshot — i.e. a single-person "meet the
    <office>" page (e.g. Atlanta's mayor). On multi-headshot department pages
    (e.g. Boston's mayor's office, which also lists cabinet) the bio cannot be
    reliably tied to one person, so those profiles carry the photo only.
    """
    harv = _TextHarvester()
    harv.feed(fetch_html(url))

    # name_key -> (display_name, photo_url); first headshot wins per person.
    photos: dict[str, tuple[str, str]] = {}
    for alt, src, title in harv.images:
        if "headshot" not in alt.lower() and "headshot" not in title.lower():
            continue
        name = _name_from_headshot(alt, title)
        key = _name_key(name)
        if key and key not in photos:
            photos[key] = (name, urljoin(url, src))

    biography = _extract_biography(harv.chunks) if len(photos) == 1 else None

    return {
        key: OfficialProfile(
            full_name=name,
            photo_url=photo_url,
            biography=biography,
            source_url=url,
        )
        for key, (name, photo_url) in photos.items()
    }


def scrape_official_photos(url: str) -> dict[str, str]:
    """Scrape ``name -> absolute headshot URL`` from a department page.

    Thin wrapper over :func:`scrape_official_profile` kept for photo-only callers
    and the seed-refresh flow; returns just the headshot URLs.
    """
    return {
        key: prof.photo_url
        for key, prof in scrape_official_profile(url).items()
        if prof.photo_url
    }


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
# CivicPlus directory scrape (Northport-style: per-member detail pages)
# ---------------------------------------------------------------------------
# Section labels CivicPlus directory.aspx pages use to structure the bio body.
_CIVICPLUS_BIO_SECTIONS = {
    "Personal Profile", "Professional Profile", "Biography", "Education",
    "Areas of Interest", "Overall Goals", "Voting District Information", "Poll Location",
}
# Header/footer image alts that are site chrome, not a member headshot.
_CIVICPLUS_IMG_CHROME = {
    "homepage", "facebook", "twitter", "instagram", "employee email", "search", "youtube",
}
# Detail-page link on a CivicPlus roster: ``directory.aspx?eid=37``.
_CIVICPLUS_EID_RE = re.compile(r"directory\.aspx\?eid=(\d+)", re.IGNORECASE)
_CIVICPLUS_PLACEHOLDER = "coming soon!"
_CIVICPLUS_BIO_END = "Return to Staff Directory"


def _civicplus_title_district(title_text: str, config: MunicipalCouncilConfig) -> tuple[str, Optional[str]]:
    """Map a CivicPlus "Title:" value to a (display title, district) pair.

    Examples: "Mayor" -> (Mayor, None); "President / Council Member - District 4"
    -> (City Council President, District 4); "Pro Tempore / Council Member -
    District 2" -> (City Councilor (Mayor Pro Tempore), District 2).
    """
    low = (title_text or "").lower()
    dm = _DISTRICT_RE.search(title_text or "")
    district = f"District {dm.group(1)}" if dm else None
    if "mayor" in low and "council" not in low:
        title = "Mayor"
    elif "president" in low:
        title = "City Council President"
    elif "pro tempore" in low:
        title = "City Councilor (Mayor Pro Tempore)"
    else:
        title = config.member_title
    return title, district


def _civicplus_biography(chunks: list[str], start: int) -> Optional[str]:
    """Join a CivicPlus detail page's section/prose chunks into a bio string.

    Reads from the first bio-section header (``start``) up to the page footer
    (``Return to Staff Directory``); drops "Coming soon!" placeholders and any
    section header left with no content; blanks a line before each kept header.
    A lone surviving header (e.g. a mayor with only a one-line note) is dropped.
    """
    try:
        end = chunks.index(_CIVICPLUS_BIO_END)
    except ValueError:
        end = len(chunks)
    seg = [c for c in chunks[start:end] if c.lower() != _CIVICPLUS_PLACEHOLDER]
    kept: list[str] = []
    for i, c in enumerate(seg):
        # Skip an empty section: a header immediately followed by another header.
        if c in _CIVICPLUS_BIO_SECTIONS and (i + 1 >= len(seg) or seg[i + 1] in _CIVICPLUS_BIO_SECTIONS):
            continue
        kept.append(c)
    if sum(1 for c in kept if c in _CIVICPLUS_BIO_SECTIONS) == 1:
        kept = [c for c in kept if c not in _CIVICPLUS_BIO_SECTIONS]
    out: list[str] = []
    for c in kept:
        if c in _CIVICPLUS_BIO_SECTIONS and out:
            out.append("")
        out.append(c)
    return "\n".join(out).strip() or None


def parse_civicplus_member(html: str, config: MunicipalCouncilConfig) -> Optional[CouncilMember]:
    """Parse one CivicPlus ``directory.aspx`` detail page into a CouncilMember.

    Layout: a "Staff Directory" breadcrumb, then the member NAME, a category
    ("City Council"/"Mayor"), a "Title: ..." line, an optional "Phone:" in the
    contact block, and a sectioned biography. The headshot is the one ``<img>``
    whose ``alt`` equals the member name (CivicPlus serves it from
    ``/ImageRepository/Document?documentID=...``). Returns ``None`` if no name.
    """
    harv = _TextHarvester()
    harv.feed(html)
    chunks = harv.chunks
    try:
        i = chunks.index("Staff Directory")
    except ValueError:
        return None
    if i + 1 >= len(chunks):
        return None
    name = re.sub(r"\s+", " ", chunks[i + 1]).strip()

    # Title line within the next few chunks after the name.
    title_idx = i + 1
    title_text = ""
    for j in range(i + 2, min(i + 9, len(chunks))):
        if chunks[j].startswith("Title:"):
            title_text = chunks[j][len("Title:"):].strip()
            title_idx = j
            break
    title, district = _civicplus_title_district(title_text, config)

    # Bio starts at the first section header after the title.
    bio_start = next(
        (k for k in range(title_idx + 1, len(chunks)) if chunks[k] in _CIVICPLUS_BIO_SECTIONS),
        len(chunks),
    )

    # Phone lives only in the contact block (between title and the bio body); the
    # page footer also has a "Phone:" (city hall) that must NOT be captured.
    phone: Optional[str] = None
    for j in range(title_idx + 1, bio_start):
        if chunks[j].startswith("Phone:"):
            if j + 1 < bio_start and re.match(r"[\d(]", chunks[j + 1]):
                phone = chunks[j + 1].strip()
            break

    biography = _civicplus_biography(chunks, bio_start) if bio_start < len(chunks) else None

    # Headshot: the <img> whose alt is the member's name. CivicPlus sometimes
    # drops a generational suffix from the alt ("Woodrow Washington" for "Woodrow
    # Washington III"), so accept a name that is a token-subset either way. Never
    # fall back to a logo/social image (site chrome shares no name token).
    name_key = _name_key(name)
    photo_url: Optional[str] = None
    for alt, src, _title in harv.images:
        alt_key = _name_key(alt)
        if "documentid=" not in src.lower() or alt_key in _CIVICPLUS_IMG_CHROME:
            continue
        if alt_key == name_key or alt_key in name_key or name_key in alt_key:
            photo_url = urljoin(config.url, src)
            break

    return CouncilMember(
        full_name=name,
        title=title,
        jurisdiction=config.jurisdiction,
        state_code=config.state_code,
        state=config.state,
        district=district,
        phone=phone,
        photo_url=photo_url,
        biography=biography,
    )


def scrape_civicplus_directory(config: MunicipalCouncilConfig) -> list[CouncilMember]:
    """Scrape a CivicPlus council roster + each member's detail page.

    Discovers the ``directory.aspx?eid=N`` detail links off the roster page
    (``config.url``) and parses each into a full CouncilMember (name, title,
    district, headshot, biography). Members sort mayor-first then by district.
    Per-page failures are logged and skipped; network failure -> empty list.
    """
    try:
        roster_html = fetch_html(config.url)
    except Exception as exc:
        logger.warning("CivicPlus roster fetch for {} failed ({})", config.slug, exc)
        return []

    eids: list[str] = []
    for eid in _CIVICPLUS_EID_RE.findall(roster_html):
        if eid not in eids:
            eids.append(eid)
    if not eids:
        logger.warning("no directory.aspx?eid links found on {}", config.url)
        return []

    base = config.url.split("//", 1)
    origin = (base[0] + "//" + base[1].split("/", 1)[0]) if len(base) == 2 else config.url
    members: list[CouncilMember] = []
    for eid in eids:
        url = urljoin(origin + "/", f"directory.aspx?eid={eid}")
        try:
            member = parse_civicplus_member(fetch_html(url), config)
        except Exception as exc:
            logger.warning("CivicPlus detail parse failed for {} ({})", url, exc)
            continue
        if member and member.full_name:
            members.append(member)

    def _order(m: CouncilMember) -> tuple[int, int]:
        dm = _DISTRICT_RE.search(m.district or "")
        return (0, 0) if m.district is None else (1, int(dm.group(1)) if dm else 99)

    members.sort(key=_order)
    logger.success("scraped {} CivicPlus members from {}", len(members), config.url)
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
        logger.warning("roster-page headshots for {} failed ({}); trying detail pages", config.slug, exc)
        photos = {}

    enriched: list[CouncilMember] = []
    filled = 0
    for m in members:
        url = photos.get(_name_key(m.full_name))
        # Fall back to a per-member detail page for sites (e.g. caboosecms /
        # Tuscaloosa) whose roster page carries no inline headshots.
        if not url and not m.photo_url:
            url = _detail_page_photo(config, m.district)
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
    parse is too noisy to trust for membership) — EXCEPT CivicPlus directory sites
    (``civicplus_directory=True``, e.g. Northport), where each member has a
    structured detail page so the live scrape re-pulls names/titles/districts/
    headshots/biographies in full. Cities with no curated roster fall back to the
    best-effort parse.
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
        # CivicPlus detail pages are structured enough to trust for full membership
        # (incl. biographies), so re-scrape rather than just overlaying photos.
        if cfg.civicplus_directory:
            scraped = scrape_civicplus_directory(cfg)
            if scraped:
                return scraped
            logger.warning("CivicPlus live scrape of {} yielded 0; using curated", slug)
        elif curated is not None:
            return _overlay_live_photos(list(curated), cfg)
        else:
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


def _emit_profiles(city: str, json_out: Optional[str]) -> int:
    """Scrape ``OFFICIAL_PROFILE_SOURCES[city]`` and dump mayor/exec profiles.

    Emits rows shaped for the ``official_photo_override`` seed (full_name,
    state_code, photo_url, biography, source_url) so a verified live run can be
    curated into the seed. Requires network.
    """
    city = city.lower().strip()
    urls = OFFICIAL_PROFILE_SOURCES.get(city)
    if not urls:
        logger.error("no profile sources configured for city {!r}", city)
        return 1
    state_code = CONFIGS[city].state_code if city in CONFIGS else ""
    profiles: dict[str, OfficialProfile] = {}
    for url in urls:
        try:
            profiles.update(scrape_official_profile(url))
        except Exception as exc:
            logger.warning("profile scrape of {} failed ({})", url, exc)
    rows = [
        {
            "full_name": p.full_name,
            "state_code": state_code,
            "photo_url": p.photo_url or "",
            "biography": p.biography or "",
            "source_url": p.source_url or "",
        }
        for p in profiles.values()
    ]
    for r in rows:
        logger.info(
            "  {} — photo={} bio={} chars", r["full_name"], bool(r["photo_url"]), len(r["biography"])
        )
    payload = json.dumps(rows, indent=2)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        logger.success("wrote {}", json_out)
    else:
        print(payload)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="tuscaloosa", help="City slug (default: tuscaloosa)")
    p.add_argument("--live", action="store_true", help="Scrape the live page instead of the curated roster")
    p.add_argument("--json", dest="json_out", default=None, help="Write the roster to this JSON file")
    p.add_argument(
        "--profiles",
        metavar="CITY",
        default=None,
        help="Scrape mayor/executive profiles (photo + bio) from CITY's "
        "OFFICIAL_PROFILE_SOURCES and emit JSON rows for the "
        "official_photo_override seed (requires network)",
    )
    args = p.parse_args(argv)

    if args.profiles:
        return _emit_profiles(args.profiles, args.json_out)

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
