"""County municipalities directory → bronze_websites_ballotpedia rows."""

from __future__ import annotations

import requests

from scripts.datasources.jurisdiction_pilot.county_municipality_websites import (
    discover_county_municipalities_page_url,
    extract_county_municipality_website_links,
    scrape_county_municipality_websites,
)
from scripts.datasources.jurisdiction_pilot.http_fetch import BROWSER_USER_AGENT

_HEADERS = {"User-Agent": BROWSER_USER_AGENT}
_SHELBY_MUNI = "https://www.shelbyal.com/185/Municipalities"
_SHELBY_HOME = "https://www.shelbyal.com/"


def test_shelby_municipalities_extract():
    r = requests.get(_SHELBY_MUNI, timeout=20, headers=_HEADERS)
    assert r.status_code == 200
    rows = extract_county_municipality_website_links(
        r.text,
        r.url,
        county_name="Shelby County",
        state_code="AL",
        county_website_url=_SHELBY_HOME,
    )
    names = {row["raw_row"]["municipality_name"] for row in rows}
    assert "Alabaster" in names
    assert "Pelham" in names
    assert "Wilsonville" in names
    assert len(names) >= 15
    sample = next(row for row in rows if row["raw_row"]["municipality_name"] == "Alabaster")
    assert sample["target_url"].startswith("http")
    assert sample["raw_row"]["municipality_web_address"] == sample["target_url"]
    assert sample["raw_row"]["page_found"] == _SHELBY_MUNI
    assert sample["raw_row"]["county_name"] == "Shelby County"
    assert sample["source_page_kind"] == "county_municipalities"


def test_discover_shelby_municipalities_page():
    s = requests.Session()
    s.headers["User-Agent"] = BROWSER_USER_AGENT
    url = discover_county_municipalities_page_url(_SHELBY_HOME, session=s)
    assert url and "Municipalities" in url


def test_scrape_county_municipality_websites_shelby():
    s = requests.Session()
    s.headers["User-Agent"] = BROWSER_USER_AGENT
    rows, page = scrape_county_municipality_websites(
        county_name="Shelby County",
        state_code="AL",
        county_website_url=_SHELBY_HOME,
        session=s,
    )
    assert page
    assert len(rows) >= 15
