#!/usr/bin/env python3
"""
Download GoMeet (``gomeet.com``) meeting recordings for a scraped jurisdiction folder.

Sweet Grass County MT wraps recordings behind a lightweight gate (“Log in by entering your
information below”). This script uses Playwright to fill visible email/password/text inputs with
the **same** address (your site repeats the prompt twice), submits the form, exports cookies,
sniffs the authenticated session for media **URLs** (often the browser bar still shows
``RecordingDefault.aspx?…`` while ``Content-Type`` is ``video/mp4`` — not a separate ``.mp4``
path), then runs ``yt-dlp`` with cookies against that URL. When ``ffmpeg`` is available and
``SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS`` is not disabled, each downloaded container (``.mp4`` / ``.webm`` / …)
is transcoded to **Opus** (``.opus``) and the video file is removed by default
(``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS``), matching SuiteOne behavior in the meetings pipeline.
Use ``--skip-opus`` to keep the original file only.

**Credentials:** pass ``--email`` or set env ``GOMEET_LOGIN_EMAIL`` in the repo ``.env`` (loaded
automatically) or the shell. Do not commit real addresses. For optional runs without credentials,
use ``--skip-without-email`` to exit successfully with a warning.

Discover URLs from, in order:

1. ``other_video_streams`` in ``_manifest.json`` (``platform`` / host ``gomeet.com``), or
2. Regex scan of ``_crawl_html/*.html`` (fallback if manifest was generated before GoMeet support).

Anchor text from ``<a href="…gomeet…">`` in crawl HTML is merged per URL so filenames mirror the
YouTube audio layout (``YYYY-MM-DD_meeting_title_snake.ext``) and PDF naming helpers from
``meeting_document_naming``. Files are written under ``_gomeet_downloads/{calendar_year}/`` (four-digit
folder name, same spirit as PDF ``{year}/`` buckets).

Examples::

    # GOMEET_LOGIN_EMAIL in repo .env is picked up automatically
    .venv/bin/python -m scripts.discovery.download_gomeet_recordings \\
        --jurisdiction-dir data/cache/scraped_meetings/MT/county/county_30097 \\
        --limit 3

    # headed Chromium if headless is blocked
    SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false \\
      .venv/bin/python -m scripts.discovery.download_gomeet_recordings \\
        --jurisdiction-dir data/cache/scraped_meetings/MT/county/county_30097 \\
        --email 'you@example.com'

Outputs under ``{jurisdiction_dir}/_gomeet_downloads/{calendar_year}/`` with YouTube-style names.
For **existing** downloads only, run ``python -m scripts.discovery.gomeet_mp4_to_opus`` on the same jurisdiction path.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from scrapers.discovery.meeting_document_naming import (
    clean_anchor_text,
    infer_calendar_folder_year,
    pdf_meeting_title,
    pick_meeting_date,
    slugify_meeting_filename,
    strip_redundant_meeting_date_from_title,
)

from scripts.discovery.gomeet_mp4_to_opus import post_ytdlp_transcode_output

ROOT = Path(__file__).resolve().parents[2]


def _load_repo_dotenv() -> None:
    """Load ``<repo>/.env`` so ``GOMEET_LOGIN_EMAIL`` and Playwright env apply to ``python -m ...``."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(ROOT / ".env")


_GOMEET_HREF = re.compile(r"https://(?:www\.)?gomeet\.com/[^\s\"'<>]+", re.I)

_MEDIA_SUFFIXES = frozenset({".mp4", ".webm", ".mkv", ".m4a", ".opus"})


@dataclass
class GomeetJob:
    """One recording URL plus best-effort meeting title context from crawl/manifest."""

    url: str
    anchor_text: str = ""
    discovered_on: str = ""


def _normalize_gomeet_url(raw: str) -> str:
    u = (raw or "").strip().rstrip(").,]\">'\"")
    return u


def _pick_richer_anchor(existing: str, candidate: str) -> str:
    a = clean_anchor_text(existing)
    b = clean_anchor_text(candidate)
    if len(b) > len(a):
        return b
    return a


