"""SQL placeholder arity for bronze YouTube persist (no DB required)."""

from __future__ import annotations

import re
from pathlib import Path


def _upsert_verified_sql() -> str:
    text = Path("scripts/discovery/bronze_jurisdiction_youtube_persist.py").read_text()
    start = text.index(
        "INSERT INTO bronze.bronze_jurisdiction_youtube (",
        text.index("def upsert_bronze_jurisdiction_youtube_verified"),
    )
    end = text.index('"""', start)
    return text[start:end]


def test_upsert_verified_preserves_metadata_on_null_conflict():
    sql = _upsert_verified_sql()
    assert "subscriber_count = COALESCE(" in sql
    assert "EXCLUDED.subscriber_count,\n                            bronze.bronze_jurisdiction_youtube.subscriber_count" in sql
    assert "video_count = COALESCE(" in sql
    assert "external_links = CASE" in sql
