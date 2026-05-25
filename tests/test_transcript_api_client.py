"""youtube-transcript-api wrapper helpers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from scripts.datasources.youtube.transcript_api_client import (
    _fetched_to_payload,
    build_proxy_config,
    build_youtube_transcript_api,
    describe_caption_egress,
    fetch_transcript_from_api,
    format_transcript_error,
    resolve_webshare_filter_ip_locations,
    resolve_webshare_proxy_credentials,
    summarize_transcript_payload,
    transcript_failure_hint,
    resolve_ytdlp_proxy_url,
)


def test_fetched_to_payload_builds_segments():
    snippet = MagicMock(text="hello", start=1.0, duration=2.0)
    fetched = MagicMock(snippets=[snippet])
    out = _fetched_to_payload("abc123", fetched, language="en", is_auto=False)
    assert out["video_id"] == "abc123"
    assert out["raw_text"] == "hello"
    assert out["transcript_source"] == "youtube_transcript_api"
    assert out["segments"][0]["start"] == 1.0


def test_resolve_webshare_proxy_credentials_from_env():
    with patch.dict(
        os.environ,
        {"PROXY_USER_NAME": "user1", "PROXY_PASSWORD": "secret"},
        clear=False,
    ):
        assert resolve_webshare_proxy_credentials() == ("user1", "secret")


def test_format_transcript_error_includes_cause_chain():
    try:
        raise ValueError("inner")
    except ValueError as inner:
        try:
            raise RuntimeError("outer") from inner
        except RuntimeError as outer:
            text = format_transcript_error(outer, max_len=500)
    assert "RuntimeError: outer" in text
    assert "ValueError: inner" in text


def test_transcript_failure_hint_proxy():
    hint = transcript_failure_hint("ProxyError: max retries exceeded with proxy")
    assert hint is not None
    assert "PROXY_USER_NAME" in hint


def test_transcript_failure_hint_407():
    hint = transcript_failure_hint(
        "Tunnel connection failed: 407 Proxy Authentication Required"
    )
    assert hint is not None
    assert "407" in hint
    assert "proxy/settings" in hint


def test_resolve_webshare_filter_ip_locations():
    with patch.dict(
        os.environ,
        {"WEBSHARE_FILTER_IP_LOCATIONS": "de, US ,ca"},
        clear=False,
    ):
        assert resolve_webshare_filter_ip_locations() == ["de", "us", "ca"]
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_webshare_filter_ip_locations() is None


@patch.dict(os.environ, {}, clear=True)
def test_resolve_ytdlp_proxy_url_prefers_explicit():
    assert resolve_ytdlp_proxy_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"


@patch.dict(
    os.environ,
    {
        "PROXY_USER_NAME": "ws_user",
        "PROXY_PASSWORD": "ws_pass",
        "WEBSHARE_FILTER_IP_LOCATIONS": "de,us",
        "WEBSHARE_RETRIES_WHEN_BLOCKED": "5",
    },
    clear=False,
)
@patch("scripts.datasources.youtube.transcript_api_client.WebshareProxyConfig")
def test_build_proxy_config_webshare_country_filter(mock_webshare: MagicMock):
    build_proxy_config()
    mock_webshare.assert_called_once_with(
        proxy_username="ws_user",
        proxy_password="ws_pass",
        retries_when_blocked=5,
        filter_ip_locations=["de", "us"],
    )


@patch("scripts.datasources.youtube.transcript_api_client.WebshareProxyConfig")
@patch.dict(
    os.environ,
    {"PROXY_USER_NAME": "ws_user", "PROXY_PASSWORD": "ws_pass"},
    clear=False,
)
def test_build_proxy_config_prefers_webshare(mock_webshare: MagicMock):
    mock_webshare.return_value.http_url = "http://ws_user-rotate:ws_pass@p.webshare.io:80/"
    cfg = build_proxy_config()
    mock_webshare.assert_called_once_with(
        proxy_username="ws_user",
        proxy_password="ws_pass",
        retries_when_blocked=10,
    )
    assert cfg is mock_webshare.return_value


@patch("scripts.datasources.youtube.transcript_api_client.WebshareProxyConfig")
@patch.dict(
    os.environ,
    {
        "PROXY_USER_NAME": "ws_user",
        "PROXY_PASSWORD": "ws_pass",
        "YOUTUBE_YTDLP_USE_WEBSHARE": "1",
    },
    clear=False,
)
def test_resolve_ytdlp_proxy_url_webshare_only_when_opt_in(mock_webshare: MagicMock):
    mock_webshare.return_value.http_url = "http://ws_user-rotate:ws_pass@p.webshare.io:80/"
    assert "webshare.io" in (resolve_ytdlp_proxy_url() or "")


@patch("scripts.datasources.youtube.transcript_api_client.YouTubeTranscriptApi")
@patch("scripts.datasources.youtube.transcript_api_client.build_proxy_config")
def test_build_youtube_transcript_api_passes_proxy_config(
    mock_proxy_cfg: MagicMock,
    mock_api: MagicMock,
):
    mock_proxy_cfg.return_value = MagicMock(name="proxy_config")
    build_youtube_transcript_api()
    mock_api.assert_called_once_with(
        proxy_config=mock_proxy_cfg.return_value,
        http_client=None,
    )


@patch(
    "scripts.datasources.youtube.transcript_api_client.fetch_transcript_bundle",
    return_value={
        "video_id": "vid1",
        "raw_text": "hi",
        "segments": [{"text": "hi", "start": 0.0, "duration": 1.0}],
        "language": "en",
        "is_auto_generated": True,
        "transcript_source": "youtube_transcript_api",
        "caption_raw_data": [],
        "caption_preserve_formatting": True,
    },
)
def test_fetch_transcript_from_api_delegates_to_bundle(mock_bundle: MagicMock):
    result = fetch_transcript_from_api(
        "vid1",
        cookies_file="/nonexistent/cookies.txt",
        retry_on_block=False,
    )
    mock_bundle.assert_called_once()
    assert result["raw_text"] == "hi"
    assert result["transcript_source"] == "youtube_transcript_api"


@patch.dict(
    os.environ,
    {"PROXY_USER_NAME": "ws_user", "PROXY_PASSWORD": "ws_pass", "WEBSHARE_FILTER_IP_LOCATIONS": "us"},
    clear=False,
)
def test_describe_caption_egress_webshare():
    info = describe_caption_egress(cookies_path="/tmp/cookies.txt", ytdlp_fallback=True)
    assert info["caption_egress_mode"] == "webshare"
    assert "ws_user" in info["caption_egress_detail"]
    assert info["webshare_configured"] is True
    assert info["ytdlp_egress_mode"] == "direct"


def test_summarize_transcript_payload():
    text = summarize_transcript_payload(
        {
            "transcript_source": "youtube_transcript_api",
            "language": "en",
            "is_auto_generated": True,
            "raw_text": "hello world",
            "segments": [{"text": "hello world", "start": 0, "duration": 1}],
        }
    )
    assert "youtube_transcript_api" in text
    assert "chars=11" in text
