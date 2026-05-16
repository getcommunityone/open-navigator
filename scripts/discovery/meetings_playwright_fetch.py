"""
Optional **Chromium (Playwright)** HTML fetch for meetings scraping when ``httpx`` gets blocked.

Typical cases: ``403`` / ``401`` / ``429`` from bot-aware CDNs, ``202`` oddities, or a ``200`` body
that still matches :func:`comprehensive_discovery_pipeline_jurisdiction._captcha_or_bot_wall_reason`.

Environment (defaults favor automation-friendly setups):

- ``SCRAPED_MEETINGS_PLAYWRIGHT_FALLBACK`` — ``true`` / ``false`` (default ``true``).
- ``SCRAPED_MEETINGS_PLAYWRIGHT_MAX_CONCURRENT`` — default ``2``.
- ``SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE`` — path to Chrome/Chromium binary (WSL/Linux).
- ``SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL`` — ``chrome`` | ``msedge`` | ``chromium`` to use that
  browser install (often fewer Akamai false positives). If it is missing (e.g. no binary at
  ``/opt/google/chrome/chrome``), we **fall back** to bundled Chromium. Install Chrome with the
  distro .deb **or** run ``playwright install chrome`` from the venv.
- ``SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS`` — ``true`` / ``false`` (default ``true``). A visible
  window is **not** required for scraping; use headed mode only when a host blocks headless.
- ``SCRAPED_MEETINGS_PLAYWRIGHT_STEALTH`` — ``true`` / ``false`` (default ``true``). Uses
  ``playwright-stealth`` when importable.

Requires ``playwright install chromium``. On Linux/WSL often ``sudo .venv/bin/python -m playwright
install-deps``. If ``install-deps`` fails on Ubuntu 24.04, use Playwright **1.49+** (repo pins 1.52).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

_missing_os_deps_logged = False
_http_403_playwright_hint_logged = False

# Lazy singleton — created on first use within a process.
_pw_sem_instance: Optional[asyncio.Semaphore] = None

_NAV_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


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
    """Retry with a real browser when the plain HTTP client got a gate-ish status."""
    return status_code in (401, 403, 429, 202)


def _stealth_enabled() -> bool:
    v = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_STEALTH") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _chromium_launch_options() -> Dict[str, Any]:
    """Headless Chromium with light anti-automation flags; optional system Chrome / channel."""
    headless_env = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS") or "true").strip().lower()
    headless = headless_env not in ("0", "false", "no", "off")
    args = [
        "--disable-blink-features=AutomationControlled",
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


def _captcha_hint(html: str, headers: Dict[str, str]) -> Optional[str]:
    from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import (
        _captcha_or_bot_wall_reason,
    )

    return _captcha_or_bot_wall_reason(html, headers)


def _trivial_http_error_wall(html: str) -> bool:
    """True when HTML is clearly an access-denied interstitial, not a real site shell."""
    raw = html or ""
    if len(raw) < 600:
        return True
    h = raw[:8000].lower()
    needles = (
        "access denied",
        "you don't have permission",
        "403 forbidden",
        "http error 403",
        "error 403",
        "request blocked",
        "forbidden: target",
        "errors.edgesuite.net",
    )
    return any(n in h for n in needles)


def _dom_looks_like_real_document(html: str) -> bool:
    """Prefer accepting ``(status>=400)`` only when the DOM is plausibly a normal page."""
    raw = html or ""
    if len(raw) < 800:
        return False
    low = raw[:25000].lower()
    if "<html" not in low and "<!doctype html" not in low:
        return False
    if _trivial_http_error_wall(raw):
        return False
    return True


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

    st = resp.status if resp is not None else 0
    extra_sleep = 2.1 if st >= 400 else 0.45
    # Long sleep after a bot-wall status gives scripts time to close the tab — shorten if we
    # already captured a full document.
    if st >= 400 and len(best) >= 8000:
        extra_sleep = min(extra_sleep, 0.55)
    await asyncio.sleep(extra_sleep)
    await _snap()

    html = best
    try:
        final_url = str(page.url)
    except Exception:
        final_url = url
    return resp, html, hdrs, final_url


def _log_playwright_403_hint_once() -> None:
    global _http_403_playwright_hint_logged
    if _http_403_playwright_hint_logged:
        return
    _http_403_playwright_hint_logged = True
    logger.warning(
        "Playwright navigation returned HTTP 403 (often Akamai / bot rules vs headless). "
        "Try, in order: install Google Chrome in WSL and set "
        "SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL=chrome (or CHROMIUM_EXECUTABLE to its path); "
        "SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false on a machine with a display (WSLg); "
        "or run the scraper from Windows / a non-WSL network path. "
        "Some hosts never serve real HTML to automation."
    )


async def fetch_resource_bytes_via_playwright(
    url: str,
    *,
    timeout_ms: int,
    user_agent: str,
    max_bytes: int,
) -> Tuple[Optional[int], str, Optional[bytes], str]:
    """
    Fetch a URL and return raw **network** bytes via Chromium (``Response.body``), not ``page.content()``.

    Intended for **XML sitemaps** and ``robots.txt`` when ``httpx`` gets ``403`` / TLS errors.
    Returns ``(status, final_url, body_bytes, error_reason)``. ``body_bytes`` is set only when
    ``status == 200`` and size ``<= max_bytes``; otherwise ``error_reason`` explains the miss.
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
                        locale="en-US",
                        java_script_enabled=True,
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept": (
                                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                                "application/rss+xml;q=0.9,*/*;q=0.8"
                            ),
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                        },
                    )
                    await ctx.add_init_script(_NAV_INIT_SCRIPT)
                    page = await ctx.new_page()
                    if _stealth_enabled():
                        try:
                            from playwright_stealth import Stealth

                            await Stealth().apply_stealth_async(page)
                        except Exception:
                            pass
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
                        if st == 403:
                            _log_playwright_403_hint_once()
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
    user_agent: str,
) -> Tuple[Optional[str], str, str]:
    """
    Return ``(html, "", final_url)`` on success, or ``(None, reason, final_url)``.

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
                        locale="en-US",
                        java_script_enabled=True,
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept": (
                                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                                "image/avif,image/webp,image/apng,*/*;q=0.8"
                            ),
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                        },
                    )
                    await ctx.add_init_script(_NAV_INIT_SCRIPT)
                    page = await ctx.new_page()
                    if _stealth_enabled():
                        try:
                            from playwright_stealth import Stealth

                            await Stealth().apply_stealth_async(page)
                        except Exception as exc:
                            logger.warning(
                                "meetings_playwright_stealth_failed detail={}",
                                repr(exc),
                            )

                    resp, html, hdrs, final_url = await _goto_collect_html(page, url, timeout_ms)
                    st = resp.status if resp is not None else 0

                    if st >= 400:
                        if _dom_looks_like_real_document(html) and not _captcha_hint(html, hdrs):
                            logger.info(
                                f"meetings_playwright_accepted_despite_http_status "
                                f"url={url!r} status={st} html_chars={len(html)}",
                            )
                            return html, "", final_url
                        if st == 403:
                            _log_playwright_403_hint_once()
                        return None, f"playwright_http_{st}", final_url

                    n = len(html or "")
                    if n < 400:
                        return None, f"playwright_short_body_{n}", final_url
                    cap = _captcha_hint(html or "", hdrs)
                    if cap:
                        return None, f"playwright_captcha:{cap}", final_url
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
    user_agent: str,
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
    try:
        from urllib.parse import urlparse

        same_site = urlparse(ref).netloc.lower().split(":")[0] == urlparse(url).netloc.lower().split(
            ":"
        )[0]
        sec_fetch_site = "same-origin" if same_site else "cross-site"
    except Exception:
        sec_fetch_site = "cross-site"

    async with _pw_semaphore():
        try:
            async with async_playwright() as p:
                browser = await _launch_chromium_browser(p)
                try:
                    hdrs = {
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;q=0.9,"
                            "image/avif,image/webp,image/apng,*/*;q=0.8"
                        ),
                        "Upgrade-Insecure-Requests": "1",
                        "Referer": ref,
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": sec_fetch_site,
                        "Sec-Fetch-User": "?1",
                    }
                    ctx = await browser.new_context(
                        viewport={"width": 1280, "height": 1800},
                        user_agent=user_agent,
                        locale="en-US",
                        java_script_enabled=True,
                        extra_http_headers=hdrs,
                    )
                    await ctx.add_init_script(_NAV_INIT_SCRIPT)
                    page = await ctx.new_page()
                    if _stealth_enabled():
                        try:
                            from playwright_stealth import Stealth

                            await Stealth().apply_stealth_async(page)
                        except Exception as exc:
                            logger.warning(
                                "meetings_playwright_stealth_failed html_print detail={}",
                                repr(exc),
                            )

                    resp, html_chunk, rhdrs, final_url = await _goto_collect_html(page, url, timeout_ms)
                    st = resp.status if resp is not None else 0

                    if st >= 400:
                        if not (_dom_looks_like_real_document(html_chunk) and not _captcha_hint(html_chunk, rhdrs)):
                            if st == 403:
                                _log_playwright_403_hint_once()
                            return None, f"playwright_http_{st}"

                    cap = _captcha_hint(html_chunk or "", rhdrs)
                    if cap:
                        return None, f"playwright_captcha:{cap}"

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
