"""Shared web-origin allowlist for CORS and OAuth redirect validation.

Security-critical: this is the single source of truth for which browser origins
the API trusts. Two callers depend on it:

  - CORS middleware (``api/main.py``, ``api/app.py``) — which origins may read
    API responses cross-site.
  - OAuth ``redirect_uri`` validation (``api/routes/auth.py``) — where a freshly
    minted 7-day JWT is appended to the redirect target after login, so an
    unvalidated target leaks the token to an attacker-controlled site.

Configuration (env):
  CORS_ALLOWED_ORIGINS  Comma-separated absolute origins, e.g.
                        "https://www.communityone.com,https://foo.hf.space".
                        When set, it is the *exact* allowlist and the built-in
                        defaults are ignored.
  FRONTEND_URL          Single production frontend origin. Added to the defaults
                        only when CORS_ALLOWED_ORIGINS is not set.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urlsplit

# Local dev origins that are always safe when no explicit allowlist is set:
# Vite (5173), Docusaurus (3000), and the API itself (8001), on both loopback
# spellings.
_DEV_DEFAULT_ORIGINS: Tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
)

# Established production origin for this project (see the FRONTEND_URL default in
# api/routes/data_deletion.py). Included so a default deploy still works if the
# operator hasn't set CORS_ALLOWED_ORIGINS yet.
_PROD_DEFAULT_ORIGINS: Tuple[str, ...] = ("https://www.communityone.com",)


def _normalize_origin(value: str) -> Optional[str]:
    """Reduce a URL/origin string to canonical ``scheme://host[:port]``.

    Returns None when it is not an absolute http(s) origin. Default ports
    (443/80) are dropped so ``https://x:443`` matches ``https://x``.
    """
    if not value:
        return None
    # urlsplit (bad IPv6 literal) and the .port property (out-of-range or
    # non-numeric port) raise ValueError on malformed input. A malformed
    # candidate is simply not a usable origin — drop it, never propagate. This
    # matters because the value can be an attacker-supplied redirect_uri (a raw
    # 500 would hard-fail login) or an operator typo in CORS_ALLOWED_ORIGINS /
    # FRONTEND_URL (would otherwise crash the app at startup).
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    if port is not None and not (
        (parts.scheme == "https" and port == 443)
        or (parts.scheme == "http" and port == 80)
    ):
        return f"{parts.scheme}://{host}:{port}"
    return f"{parts.scheme}://{host}"


@lru_cache(maxsize=1)
def allowed_origins() -> Tuple[str, ...]:
    """The trusted origins, normalized and de-duplicated (order preserved).

    ``CORS_ALLOWED_ORIGINS`` is authoritative when set; otherwise fall back to
    the dev + production defaults plus ``FRONTEND_URL`` if present. Cached for
    the process lifetime — env is read once at startup, matching how the CORS
    middleware consumes it.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        candidates = raw.split(",")
    else:
        candidates = list(_DEV_DEFAULT_ORIGINS) + list(_PROD_DEFAULT_ORIGINS)

    # FRONTEND_URL is the app's own frontend — always trusted, whether or not an
    # explicit CORS_ALLOWED_ORIGINS list is set, so login redirects back to it
    # never get dropped.
    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    if frontend_url:
        candidates.append(frontend_url)

    # dict preserves insertion order while de-duplicating.
    seen: "dict[str, None]" = {}
    for candidate in candidates:
        normalized = _normalize_origin(candidate)
        if normalized:
            seen.setdefault(normalized, None)
    return tuple(seen)


def is_allowed_origin(value: str) -> bool:
    """True if ``value``'s origin is in the allowlist."""
    normalized = _normalize_origin(value)
    return normalized is not None and normalized in allowed_origins()


def is_safe_redirect(value: Optional[str]) -> bool:
    """True if ``value`` is a safe post-login redirect target.

    Safe means one of:
      - absent/empty (the caller falls back to a trusted default);
      - a same-origin relative path like ``/dashboard`` (but NOT a
        protocol-relative ``//evil.com`` or a backslash-smuggled variant);
      - an absolute URL whose origin is in the allowlist.
    """
    if not value:
        return True
    # WHATWG: browsers strip ASCII tab/newline/CR from anywhere in a URL before
    # parsing it. Do the same first, so a smuggled "/\t/evil.com" can't pose as
    # a relative path here yet resolve to protocol-relative "//evil.com" in the
    # browser. (Starlette's Location quoting happens to neutralize this today,
    # but the validator must be self-sufficient for any other caller.)
    cleaned = value.translate({0x09: None, 0x0A: None, 0x0D: None})
    if not cleaned:
        return True
    if cleaned.startswith("/") and not cleaned.startswith("//") and "\\" not in cleaned[:2]:
        return True
    return is_allowed_origin(cleaned)
