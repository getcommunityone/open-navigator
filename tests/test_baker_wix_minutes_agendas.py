"""Baker County Wix minutes-and-agendas page: PDF links use aria-label, not table <a>."""

from pathlib import Path

from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import MEETING_HINTS
from scripts.discovery.meetings_platform_heuristics import (
    classify_document,
    extract_meeting_urls,
)

_BAKER_MINUTES = "https://www.bakercountyga.com/minutes-and-agendas"
_HOME = "https://www.bakercountyga.com/"


def test_baker_wix_ugd_pdfs_classified_via_aria_label() -> None:
    import urllib.request

    try:
        with urllib.request.urlopen(
            "https://www.bakercountyga.com/minutes-and-agendas",
            timeout=30,
        ) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except OSError:
        import pytest

        pytest.skip("network unavailable for Baker County minutes page")
    _, pdfs = extract_meeting_urls(raw, _BAKER_MINUTES, _HOME, generic_hint=MEETING_HINTS)
    assert len(pdfs) >= 10
    types = {classify_document(url, anchor) for url, anchor in pdfs}
    assert "agenda" in types
    assert "minutes" in types
    labeled = [a for _, a in pdfs if a.strip()]
    assert len(labeled) >= 10


def test_link_anchor_text_snippet() -> None:
    from bs4 import BeautifulSoup

    html = """
    <a href="/_files/ugd/foo.pdf" aria-label="July 2022 Agenda" target="_blank"></a>
    <a href="/_files/ugd/bar.pdf" title="August 2 minutes"></a>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    from scripts.discovery.meetings_platform_heuristics import _link_anchor_text

    assert _link_anchor_text(links[0]) == "July 2022 Agenda"
    assert _link_anchor_text(links[1]) == "August 2 minutes"
    assert classify_document(links[0]["href"], _link_anchor_text(links[0])) == "agenda"
    assert classify_document(links[1]["href"], _link_anchor_text(links[1])) == "minutes"
