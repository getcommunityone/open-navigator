#!/usr/bin/env python3
"""
Try loading a URL with Playwright after passing bot walls manually.

Use this when the meetings pipeline hits ``captcha:cloudflare_js_challenge``:
1. In Chrome, open the URL, complete Cloudflare / Turnstile if shown.
2. Export cookies (Cookie-Editor / EditThisCookie) as JSON array of
   {name, value, domain, path, ...} — save e.g. ``./cookies.json``.
3. Run this script with ``--cookies-json`` or use ``--storage-state`` from
   ``playwright codegen`` / ``await context.storage_state(path=...)``.

Examples (repo root, venv active)::

    .venv/bin/python scripts/development/try_scrape_with_cookies.py \\
        --url 'https://www.tuscaloosacityschools.com/about-us/calendar' \\
        --out /tmp/tcs_try.html

    .venv/bin/python scripts/development/try_scrape_with_cookies.py \\
        --url 'https://www.tuscaloosacityschools.com/about-us/board-of-education/meet-the-board-members' \\
        --cookies-json ./tusc_cookies.json \\
        --wait-ms 8000

    # After one successful manual session in Playwright:
    .venv/bin/python scripts/development/try_scrape_with_cookies.py \\
        --url 'https://www.tuscaloosacityschools.com/' \\
        --storage-state ./tusc_state.json

Env (optional, same spirit as meetings scraper)::

    SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL=chrome
    SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/google-chrome
    TRY_SCRAPE_HEADLESS=false   # default is false (visible browser)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def _launch_kwargs() -> Dict[str, Any]:
    exe = (os.environ.get("SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE") or "").strip()
    ch = (os.environ.get("SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL") or "").strip().lower()
    kw: Dict[str, Any] = {"headless": _headless()}
    if exe and Path(exe).is_file():
        kw["executable_path"] = exe
    elif ch in ("chrome", "msedge", "chromium"):
        kw["channel"] = ch
    return kw


def _headless() -> bool:
    v = (os.environ.get("TRY_SCRAPE_HEADLESS") or "false").strip().lower()
    return v in ("1", "true", "yes", "on")


def _registrable_cookie_domain(host: str) -> str:
    """Best-effort eTLD+1 style domain with leading dot for Playwright (not a full PSL)."""
    h = (host or "").lower().strip()
    if not h:
        return ""
    parts = [p for p in h.split(".") if p]
    if len(parts) >= 2:
        return "." + ".".join(parts[-2:])
    return "." + h if not h.startswith(".") else h


def _normalize_playwright_cookies(raw: List[Dict[str, Any]], page_host: str) -> List[Dict[str, Any]]:
    """Map common browser-extension exports to Playwright's add_cookies shape."""
    out: List[Dict[str, Any]] = []
    fallback_domain = _registrable_cookie_domain(page_host)
    for c in raw:
        name = (c.get("name") or "").strip()
        value = c.get("value")
        if not name or value is None:
            continue
        raw_dom = (c.get("domain") or "").strip()
        if raw_dom.startswith("."):
            domain = raw_dom
        elif raw_dom:
            # Extension often stores host without leading dot
            domain = _registrable_cookie_domain(raw_dom.lstrip("."))
        else:
            domain = fallback_domain
        path = (c.get("path") or "/").strip() or "/"
        if not domain:
            domain = fallback_domain
        entry: Dict[str, Any] = {
            "name": name,
            "value": str(value),
            "domain": domain,
            "path": path,
        }
        if "secure" in c:
            entry["secure"] = bool(c["secure"])
        if c.get("httpOnly") is not None:
            entry["httpOnly"] = bool(c["httpOnly"])
        ss = c.get("sameSite")
        if ss in ("Strict", "Lax", "None"):
            entry["sameSite"] = ss
        exp = c.get("expirationDate")
        if isinstance(exp, (int, float)) and exp > 0:
            entry["expires"] = float(exp)
        out.append(entry)
    return out


async def _run(
    url: str,
    out_path: Path,
    cookies_json: Optional[Path],
    storage_state: Optional[Path],
    wait_ms: int,
) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install Playwright in this venv: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    cookies: Optional[List[Dict[str, Any]]] = None
    if cookies_json:
        data = json.loads(cookies_json.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "cookies" in data:
            data = data["cookies"]
        if not isinstance(data, list):
            print("cookies JSON must be a list of cookie objects (or {\"cookies\": [...]})", file=sys.stderr)
            return 1
        cookies = _normalize_playwright_cookies(data, host)

    async with async_playwright() as p:
        browser = await p.chromium.launch(**_launch_kwargs())
        try:
            if storage_state and storage_state.is_file():
                ctx = await browser.new_context(
                    storage_state=str(storage_state),
                    viewport={"width": 1280, "height": 900},
                )
            else:
                ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            if cookies:
                await ctx.add_cookies(cookies)
            try:
                from playwright_stealth import Stealth

                page = await ctx.new_page()
                await Stealth().apply_stealth_async(page)
            except Exception:
                page = await ctx.new_page()

            resp = await page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            await asyncio.sleep(max(0, wait_ms) / 1000.0)
            html = await page.content()
            title = await page.title()
            final = page.url
            st = resp.status if resp is not None else 0

            out_path.write_text(html, encoding="utf-8")
            print(f"status={st} title={title!r}")
            print(f"final_url={final}")
            print(f"wrote {len(html)} chars -> {out_path}")
            low = html[:12000].lower()
            if "cf-challenge" in low or "turnstile" in low or "just a moment" in low:
                print("note: page still looks like a bot wall — try visible Chrome (headless=false), real channel=chrome, or fresher cookies.", file=sys.stderr)
            return 0
        finally:
            await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Page to open (after you export cookies from same origin if needed)")
    ap.add_argument("--out", type=Path, default=Path("/tmp/try_scrape_out.html"), help="Where to save raw HTML")
    ap.add_argument("--cookies-json", type=Path, default=None, help="JSON array of cookies from browser extension")
    ap.add_argument("--storage-state", type=Path, default=None, help="Playwright storage_state.json from a prior session")
    ap.add_argument("--wait-ms", type=int, default=4000, help="Extra wait after domcontentloaded (JS challenges)")
    args = ap.parse_args()
    if args.cookies_json and args.storage_state:
        print("Use only one of --cookies-json or --storage-state", file=sys.stderr)
        sys.exit(2)
    rc = asyncio.run(
        _run(
            args.url,
            args.out,
            args.cookies_json,
            args.storage_state,
            args.wait_ms,
        )
    )
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
