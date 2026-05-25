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


def test_upsert_verified_placeholders_match_row_values():
    sql = _upsert_verified_sql()
    before_now = sql.split("NOW()")[0]
    placeholders = len(re.findall(r"%s", before_now))
    # _row_values returns 22 fields; upsert passes base[0], *base[1:], source, is_primary.
    expected_params = 22 + 2
    assert placeholders == expected_params
