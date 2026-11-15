"""DC-1.3 (#248): application-link checks and the 30-day staleness rule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

import ingestion.data_centers.application_links as al
from ingestion.data_centers.application_links import (
    check_link,
    classify,
    is_http_url,
    is_stale,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    """Test hosts don't resolve here: treat example.com names as public, IPs by their class."""
    real = al.host_is_public

    def fake(host):
        if host and host.endswith("example.com"):
            return True
        return real(host)

    monkeypatch.setattr(al, "host_is_public", fake)


@pytest.mark.parametrize(
    ("code", "expected"),
    [(200, "live"), (301, "live"), (404, "dead"), (410, "dead"), (403, "error"), (500, "error"), (None, "error")],
)
def test_classify(code, expected) -> None:
    assert classify(code) == expected


def test_is_stale_rules() -> None:
    assert is_stale(None, NOW) is True
    assert is_stale(NOW - timedelta(days=29), NOW) is False
    assert is_stale(NOW - timedelta(days=30), NOW) is False
    assert is_stale(NOW - timedelta(days=31), NOW) is True
    # A naive timestamp is read as UTC rather than raising.
    assert is_stale((NOW - timedelta(days=2)).replace(tzinfo=None), NOW) is False


def test_is_http_url() -> None:
    assert is_http_url("https://jobs.example.com/apply")
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url("jobs.example.com")
    assert not is_http_url(None)


def test_live_page_is_verified() -> None:
    result = check_link("https://jobs.example.com/a", client=_client(lambda r: httpx.Response(200)))
    assert result.status == "live" and result.http_status == 200 and result.verified


def test_gone_page_is_dead_and_not_verified() -> None:
    result = check_link("https://jobs.example.com/a", client=_client(lambda r: httpx.Response(404)))
    assert result.status == "dead" and not result.verified


def test_head_refused_falls_back_to_get() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(405 if request.method == "HEAD" else 200)

    result = check_link("https://jobs.example.com/a", client=_client(handler))
    assert seen == ["HEAD", "GET"] and result.status == "live"


def test_network_failure_is_error_not_dead() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    result = check_link("https://jobs.example.com/a", client=_client(handler))
    assert result.status == "error" and result.http_status is None


def test_non_http_url_is_never_requested() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("requested a non-http URL")

    assert check_link("ftp://example.com/x", client=_client(handler)).status == "error"


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/", "http://localhost:8001/"],
)
def test_private_hosts_are_refused_without_a_request(url) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError(f"requested {request.url}")

    assert check_link(url, client=_client(handler)).status == "error"


def test_redirect_to_a_private_host_is_refused() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    result = check_link("https://jobs.example.com/a", client=_client(handler))
    assert result.status == "error" and seen == ["https://jobs.example.com/a"]


def test_public_redirects_are_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200)

    assert check_link("https://jobs.example.com/old", client=_client(handler)).status == "live"


def test_redirect_loop_is_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://jobs.example.com/loop"})

    assert check_link("https://jobs.example.com/loop", client=_client(handler)).status == "error"
