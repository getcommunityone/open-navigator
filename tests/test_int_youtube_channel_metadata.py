"""Tests for int YouTube channel metadata cache helpers."""

from scripts.discovery.int_youtube_channel_metadata import _norm_channel_id


def test_norm_channel_id_accepts_uc_only():
    assert _norm_channel_id("UCabc123def456") == "UCabc123def456"
    assert _norm_channel_id("@CityOfFoo") is None
    assert _norm_channel_id("") is None
