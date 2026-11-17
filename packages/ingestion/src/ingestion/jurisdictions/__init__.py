"""Jurisdiction-level ingestion + analysis libraries.

See ``mapping`` for jurisdiction website / YouTube mapping-quality analysis
(shared SQL, state ACS rollups, live YouTube diagnostics, dashboard JSON export,
and Hugging Face Parquet publisher).
"""
from __future__ import annotations

from ingestion.jurisdictions.columns import (
    DETAILS_TO_JURISDICTION,
    JURISDICTION_TABLE,
    map_legacy_jurisdiction_column,
)

__all__ = [
    "JURISDICTION_TABLE",
    "DETAILS_TO_JURISDICTION",
    "map_legacy_jurisdiction_column",
]