def enrich_anchor_from_recording_page_title(anchor_text: str, page_title: str) -> str:
    """Use ``Meeting Recording: …`` / ``<title>`` tails when crawl anchors are empty or generic."""
    t = (page_title or "").strip()
    if not t:
        return anchor_text
    low = t.lower()
    if "meeting recording" in low:
        parts = re.split(r":+", t, maxsplit=1)
        if len(parts) > 1:
            tail = parts[-1].strip()
            if tail and tail.lower() not in {"welcome", "online", "home", "sign in", "log in"}:
                base = clean_anchor_text(anchor_text)
                if not base:
                    return tail[:500]
                if tail.lower() not in base.lower():
                    return f"{base} — {tail}"[:500]
                return base
    if not clean_anchor_text(anchor_text) and 12 < len(t) < 300:
        return t
    return anchor_text


def build_gomeet_video_stem_and_year(url: str, anchor_text: str, *, fallback_year: int) -> Tuple[str, str]:
    """
    Calendar-year folder (string) + yt-dlp stem ``YYYY-MM-DD_title_snake`` / ``{year}_…`` / ``undated_…``.

    Aligns with :func:`scrapers.discovery.meeting_document_naming.build_meeting_pdf_disk_filename`
    prefixes without embedding ``doc_type``.
    """
    anchor = clean_anchor_text(anchor_text)
    d, _ = pick_meeting_date(url=url, anchor=anchor)
    cy = infer_calendar_folder_year(url, anchor, "", fallback_year=fallback_year)
    year_folder = str(cy)

    raw_title = pdf_meeting_title(anchor_text, url).strip() or "gomeet_recording"
    if d:
        date_prefix = d.isoformat()
        raw_title = strip_redundant_meeting_date_from_title(raw_title, d) or "gomeet_recording"
    else:
        ys = year_folder.strip()
        if ys.isdigit() and len(ys) == 4:
            yi = int(ys)
            date_prefix = ys if 1990 <= yi <= 2100 else "undated"
        else:
            date_prefix = "undated"

    slug = slugify_meeting_filename(raw_title)
    weak = frozenset(
        {
            "document",
            "meeting_document",
            "recording",
            "welcome",
            "meeting_recording",
            "gomeet_recording",
            "video",
        }
    )
    if slug in weak or len(slug) < 4:
        h = hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:8]
        slug = f"{slug}_{h}"

    stem = f"{date_prefix}_{slug}"
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    stem = re.sub(r"_+", "_", stem)
    if len(stem) > 200:
        stem = stem[:180].rstrip("._")
    return year_folder, stem


def _scrape_gomeet_links_from_html(blob: str, page_base: str) -> Dict[str, str]:
    """Map normalized GoMeet URL → richest anchor text from ``<a href>``."""
    best: Dict[str, str] = {}
    try:
        soup = BeautifulSoup(blob or "", "html.parser")
    except Exception:
        return best
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if "gomeet.com" not in href.lower():
            continue
        full = href if href.lower().startswith("http") else urljoin(page_base or "https://www.gomeet.com/", href)
        nu = _normalize_gomeet_url(full)
        if not nu.startswith("http"):
            continue
        label = clean_anchor_text(tag.get_text(" ", strip=True))
        if not label:
            continue
        prev = best.get(nu, "")
        best[nu] = _pick_richer_anchor(prev, label)
    return best


def iter_gomeet_jobs(jurisdiction_dir: Path) -> List[GomeetJob]:
    """Ordered jobs: manifest ``other_video_streams`` first, then crawl-only URLs."""
    manifest = jurisdiction_dir / "_manifest.json"
    ordered_keys: List[str] = []
    jobs: Dict[str, GomeetJob] = {}

    def touch(url_raw: str, *, anchor: str = "", discovered_on: str = "") -> None:
        nu = _normalize_gomeet_url(url_raw)
        if not nu.startswith("http") or "gomeet.com" not in nu.lower():
            return
        if nu not in jobs:
            jobs[nu] = GomeetJob(url=nu, anchor_text=anchor, discovered_on=discovered_on)
            ordered_keys.append(nu)
        else:
            j = jobs[nu]
            j.anchor_text = _pick_richer_anchor(j.anchor_text, anchor)
            if discovered_on and not j.discovered_on:
                j.discovered_on = discovered_on

    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("manifest_json_skip path={} err={}", manifest, exc)
            data = {}
        for row in data.get("other_video_streams") or []:
            if not isinstance(row, dict):
                continue
            u = (row.get("url") or "").strip()
            if "gomeet.com" not in u.lower():
                continue
            touch(
                u,
                anchor="",
                discovered_on=(row.get("discovered_on") or row.get("page_url") or "") or "",
            )

    crawl = jurisdiction_dir / "_crawl_html"
    if crawl.is_dir():
        for html_path in sorted(crawl.glob("*.html")):
            try:
                blob = html_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            base = f"file://{html_path.resolve()}"
            link_map = _scrape_gomeet_links_from_html(blob, base)
            for nu, anchor in link_map.items():
                touch(nu, anchor=anchor, discovered_on=base)
            for m in _GOMEET_HREF.finditer(blob):
                touch(m.group(0))

    if not ordered_keys:
        return []

    seen: Set[str] = set()
    out: List[GomeetJob] = []
    for k in ordered_keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(jobs[k])
    return out


