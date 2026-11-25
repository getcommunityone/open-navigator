"""ingestion.data_centers.fetch_hearing_sources (#955): fetch official pages behind hearing leads.

The fetcher is a stand-in; nothing here touches the network or a database.
"""

from __future__ import annotations

import httpx
from ingestion.data_centers.fetch_hearing_sources import (
    clean_url,
    fetch_source,
    page_text,
)


class _Fetcher:
    def __init__(self, response: httpx.Response | None = None, error: Exception | None = None):
        self.response, self.error, self.urls = response, error, []

    def get(self, url: str) -> httpx.Response:
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.response  # type: ignore[return-value]


def _resp(status: int, body: bytes, ctype: str, url: str = "https://town.example.gov/agenda") -> httpx.Response:
    return httpx.Response(status, content=body, headers={"content-type": ctype}, request=httpx.Request("GET", url))


def test_clean_url_drops_tracking_parameters_only() -> None:
    url = "https://x.legistar.com/LegislationDetail.aspx?GUID=ABC&ID=8301424&Options&Search&utm_source=chatgpt.com"
    assert clean_url(url) == "https://x.legistar.com/LegislationDetail.aspx?GUID=ABC&ID=8301424&Options=&Search="
    # no tracking parameter: the official URL comes back exactly as given, not re-encoded
    plain = "https://x.legistar.com/LegislationDetail.aspx?GUID=ABC&ID=8301424&Options&Search"
    assert clean_url(plain) == plain
    assert clean_url("https://www.wichita.gov/datacenters?utm_source=chatgpt.com") == "https://www.wichita.gov/datacenters"


def test_html_page_keeps_main_content_text() -> None:
    body = b"<html><head><title>T</title></head><body><nav>Menu</nav><main><p>Public hearing on data centers, December 3</p></main></body></html>"
    page = fetch_source(_Fetcher(_resp(200, body, "text/html; charset=utf-8")), "lead-1", "https://town.example.gov/agenda?utm_source=x")
    assert page.error is None and page.http_status == 200
    assert page.page_text == "Public hearing on data centers, December 3"
    assert page.source_url == "https://town.example.gov/agenda"  # stored without the tracking parameter


def test_pdf_agenda_goes_through_the_pdf_extractor() -> None:
    seen = []
    text = page_text(b"%PDF-1.7 ...", "application/pdf", pdf_text=lambda b: seen.append(b) or "AGENDA data center moratorium")
    assert text == "AGENDA data center moratorium" and seen


def test_every_outcome_is_recorded_not_raised() -> None:
    blocked = fetch_source(_Fetcher(error=PermissionError("robots.txt disallows x")), "l", "https://x.gov/a")
    assert blocked.page_text is None and blocked.error.startswith("not fetched:")
    missing = fetch_source(_Fetcher(_resp(404, b"gone", "text/html")), "l", "https://x.gov/a")
    assert missing.error == "HTTP 404" and missing.page_text is None
    down = fetch_source(_Fetcher(error=httpx.ConnectError("refused")), "l", "https://x.gov/a")
    assert down.error.startswith("ConnectError")
    challenge = fetch_source(
        _Fetcher(_resp(200, b"<html><title>Just a moment...</title>Checking your browser cf-chl</html>", "text/html")),
        "l", "https://x.gov/a",
    )
    assert challenge.page_text is None and "bot challenge" in (challenge.error or "")


def test_scanned_pdf_says_why_it_has_no_text() -> None:
    page = fetch_source(_Fetcher(_resp(200, b"%PDF-1.7 scanned", "application/pdf")), "l", "https://x.gov/a.pdf",
                        pdf_text=lambda b: "  ")
    assert page.page_text is None and page.error == "PDF has no text layer (scanned?)"
