"""Unit tests for ChampDS API helpers."""

from __future__ import annotations

import pytest

from scripts.discovery.champds_client import (
    champds_api_host,
    parse_champds_archive_embed_url,
    vod_stream_url,
)


def test_champds_api_host() -> None:
    assert champds_api_host("play.champds.com") == "playapi.champds.com"


def test_parse_champds_archive_embed_url() -> None:
    u = "https://play.champds.com/gwinnettcoga/archive/1"
    assert parse_champds_archive_embed_url(u) == ("gwinnettcoga", 1)
    assert parse_champds_archive_embed_url("https://example.com/") is None


def test_vod_stream_url_vod2() -> None:
    svc = {
        "8": {
            "URLBase": "https://securestream11.champds.com",
            "URLFilename": "%MEDIA_PATH%",
        }
    }
    media = {"VOD2": "/VOD/event/GwinnettCoGA/311/x/master.m3u8"}
    assert vod_stream_url(svc, media) == (
        "https://securestream11.champds.com/VOD/event/GwinnettCoGA/311/x/master.m3u8"
    )


def test_vod_stream_url_missing_service() -> None:
    with pytest.raises(ValueError, match="missing ServicesAndMachineInfo"):
        vod_stream_url({}, {"VOD2": "/x.m3u8"})
