#!/usr/bin/env python3
"""
Experimental: fetch YouTube transcript JSON by driving Chromium and intercepting
Innertube network calls (e.g. ``youtubei/v1/get_transcript``).

This bypasses Webshare/proxy issues for the *browser* path but is slow and brittle
(UI selectors change). Not wired into ``load_youtube_events_to_postgres.py`` yet.

Prerequisites (repo root):
  .venv/bin/python -m playwright install chromium
  # WSL/Linux if Chromium fails to start:
  # sudo .venv/bin/python -m playwright install-deps

Usage:
  set -a && source .env && set +a
  .venv/bin/python scripts/datasources/youtube/fetch_transcript_playwright.py \\
    --video-url 'https://www.youtube.com/watch?v=yMWz9ocMzRU' \\
    --cookies youtube_cookies.txt \\
    --out /tmp/transcript_playwright.json

  # Headed browser if headless is blocked:
  SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false \\
    .venv/bin/python scripts/datasources/youtube/fetch_transcript_playwright.py --video-id dQw4w9WgXcQ
"""

from __future__ import annotations

import argparse
import json
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_TRANSCRIPT_URL_MARKERS = (
    "youtubei/v1/get_transcript",
    "/api/timedtext",
    "timedtext?v=",
    "timedtext&",
    "/timedtext?",
)

# Innertube responses that often embed caption track URLs before the panel opens.
_INNERTUBE_URL_MARKERS = (
    "youtubei/v1/player",
    "youtubei/v1/next",
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _video_id_from_arg(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty video id/url")
    if "youtube.com" in raw or "youtu.be" in raw:
        parsed = urlparse(raw)
        if parsed.hostname and "youtu.be" in parsed.hostname:
            vid = parsed.path.strip("/").split("/")[0]
        else:
            vid = (parse_qs(parsed.query).get("v") or [""])[0]
        if not vid:
            raise ValueError(f"could not parse video id from URL: {raw!r}")
        return vid
    return raw


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _load_playwright_cookies(cookies_file: Optional[str]) -> list[dict[str, Any]]:
    path = (cookies_file or "").strip()
    if not path:
        path = (Path.cwd() / "youtube_cookies.txt").as_posix()
    p = Path(path)
    if not p.is_file():
        return []
    jar = MozillaCookieJar(str(p.resolve()))
    jar.load(ignore_discard=True, ignore_expires=True)
    out: list[dict[str, Any]] = []
    for c in jar:
        if "youtube" not in (c.domain or ""):
            continue
        out.append(
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path or "/",
                "expires": int(c.expires) if c.expires else -1,
                "httpOnly": bool(getattr(c, "_rest", {}).get("HttpOnly", False)),
                "secure": bool(c.secure),
                "sameSite": "Lax",
            }
        )
    return out


def _response_kind(url: str) -> Optional[str]:
    u = (url or "").lower()
    if any(m in u for m in _TRANSCRIPT_URL_MARKERS):
        return "transcript"
    if any(m in u for m in _INNERTUBE_URL_MARKERS):
        return "innertube"
    return None


def _find_caption_tracks(obj: Any, *, found: Optional[list] = None) -> list[dict[str, Any]]:
    """Walk JSON for captionTracks / playerCaptionsTracklistRenderer."""
    if found is None:
        found = []
    if isinstance(obj, dict):
        if "captionTracks" in obj and isinstance(obj["captionTracks"], list):
            for tr in obj["captionTracks"]:
                if isinstance(tr, dict):
                    found.append(tr)
        for v in obj.values():
            _find_caption_tracks(v, found=found)
    elif isinstance(obj, list):
        for item in obj:
            _find_caption_tracks(item, found=found)
    return found


def _apply_stealth(page: Any) -> None:
    try:
        from playwright_stealth import stealth_sync

        stealth_sync(page)
    except Exception:
        pass


def _try_open_transcript_panel(page: Any, *, wait_ms: int) -> list[str]:
    """Click through common transcript UI paths; return notes for logging."""
    notes: list[str] = []
    expand_selectors = (
        "#expand",
        "tp-yt-paper-button#expand",
        "ytd-text-inline-expander #expand",
    )
    for sel in expand_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                loc.click(timeout=3000)
                notes.append(f"clicked expand: {sel}")
                page.wait_for_timeout(800)
                break
        except Exception:
            continue

    transcript_selectors = (
        "button:has-text('Show transcript')",
        "button:has-text('Open transcript')",
        "ytd-video-description-transcript-section-renderer button",
        "[aria-label*='transcript' i]",
        "[aria-label*='Transcript' i]",
    )
    for sel in transcript_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=2000):
                loc.click(timeout=5000)
                notes.append(f"clicked transcript: {sel}")
                page.wait_for_timeout(wait_ms)
                return notes
        except Exception as exc:
            notes.append(f"miss {sel}: {type(exc).__name__}")
    return notes


