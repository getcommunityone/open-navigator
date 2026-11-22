"""YouTube Data API key pool (#716)."""

from __future__ import annotations

import pytest

from scrapers.youtube import youtube_api_keys as yak


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    yak.reset_youtube_key_pool()
    for i in range(1, 11):
        monkeypatch.delenv(f"YOUTUBE_API_KEY_{i}", raising=False)
        monkeypatch.delenv(f"YOUTUBE_KEY_TIER_{i}", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_KEY_TIER", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEYS", raising=False)
    monkeypatch.delenv("YOUTUBE_USE_TIER", raising=False)
    yield
    yak.reset_youtube_key_pool()


def test_resolve_numbered_and_plain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY_1", "key-one")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_1", "free")
    monkeypatch.setenv("YOUTUBE_API_KEY_2", "key-two")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_2", "free")
    # Legacy alias of KEY_1 — same value, tagged free so it does not sort as untagged.
    monkeypatch.setenv("YOUTUBE_API_KEY", "key-one")
    monkeypatch.setenv("YOUTUBE_KEY_TIER", "free")
    assert yak.resolve_youtube_api_keys(env_path="/nonexistent/.env") == [
        "key-one",
        "key-two",
    ]


def test_resolve_free_before_paid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY_1", "paid-first")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_1", "paid")
    monkeypatch.setenv("YOUTUBE_API_KEY_2", "free-second")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_2", "free")
    assert yak.resolve_youtube_api_keys(env_path="/nonexistent/.env", tier="all") == [
        "free-second",
        "paid-first",
    ]
    assert yak.resolve_youtube_api_keys(env_path="/nonexistent/.env", tier="free") == [
        "free-second"
    ]


def test_rotate_on_exhausted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY_1", "key-a")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_1", "free")
    monkeypatch.setenv("YOUTUBE_API_KEY_2", "key-b")
    monkeypatch.setenv("YOUTUBE_KEY_TIER_2", "paid")
    yak.reset_youtube_key_pool()
    assert yak.youtube_api_key() == "key-a"
    assert yak.mark_youtube_key_exhausted("key-a") == "key-b"
    assert yak.youtube_api_key() == "key-b"
    assert yak.mark_youtube_key_exhausted("key-b") is None


def test_is_youtube_quota_error():
    assert yak.is_youtube_quota_error(RuntimeError("quotaExceeded"))
    assert not yak.is_youtube_quota_error(RuntimeError("not found"))
