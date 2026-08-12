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