def fetch_transcript_via_playwright(
    video_id: str,
    *,
    cookies_file: Optional[str] = None,
    headless: Optional[bool] = None,
    navigation_timeout_ms: int = 60_000,
    panel_wait_ms: int = 4000,
) -> dict[str, Any]:
    """
    Launch Chromium, open the watch page, try to open the transcript panel, and
    collect JSON from intercepted transcript-related responses.
    """
    from playwright.sync_api import sync_playwright

    from scripts.discovery.meetings_playwright_fetch import _chromium_launch_options

    video_id = _video_id_from_arg(video_id)
    url = _watch_url(video_id)
    captured: list[dict[str, Any]] = []
    caption_tracks: list[dict[str, Any]] = []
    youtubei_urls_seen: list[str] = []

    launch_opts = dict(_chromium_launch_options())
    if headless is not None:
        launch_opts["headless"] = headless

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_opts)
        context = browser.new_context(
            user_agent=_USER_AGENT,
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        cookies = _load_playwright_cookies(cookies_file)
        if cookies:
            context.add_cookies(cookies)
            logger.info("Loaded {} YouTube cookie(s) into browser context", len(cookies))

        page = context.new_page()
        _apply_stealth(page)

        def handle_response(response: Any) -> None:
            try:
                url = response.url or ""
                if "youtubei/v1/" in url and url not in youtubei_urls_seen:
                    youtubei_urls_seen.append(url)
                kind = _response_kind(url)
                if not kind:
                    return
                body = response.json()
                entry: dict[str, Any] = {
                    "kind": kind,
                    "url": url,
                    "status": response.status,
                    "payload": body,
                }
                if kind == "innertube":
                    tracks = _find_caption_tracks(body)
                    if tracks:
                        entry["caption_tracks"] = tracks
                        for tr in tracks:
                            if tr not in caption_tracks:
                                caption_tracks.append(tr)
                captured.append(entry)
                logger.info("Intercepted {} response ({})", kind, response.status)
            except Exception as exc:
                logger.debug("Response parse skip {}: {}", response.url[:120], exc)

        page.on("response", handle_response)
        page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
        page.wait_for_timeout(2000)
        ui_notes = _try_open_transcript_panel(page, wait_ms=panel_wait_ms)
        page.wait_for_timeout(1500)
        browser.close()

    timedtext_fetched: list[dict[str, Any]] = []
    if caption_tracks:
        import requests

        for tr in caption_tracks[:3]:
            base = (tr.get("baseUrl") or "").strip()
            if not base:
                continue
            try:
                r = requests.get(base, timeout=20, headers={"User-Agent": _USER_AGENT})
                r.raise_for_status()
                timedtext_fetched.append(
                    {
                        "languageCode": tr.get("languageCode"),
                        "name": tr.get("name", {}).get("simpleText") if isinstance(tr.get("name"), dict) else tr.get("name"),
                        "baseUrl": base[:200] + "..." if len(base) > 200 else base,
                        "format": tr.get("kind"),
                        "body_preview": (r.text or "")[:500],
                        "body_length": len(r.text or ""),
                    }
                )
                logger.info(
                    "Fetched timedtext track lang={} bytes={}",
                    tr.get("languageCode"),
                    len(r.text or ""),
                )
            except Exception as exc:
                timedtext_fetched.append(
                    {
                        "languageCode": tr.get("languageCode"),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    return {
        "video_id": video_id,
        "watch_url": url,
        "ui_interaction": ui_notes,
        "youtubei_urls_seen": youtubei_urls_seen[-30:],
        "caption_tracks": caption_tracks,
        "timedtext_fetched": timedtext_fetched,
        "intercepted": captured,
        "intercept_count": len(captured),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experimental Playwright transcript capture (network intercept)."
    )
    parser.add_argument("--video-id", default="", help="YouTube video id")
    parser.add_argument("--video-url", default="", help="Full watch URL")
    parser.add_argument(
        "--cookies",
        default="",
        help="Netscape cookies.txt (default: ./youtube_cookies.txt if present)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Write JSON result to this path (default: stdout only)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Visible browser (or SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false)",
    )
    args = parser.parse_args()

    vid = (args.video_id or args.video_url or "").strip()
    if not vid:
        parser.error("Provide --video-id or --video-url")

    headless = False if args.headed else None
    result = fetch_transcript_via_playwright(
        vid,
        cookies_file=args.cookies or None,
        headless=headless,
    )

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        logger.info("Wrote {} ({} intercepts)", out_path, result["intercept_count"])
    else:
        print(text)

    has_tracks = bool(result.get("caption_tracks"))
    has_timedtext = any(
        (t.get("body_length") or 0) > 0 for t in (result.get("timedtext_fetched") or [])
    )
    if result["intercept_count"] == 0 and not has_tracks:
        logger.warning(
            "No transcript/innertube responses captured. Try --headed, refresh cookies, "
            "or a video that has captions enabled. youtubei URLs seen: {}",
            len(result.get("youtubei_urls_seen") or []),
        )
        return 2
    if has_tracks and not has_timedtext:
        logger.warning(
            "Found caption track URLs in player/next JSON but timedtext download failed "
            "(often IP/proxy — same as caption API blocks)."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
