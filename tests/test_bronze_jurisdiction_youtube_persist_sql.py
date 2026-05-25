"""SQL placeholder arity for bronze YouTube persist (no DB required)."""

from __future__ import annotations

import re
from pathlib import Path


def _upsert_verified_sql() -> str:
    text = Path("scripts/discovery/int_events_channels_persist.py").read_text()
    start = text.index(
        "INSERT INTO intermediate.int_events_channels (",
        text.index("def upsert_int_events_channels_verified"),
    )
    end = text.index('"""', start)
    return text[start:end]


def test_upsert_verified_preserves_metadata_on_null_conflict():
    sql = _upsert_verified_sql()
    assert "subscriber_count = COALESCE(" in sql
    assert "EXCLUDED.subscriber_count,\n                            intermediate.int_events_channels.subscriber_count" in sql
    assert "video_count = COALESCE(" in sql
    assert "external_links = CASE" in sql
