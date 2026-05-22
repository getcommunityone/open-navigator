"""
Regression test: re-extract contacts from cached `_crawl_html/` snapshots for the
first 10 Georgia counties (alphabetical by FIPS) and compare against the on-disk
`_contact_images/contacts.json` golden bundles.

The test is purely offline — it reads `_manifest.json` for homepage / jurisdiction
metadata, walks the saved HTML snapshots, re-runs the structured extractor +
bundler, and asserts that the resulting bundle matches the golden file on stable
fields (contact_count, department_office_count, set of emails, set of names,
email→name mapping).

Counties that lack a complete fixture pair (missing `_manifest.json` or
`contacts.json`, or with no HTML snapshots) are skipped with a clear reason.
A meta-test asserts the qualifying-county count never drops below the level
recorded here, so a regression in crawl completeness shows up as a failure
rather than a silent skip.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import pytest

from scripts.discovery.contact_directory_heuristics import classify_contact_directory_page
from scripts.discovery.contact_extract_from_html import (
    extract_structured_contacts_from_html,
    infer_profile_url_from_source_page,
)
from scripts.discovery.contacts_bundle import build_contacts_bundle


_REPO_ROOT = Path(__file__).resolve().parents[1]
_GA_COUNTY_CACHE = _REPO_ROOT / "data" / "cache" / "scraped_meetings" / "GA" / "county"

# First 10 GA counties alphabetically by FIPS (5-digit state+county code).
FIRST_10_GA_COUNTIES: Tuple[str, ...] = (
    "appling_13001",
    "atkinson_13003",
    "bacon_13005",
    "baker_13007",
    "baldwin_13009",
    "banks_13011",
    "barrow_13013",
    "bartow_13015",
    "ben_hill_13017",
    "berrien_13019",
)

# Floor on counties that must have a complete fixture pair. If a previously
# qualifying county loses its fixtures (manifest deleted, contacts.json gone),
# the meta-test below fails — the regression net should grow, not shrink.
MIN_QUALIFYING_COUNTIES = 5


def _snapshot_stem_to_page_url(homepage: str, snap_stem: str) -> str:
    """Reconstruct the page URL a crawl-html snapshot was scraped from.

    Mirrors `scripts.discovery.refresh_contacts_from_crawl_html._snapshot_stem_to_page_url`.
    """
    slug = snap_stem[5:] if snap_stem.startswith("page_") else snap_stem
    slug = slug.lstrip("_")
    if slug == "index":
        path = "/"
    elif slug.isdigit():
        path = f"/{slug}"
    else:
        m = re.match(r"^(\d+)_(.+)$", slug)
        path = f"/{m.group(1)}/{m.group(2)}" if m else "/" + slug.replace("_", "/")
    base = (homepage or "").strip().rstrip("/")
    if not base:
        return path
    p = urlparse(base)
    return urljoin(f"{p.scheme}://{p.netloc}", path)


def _regenerate_contacts_bundle(jurisdiction_dir: Path) -> Dict[str, Any]:
    """Rebuild the contacts bundle purely from on-disk crawl artifacts.

    Reads `_manifest.json` for homepage / jurisdiction / cached profile images,
    iterates `_crawl_html/page_*.html` snapshots, classifies each as a contact
    directory page, extracts structured contact rows, and assembles the bundle
    via `build_contacts_bundle`. No network I/O.
    """
    manifest = json.loads((jurisdiction_dir / "_manifest.json").read_text(encoding="utf-8"))
    homepage = str(manifest.get("homepage_url") or "").strip()

    structured: List[Dict[str, Any]] = []
    for snap in sorted((jurisdiction_dir / "_crawl_html").glob("page_*.html")):
        page_url = _snapshot_stem_to_page_url(homepage, snap.stem)
        html = snap.read_text(encoding="utf-8", errors="replace")
        cdir = classify_contact_directory_page(page_url, html)
        if not cdir.get("is_directory"):
            continue
        kind = str(cdir.get("directory_kind") or "unknown")
        score = int(cdir.get("score") or 0)
        for prow in extract_structured_contacts_from_html(html, page_url):
            prow["source_page_url"] = page_url
            prow["page_classification"] = kind
            prow["directory_score"] = score
            infer_profile_url_from_source_page(prow)
            structured.append(prow)

    return build_contacts_bundle(
        jurisdiction_id=str(manifest.get("jurisdiction_id") or ""),
        state=str(manifest.get("state") or ""),
        homepage_url=homepage,
        scraped_at=manifest.get("scraped_at"),
        scrape_batch_id=str(manifest.get("scrape_batch_id") or ""),
        structured_contacts=structured,
        contact_profile_images=list(manifest.get("contact_profile_images") or []),
        extracted_contacts=manifest.get("extracted_contacts"),
    )


def _skip_if_no_fixture(jurisdiction_dir: Path) -> None:
    manifest = jurisdiction_dir / "_manifest.json"
    crawl_html = jurisdiction_dir / "_crawl_html"
    golden = jurisdiction_dir / "_contact_images" / "contacts.json"
    if not manifest.is_file():
        pytest.skip(f"{jurisdiction_dir.name}: missing _manifest.json (incomplete crawl)")
    if not crawl_html.is_dir() or not list(crawl_html.glob("page_*.html")):
        pytest.skip(f"{jurisdiction_dir.name}: no crawl_html snapshots")
    if not golden.is_file():
        pytest.skip(f"{jurisdiction_dir.name}: missing contacts.json golden")


def _email_name_map(contacts: List[Dict[str, Any]]) -> Dict[str, str]:
    """Lowercased email → first non-empty person_name seen for that email."""
    out: Dict[str, str] = {}
    for row in contacts:
        em = str(row.get("email") or "").strip().lower()
        if not em:
            continue
        nm = str(row.get("person_name") or "").strip().lower()
        if em not in out and nm:
            out[em] = nm
    return out


@pytest.mark.parametrize("county", FIRST_10_GA_COUNTIES)
def test_contact_scraper_regression_first_10_ga_counties(county: str) -> None:
    """Re-extract contacts from cached HTML; assert bundle matches golden."""
    jurisdiction_dir = _GA_COUNTY_CACHE / county
    _skip_if_no_fixture(jurisdiction_dir)

    golden = json.loads(
        (jurisdiction_dir / "_contact_images" / "contacts.json").read_text(encoding="utf-8")
    )
    actual = _regenerate_contacts_bundle(jurisdiction_dir)

    assert actual["contact_count"] == golden["contact_count"], (
        f"{county}: contact_count drifted ({actual['contact_count']} vs golden {golden['contact_count']})"
    )
    assert actual["department_office_count"] == golden["department_office_count"], (
        f"{county}: department_office_count drifted "
        f"({actual['department_office_count']} vs golden {golden['department_office_count']})"
    )

    actual_emails = {str(r.get("email") or "").lower() for r in actual["contacts"] if r.get("email")}
    golden_emails = {str(r.get("email") or "").lower() for r in golden["contacts"] if r.get("email")}
    assert actual_emails == golden_emails, (
        f"{county}: email set drifted\n  missing: {golden_emails - actual_emails}\n  extra:   {actual_emails - golden_emails}"
    )

    actual_names = {str(r.get("person_name") or "").lower() for r in actual["contacts"] if r.get("person_name")}
    golden_names = {str(r.get("person_name") or "").lower() for r in golden["contacts"] if r.get("person_name")}
    assert actual_names == golden_names, (
        f"{county}: person_name set drifted\n  missing: {golden_names - actual_names}\n  extra:   {actual_names - golden_names}"
    )

    actual_map = _email_name_map(actual["contacts"])
    golden_map = _email_name_map(golden["contacts"])
    shared = actual_map.keys() & golden_map.keys()
    mismatched = {em: (actual_map[em], golden_map[em]) for em in shared if actual_map[em] != golden_map[em]}
    assert not mismatched, f"{county}: email→name mapping drifted: {mismatched}"


def test_qualifying_county_count_does_not_shrink() -> None:
    """Guard against silent skips: at least MIN_QUALIFYING_COUNTIES must run."""
    qualifying = []
    for county in FIRST_10_GA_COUNTIES:
        jdir = _GA_COUNTY_CACHE / county
        if (
            (jdir / "_manifest.json").is_file()
            and (jdir / "_contact_images" / "contacts.json").is_file()
            and (jdir / "_crawl_html").is_dir()
            and list((jdir / "_crawl_html").glob("page_*.html"))
        ):
            qualifying.append(county)
    assert len(qualifying) >= MIN_QUALIFYING_COUNTIES, (
        f"Only {len(qualifying)} of the first 10 GA counties have a complete fixture pair "
        f"(expected >= {MIN_QUALIFYING_COUNTIES}). Qualifying: {qualifying}"
    )
