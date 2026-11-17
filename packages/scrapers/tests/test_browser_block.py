"""The browser fallback is a plain browser: no stealth, and bot protection is reported as blocked.

Decision 2026-11-16 (issue #443). No network: every check runs on strings or source files.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from scrapers.discovery import browser_block, meetings_playwright_fetch
from scrapers.discovery.browser_block import (
    BlockedError,
    blocked_reason,
    challenge_page_reason,
    is_blocked_reason,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_STEALTH_IMPORT = re.compile(
    r"^\s*(from\s+playwright_stealth\b|import\s+playwright_stealth\b)", re.M
)

CLOUDFLARE_JUST_A_MOMENT = """<!DOCTYPE html><html lang="en-US"><head>
<title>Just a moment...</title>
<meta http-equiv="refresh" content="390">
</head><body><div class="main-wrapper" role="main">
<noscript>Enable JavaScript and cookies to continue</noscript>
<script>(function(){window._cf_chl_opt={cvId: '3',cZone: 'example.gov',cType: 'managed'};}());</script>
</div></body></html>"""

CLOUDFLARE_ATTENTION_REQUIRED = """<!DOCTYPE html><html><head>
<title>Attention Required! | Cloudflare</title></head>
<body><h1>Sorry, you have been blocked</h1><p>Cloudflare Ray ID: 8a1b2c3d4e5f</p></body></html>"""

AKAMAI_ACCESS_DENIED = """<HTML><HEAD>
<TITLE>Access Denied</TITLE>
</HEAD><BODY>
<H1>Access Denied</H1>
You don't have permission to access "http&#58;&#47;&#47;www&#46;example&#46;gov&#47;" on this server.<P>
Reference&#32;&#35;18&#46;5f3c1702&#46;1700000000&#46;1a2b3c4d
<P>https&#58;&#47;&#47;errors&#46;edgesuite&#46;net&#47;18&#46;5f3c1702
</BODY></HTML>"""

NORMAL_PAGE = """<!DOCTYPE html><html><head><title>City Council Meetings | Example City</title>
<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script></head>
<body><nav>Home | Departments | Contact</nav>
<h1>City Council Meetings</h1>
<ul><li><a href="/agendas/2026-11-03.pdf">Agenda, November 3, 2026</a></li>
<li><a href="https://www.youtube.com/@examplecitygov">Watch on YouTube</a></li></ul>
<form><div class="g-recaptcha" data-sitekey="abc"></div>Contact the clerk</form>
</body></html>"""


def _package_python_files() -> list[Path]:
    roots = [REPO_ROOT / "packages", REPO_ROOT / "api"]
    return [
        p
        for root in roots
        if root.is_dir()
        for p in root.rglob("*.py")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]


def test_no_playwright_stealth_import_in_packages_or_api() -> None:
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in _package_python_files()
        if _STEALTH_IMPORT.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert offenders == []


def test_playwright_stealth_not_declared_as_a_dependency() -> None:
    pyproject = (REPO_ROOT / "packages" / "scrapers" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "playwright-stealth" not in pyproject
    for req in REPO_ROOT.glob("requirements*.txt"):
        assert "playwright-stealth" not in req.read_text(encoding="utf-8"), req.name


def test_fetch_module_has_no_fingerprint_spoofing() -> None:
    src = Path(meetings_playwright_fetch.__file__).read_text(encoding="utf-8")
    code = src.split('"""', 2)[
        2
    ]  # skip the module docstring, which explains the policy
    assert "AutomationControlled" not in code
    assert "navigator, 'webdriver'" not in code
    assert "add_init_script" not in code
    assert "Sec-Fetch" not in code


def test_launch_options_have_no_anti_automation_flags() -> None:
    args = meetings_playwright_fetch._chromium_launch_options()["args"]
    assert not any("AutomationControlled" in a for a in args)


@pytest.mark.parametrize(
    ("html", "token"),
    [
        (CLOUDFLARE_JUST_A_MOMENT, "cloudflare_just_a_moment"),
        (CLOUDFLARE_ATTENTION_REQUIRED, "cloudflare_attention_required"),
        (AKAMAI_ACCESS_DENIED, "akamai_access_denied"),
    ],
)
def test_challenge_pages_are_blocked(html: str, token: str) -> None:
    assert challenge_page_reason(html) == token
    assert blocked_reason(200, html) == f"challenge:{token}"


def test_cloudflare_mitigated_header_is_blocked() -> None:
    assert blocked_reason(200, "<html></html>", {"CF-Mitigated": "challenge"}) == (
        "challenge:cloudflare_challenge"
    )


@pytest.mark.parametrize("status", [403, 429])
def test_blocked_statuses(status: int) -> None:
    assert blocked_reason(status, NORMAL_PAGE) == f"http_{status}"


def test_normal_page_passes() -> None:
    # A real page behind Cloudflare bot management with a form reCAPTCHA is not a challenge.
    assert challenge_page_reason(NORMAL_PAGE) is None
    assert blocked_reason(200, NORMAL_PAGE, {"server": "cloudflare"}) is None


