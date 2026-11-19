"""Normalize bronze YouTube ``channel_type`` labels (#562).

Landed rows historically used both ``municipal`` and ``municipality`` (and
``unknown``) for the same city channel. Staging already maps ``municipality`` →
``municipal``; keep bronze consistent at write time.
"""

from __future__ import annotations

# Accepted values used by stg_youtube__event / contracts.
CANONICAL_CHANNEL_TYPES = frozenset({"municipal", "county", "state", "school", "unknown"})

_ALIASES = {
    "municipality": "municipal",
    "city": "municipal",
    "town": "municipal",
    "village": "municipal",
    "municipal": "municipal",
    "county": "county",
    "parish": "county",
    "state": "state",
    "commonwealth": "state",
    "school": "school",
    "school_district": "school",
    "education": "school",
    "unknown": "unknown",
    "": "unknown",
}


def normalize_channel_type(raw: str | None) -> str:
    """Return a canonical channel_type label."""
    key = (raw or "").strip().lower()
    return _ALIASES.get(key, key if key in CANONICAL_CHANNEL_TYPES else "unknown")
