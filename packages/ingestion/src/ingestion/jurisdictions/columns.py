"""Canonical jurisdiction table and legacy column mapping definitions."""
from __future__ import annotations

JURISDICTION_TABLE = "jurisdiction"

# Legacy jurisdictions_details_search column -> public.jurisdiction column
DETAILS_TO_JURISDICTION: dict[str, str] = {
    "jurisdiction_name": "name",
    "jurisdiction_type": "type",
    "status": "discovery_status",
}


def map_legacy_jurisdiction_column(column_name: str) -> str:
    """Translate a legacy jurisdictions_details_search column name to public.jurisdiction."""
    cleaned = (column_name or "").strip()
    return DETAILS_TO_JURISDICTION.get(cleaned, cleaned)


__all__ = [
    "JURISDICTION_TABLE",
    "DETAILS_TO_JURISDICTION",
    "map_legacy_jurisdiction_column",
]