@pytest.mark.parametrize("status", [401, 403, 429])
def test_blocks_are_never_retried_through_the_browser(status: int) -> None:
    assert meetings_playwright_fetch.httpx_status_should_try_playwright(status) is False


def test_blocked_reason_helpers() -> None:
    assert is_blocked_reason("blocked:http_403")
    assert not is_blocked_reason("playwright_http_404")
    assert not is_blocked_reason(None)
    err = BlockedError("https://example.gov/", "http_429")
    assert err.reason == "http_429" and "example.gov" in str(err)
    assert browser_block.BLOCKED_STATUSES == frozenset({403, 429})


class _FakeResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.headers = headers or {}


class _FakePage:
    def __init__(self, status: int, html: str) -> None:
        self._resp = _FakeResponse(status)
        self._html = html
        self.url = "https://example.gov/meetings"

    async def goto(self, url: str, **_: object) -> _FakeResponse:
        return self._resp

    async def content(self) -> str:
        return self._html

    async def wait_for_load_state(self, *_: object, **__: object) -> None:
        return None


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.kwargs: dict[str, object] = {}

    async def new_page(self) -> _FakePage:
        return self._page


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.context = _FakeContext(page)

    async def new_context(self, **kwargs: object) -> _FakeContext:
        self.context.kwargs = kwargs
        return self.context

    async def close(self) -> None:
        return None


def _run_fetch(
    monkeypatch: pytest.MonkeyPatch, status: int, html: str
) -> tuple[object, ...]:
    """Drive fetch_html_via_playwright against a fake browser (no Chromium, no network)."""
    import sys
    import types

    page = _FakePage(status, html)
    browser = _FakeBrowser(page)

    class _PW:
        async def __aenter__(self) -> "_PW":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    fake_async_api = types.ModuleType("playwright.async_api")
    fake_async_api.async_playwright = lambda: _PW()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_async_api)

    async def _launch(_p: object) -> _FakeBrowser:
        return browser

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr(meetings_playwright_fetch, "_launch_chromium_browser", _launch)
    monkeypatch.setattr(meetings_playwright_fetch.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(meetings_playwright_fetch, "_pw_sem_instance", None)
    monkeypatch.setenv("SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK", "true")
    result = asyncio.run(
        meetings_playwright_fetch.fetch_html_via_playwright(
            "https://example.gov/meetings", timeout_ms=5000, user_agent="ExampleUA/1.0"
        )
    )
    return result + (browser.context.kwargs,)


def test_fetch_html_reports_challenge_as_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html, reason, _final, _ctx = _run_fetch(monkeypatch, 200, CLOUDFLARE_JUST_A_MOMENT)
    assert html is None
    assert reason == "blocked:challenge:cloudflare_just_a_moment"


def test_fetch_html_reports_403_as_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    html, reason, _final, _ctx = _run_fetch(monkeypatch, 403, NORMAL_PAGE)
    assert html is None
    assert reason == "blocked:http_403"


def test_fetch_html_returns_normal_page(monkeypatch: pytest.MonkeyPatch) -> None:
    html, reason, _final, ctx = _run_fetch(monkeypatch, 200, NORMAL_PAGE)
    assert html == NORMAL_PAGE
    assert reason == ""
    # One fixed UA from the caller; no forged browser headers.
    assert ctx["user_agent"] == "ExampleUA/1.0"
    assert "extra_http_headers" not in ctx


class _HttpxLikeResponse:
    def __init__(self, url: str, text: str, status_code: int) -> None:
        self.url = url
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers: dict[str, str] = {}


@pytest.mark.parametrize(
    ("status", "html"),
    [(403, NORMAL_PAGE), (429, ""), (200, CLOUDFLARE_JUST_A_MOMENT)],
)
def test_youtube_discovery_moves_on_when_homepage_is_blocked(
    monkeypatch: pytest.MonkeyPatch, status: int, html: str
) -> None:
    """A blocked seed page is recorded and skipped: no site-search probes, no browser."""
    import sys
    import types

    from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

    pw_calls: list[str] = []

    async def fake_playwright_fetch(url: str, **_: object) -> tuple[None, str, str]:
        pw_calls.append(url)
        return None, "should-not-be-called", url

    fake_module = types.ModuleType("scrapers.discovery.meetings_playwright_fetch")
    fake_module.fetch_html_via_playwright = fake_playwright_fetch  # type: ignore[attr-defined]
    fake_module.playwright_fallback_enabled = lambda: True  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "scrapers.discovery.meetings_playwright_fetch", fake_module
    )

    async def _run() -> tuple[list[str], list[str]]:
        discovery = YouTubeChannelDiscovery()
        gets: list[str] = []

        async def fake_get(
            url: str, *args: object, **kwargs: object
        ) -> _HttpxLikeResponse:
            gets.append(url)
            return _HttpxLikeResponse(url, html, status)

        discovery.client.get = fake_get  # type: ignore[method-assign]
        try:
            channels = await discovery._scrape_website_for_channels(
                "https://example.gov/"
            )
        finally:
            await discovery.close()
        return channels, gets

    channels, gets = asyncio.run(_run())
    assert channels == []
    assert gets == ["https://example.gov/"]
    assert pw_calls == []
