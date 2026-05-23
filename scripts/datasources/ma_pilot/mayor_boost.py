"""
Mayor-specific extraction helpers.

The default directory classifier (``classify_contact_directory_page``) only flags a page
as a contact directory when ``score >= 18``. A single-bio mayor page (one person, one
photo, no roster) often misses that threshold even though the row is exactly what we
want to capture. These helpers:

1. Recognize mayor-style URLs (``/mayor``, ``/mayors-office``, ``mayor_s_office/``, …).
2. Tag mayor-titled rows from any extractor pass so callers can persist them
   unconditionally instead of discarding low-score pages.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

_MAYOR_URL_RE = re.compile(
    r"(?:^|[/_-])"
    r"(?:mayors?|mayor[-_]?s?[-_]?office|mayors?office|mayor_s_office)"
    r"(?:[/_.-]|$)",
    re.IGNORECASE,
)

_MAYOR_TITLE_RE = re.compile(r"\bmayor\b", re.IGNORECASE)


def is_mayor_seed_url(url: str) -> bool:
    """True when the URL path looks like a mayor's office / bio page."""
    if not url:
        return False
    try:
        path = (urlparse(url).path or "").lower()
    except Exception:
        return False
    if not path:
        return False
    return bool(_MAYOR_URL_RE.search(path))


def is_mayor_row(row: dict[str, Any]) -> bool:
    """True when a contact row has a Mayor-ish title.

    Excludes 'Vice Mayor' by itself by stripping that phrase before the match. A title
    like 'Mayor & Councilor-at-Large' or 'Acting Mayor' still matches.
    """
    title = str(row.get("title_or_role") or "").strip()
    if not title:
        return False
    stripped = re.sub(r"\bvice[\s-]?mayor\b", "", title, flags=re.IGNORECASE)
    return bool(_MAYOR_TITLE_RE.search(stripped))


def tag_mayor_rows(rows: Iterable[dict[str, Any]], *, source_page_url: str) -> list[dict[str, Any]]:
    """
    Return rows with ``is_mayor`` set to True for any row that should bypass the
    directory-score gate. Triggers when the source URL is a mayor page OR the row
    title contains "Mayor".
    """
    seed_is_mayor = is_mayor_seed_url(source_page_url)
    out: list[dict[str, Any]] = []
    for r in rows:
        tagged = dict(r)
        tagged["is_mayor"] = bool(is_mayor_row(r) or (seed_is_mayor and r.get("person_name")))
        out.append(tagged)
    return out
