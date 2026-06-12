"""Small pure text helpers shared across packages.

``slug_snake_case`` lives here (a low-level home) so callers such as
``core_lib.jurisdictions`` and ``scrapers.youtube`` can depend on it without
pointing the dependency arrow upward into ``scrapers``.
"""

from __future__ import annotations

import re

__all__ = ["slug_snake_case"]


def slug_snake_case(text: str, *, max_length: int = 64) -> str:
    """Lowercase snake_case for cache directory names (non-alphanumeric → single ``_``)."""
    if not text:
        return "unknown"
    s = str(text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_length].rstrip("_") or "unknown")
