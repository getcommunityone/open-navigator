"""Unit tests for api/origins.py — the CORS + OAuth-redirect allowlist.

These guard the fix for the OAuth token-exfiltration bug: an attacker-controlled
redirect_uri must never be treated as a safe post-login redirect target.
"""
import importlib

import pytest


@pytest.fixture
def origins(monkeypatch):
    """Reload the module fresh so env changes take effect (allowed_origins is
    lru_cached for the process lifetime)."""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    import api.origins as mod

    importlib.reload(mod)
    yield mod
    # Leave a clean module for the next test.
    importlib.reload(mod)


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
    import api.origins as mod

    importlib.reload(mod)
    try:
        assert mod.is_allowed_origin("https://only.example")
        # A default that is NOT in the explicit list must now be rejected.
        assert not mod.is_allowed_origin("https://www.communityone.com")
        assert not mod.is_allowed_origin("http://localhost:5173")
    finally:
        importlib.reload(mod)


def test_default_port_normalization(origins):
    assert origins.is_allowed_origin("https://www.communityone.com:443")
    assert origins.is_allowed_origin("http://localhost:5173")
