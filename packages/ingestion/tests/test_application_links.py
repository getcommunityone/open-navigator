"""DC-1.3 (#248): application-link checks and the 30-day staleness rule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from ingestion.data_centers.application_links import (
    check_link,
    classify,
    is_http_url,
    is_stale,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


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