def iter_gomeet_urls(jurisdiction_dir: Path) -> List[str]:
    """Backward-compatible URL-only list."""
    return [j.url for j in iter_gomeet_jobs(jurisdiction_dir)]


def _write_netscape_cookies(cookies: List[dict], path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in cookies:
        domain = (c.get("domain") or "").lstrip()
        if not domain:
            continue
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path_s = c.get("path") or "/"
        secure = "TRUE" if c.get("secure") else "FALSE"
        exp = c.get("expires")
        if exp is None or float(exp) < 0:
            expires_s = "0"
        else:
            expires_s = str(int(float(exp)))
        name = c.get("name") or ""
        value = c.get("value") or ""
        if not name:
            continue
        lines.append(f"{domain}\t{include_sub}\t{path_s}\t{secure}\t{expires_s}\t{name}\t{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _fill_gate_on_frame(fr, email: str, lp: str) -> None:
    """Fill gate inputs inside a single Playwright Frame (main page or iframe)."""
    loc = fr.locator(
        'input[type="email"], input[type="password"], input[type="text"], input:not([type])'
    )
    n = await loc.count()
    logger.info("{}gate_locator_candidates n={}", lp, n)
    filled = 0
    for i in range(min(n, 8)):
        inp = loc.nth(i)
        try:
            if not await inp.is_visible():
                continue
            typ = ((await inp.get_attribute("type")) or "text").lower()
            if typ in ("hidden", "submit", "button", "checkbox", "radio", "file"):
                continue
            await inp.fill(email)
            filled += 1
        except Exception:
            continue
    logger.info("{}gate_fields_filled={}", lp, filled)
    if filled == 0:
        raise RuntimeError("No gate inputs filled — update selectors for this GoMeet skin.")

    clicked = False
    logger.info("{}gate_click_submit…", lp)
    for sel in ('button[type="submit"]', 'input[type="submit"]'):
        hit = fr.locator(sel)
        if await hit.count() == 0:
            continue
        btn = hit.first
        try:
            if await btn.is_visible():
                await btn.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        try:
            await fr.get_by_role("button", name=re.compile(r"log\s*in|submit|continue", re.I)).click()
            clicked = True
        except Exception:
            pass
    if not clicked:
        try:
            await fr.keyboard.press("Enter")
        except Exception:
            pass
    logger.info("{}gate_submit_dispatched clicked={}", lp, clicked)


async def _submit_gomeet_gate(page, email: str, *, log_prefix: str = "") -> None:
    """Fill visible gate inputs — searches main document and iframes (GoMeet may nest the form)."""
    lp = f"{log_prefix} " if log_prefix else ""
    logger.info(
        "{}gate_poll_inputs_main_and_iframes (up to 90s; heartbeats mean Playwright is alive)…",
        lp,
    )
    deadline = time.monotonic() + 90.0
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        frames = list(page.frames)
        # Exclude ASP.NET/WebForms hidden inputs (__EVENTTARGET, etc.) — generic "input"
        # visibility waits pick those first and never succeed.
        inp_sel = 'input:not([type="hidden"])'
        for fi, fr in enumerate(frames):
            try:
                n_inp = await fr.locator(inp_sel).count()
            except Exception:
                continue
            if n_inp == 0:
                continue
            visible = 0
            for j in range(min(n_inp, 16)):
                try:
                    el = fr.locator(inp_sel).nth(j)
                    if await el.is_visible():
                        visible += 1
                except Exception:
                    continue
            if visible == 0:
                continue
            frag = (getattr(fr, "url", None) or "")[:120]
            logger.info(
                "{}gate_inputs_found frame_index={} frames_total={} visible_inputs={} frame_url={!r}",
                lp,
                fi,
                len(frames),
                visible,
                frag,
            )
            await _fill_gate_on_frame(fr, email, lp)
            return

        if attempt == 1 or attempt % 4 == 0:
            logger.info(
                "{}gate_poll attempt={} elapsed_s={:.0f} frames_seen={} (waiting for inputs…) ",
                lp,
                attempt,
                time.monotonic() - (deadline - 90.0),
                len(frames),
            )
        await asyncio.sleep(2)

    raise TimeoutError(
        "gate_timeout: no visible <input> in main frame or iframes within 90s — "
        "try SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false or inspect site DOM."
    )


def urlparse_last_segment(url: str) -> str:
    return (url.rstrip("/").split("/")[-1] or "recording").split("?")[0]


def output_stem(url: str) -> str:
    raw = urlparse_last_segment(url)
    return re.sub(r"[^\w.-]+", "_", raw)[:120] or "recording"


_M3U8_IN_HTML = re.compile(r'https?://[^\s"\'<>]+m3u8[^\s"\'<>]*', re.I)
_MP4_IN_HTML = re.compile(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', re.I)
_MPD_IN_HTML = re.compile(r'https?://[^\s"\'<>]+\.mpd[^\s"\'<>]*', re.I)
_ISM_MANIFEST_HTML = re.compile(r'https?://[^\s"\'<>]+\.ism/manifest[^\s"\'<>]*', re.I)


def _remember_media_url(bucket: List[str], raw: str, *, base_url: str, trust_as_media: bool = False) -> None:
    u = (raw or "").strip()
    if not u or u.startswith("blob:") or u.startswith("data:"):
        return
    if not u.startswith("http"):
        try:
            u = urljoin(base_url, u)
        except Exception:
            return
    if trust_as_media:
        if u not in bucket:
            bucket.append(u)
        return

    lu = u.lower()
    path_q = lu.split("?", 1)[0]
    stream_like = (
        ".m3u8" in lu
        or path_q.endswith(".mp4")
        or path_q.endswith(".mpd")
        or ".ism/manifest" in lu
        or "format=m3u8" in lu
    )
    if not stream_like:
        return
    if u not in bucket:
        bucket.append(u)


def pick_gomeet_stream_url(candidates: List[str]) -> str | None:
    """Prefer a master / playlist m3u8, then any m3u8, then mp4."""
    if not candidates:
        return None
    lowered = [(u, u.lower()) for u in candidates]

    def score(item: tuple[str, str]) -> tuple[int, int]:
        _u, lu = item
        path = lu.split("?", 1)[0]
        if path.endswith(".mp4"):
            return (2, -len(lu))
        if path.endswith(".mpd") or ".ism/manifest" in lu:
            return (3, -len(lu))
        pri = 0
        if "master" in lu or "playlist" in lu or "index.m3u8" in lu:
            pri = 5
        elif ".m3u8" in lu:
            pri = 4
        if pri > 0:
            return (pri, -len(lu))
        # GoMeet often serves inline MP4 bytes on RecordingDefault.aspx (path stays .aspx).
        if "recordingdefault.aspx" in lu:
            return (2, -len(lu))
        return (0, -len(lu))

    lowered.sort(key=score, reverse=True)
    return lowered[0][0]


def _gomeet_media_response_handler(bucket: List[str], debug_hints: List[str]):
    """Capture manifest/media URLs from Playwright responses (attach before goto)."""

    _HINT_KEYS = (
        ".m3u8",
        "chunklist",
        "stream.mp4",
        ".mpd",
        ".ism",
        "mediapackage",
        "/hls/",
        "format=m3u8",
    )
    _MAX_HINTS = 60

    def on_response(response) -> None:
        try:
            url = response.url
            ct = (response.headers.get("content-type") or "").lower()
            lu = url.lower()
            if ".m3u8" in lu or "mpegurl" in ct or "application/vnd.apple.mpegurl" in ct:
                _remember_media_url(bucket, url, base_url=url)
            path = lu.split("?", 1)[0]
            cd = (response.headers.get("content-disposition") or "").lower()
            mp4_body = (
                "video/mp4" in ct
                or path.endswith(".mp4")
                or (
                    "octet-stream" in ct
                    and "attachment" in cd
                    and ".mp4" in cd
                )
            )
            if mp4_body:
                _remember_media_url(bucket, url, base_url=url, trust_as_media=True)
            if path.endswith(".mpd") or "dash+xml" in ct:
                _remember_media_url(bucket, url, base_url=url)
            if ".ism/manifest" in lu:
                _remember_media_url(bucket, url, base_url=url)

            streamish = (
                any(k in lu for k in _HINT_KEYS)
                or "mpegurl" in ct
                or "dash+xml" in ct
                or "video/mp4" in ct
            )
            if len(debug_hints) < _MAX_HINTS and streamish:
                cand = url[:260]
                if cand not in debug_hints:
                    debug_hints.append(cand)
        except Exception:
            pass

    return on_response


_DOM_MEDIA_JS = """() => {
  const out = [];
  for (const v of document.querySelectorAll("video")) {
    if (v.src) out.push(v.src);
    if (v.currentSrc) out.push(v.currentSrc);
  }
  for (const s of document.querySelectorAll("video source, audio source")) {
    if (s.src) out.push(s.src);
  }
  return out;
}"""


async def gather_gomeet_media_candidates(page, bucket: List[str], *, log_prefix: str) -> None:
    """Merge video/audio tag URLs and HTML regex hits from every frame into bucket."""
    for fi, fr in enumerate(page.frames):
        try:
            dom_urls = await fr.evaluate(_DOM_MEDIA_JS)
            base = (getattr(fr, "url", None) or page.url or "").strip() or "https://www.gomeet.com/"
            if isinstance(dom_urls, list):
                for u in dom_urls:
                    if isinstance(u, str):
                        _remember_media_url(bucket, u, base_url=base)
        except Exception as exc:
            logger.info("{} collect_dom_media_skip frame_index={} {!r}", log_prefix, fi, exc)

    for fi, fr in enumerate(page.frames):
        try:
            blob = await fr.content()
            base = (getattr(fr, "url", None) or page.url or "").strip() or "https://www.gomeet.com/"
            for rx in (_M3U8_IN_HTML, _MP4_IN_HTML, _MPD_IN_HTML, _ISM_MANIFEST_HTML):
                for m in rx.finditer(blob):
                    _remember_media_url(bucket, m.group(0), base_url=base)
        except Exception as exc:
            logger.info("{} collect_html_media_skip frame_index={} {!r}", log_prefix, fi, exc)

    logger.info(
        "{} media_candidates_found n={} sample={}",
        log_prefix,
        len(bucket),
        [_short_url(u) for u in bucket[:8]],
    )


async def try_start_gomeet_playback(page, *, log_prefix: str) -> None:
    """Best-effort: unmute + play() + click video + obvious Play buttons (HLS often loads lazily)."""
    logger.info("{} playback_try_start", log_prefix)
    for fi, fr in enumerate(page.frames):
        try:
            await fr.evaluate(
                """() => {
                  document.querySelectorAll("video,audio").forEach((m) => {
                    try {
                      m.muted = true;
                      m.play();
                    } catch (e) {}
                  });
                }"""
            )
        except Exception as exc:
            logger.info("{} playback_eval_skip frame_index={} {!r}", log_prefix, fi, exc)

    try:
        if await page.locator("video").count() > 0:
            await page.locator("video").first.click(timeout=8000)
    except Exception:
        pass

    for pat in (r"play\s*recording", r"^play$", r"watch", r"start"):
        try:
            await page.get_by_role("button", name=re.compile(pat, re.I)).first.click(timeout=2500)
            break
        except Exception:
            continue

    try:
        await page.keyboard.press("Space")
    except Exception:
        pass


def _short_url(u: str, max_len: int = 96) -> str:
    u = (u or "").strip()
    return u if len(u) <= max_len else u[: max_len - 3] + "..."


def _heartbeat(tag: str, stop: threading.Event, interval_s: float = 25.0) -> None:
    """Background thread: proves the process is alive during long Playwright / yt-dlp waits."""
    start = time.monotonic()
    n = 0
    while not stop.wait(timeout=interval_s):
        n += 1
        elapsed = int(time.monotonic() - start)
        logger.info(
            "gomeet_heartbeat tag={} elapsed_s={} ticks={} (still working — not stuck)",
            tag,
            elapsed,
            n,
        )


async def _download_one_url(
    *,
    launch_kw: dict,
    job: GomeetJob,
    fallback_year: int,
    email: str,
    out_dir: Path,
    yt_dlp_bin: str,
    navigation_timeout_ms: float,
    yt_dlp_quiet: bool,
    log_prefix: str,
    skip_opus: bool = False,
) -> tuple[bool, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    url = job.url.strip()
    provisional_stem = output_stem(url)
    page_title_snapshot = ""

    from playwright.async_api import async_playwright

    cookies: List[dict] = []
    media_bucket: List[str] = []
    stream_debug_hints: List[str] = []
    hb_stop = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat,
        kwargs={"tag": log_prefix, "stop": hb_stop, "interval_s": 12.0},
        daemon=True,
    )

    logger.info(
        "{} playwright_start url={} id={} headless={}",
        log_prefix,
        _short_url(url),
        provisional_stem,
        launch_kw.get("headless", True),
    )
    hb_thread.start()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kw)
            try:
                context = await browser.new_context(locale="en-US")
                page = await context.new_page()
                page.set_default_navigation_timeout(int(navigation_timeout_ms))
                media_handler = _gomeet_media_response_handler(media_bucket, stream_debug_hints)
                page.on("response", media_handler)
                try:
                    logger.info("{} goto domcontentloaded…", log_prefix)
                    await page.goto(url, wait_until="domcontentloaded")
                    logger.info("{} gate_fill_submit…", log_prefix)
                    await _submit_gomeet_gate(page, email, log_prefix=log_prefix)

                    stream_early = False
                    logger.info("{} post_gate_media_poll (up to 10s — catches POST MP4 on RecordingDefault.aspx)", log_prefix)
                    deadline_pg = time.monotonic() + 10.0
                    while time.monotonic() < deadline_pg:
                        su_pg = pick_gomeet_stream_url(media_bucket)
                        if su_pg:
                            logger.info(
                                "{} media_detected_post_gate_eliding_playback url={}",
                                log_prefix,
                                _short_url(su_pg),
                            )
                            stream_early = True
                            break
                        await asyncio.sleep(0.4)

                    if not stream_early:
                        logger.info(
                            "{} wait_post_login (networkidle up to 60s; long-lived streams may skip early)",
                            log_prefix,
                        )
                        try:
                            await page.wait_for_load_state("networkidle", timeout=60_000)
                        except Exception as exc:
                            logger.info(
                                "{} networkidle_timeout_or_skip fallback_sleep_3s detail={!r}",
                                log_prefix,
                                exc,
                            )
                            await asyncio.sleep(3)
                        try:
                            await page.wait_for_selector("video,audio", timeout=45_000)
                        except Exception:
                            logger.info(
                                "{} no_video_audio_selector_yet (playback retry may still surface m3u8)",
                                log_prefix,
                            )
                        for settle_pass in (1, 2):
                            logger.info("{} playback_settle_pass={}/2", log_prefix, settle_pass)
                            await try_start_gomeet_playback(page, log_prefix=log_prefix)
                            sleep_s = 14 if settle_pass == 1 else 22
                            logger.info(
                                "{} playback_settle_sleep_s={} (heartbeats continue — capturing lazy streams)",
                                log_prefix,
                                sleep_s,
                            )
                            await asyncio.sleep(sleep_s)
                            await gather_gomeet_media_candidates(page, media_bucket, log_prefix=log_prefix)
                            if pick_gomeet_stream_url(media_bucket):
                                break
                    try:
                        page_title_snapshot = await page.title()
                    except Exception:
                        page_title_snapshot = ""
                    cookies = await context.cookies()
                    logger.info("{} playwright_done cookies_saved={}", log_prefix, len(cookies))
                finally:
                    try:
                        page.remove_listener("response", media_handler)
                    except Exception:
                        pass
                    await context.close()
            except Exception as exc:
                return False, f"playwright:{exc!r}"
            finally:
                await browser.close()
    finally:
        hb_stop.set()
        hb_thread.join(timeout=2.0)

    stream_url = pick_gomeet_stream_url(media_bucket)
    if not stream_url:
        logger.warning(
            "{} no_stream_url network_hints_tail={}",
            log_prefix,
            stream_debug_hints[-25:],
        )
        return (
            False,
            "no_stream_url: yt-dlp cannot fetch RecordingDefault.aspx directly (unsupported). "
            "After gate login we found no m3u8/mpd/mp4 in network/DOM — check log "
            "no_stream_url network_hints_tail=... for playlist-looking URLs; try headed "
            "SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS=false, DRM/MediaSource-only blob playback, "
            "or manual DevTools Network.",
        )

    enriched_anchor = enrich_anchor_from_recording_page_title(job.anchor_text, page_title_snapshot)
    year_folder, stem = build_gomeet_video_stem_and_year(url, enriched_anchor, fallback_year=fallback_year)
    year_dir = out_dir / year_folder
    year_dir.mkdir(parents=True, exist_ok=True)
    target_tpl = str(year_dir / f"{stem}.%(ext)s")
    logger.info(
        "{} output_layout year_folder={} file_stem={}",
        log_prefix,
        year_folder,
        stem,
    )

    logger.info(
        "{} yt_dlp_input_stream_url={} (recording_gate_page={})",
        log_prefix,
        _short_url(stream_url),
        _short_url(url),
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="gomeet_cookies_", delete=False, encoding="utf-8"
    ) as tmp:
        cookie_path = Path(tmp.name)
    try:
        _write_netscape_cookies(cookies, cookie_path)
        cmd = [
            yt_dlp_bin,
            "--newline",
            "--progress",
            "--no-warnings",
            "--add-header",
            f"Referer:{url}",
            "-o",
            target_tpl,
            "--cookies",
            str(cookie_path),
            "--retries",
            "5",
            "--fragment-retries",
            "5",
            stream_url,
        ]
        logger.info(
            "{} yt_dlp_start (quiet={}) — output streams below if quiet=false",
            log_prefix,
            yt_dlp_quiet,
        )
        hb_stop2 = threading.Event()
        hb_thread2 = threading.Thread(
            target=_heartbeat,
            kwargs={"tag": f"{log_prefix}/yt-dlp", "stop": hb_stop2, "interval_s": 20.0},
            daemon=True,
        )
        hb_thread2.start()
        try:
            if yt_dlp_quiet:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                    cwd=str(ROOT),
                )
                if proc.returncode != 0:
                    tail = (proc.stderr or proc.stdout or "")[-2500:]
                    return False, f"yt-dlp_exit_{proc.returncode}:{tail}"
            else:
                # Let yt-dlp draw progress to the terminal (not “stuck” when buffers are empty).
                proc = subprocess.run(
                    cmd,
                    timeout=3600,
                    cwd=str(ROOT),
                )
                if proc.returncode != 0:
                    return (
                        False,
                        f"yt-dlp_exit_{proc.returncode} (re-run with --yt-dlp-quiet for captured stderr)",
                    )
        finally:
            hb_stop2.set()
            hb_thread2.join(timeout=2.0)

        logger.info("{} yt_dlp_exit_ok stem={}", log_prefix, stem)
        if not skip_opus:
            post_ytdlp_transcode_output(year_dir, stem, respect_download_mp4_opus_env=True)
        return True, ""
    finally:
        try:
            cookie_path.unlink(missing_ok=True)
        except OSError:
            pass


async def _async_main(args: argparse.Namespace) -> int:
    email = (args.email or os.getenv("GOMEET_LOGIN_EMAIL") or "").strip()
    if not email:
        if args.skip_without_email:
            logger.warning(
                "No --email / GOMEET_LOGIN_EMAIL; skipping GoMeet downloads "
                "(gate form requires an address). Exit 0."
            )
            return 0
        logger.error("Set --email or GOMEET_LOGIN_EMAIL for the gate form.")
        return 2

    jdir = Path(args.jurisdiction_dir).expanduser().resolve()
    if not jdir.is_dir():
        logger.error("Not a directory: {}", jdir)
        return 2

    yt_dlp_bin = shutil.which(args.yt_dlp) or args.yt_dlp
    if not yt_dlp_bin:
        logger.error("yt-dlp not found on PATH (install yt-dlp or pass --yt-dlp).")
        return 2

    fy_raw = int(args.fallback_year or 0)
    fallback_year = fy_raw if 1990 <= fy_raw <= 2100 else datetime.now().year

    jobs = iter_gomeet_jobs(jdir)
    if args.limit > 0:
        jobs = jobs[: args.limit]
    if not jobs:
        logger.error(
            "No gomeet.com URLs found under {} (populate manifest other_video_streams or keep "
            "_crawl_html snapshots).",
            jdir,
        )
        return 2

    out_root = (Path(args.out_dir).expanduser().resolve() if args.out_dir else jdir / "_gomeet_downloads")
    out_root.mkdir(parents=True, exist_ok=True)

    n_total = len(jobs)
    logger.info(
        "gomeet_batch_start n_jobs={} out_dir={} fallback_year={} concurrency={} yt_dlp_quiet={}",
        n_total,
        out_root,
        fallback_year,
        max(1, args.concurrency),
        args.yt_dlp_quiet,
    )
    if args.skip_opus:
        logger.warning(
            "skip_opus=True: no post-download transcoding; MP4/webm sources are left on disk for this run"
        )

    launch_kw = {
        "headless": (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_HEADLESS") or "true").strip().lower()
        not in ("0", "false", "no", "off")
    }
    exe = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_CHROMIUM_EXECUTABLE") or "").strip()
    if exe and Path(exe).is_file():
        launch_kw["executable_path"] = exe
    else:
        ch = (os.getenv("SCRAPED_MEETINGS_PLAYWRIGHT_CHANNEL") or "").strip().lower()
        if ch in ("chrome", "msedge", "chromium"):
            launch_kw["channel"] = ch

    sem = asyncio.Semaphore(max(1, args.concurrency))

    ok_n = 0
    fail_n = 0

    async def one(idx: int, job: GomeetJob) -> None:
        nonlocal ok_n, fail_n
        prefix = f"gomeet[{idx}/{n_total}]"
        y0, stem0 = build_gomeet_video_stem_and_year(job.url, job.anchor_text, fallback_year=fallback_year)
        dest_dir = out_root / y0
        if args.skip_existing:
            media = [
                p
                for p in dest_dir.glob(f"{re.escape(stem0)}.*")
                if p.suffix.lower() in _MEDIA_SUFFIXES
            ]
            if media:
                logger.info("{} skip_existing path={}", prefix, media[0])
                ok_n += 1
                return
        async with sem:
            good, err = await _download_one_url(
                launch_kw=launch_kw,
                job=job,
                fallback_year=fallback_year,
                email=email,
                out_dir=out_root,
                yt_dlp_bin=yt_dlp_bin,
                navigation_timeout_ms=float(args.timeout * 1000),
                yt_dlp_quiet=args.yt_dlp_quiet,
                log_prefix=prefix,
                skip_opus=args.skip_opus,
            )
        label = f"{y0}/{stem0}"
        if good:
            ok_n += 1
            logger.success("{} done_ok {}", prefix, label)
        else:
            fail_n += 1
            logger.warning("{} done_fail {} detail={}", prefix, label, err)

    await asyncio.gather(*(one(i + 1, j) for i, j in enumerate(jobs)))
    logger.info("gomeet_batch_done ok={} fail={} out_dir={}", ok_n, fail_n, out_root)
    return 0 if fail_n == 0 else 1


def main() -> None:
    _load_repo_dotenv()
    ap = argparse.ArgumentParser(description="Download GoMeet recordings after gate login.")
    ap.add_argument(
        "--jurisdiction-dir",
        required=True,
        help="Scrape folder e.g. data/cache/scraped_meetings/MT/county/county_30097",
    )
    ap.add_argument(
        "--email",
        default="",
        help="Same value for both gate fields; else env GOMEET_LOGIN_EMAIL.",
    )
    ap.add_argument(
        "--skip-without-email",
        action="store_true",
        help="If email is unset, log and exit 0 instead of failing (for optional pipeline steps).",
    )
    ap.add_argument("--out-dir", default="", help="Video output directory (default _gomeet_downloads).")
    ap.add_argument(
        "--fallback-year",
        type=int,
        default=0,
        metavar="YYYY",
        help="Calendar year for folder + filename when the meeting date cannot be inferred (default: current year).",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max URLs (0 = all).")
    ap.add_argument("--concurrency", type=int, default=1, help="Parallel downloads (default 1).")
    ap.add_argument("--timeout", type=float, default=120.0, help="Navigation timeout (seconds).")
    ap.add_argument("--yt-dlp", default="yt-dlp", help="yt-dlp executable name or path.")
    ap.add_argument(
        "--yt-dlp-quiet",
        action="store_true",
        help="Capture yt-dlp output only (less console noise; logs tail on failure). Default: stream yt-dlp to your terminal.",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip when an output file with matching stem already exists.",
    )
    ap.add_argument(
        "--skip-opus",
        action="store_true",
        help="Do not transcode to Opus or delete MP4 (overrides SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS for this run).",
    )
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
