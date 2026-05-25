"""HTTP fetch helpers for jurisdiction pilot (bot walls, optional Playwright)."""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import requests

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_USER_AGENT = BROWSER_USER_AGENT


def bot_wall_reason(html: str, status_code: int) -> Optional[str]:
    """Return a short token when the body is a captcha interstitial, not real site HTML."""
    if not html:
        if status_code == 202:
            return "http_202_empty"
        return None
    low = html.lower()
    if len(html) < 8000:
        if "sgcaptcha" in low or "/.well-known/captcha/" in low:
            return "siteground_sgcaptcha"
        if "robot challenge" in low:
            return "siteground_robot_challenge"
    if status_code == 202 and ("sgcaptcha" in low or "refresh" in low[:500]):
        return "siteground_sgcaptcha_202"
    try:
        from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import (
            _captcha_or_bot_wall_reason,
        )

        return _captcha_or_bot_wall_reason(html, None)
    except Exception:
        return None


def fetch_page_html(
    url: str,
    session: requests.Session,
    *,
    timeout_s: int = 12,
    try_playwright: bool = True,
) -> tuple[int, str, Optional[str]]:
    """
    GET ``url``. Returns ``(status_code, html, block_reason)``.

    ``block_reason`` is set when the response is a bot wall (HTML discarded).
    Tries Playwright when requests returns 202/403/etc. or a captcha body.
    """
    block: Optional[str] = None
    status = 0
    html = ""
    try:
        resp = session.get(url, timeout=timeout_s, allow_redirects=True)
        status = resp.status_code
        html = resp.text or ""
    except requests.RequestException:
        return 0, "", "request_error"

    block = bot_wall_reason(html, status)
    if not block and status == 200 and html:
        return status, html, None

    if try_playwright:
        from scripts.discovery.meetings_playwright_fetch import (
            fetch_html_via_playwright,
            httpx_status_should_try_playwright,
            playwright_fallback_enabled,
        )

        if playwright_fallback_enabled() and (
            block or httpx_status_should_try_playwright(status)
        ):
            phtml, perr, _final = asyncio.run(
                fetch_html_via_playwright(
                    url,
                    timeout_ms=max(30_000, timeout_s * 1000),
                    user_agent=_USER_AGENT,
                )
            )
            if phtml:
                pblock = bot_wall_reason(phtml, 200)
                if not pblock:
                    return 200, phtml, None
                block = pblock or block
            elif perr and not block:
                block = perr

    if block:
        return status, "", block
    if status != 200:
        return status, "", f"http_{status}"
    return status, html, None
