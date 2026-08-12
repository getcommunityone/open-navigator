"""Unit tests for api/origins.py — the CORS + OAuth-redirect allowlist.

These guard the fix for the OAuth token-exfiltration bug: an attacker-controlled
redirect_uri must never be treated as a safe post-login redirect target.
"""
import pytest

import api.origins as mod


@pytest.fixture
def origins(monkeypatch):
    """Clear the lru_cache so this test's env takes effect (allowed_origins reads
    CORS_ALLOWED_ORIGINS and FRONTEND_URL inside the cached call)."""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    mod.allowed_origins.cache_clear()
    yield mod
    # Leave a clean cache for the next test (monkeypatch restores the env first).
    mod.allowed_origins.cache_clear()


def test_frontend_url_is_trusted(origins):
    assert origins.is_allowed_origin("https://app.example.com")
    assert origins.is_safe_redirect("https://app.example.com")


def test_default_dev_and_prod_origins(origins):
    assert origins.is_allowed_origin("http://localhost:5173")
    assert origins.is_allowed_origin("https://www.communityone.com")


def test_attacker_origin_rejected(origins):
    assert not origins.is_allowed_origin("https://evil.example")
    assert not origins.is_safe_redirect("https://evil.example/collect")


def test_relative_path_is_safe_but_not_protocol_relative(origins):
    assert origins.is_safe_redirect("/dashboard")
    assert not origins.is_safe_redirect("//evil.example")
    assert not origins.is_safe_redirect("/\\evil.example")


def test_absent_redirect_is_safe(origins):
    assert origins.is_safe_redirect(None)
    assert origins.is_safe_redirect("")


@pytest.mark.parametrize(
    "value",
    [
        "https://x:99999",          # port out of range
        "https://good.com:70000",   # port out of range
        "http://a:-1",              # negative port
        "http://a:notaport",        # non-numeric port
        "https://[::1",             # invalid IPv6 literal
    ],
)
def test_malformed_origin_is_rejected_not_raised(origins, value):
    # urlsplit()/.port raise ValueError on these. The validator must swallow it
    # and treat the value as unusable, never propagate a 500 to the login
    # endpoint or crash the app at CORS-middleware construction.
    assert origins._normalize_origin(value) is None
    assert not origins.is_allowed_origin(value)
    assert not origins.is_safe_redirect(value)


@pytest.mark.parametrize(
    "value",
    ["/\t/evil.example", "/\r\n//evil.example", "/\n/evil.example"],
)
def test_control_char_smuggled_path_rejected(origins, value):
    # WHATWG strips tab/CR/LF before parsing, so "/\t/evil" resolves to the
    # protocol-relative "//evil" in a browser. The validator strips them too,
    # so it must NOT accept these as safe same-origin paths.
    assert not origins.is_safe_redirect(value)


def test_wildcard_never_enters_allowlist(monkeypatch):
    # A "*" in the env must not resurrect the reflect-any-origin CORS bug.
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    mod.allowed_origins.cache_clear()
    try:
        assert "*" not in mod.allowed_origins()
        assert not mod.is_allowed_origin("https://evil.example")
    finally:
        mod.allowed_origins.cache_clear()


def test_explicit_allowlist_overrides_defaults(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://only.example")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    mod.allowed_origins.cache_clear()
    try:
        assert mod.is_allowed_origin("https://only.example")
        # A default that is NOT in the explicit list must now be rejected.
        assert not mod.is_allowed_origin("https://www.communityone.com")
        assert not mod.is_allowed_origin("http://localhost:5173")
    finally:
        mod.allowed_origins.cache_clear()


def test_default_port_normalization(origins):
    assert origins.is_allowed_origin("https://www.communityone.com:443")
    assert origins.is_allowed_origin("http://localhost:5173")
