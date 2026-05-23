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
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "contact_extract"

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


_APPLING_DIR = _GA_COUNTY_CACHE / "appling_13001"
_APPLING_TARGET_DOMAIN = "applingcountyga.org"
_APPLING_TARGET_URL_FRAGMENT = "page_id=1464"
_APPLING_EXPECTED_NAMES = frozenset({
    "reid lovett",
    "daryl edwards",
    "jakharis jones",
    "chad kent",
    "leslie burch",
    "randy sellers",
    "ricky barnes",
})


def test_appling_cache_proves_commissioners_page_was_crawled_and_extracted() -> None:
    """Offline regression on appling_13001/: cache must show the BOC page was reached.

    Fails unless Appling County's scraped-meetings cache demonstrates the full chain:
      1. ``applingcountyga.org`` is listed in ``homepage_url_candidates`` (candidate
         discovery added the real county domain — not just Baxley / applingcounty.gov).
      2. A URL containing ``applingcountyga.org`` AND ``page_id=1464`` appears in
         ``pages_fetched`` (the slow site was crawled deeply enough to reach the BOC
         roster page at https://applingcountyga.org/?page_id=1464).
      3. All seven officials named on that page appear in the rebuilt contacts bundle
         (Reid Lovett, Daryl Edwards, Jakharis Jones, Chad Kent, Leslie Burch,
         Randy Sellers, Ricky Barnes) — the extractor handled the two prose paragraphs
         ("L – R Standing …" / "L – R Seated …") separated by semicolons.

    If this test fails, the fix is upstream in the scrape pipeline (extend Appling's
    homepage candidates, give the crawler enough patience for the slow host, and let
    the AI extractor at the resulting HTML) — not in this assertion.
    """
    manifest_path = _APPLING_DIR / "_manifest.json"
    assert manifest_path.is_file(), (
        f"appling_13001: missing _manifest.json at {manifest_path} — crawl never ran"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    candidates = [str(c) for c in (manifest.get("homepage_url_candidates") or [])]
    assert any(_APPLING_TARGET_DOMAIN in c for c in candidates), (
        f"appling_13001: homepage_url_candidates does not include {_APPLING_TARGET_DOMAIN!r}; "
        f"got {candidates}. Candidate discovery must add the real county domain."
    )

    pages_fetched = [str(u) for u in (manifest.get("pages_fetched") or [])]
    matching = [
        u for u in pages_fetched
        if _APPLING_TARGET_DOMAIN in u and _APPLING_TARGET_URL_FRAGMENT in u
    ]
    assert matching, (
        f"appling_13001: no fetched page matches {_APPLING_TARGET_DOMAIN}/?{_APPLING_TARGET_URL_FRAGMENT}. "
        f"Pages fetched: {pages_fetched}. The crawler must reach the BOC roster page."
    )

    bundle = _regenerate_contacts_bundle(_APPLING_DIR)
    extracted_names = {
        str(r.get("person_name") or "").strip().lower()
        for r in bundle.get("contacts", [])
        if r.get("person_name")
    }
    missing = _APPLING_EXPECTED_NAMES - extracted_names
    assert not missing, (
        f"appling_13001: contacts bundle missing {sorted(missing)} from "
        f"https://{_APPLING_TARGET_DOMAIN}/?{_APPLING_TARGET_URL_FRAGMENT}; "
        f"got {sorted(extracted_names)}"
    )


def test_applingcountyga_commissioners_page_extracts_all_seven() -> None:
    """AI extractor must recover every official named on the Appling County BOC page.

    Live-fetches https://applingcountyga.org/?page_id=1464 via crawl4ai + Groq LLM
    extraction (``scripts.discovery.contact_extract_crawl4ai``). The page lists the
    seven officials in two prose paragraphs ("L – R Standing …" / "L – R Seated …")
    separated by semicolons — a pattern the heuristic HTML extractor cannot follow.
    Skipped when ``GROQ_API_KEY`` is unset so this stays green in CI without keys.
    """
    import os

    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping live AI extraction test")

    from scripts.discovery.contact_extract_crawl4ai import extract_contact_directory_sync

    directory = extract_contact_directory_sync("https://applingcountyga.org/?page_id=1464")
    extracted_names = {
        (rec.name or "").strip().lower() for rec in directory.contacts if rec.name
    }

    expected_names = {
        "reid lovett",
        "daryl edwards",
        "jakharis jones",
        "chad kent",
        "leslie burch",
        "randy sellers",
        "ricky barnes",
    }
    missing = expected_names - extracted_names
    assert not missing, (
        f"applingcountyga.org/?page_id=1464: AI extractor missed {sorted(missing)}; "
        f"got {sorted(extracted_names)}"
    )


_BAKER_DIR = _GA_COUNTY_CACHE / "baker_13007"
_BAKER_BOC_PAGE_URL = "https://www.bakercountyga.com/board-of-commissioners-1"
_BAKER_EXPECTED_NAMES = frozenset({
    "connie hobbs",
    "vann irvin",
    "matt bryan",
    "tommy rentz",
    "chris moore",
})
_BAKER_EXPECTED_HEADSHOTS = frozenset({
    "headshot_ConnieHobbs-768x1024_edited.jpg",
    "headshot_VannIrvin-768x1024_edited.jpg",
    "headshot_MattBryan-768x1024_edited.jpg",
    "headshot_TommyRentz-768x1024_edited.jpg",
})


def test_baker_cache_proves_commissioners_page_was_crawled_and_extracted() -> None:
    """Offline regression on baker_13007/: BOC page must yield all 5 commissioners.

    Baker County's board-of-commissioners-1 page (Wix-built) lists the 5 commissioners
    as ``<h2>Name, District</h2>`` headings paired with ``<img alt="headshot_<Name>-...
    _edited.jpg">`` tags. The cached snapshot
    (``page__board-of-commissioners-1.html``) contains every name and headshot today,
    but the structured extractor currently recovers none of them.

    This test fails until the rebuilt bundle includes:
      1. ``board-of-commissioners-1`` in ``pages_fetched`` (proves the crawl reached it),
      2. ``person_name`` rows for all five commissioners (Connie Hobbs, Vann Irvin,
         Matt Bryan, Tommy Rentz, Chris Moore), and
      3. the four named headshot filenames referenced on that page
         (ConnieHobbs / VannIrvin / MattBryan / TommyRentz).

    If this test fails, the fix is upstream: teach the Wix-style HTML extractor to
    pair adjacent rich-text headings with their sibling headshot ``<img>`` and to
    resolve ``srcSet`` URLs against ``static.wixstatic.com`` (the manifest currently
    records them rooted at the county domain, which 404s).
    """
    manifest_path = _BAKER_DIR / "_manifest.json"
    assert manifest_path.is_file(), (
        f"baker_13007: missing _manifest.json at {manifest_path} — crawl never ran"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pages_fetched = [str(u) for u in (manifest.get("pages_fetched") or [])]
    assert _BAKER_BOC_PAGE_URL in pages_fetched, (
        f"baker_13007: {_BAKER_BOC_PAGE_URL} not in pages_fetched; "
        f"got {pages_fetched}. The crawler must reach the BOC page."
    )

    bundle = _regenerate_contacts_bundle(_BAKER_DIR)
    extracted_names = {
        str(r.get("person_name") or "").strip().lower()
        for r in bundle.get("contacts", [])
        if r.get("person_name")
    }
    missing_names = _BAKER_EXPECTED_NAMES - extracted_names
    assert not missing_names, (
        f"baker_13007: contacts bundle missing {sorted(missing_names)} from "
        f"{_BAKER_BOC_PAGE_URL}; got {sorted(extracted_names)}"
    )

    bundle_blob = json.dumps(bundle, ensure_ascii=False)
    missing_headshots = sorted(
        h for h in _BAKER_EXPECTED_HEADSHOTS if h not in bundle_blob
    )
    assert not missing_headshots, (
        f"baker_13007: rebuilt bundle does not reference headshot filenames "
        f"{missing_headshots} from {_BAKER_BOC_PAGE_URL}"
    )


_BERRIEN_DIR = _GA_COUNTY_CACHE / "berrien_13019"
_BERRIEN_BOC_PAGE_URL = "https://berriencountygeorgia.com/commissioners/"
_BERRIEN_EXPECTED_COMMISSIONERS: Tuple[Tuple[str, str], ...] = (
    ("john nugent", "district 1"),
    ("ronnie gaskins", "district 2"),
    ("jimmy parker", "district 3"),
    ("kylon fort", "district 4"),
    ("david harrod", "district 5"),
)

_BANKS_DIR = _GA_COUNTY_CACHE / "banks_13011"
_BANKS_BOC_PAGE_URL = "https://www.bankscountyga.org/1227/Board-of-Commissioners"
_BANKS_DANNY_EXPECTED = {
    "person_name": "danny maxwell",
    "title_or_role": "vice chairman district 1",
    "phone": "(706) 654-8326",
    "email": "djmaxwell@co.banks.ga.us",
}

_BULLOCH_DIR = _GA_COUNTY_CACHE / "bulloch_13031"
_BULLOCH_BOC_PAGE_PATH = "/commissioners/"
_BULLOCH_EXPECTED_EMAILS = frozenset(
    {
        "dbennett@bullochcounty.net",
        "rmosley@bullochcounty.net",
        "asimmons@bullochcounty.net",
        "rdavis@bullochcounty.net",
        "toby.conner@bullochcounty.net",
        "nnewkirk@bullochcounty.net",
        "trushing@bullochcounty.net",
    }
)


def test_berrien_cache_proves_commissioners_page_was_crawled_and_extracted() -> None:
    """Offline regression on berrien_13019/: BOC page must yield exactly 5 commissioners.

    Berrien County's commissioners page (Elementor-built WordPress) lists the 5
    commissioners as ``elementor-image-box`` blocks pairing
    ``<h3 class="elementor-image-box-title">Name</h3>`` with
    ``<p class="elementor-image-box-description">District N</p>``. The cached
    snapshot (``page__commissioners_.html``) contains every name and district
    label today, but the structured extractor currently recovers only the staff
    ``mailto:`` rows (Brenda/Teresa/Jenny/Ashley) and none of the elected officials.

    This test fails until the rebuilt bundle includes person rows for all five
    commissioners — John Nugent (District 1), Ronnie Gaskins (District 2),
    Jimmy Parker (District 3), Kylon Fort (District 4), David Harrod (District 5) —
    each with their district as ``title_or_role``.

    If this test fails, the fix is upstream: teach the Elementor HTML extractor to
    pair adjacent ``elementor-image-box-title`` headings with their sibling
    ``elementor-image-box-description`` so name + district are emitted together.
    """
    manifest_path = _BERRIEN_DIR / "_manifest.json"
    assert manifest_path.is_file(), (
        f"berrien_13019: missing _manifest.json at {manifest_path} — crawl never ran"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pages_fetched = [str(u) for u in (manifest.get("pages_fetched") or [])]
    assert _BERRIEN_BOC_PAGE_URL in pages_fetched, (
        f"berrien_13019: {_BERRIEN_BOC_PAGE_URL} not in pages_fetched; "
        f"got {pages_fetched}. The crawler must reach the BOC page."
    )

    bundle = _regenerate_contacts_bundle(_BERRIEN_DIR)
    extracted_pairs = {
        (
            str(r.get("person_name") or "").strip().lower(),
            str(r.get("title_or_role") or "").strip().lower(),
        )
        for r in bundle.get("contacts", [])
        if r.get("person_name")
        and str(r.get("source_page_url") or "") == _BERRIEN_BOC_PAGE_URL
    }
    missing_pairs = sorted(set(_BERRIEN_EXPECTED_COMMISSIONERS) - extracted_pairs)
    assert not missing_pairs, (
        f"berrien_13019: contacts bundle missing {missing_pairs} from "
        f"{_BERRIEN_BOC_PAGE_URL}; got {sorted(extracted_pairs)}"
    )

    commissioner_names = {name for name, _ in _BERRIEN_EXPECTED_COMMISSIONERS}
    extracted_commissioner_rows = [
        r for r in bundle.get("contacts", [])
        if str(r.get("person_name") or "").strip().lower() in commissioner_names
        and str(r.get("source_page_url") or "") == _BERRIEN_BOC_PAGE_URL
    ]
    assert len(extracted_commissioner_rows) == 5, (
        f"berrien_13019: expected exactly 5 commissioner rows from "
        f"{_BERRIEN_BOC_PAGE_URL}, got {len(extracted_commissioner_rows)}: "
        f"{[(r.get('person_name'), r.get('title_or_role')) for r in extracted_commissioner_rows]}"
    )


def test_banks_cache_requires_danny_maxwell_full_contact_fields() -> None:
    """Banks County BOC page must emit Danny Maxwell with name, role, phone, and email.

    This fails unless the rebuilt bundle includes a contact row from
    ``/1227/Board-of-Commissioners`` with all of:
      - person_name = Danny Maxwell
      - title_or_role = Vice Chairman District 1
      - phone = (706) 654-8326
      - email = djmaxwell@co.banks.ga.us
    """
    manifest_path = _BANKS_DIR / "_manifest.json"
    assert manifest_path.is_file(), (
        f"banks_13011: missing _manifest.json at {manifest_path} — crawl never ran"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pages_fetched = [str(u) for u in (manifest.get("pages_fetched") or [])]
    assert _BANKS_BOC_PAGE_URL in pages_fetched, (
        f"banks_13011: {_BANKS_BOC_PAGE_URL} not in pages_fetched; got {pages_fetched}"
    )

    bundle = _regenerate_contacts_bundle(_BANKS_DIR)
    target_rows = [
        r
        for r in bundle.get("contacts", [])
        if str(r.get("source_page_url") or "") == _BANKS_BOC_PAGE_URL
        and str(r.get("email") or "").strip().lower() == _BANKS_DANNY_EXPECTED["email"]
    ]
    assert target_rows, (
        "banks_13011: missing Danny Maxwell email row from "
        f"{_BANKS_BOC_PAGE_URL}; got emails "
        f"{sorted({str(r.get('email') or '').lower() for r in bundle.get('contacts', []) if r.get('email')})}"
    )

    row = target_rows[0]
    assert str(row.get("person_name") or "").strip().lower() == _BANKS_DANNY_EXPECTED["person_name"], (
        f"banks_13011: expected person_name {_BANKS_DANNY_EXPECTED['person_name']!r} "
        f"for {_BANKS_DANNY_EXPECTED['email']}, got {row.get('person_name')!r}"
    )
    assert str(row.get("title_or_role") or "").strip().lower() == _BANKS_DANNY_EXPECTED["title_or_role"], (
        f"banks_13011: expected title_or_role {_BANKS_DANNY_EXPECTED['title_or_role']!r} "
        f"for {_BANKS_DANNY_EXPECTED['email']}, got {row.get('title_or_role')!r}"
    )
    assert str(row.get("phone") or "").strip() == _BANKS_DANNY_EXPECTED["phone"], (
        f"banks_13011: expected phone {_BANKS_DANNY_EXPECTED['phone']!r} "
        f"for {_BANKS_DANNY_EXPECTED['email']}, got {row.get('phone')!r}"
    )


def test_bulloch_cache_proves_commissioners_page_was_crawled_and_extracted() -> None:
    """Bulloch commissioners page must be crawled and yield commissioner emails.

    Asserts that the cache includes a fetched ``/commissioners/`` page and that
    rebuilt contacts contain the seven commissioner emails sourced from that page.
    """
    manifest_path = _BULLOCH_DIR / "_manifest.json"
    assert manifest_path.is_file(), (
        f"bulloch_13031: missing _manifest.json at {manifest_path} — crawl never ran"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pages_fetched = [str(u) for u in (manifest.get("pages_fetched") or [])]
    commissioners_pages = [u for u in pages_fetched if _BULLOCH_BOC_PAGE_PATH in u]
    assert commissioners_pages, (
        f"bulloch_13031: no fetched URL contains {_BULLOCH_BOC_PAGE_PATH!r}; "
        f"got {pages_fetched}"
    )

    bundle = _regenerate_contacts_bundle(_BULLOCH_DIR)
    contacts = list(bundle.get("contacts") or [])
    by_email = {
        str(r.get("email") or "").strip().lower(): r
        for r in contacts
        if str(r.get("email") or "").strip()
    }
    extracted_emails = set(by_email.keys())

    missing = sorted(_BULLOCH_EXPECTED_EMAILS - extracted_emails)
    assert not missing, (
        f"bulloch_13031: missing commissioner emails {missing}; "
        f"got {sorted(extracted_emails)}"
    )

    wrong_source = []
    for email in sorted(_BULLOCH_EXPECTED_EMAILS):
        src = str((by_email.get(email) or {}).get("source_page_url") or "")
        if _BULLOCH_BOC_PAGE_PATH not in src:
            wrong_source.append((email, src))
    assert not wrong_source, (
        "bulloch_13031: commissioner emails were not attributed to commissioners page: "
        f"{wrong_source}"
    )


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
