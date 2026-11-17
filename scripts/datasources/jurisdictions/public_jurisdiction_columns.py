"""Backward-compatible shim for ``ingestion.jurisdictions.columns``."""
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
