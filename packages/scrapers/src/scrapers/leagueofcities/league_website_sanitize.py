"""
Normalize league municipal ``website`` values before cache load or bronze upsert.

Rejects scheme-only URLs (e.g. ``https://`` from empty iMIS website cells), broken
double schemes, and hosts without a domain label.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Bare scheme or scheme + slash only (common when directory cell is empty).
_SCHEME_ONLY_RE = re.compile(r"^https?://\s*/?\s*$", re.I)

_JUNK_LITERALS = frozenset(
    {
        "https://",
        "http://",
        "https://)",
        "http://)",
        "https:",
        "http:",
    }
)

_LOOSE_DOMAIN_RE = re.compile(
    r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(/[^\s]*)?$",
    re.I,
)


def fix_double_scheme_url(url: str) -> str:
    """``http://https://example.com`` → ``https://example.com``."""
    u = (url or "").strip()
    if not u:
        return u
    m = re.match(r"^https?://(https?://.+)$", u, re.DOTALL)
    if m:
        return m.group(1).strip()
    return u


def _has_usable_netloc(netloc: str) -> bool:
    host = (netloc or "").strip().lower()
    if not host or host in ("https", "http"):
        return False
    if "." not in host:
        return False
    return True


def sanitize_league_website(url: str | None) -> str | None:
    """
    Return a normalized ``https://host…`` URL, or ``None`` if missing / unusable.
    """
    if url is None:
        return None
    s = fix_double_scheme_url(str(url).strip())
    if not s or s in _JUNK_LITERALS or _SCHEME_ONLY_RE.match(s):
        return None

    if not re.match(r"^https?://", s, re.I):
        if re.match(r"^www\.[a-z0-9.-]+\.[a-z]{2,}(/.*)?$", s, re.I):
            s = "https://" + s
        elif _LOOSE_DOMAIN_RE.match(s):
            s = "https://" + s.lstrip("/")
        else:
            return None

    try:
        p = urlparse(s)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if not _has_usable_netloc(p.netloc):
        return None

    low = s.lower()
    if low.startswith("http://"):
        s = "https://" + s[7:]
    return s.rstrip("/") if s.count("/") == 2 and s.endswith("/") else s
