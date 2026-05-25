"""Deprecated: use ``scripts.discovery.int_events_channels_persist``."""

from scripts.discovery.int_events_channels_persist import (  # noqa: F401
    insert_bronze_jurisdiction_youtube,
    insert_bronze_jurisdiction_youtube_candidates,
    insert_int_events_channels_candidates,
    upsert_bronze_jurisdiction_youtube_verified,
    upsert_int_events_channels_verified,
)

__all__ = [
    "insert_bronze_jurisdiction_youtube",
    "insert_bronze_jurisdiction_youtube_candidates",
    "insert_int_events_channels_candidates",
    "upsert_bronze_jurisdiction_youtube_verified",
    "upsert_int_events_channels_verified",
]
