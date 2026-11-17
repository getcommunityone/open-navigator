"""
Optional **Chromium (Playwright)** fetch for meetings scraping: a plain, honest browser.

It is for pages that load normally but render their links (agenda lists, site-search results)
with JavaScript, plus a few transport cases (``httpx`` TLS/CA failures, vendor HTML printed to
PDF). It does **not** try to get past bot protection: no ``playwright-stealth``, no fingerprint
spoofing (``navigator.webdriver`` masking, automation-flag hiding), no rotating user agents or
IPs. An HTTP ``403`` / ``429`` or a known challenge page (Cloudflare "Just a moment",
"Attention Required", Akamai "Access Denied", ...) is returned as a ``blocked:<reason>`` result
(see :mod:`scrapers.discovery.browser_block`) and the caller moves on. Decision: issue #443.

Environment:

- ``SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK`` — ``true`` / ``false`` (default ``true``).
- ``SCRAPED_MEETINGS_PLAYWRIGHT_MAX_CONCURRENT`` — default ``2``.
- ``SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE`` — path to a Chrome/Chromium binary (WSL/Linux).
- ``SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL`` — ``chrome`` | ``msedge`` | ``chromium`` to use that
  browser install. If it is missing we **fall back** to bundled Chromium.
- ``SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS`` — ``true`` / ``false`` (default ``true``); headed mode
  is for local debugging only.

Requires ``playwright install chromium``. On Linux/WSL often ``sudo .venv/bin/python -m playwright
install-deps``. If ``install-deps`` fails on Ubuntu 24.04, use Playwright **1.49+** (repo pins 1.52).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from scrapers.discovery.browser_block import (
    BLOCKED_PREFIX,
    BLOCKED_STATUSES,
    blocked_reason,
)

_missing_os_deps_logged = False

# Lazy singleton — created on first use within a process.
_pw_sem_instance: Optional[asyncio.Semaphore] = None


def playwright_fallback_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _max_concurrent() -> int:
    try:
        return max(1, int((os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_MAX_CONCURRENT") or "2").strip()))
    except ValueError:
        return 2


def _pw_semaphore() -> asyncio.Semaphore:
    global _pw_sem_instance
    if _pw_sem_instance is None:
        _pw_sem_instance = asyncio.Semaphore(_max_concurrent())
    return _pw_sem_instance


def httpx_status_should_try_playwright(status_code: int) -> bool:
    """Whether a non-200 ``httpx`` status is worth one plain-browser load.

    Only ``202`` (an accepted-but-unrendered shell some sites serve to non-JS clients). Blocks —
    ``403`` / ``429`` and auth walls (``401``) — are never retried through a browser: the caller
    records them and moves on (issue #443).
    """
    if status_code in BLOCKED_STATUSES:
        return False
    return status_code == 202


def _blocked(reason: str) -> str:
    return f"{BLOCKED_PREFIX}{reason}"


def _log_blocked(url: str, reason: str) -> None:
    logger.info("meetings_playwright_blocked url={} reason={}", url[:200], reason)


# Plain desktop browser context: Playwright's own Chromium headers, one fixed UA from the caller.
_CONTEXT_DEFAULTS: Dict[str, Any] = {
    "locale": "en-US",
    "java_script_enabled": True,
}


def _chromium_launch_options() -> Dict[str, Any]:
    """Headless Chromium (no anti-automation flags); optional system Chrome / channel."""
    headless_env = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS") or "true").strip().lower()
    headless = headless_env not in ("0", "false", "no", "off")
    args = [
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ]
    opts: Dict[str, Any] = {"headless": headless, "args": args}
    exe = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE") or "").strip()
    if exe:
        p = Path(exe).expanduser()
        if p.is_file():
            opts["executable_path"] = str(p)
        else:
            logger.warning(
                "SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE is not a file (ignored): {}",
                p,
            )
    else:
        ch = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL") or "").strip().lower()
        if ch in ("chrome", "msedge", "chromium"):
            opts["channel"] = ch
    return opts


async def _launch_chromium_browser(p: Any) -> Any:
    """Launch Chromium; if ``channel=`` is set but that browser is not installed, retry without it."""
    opts = _chromium_launch_options()
    try:
        return await p.chromium.launch(**opts)
    except Exception as exc:
        msg = f"{type(exc).__name__} {exc}".lower()
        if "channel" not in opts:
            raise
        if not any(
            s in msg
            for s in (
                "is not found",
                "not found at",
                "executable doesn't exist",
                "was not found",
            )
        ):
            raise
        ch = opts.get("channel")
        logger.warning(
            "meetings_playwright_channel_browser_missing channel={} — retrying bundled Chromium. "
            "Install Google Chrome in WSL (``.deb``) or run ``playwright install chrome`` in the "
            "venv; unset CHANNEL to silence this. detail_snip={}",
            ch,
            str(exc).replace("\n", " ")[:400],
        )
        opts2 = {k: v for k, v in opts.items() if k != "channel"}
        return await p.chromium.launch(**opts2)


def _playwright_failure_reason(exc: BaseException) -> str:
    """Map launch/runtime errors to short reasons; log actionable hint once for missing OS libs."""
    global _missing_os_deps_logged
    blob = f"{type(exc).__name__} {exc!s}".lower()
    if "missing dependencies" in blob or "install-deps" in blob:
        if not _missing_os_deps_logged:
            _missing_os_deps_logged = True
            repo = Path(__file__).resolve().parents[2]
            vpy = repo / ".venv" / "bin" / "python"
            if vpy.is_file():
                install_line = f"  cd {repo} && sudo {vpy} -m playwright install-deps"
            else:
                install_line = (
                    "  cd <your-repo> && sudo .venv/bin/python -m playwright install-deps"
                )
            logger.error(
                "Playwright cannot launch Chromium: this Linux/WSL environment is missing browser "
                "libraries. ``sudo`` does not use your venv PATH — call Playwright via the venv "
                "binary (absolute path):\n{}\n"
                "Or from the repo after ``cd``: ``sudo ./.venv/bin/playwright install-deps``\n"
                "On Ubuntu 24.04 (Noble), Playwright before ~1.45 lists wrong apt package names "
                "(``libicu70``, ``libasound2``, …) and ``install-deps`` exits 100 — upgrade the "
                "``playwright`` pip package (repo pins 1.52+), then rerun ``install-deps``.\n"
                "Alternative: install Chrome/Chromium in WSL and set "
                "SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE.",
                install_line,
            )
        return "playwright_missing_os_deps"
    return f"playwright_exc:{type(exc).__name__}:{exc!r}"


async def _goto_collect_html(
    page: Any, url: str, timeout_ms: int
) -> Tuple[Any, str, Dict[str, str], str]:
    """
    Navigate and return HTML. Some WAFs / pages call ``window.close()`` or tear down the tab
    after load; we keep the **longest** successful ``page.content()`` snapshot so a late
    ``TargetClosedError`` does not lose a good first paint.
    """
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    hdrs: Dict[str, str] = {}
    if resp is not None:
        try:
            hdrs = dict(resp.headers)
        except Exception:
            hdrs = {}

    best = ""

    async def _snap() -> None:
        nonlocal best
        try:
            chunk = await page.content() or ""
            if len(chunk) > len(best):
                best = chunk
        except Exception:
            pass

    await asyncio.sleep(0.15)
    await _snap()

    nw_cap = min(18_000, max(4000, int(timeout_ms * 0.28)))
    try:
        await page.wait_for_load_state("networkidle", timeout=nw_cap)
    except Exception:
        pass
    await _snap()

    await asyncio.sleep(0.45)
    await _snap()

    html = best
    try:
        final_url = str(page.url)
    except Exception:
        final_url = url
    return resp, html, hdrs, final_url


async def fetch_resource_bytes_via_playwright(
    url: str,
    *,
    timeout_ms: int,
    user_agent: Optional[str] = None,
    max_bytes: int,
) -> Tuple[Optional[int], str, Optional[bytes], str]:
    """
    Fetch a URL and return raw **network** bytes via Chromium (``Response.body``), not ``page.content()``.

    Intended for **XML sitemaps** and ``robots.txt`` when ``httpx`` gets ``403`` / TLS errors.
    Returns ``(status, final_url, body_bytes, error_reason)``. ``body_bytes`` is set only when
    ``status == 200`` and size ``<= max_bytes``; otherwise ``error_reason`` explains the miss
    (``blocked:http_403`` / ``blocked:http_429`` when the host refuses automated access).
    """
    if not playwright_fallback_enabled():
        return None, url, None, "playwright_disabled"
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, url, None, "playwright_not_installed"

    async with _pw_semaphore():
        try:
            async with async_playwright() as p:
                browser = await _launch_chromium_browser(p)
                try:
                    ctx = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=user_agent,
                        **_CONTEXT_DEFAULTS,
                    )
                    page = await ctx.new_page()
                    resp = await page.goto(
                        url, wait_until="domcontentloaded", timeout=timeout_ms
                    )
                    await asyncio.sleep(0.22)
                    final = str(page.url)
                    if resp is None:
                        return None, final, None, "playwright_no_response"
                    st = resp.status
                    try:
                        raw = await resp.body()
                    except Exception as exc:
                        return st, final, None, _playwright_failure_reason(exc)
                    if len(raw) > max_bytes:
                        return st, final, None, f"oversize_{len(raw)}_bytes"
                    if st != 200:
                        blk = blocked_reason(st)
                        if blk:
                            _log_blocked(url, blk)
                            return st, final, None, _blocked(blk)
                        return st, final, None, f"playwright_http_{st}"
                    return st, final, raw, ""
                finally:
                    await browser.close()
        except Exception as exc:
            return None, url, None, _playwright_failure_reason(exc)


async def fetch_html_via_playwright(
    url: str,
    *,
    timeout_ms: int,
    user_agent: Optional[str] = None,
) -> Tuple[Optional[str], str, str]:
    """
    Return ``(html, "", final_url)`` on success, or ``(None, reason, final_url)``.

    ``reason`` starts with ``blocked:`` (``blocked:http_403``, ``blocked:challenge:<token>``) when
    the host answered with bot protection; callers record it and do not retry the URL elsewhere.

    ``final_url`` is the browser URL after redirects (same as ``url`` when navigation never ran).

    Uses one short-lived Chromium instance per call (held behind a process-wide semaphore).
    """
    if not playwright_fallback_enabled():
        return None, "playwright_disabled", url
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "playwright_not_installed", url

    async with _pw_semaphore():
        try:
            async with async_playwright() as p:
                browser = await _launch_chromium_browser(p)
                try:
                    ctx = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=user_agent,
                        **_CONTEXT_DEFAULTS,
                    )
                    page = await ctx.new_page()

                    resp, html, hdrs, final_url = await _goto_collect_html(page, url, timeout_ms)
                    st = resp.status if resp is not None else 0

                    blk = blocked_reason(st, html, hdrs)
                    if blk:
                        _log_blocked(url, blk)
                        return None, _blocked(blk), final_url
                    if st >= 400:
                        return None, f"playwright_http_{st}", final_url

                    n = len(html or "")
                    if n < 400:
                        return None, f"playwright_short_body_{n}", final_url
                    return html or None, "", final_url
                finally:
                    await browser.close()
        except Exception as exc:
            return None, _playwright_failure_reason(exc), url


def _html_print_pdf_max_bytes() -> int:
    try:
        return max(500_000, int((os.getenv("SCRAPED_MEETINGS_HTML_PRINT_MAX_BYTES") or "35000000").strip()))
    except ValueError:
        return 35_000_000


async def print_agenda_html_page_to_pdf_via_playwright(
    url: str,
    *,
    referer: str,
    timeout_ms: int,
    user_agent: Optional[str] = None,
) -> Tuple[Optional[bytes], str]:
    """
    Navigate like normal HTML scraping, then emit a **print** PDF via Chromium (Playwright).

    Used for vendors (e.g. Simbli / eBoard Solutions) that publish agendas/minutes as HTML ASP.NET
    pages. Requires ``playwright install chromium`` (same as HTML fallback).

    ``Referer`` is sent on the navigation request (many portals reject anonymous deep-links).
    """
    if not playwright_fallback_enabled():
        return None, "playwright_disabled"
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "playwright_not_installed"

    ref = (referer or "").strip() or url
    max_b = _html_print_pdf_max_bytes()

    async with _pw_semaphore():
        try:
            async with async_playwright() as p:
                browser = await _launch_chromium_browser(p)
                try:
                    ctx = await browser.new_context(
                        viewport={"width": 1280, "height": 1800},
                        user_agent=user_agent,
                        # Honest Referer: the listing page the agenda link was found on.
                        extra_http_headers={"Referer": ref},
                        **_CONTEXT_DEFAULTS,
                    )
                    page = await ctx.new_page()

                    resp, html_chunk, rhdrs, final_url = await _goto_collect_html(page, url, timeout_ms)
                    st = resp.status if resp is not None else 0

                    blk = blocked_reason(st, html_chunk, rhdrs)
                    if blk:
                        _log_blocked(url, blk)
                        return None, _blocked(blk)
                    if st >= 400:
                        return None, f"playwright_http_{st}"

                    pdf_bytes = await page.pdf(
                        format="Letter",
                        print_background=True,
                        prefer_css_page_size=False,
                        margin={
                            "top": "0.35in",
                            "bottom": "0.35in",
                            "left": "0.35in",
                            "right": "0.35in",
                        },
                    )
                    if not pdf_bytes:
                        return None, "empty_pdf"
                    if len(pdf_bytes) > max_b:
                        return None, f"pdf_oversize_{len(pdf_bytes)}_bytes"
                    if len(pdf_bytes) < 900:
                        return None, f"pdf_too_small_{len(pdf_bytes)}_bytes"
                    if not pdf_bytes.startswith(b"%PDF"):
                        return None, "non_pdf_magic"
                    logger.info(
                        "meetings_simbli_html_print_ok url={} final_url={} pdf_bytes={}",
                        url[:180],
                        final_url[:180],
                        len(pdf_bytes),
                    )
                    return pdf_bytes, ""
                finally:
                    await browser.close()
        except Exception as exc:
            return None, _playwright_failure_reason(exc)
