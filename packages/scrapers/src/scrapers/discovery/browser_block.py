"""Classify a fetched page as *blocked* (bot protection) so callers record it and move on.

Policy (decided 2026-11-16, issue #443): the browser fallback is a plain, honest browser for pages
that load normally but render their links with JavaScript. It never tries to get past bot
protection: no ``playwright-stealth``, no fingerprint spoofing, no rotating user agents or IPs.
An HTTP ``403`` / ``429`` or a known challenge page is reported as **blocked**, and the caller
must not retry it through another route (a browser, a proxy, a different user agent).

Everything here is pure (no network) so it can be unit-tested against HTML fixtures.
"""

from __future__ import annotations

import html as html_lib
from collections.abc import Mapping
from typing import Optional

#: HTTP statuses that mean "this host refuses automated access" — never retried elsewhere.
BLOCKED_STATUSES: frozenset[int] = frozenset({403, 429})

#: Prefix on reason strings returned by the fetch helpers for blocked pages.
BLOCKED_PREFIX = "blocked:"

# Only the head of the document is scanned: challenge pages are small and put their markers
# in <title> / inline scripts near the top.
_SCAN_CHARS = 60_000


class BlockedError(Exception):
    """Raised (or recorded) when a host answers with bot protection instead of the page."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"blocked url={url!r} reason={reason}")


def is_blocked_reason(reason: Optional[str]) -> bool:
    """True when a fetch helper's reason string reports a block (``blocked:…``)."""
    return bool(reason) and str(reason).startswith(BLOCKED_PREFIX)


def _header(headers: Optional[Mapping[str, str]], name: str) -> str:
    if not headers:
        return ""
    try:
        for k, v in headers.items():
            if str(k).lower() == name:
                return str(v or "").lower()
    except Exception:
        return ""
    return ""


def challenge_page_reason(
    html: Optional[str], headers: Optional[Mapping[str, str]] = None
) -> Optional[str]:
    """Return a short token when ``html`` is a bot-protection challenge, else ``None``.

    Markers are specific to interstitials (titles and challenge-only script names), so normal
    pages that merely sit behind a CDN or embed a reCAPTCHA widget in a form are not flagged.
    """
    if _header(headers, "cf-mitigated") == "challenge":
        return "cloudflare_challenge"
    if not html:
        return None
    n = len(html)
    # Akamai entity-encodes its error text (``errors&#46;edgesuite&#46;net``).
    head = html_lib.unescape(html[:_SCAN_CHARS]).lower()

    # Cloudflare
    if "<title>just a moment...</title>" in head or (
        "just a moment" in head
        and ("_cf_chl_opt" in head or "challenges.cloudflare.com" in head)
    ):
        return "cloudflare_just_a_moment"
    if "attention required! | cloudflare" in head:
        return "cloudflare_attention_required"
    if (
        "_cf_chl_opt" in head
        or "cf-browser-verification" in head
        or "cf-chl-seq" in head
    ):
        return "cloudflare_challenge"
    if "checking your browser before accessing" in head:
        return "cloudflare_interstitial"

    # Akamai
    if "errors.edgesuite.net" in head or (
        "<title>access denied</title>" in head and "reference #" in head
    ):
        return "akamai_access_denied"

    # Imperva / Incapsula
    if "incapsula incident id" in head or "_incapsula_resource" in head:
        return "incapsula_block"

    # SiteGround
    if n < 8000 and ("sgcaptcha" in head or "/.well-known/captcha/" in head):
        return "siteground_captcha"

    # DataDome, PerimeterX / HUMAN, DDoS-Guard
    if n < 12000 and "geo.captcha-delivery.com" in head:
        return "datadome_captcha"
    if "_pxcaptcha" in head or "px-captcha" in head:
        return "perimeterx_challenge"
    if "<title>ddos-guard</title>" in head or ("ddos-guard.net/" in head and n < 12000):
        return "ddos_guard"

    # Google
    if "detected unusual traffic" in head and "google" in head:
        return "google_unusual_traffic"

    # A CAPTCHA as the page's main content (only on interstitial-sized bodies).
    if n < 25000 and (
        "verify you are human" in head
        or "verify you're human" in head
        or "are you a robot" in head
    ):
        return "human_verification"
    return None


def blocked_reason(
    status_code: Optional[int],
    html: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Return ``"http_403"`` / ``"http_429"`` / ``"challenge:<token>"`` when blocked, else ``None``."""
    if status_code in BLOCKED_STATUSES:
        return f"http_{status_code}"
    challenge = challenge_page_reason(html, headers)
    if challenge:
        return f"challenge:{challenge}"
    return None
