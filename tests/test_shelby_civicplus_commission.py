"""Shelby County AL — CivicPlus commission roster + meetings."""

from __future__ import annotations

import pytest
import requests

from scripts.datasources.jurisdiction_pilot.http_fetch import BROWSER_USER_AGENT
from scripts.datasources.jurisdiction_pilot.mayor_url_discovery import (
    discover_county_commission_page_url,
    discover_seed_urls,
)
from scripts.datasources.jurisdiction_pilot.website_civicplus_meetings import (
    extract_civicplus_agenda_center_items,
    scrape_civicplus_meetings,
)
from scrapers.discovery.contact_extract_from_html import (
    extract_civicplus_commission_member_list_contacts_from_html,
    extract_structured_contacts_from_html,
)


_COMMISSION_URL = "https://www.shelbyal.com/93/County-Commission"
_HOME = "https://www.shelbyal.com/"
_HEADERS = {"User-Agent": BROWSER_USER_AGENT}


def test_discover_county_commission_via_government_hub():
    """CivicPlus counties link commission from ``/NN/Government`` (not bare ``/Elected-Officials``)."""
    r = requests.get(
        "https://www.shelbyal.com/27/Government",
        timeout=20,
        headers=_HEADERS,
    )
    if r.status_code != 200:
        pytest.skip(f"Shelby government hub unavailable ({r.status_code})")
    from scripts.datasources.jurisdiction_pilot.mayor_url_discovery import (
        _commission_url_from_html,
    )

    url = _commission_url_from_html(r.text, r.url)
    assert url and "County-Commission" in url


def test_shelby_commission_member_list_live():
    r = requests.get(_COMMISSION_URL, timeout=20, headers=_HEADERS)
    assert r.status_code == 200
    rows = extract_civicplus_commission_member_list_contacts_from_html(r.text, r.url)
    names = {x["person_name"] for x in rows}
    assert "Kevin Morris" in names
    assert "Robbie Hayes" in names
    assert any("District" in (x.get("title_or_role") or "") for x in rows)
    assert any(x.get("profile_url") and "Kevin-Morris" in x["profile_url"] for x in rows)


def test_shelby_commission_structured_extract_includes_roster():
    r = requests.get(_COMMISSION_URL, timeout=20, headers=_HEADERS)
    rows = extract_structured_contacts_from_html(r.text, r.url)
    assert any(r.get("person_name") == "Kevin Morris" for r in rows)


def test_shelby_agenda_center_counts():
    r = requests.get(
        "https://www.shelbyal.com/AgendaCenter",
        timeout=20,
        headers=_HEADERS,
    )
    events, agendas, minutes = extract_civicplus_agenda_center_items(r.text, r.url)
    titles = " ".join(e["title"] for e in events).lower()
    assert agendas > 0
    assert "planning commission" in titles
    assert "commission meeting" in titles


def test_shelby_meetings_scrape_integration():
    s = requests.Session()
    s.headers["User-Agent"] = BROWSER_USER_AGENT
    cap = scrape_civicplus_meetings(_HOME, s)
    assert cap.events_count > 0
    assert cap.agendas > 0
    assert cap.minutes > 0


def test_discover_seed_urls_finds_commission_page():
    home = requests.get(_HOME, timeout=20, headers=_HEADERS)
    if home.status_code != 200:
        pytest.skip(f"Shelby homepage unavailable ({home.status_code})")
    out = discover_seed_urls(_HOME, jurisdiction_type="county")
    assert any("County-Commission" in u for u in out["council"])
