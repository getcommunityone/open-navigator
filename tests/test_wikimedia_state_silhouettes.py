"""Wikimedia state silhouette title resolution."""

from __future__ import annotations

from ingestion.wikimedia.download import (
    _resolve_locator_title,
    _resolve_state_title,
)


def test_resolve_locator_and_state_titles():
    infos = {
        "File:Map of USA GA.svg": {
            "mime": "image/svg+xml",
            "url": "https://example.com/ga-locator.svg",
            "_page_title": "File:Map of USA GA.svg",
        },
        "File:State of Georgia.svg": {
            "mime": "image/svg+xml",
            "url": "https://upload.wikimedia.org/wikipedia/commons/b/b1/State_of_Georgia.svg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:State_of_Georgia.svg",
            "_page_title": "File:State of Georgia.svg",
        },
    }
    assert _resolve_locator_title("GA", infos) == ("File:Map of USA GA.svg", "map_of_usa")
    assert _resolve_state_title("Georgia", infos) == ("File:State of Georgia.svg", "state_of")
