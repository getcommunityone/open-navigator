"""YouTube Data API key pool (#716)."""

from __future__ import annotations

import pytest

from scrapers.youtube import youtube_api_keys as yak


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    yak.reset_youtube_key_pool()
    for i in range(1, 11):
        monkeypatch.delenv(f"YOUTUBE_API_KEY_{i}", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEYS", raising=False)
    yield
    yak.reset_youtube_key_pool()


def test_resolve_numbered_and_plain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY_1", "key-one")
    monkeypatch.setenv("YOUTUBE_API_KEY_2", "key-two")
    monkeypatch.setenv("YOUTUBE_API_KEY", "key-one")  # dedupe
    assert yak.resolve_youtube_api_keys(env_path="/nonexistent/.env") == [
        "key-one",
        "key-two",
    ]


def test_rotate_on_exhausted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY_1", "key-a")
    monkeypatch.setenv("YOUTUBE_API_KEY_2", "key-b")
    yak.reset_youtube_key_pool()
    assert yak.youtube_api_key() == "key-a"
    assert yak.mark_youtube_key_exhausted("key-a") == "key-b"
    assert yak.youtube_api_key() == "key-b"
    assert yak.mark_youtube_key_exhausted("key-b") is None


def test_is_youtube_quota_error():
    assert yak.is_youtube_quota_error(RuntimeError("quotaExceeded"))
    assert not yak.is_youtube_quota_error(RuntimeError("not found"))
