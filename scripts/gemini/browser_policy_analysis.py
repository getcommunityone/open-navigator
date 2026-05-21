#!/usr/bin/env python3
"""
Drive Gemini in a **headed Chrome** session (your profile) to run ``policy_analysis_v1`` on
YouTube rows from ``bronze.bronze_events_youtube``.

**Before running:** quit Google Chrome completely (same profile folder) or Playwright will
fail with a profile lock error.

If you only see a **blank white page** and the automation banner, the script was reusing an
empty tab without finishing navigation. Re-run with ``--open-only --pause-after-open`` to
confirm Gemini loads (and sign in if needed).

Examples::

    # List Tuscaloosa videos that would be sent (no browser)
    python scripts/gemini/browser_policy_analysis.py --dry-run

    # Analyze the most recently updated video only
    python scripts/gemini/browser_policy_analysis.py --limit 1

    # One specific video
    python scripts/gemini/browser_policy_analysis.py --video-id dQw4w9WgXcQ

    # Debug blank page / login (no prompt sent)
    python scripts/gemini/browser_policy_analysis.py --open-only --pause-after-open

    # Recommended on WSL: start Chrome yourself, then attach (avoids about:blank + profile locks)
    google-chrome --remote-debugging-port=9222
    python scripts/gemini/browser_policy_analysis.py --cdp-url http://127.0.0.1:9222 --open-only --pause-after-open

    # Or isolated Playwright Chromium profile (sign into Google once)
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --open-only --pause-after-open

    # Loop URLs in one Gemini tab (reloads gemini.google.com between videos)
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --limit 3

    # With CDP (Chrome already running with --remote-debugging-port=9222)
    python scripts/gemini/browser_policy_analysis.py --cdp-url http://127.0.0.1:9222 --limit 5

    # WSL: point at Windows Chrome user data (optional)
    export GEMINI_CHROME_USER_DATA_DIR='/mnt/c/Users/You/AppData/Local/Google/Chrome/User Data'
    export GEMINI_CHROME_PROFILE_NAME='Default'
    python scripts/gemini/browser_policy_analysis.py --limit 3

    # Same meeting, two prompts — each run gets its own timestamped .json/.md (compare via _manifest.jsonl)
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --video-id ajsME66iXbY --prompt-file prompts/policy_analysis_v1.md
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --video-id ajsME66iXbY --prompt-file prompts/policy_analysis.md

    # Use Gemini 3.1 Pro (requires Pro/Ultra in your Google account; pick in UI or automate)
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --select-model "3.1 Pro" --gemini-model "3.1 Pro" --limit 1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Sequence

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_PROMPT_PATH = _REPO_ROOT / "prompts" / "policy_analysis_v1.md"
DEFAULT_JURISDICTION_ID = "municipality_0177256"
DEFAULT_GEMINI_URL = "https://gemini.google.com/app"
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_browser_policy"

# Input + response selectors (Google changes these often — extend if UI breaks).
INPUT_SELECTORS = (
    'div[contenteditable="true"][aria-label*="Enter" i]',
    'div[contenteditable="true"][data-placeholder]',
    "div.ql-editor[contenteditable='true']",
    'div[contenteditable="true"]',
    "textarea",
)
SEND_BUTTON_SELECTORS = (
    'button[aria-label*="Send" i]',
    'button[aria-label*="Submit" i]',
    'button[data-test-id="send-button"]',
    "button.send-button",
)
RESPONSE_SELECTORS = (
    '[data-message-author-role="model"]',
    '[data-message-author-role="assistant"]',
    "model-response",
    "model-response message-content",
    "message-content.model-response-text",
    "div.model-response-text",
    "div.markdown.markdown-main-panel",
    '[class*="model-response"]',
    '[class*="assistant-message"]',
    "div.response-content",
    ".presented-response-container",
    "message-content",
)
# Only match *inside* the chat area (broad selectors false-positive on sidebar).
GENERATING_SELECTORS = (
    '[class*="thinking" i]',
    '[aria-label*="Generating" i]',
    'button[aria-label*="Stop" i]',
)
CHAT_ROOT_SELECTORS = ("main", '[role="main"]', '[class*="conversation"]')
# Policy prompt output sections — if present, Gemini is done (do not wait on sidebar spinners).
RESPONSE_COMPLETE_MARKERS = (
    "Decision Themes Index",
    "Decision ID",
    "Financial Summary",
    "People and Organizations",
    "Governing and Administrative Entities",
)


@dataclass
class VideoRow:
    video_id: str
    video_url: str
    title: Optional[str]
    last_updated: Optional[datetime]
    event_date: Optional[str]
    audio_file_path: Optional[str]
    jurisdiction_id: str


@dataclass
class GeminiRunCapture:
    response_text: str
    gemini_model: Optional[str]


def _sanitize_tag(label: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_")
    return (s[:max_len] if s else "unknown")


def default_chrome_user_data_dir() -> Path:
    explicit = (os.getenv("GEMINI_CHROME_USER_DATA_DIR") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    return home / ".config" / "google-chrome"


def default_chrome_profile() -> str:
    return (os.getenv("GEMINI_CHROME_PROFILE_NAME") or "Default").strip() or "Default"


def resolve_chrome_launch(
    user_data_root: Path,
    profile_name: str,
) -> tuple[Path, List[str]]:
    """
    Playwright ``user_data_dir`` must be Chrome's **User Data** root (has ``Local State``).
    Profile is selected via ``--profile-directory=…``.
    """
    root = user_data_root.expanduser().resolve()
    if (root / "Local State").is_file():
        return root, [f"--profile-directory={profile_name}"]
    if (root.parent / "Local State").is_file():
        return root.parent, [f"--profile-directory={root.name}"]
    if (root / profile_name).is_dir():
        return root, [f"--profile-directory={profile_name}"]
    return root, [f"--profile-directory={profile_name}"]


def _dismiss_startup_dialogs(page: Any) -> None:
    """Best-effort dismissals for consent / onboarding overlays."""
    from playwright.sync_api import TimeoutError as PwTimeout

    for label in ("Got it", "Accept all", "I agree", "Continue", "OK", "Dismiss"):
        try:
            page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I)).first.click(
                timeout=1_500
            )
            time.sleep(0.5)
        except PwTimeout:
            pass
        except Exception:
            pass


def _is_blank_chrome_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return not u or u in ("about:blank", "chrome://newtab/", "chrome://new-tab-page/")


def _navigate_to_gemini(
    page: Any,
    gemini_url: str,
    *,
    timeout_ms: int,
    allow_manual: bool = False,
) -> None:
    """Open Gemini and wait until the host is loaded (not stuck on about:blank)."""
    from playwright.sync_api import TimeoutError as PwTimeout

    logger.info("Navigating to {} …", gemini_url)

    for wait_until in ("commit", "domcontentloaded", "load"):
        try:
            response = page.goto(gemini_url, wait_until=wait_until, timeout=timeout_ms)
            status = response.status if response else "?"
            logger.info("goto({}) status={} url={}", wait_until, status, page.url)
            if not _is_blank_chrome_url(page.url):
                break
        except Exception as exc:
            logger.warning("goto({}) failed: {}", wait_until, exc)

    if _is_blank_chrome_url(page.url):
        logger.info("Trying JavaScript navigation …")
        try:
            page.evaluate("(url) => { window.location.assign(url); }", gemini_url)
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            logger.info("After JS assign: url={}", page.url)
        except Exception as exc:
            logger.warning("JS navigation failed: {}", exc)

    if _is_blank_chrome_url(page.url):
        logger.info("Trying address bar (Ctrl+L) …")
        try:
            page.keyboard.press("Control+l")
            page.wait_for_timeout(300)
            page.keyboard.type(gemini_url, delay=20)
            page.keyboard.press("Enter")
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            logger.info("After address bar: url={}", page.url)
        except Exception as exc:
            logger.warning("Address bar navigation failed: {}", exc)

    page.wait_for_timeout(2_000)

    try:
        page.wait_for_url(
            re.compile(r"(gemini\.google\.com|accounts\.google\.com)"),
            timeout=30_000,
        )
    except PwTimeout:
        logger.warning("URL after navigation attempts: {!r}", page.url)

    if "accounts.google.com" in (page.url or ""):
        logger.warning(
            "Google sign-in — log in in the browser window. Waiting up to 120s for Gemini …"
        )
        page.wait_for_url(re.compile(r"gemini\.google\.com"), timeout=120_000)

    _dismiss_startup_dialogs(page)
    page.wait_for_timeout(1_000)

    if _is_blank_chrome_url(page.url):
        if allow_manual:
            logger.warning(
                "Still on a blank tab. In the browser, go to:\n  {}\n"
                "Then press Enter in this terminal …",
                gemini_url,
            )
            input()
            return
        raise RuntimeError(
            f"Browser stuck on {page.url!r}. Try:\n"
            f"  1) python ... --cdp-url http://127.0.0.1:9222  (start Chrome with --remote-debugging-port=9222 first)\n"
            f"  2) python ... --fresh-profile  (Playwright Chromium profile; sign in once)\n"
            f"  3) python ... --open-only --pause-after-open"
        )


def _debug_screenshot(page: Any, output_dir: Path, label: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"debug_{label}_{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info("Debug screenshot: {}", path)
    return path


def _database_url(explicit: Optional[str]) -> str:
    load_dotenv(_REPO_ROOT / ".env")
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def fetch_videos(
    database_url: str,
    jurisdiction_id: str,
    *,
    limit: Optional[int] = None,
    video_id: Optional[str] = None,
) -> List[VideoRow]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT DISTINCT ON (video_url)
            video_id,
            video_url,
            title,
            last_updated,
            event_date::text AS event_date,
            audio_file_path,
            jurisdiction_id
        FROM bronze.bronze_events_youtube
        WHERE jurisdiction_id = %s
          AND video_url IS NOT NULL
          AND BTRIM(video_url) <> ''
    """
    params: list[Any] = [jurisdiction_id]
    if video_id:
        sql += " AND video_id = %s"
        params.append(video_id)
    sql += " ORDER BY video_url, last_updated DESC NULLS LAST"
    if limit is not None:
        sql = f"SELECT * FROM ({sql}) sub ORDER BY last_updated DESC NULLS LAST LIMIT %s"
        params.append(int(limit))

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    out: List[VideoRow] = []
    for r in rows:
        out.append(
            VideoRow(
                video_id=str(r["video_id"] or ""),
                video_url=str(r["video_url"] or "").strip(),
                title=(r.get("title") or None),
                last_updated=r.get("last_updated"),
                event_date=r.get("event_date"),
                audio_file_path=r.get("audio_file_path"),
                jurisdiction_id=str(r.get("jurisdiction_id") or jurisdiction_id),
            )
        )
    return out


def load_policy_prompt(prompt_path: Path) -> str:
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Policy prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def build_user_message(
    policy_prompt: str,
    video: VideoRow,
    *,
    media_source_id: str = "MS001",
) -> str:
    """Full Gemini user turn: policy instructions + MEDIA CONTEXT for one recording."""
    title = (video.title or "Untitled meeting recording").strip()
    event_date = video.event_date or "unknown"
    local_note = ""
    if video.audio_file_path:
        local_note = (
            f"\n- local_relative_path: data/cache/youtube_audio/{video.audio_file_path}"
            "\n  (Opus audio on disk; use the YouTube URL below as the canonical recording if you cannot open the local file.)"
        )

    media_block = f"""
---
## MEDIA CONTEXT (required for this analysis)

Analyze **one** governance meeting recording. Use the YouTube watch URL as the primary source.
Set `meeting.input_modality` to `video_recording` (or `audio_recording` if only audio is available).
Populate `meeting.media_sources[]` from this block exactly — do not invent URLs.

| Field | Value |
|-------|-------|
| media_source_id | {media_source_id} |
| platform | youtube |
| canonical_url | {video.video_url} |
| page_url | {video.video_url} |
| mime_type | video/youtube |
| is_primary | true |
| title | {title} |
| jurisdiction_id | {video.jurisdiction_id} |
| event_date | {event_date} |
{local_note}

**Jurisdiction:** City of Tuscaloosa, Alabama (incorporated municipality).

**Task:** Apply the policy analysis instructions below to this recording. If you cannot access the video directly, state that limitation in Document 1 under a top-level `"_error"` field, then still emit valid minimal JSON and Document 2 per the schema rules.

---
""".strip()

    return f"{media_block}\n\n{policy_prompt}"


def _first_visible_locator(page: Any, selectors: Sequence[str]) -> Any:
    from playwright.sync_api import TimeoutError as PwTimeout

    for sel in selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=4_000)
            return loc
        except PwTimeout:
            continue
    raise RuntimeError(
        "Could not find a visible Gemini input. Inspect the page and update "
        f"INPUT_SELECTORS in {__file__}"
    )


def _click_send_if_present(page: Any) -> None:
    from playwright.sync_api import TimeoutError as PwTimeout

    for sel in SEND_BUTTON_SELECTORS:
        btn = page.locator(sel).first
        try:
            if btn.is_visible(timeout=1_500):
                btn.click()
                return
        except PwTimeout:
            continue
    page.keyboard.press("Enter")


USER_PROMPT_MARKERS = (
    "MEDIA CONTEXT (required for this analysis)",
    "Analyze **one** governance meeting recording",
)


def _looks_like_user_prompt(text: str) -> bool:
    head = text[:2000]
    return any(marker in head for marker in USER_PROMPT_MARKERS)


def _model_response_count(page: Any) -> int:
    try:
        n = page.locator('[data-message-author-role="model"]').count()
        n += page.locator('[data-message-author-role="assistant"]').count()
        n += page.locator("model-response").count()
        return n
    except Exception:
        return 0


def _response_looks_complete(text: str) -> bool:
    if not text or len(text) < 400:
        return False
    hits = sum(1 for m in RESPONSE_COMPLETE_MARKERS if m in text)
    return hits >= 2


def _chat_root(page: Any) -> Any:
    for sel in CHAT_ROOT_SELECTORS:
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible(timeout=500):
                return loc
        except Exception:
            continue
    return page.locator("body")


def _is_generating(page: Any) -> bool:
    root = _chat_root(page)
    for sel in GENERATING_SELECTORS:
        try:
            loc = root.locator(sel).first
            if loc.is_visible(timeout=300):
                return True
        except Exception:
            continue
    return False


def _extract_conversation_fallback_js(page: Any) -> Optional[str]:
    """Read visible chat text when custom elements are not exposed to Playwright."""
    try:
        text = page.evaluate(
            """() => {
              const promptMark = 'MEDIA CONTEXT (required for this analysis)';
              const sectionMarks = [
                'Financial Summary',
                'Decision Themes Index',
                'People and Organizations',
              ];
              const textOf = (el) => (el.innerText || el.textContent || '').trim();
              const roots = [
                ...document.querySelectorAll('main, [role="main"], [class*="conversation"]'),
              ];
              let best = '';
              for (const el of roots) {
                const t = textOf(el);
                if (t.length <= best.length) continue;
                if (!sectionMarks.some((m) => t.includes(m))) continue;
                if (t.includes(promptMark)) {
                  let slice = t;
                  for (const m of sectionMarks) {
                    const i = t.indexOf(m);
                    if (i > 0) slice = t.slice(i);
                  }
                  if (slice.length > best.length) best = slice;
                } else {
                  best = t;
                }
              }
              return best.length > 200 ? best : null;
            }"""
        )
        return (text or "").strip() or None
    except Exception:
        return None


def _extract_model_response_js(page: Any, *, min_chars: int = 80) -> Optional[str]:
    """DOM walk for the latest model/assistant message (Gemini custom elements)."""
    try:
        text = page.evaluate(
            """(minChars) => {
              const minLen = minChars;
              const textOf = (el) => (el.innerText || el.textContent || '').trim();
              const roleOf = (el) => {
                if (!el) return '';
                const r = el.getAttribute('data-message-author-role')
                  || el.closest('[data-message-author-role]')?.getAttribute('data-message-author-role');
                return (r || '').toLowerCase();
              };
              const isUser = (el) => {
                const r = roleOf(el);
                if (r === 'user') return true;
                if (el.closest('[data-message-author-role="user"]')) return true;
                const cls = (el.className || '').toString().toLowerCase();
                return cls.includes('user-query') || cls.includes('user-message');
              };
              const isModel = (el) => {
                if (isUser(el)) return false;
                const r = roleOf(el);
                if (r === 'model' || r === 'assistant') return true;
                if (el.matches('model-response') || el.closest('model-response')) return true;
                const cls = (el.className || '').toString().toLowerCase();
                return cls.includes('model-response') || cls.includes('assistant');
              };
              const seen = [];
              const push = (el) => {
                if (!el || isUser(el)) return;
                const t = textOf(el);
                if (t.length >= minLen) seen.push(t);
              };
              for (const sel of [
                '[data-message-author-role="model"]',
                '[data-message-author-role="assistant"]',
                'model-response',
                'model-response message-content',
                'message-content.model-response-text',
                'div.model-response-text',
              ]) {
                document.querySelectorAll(sel).forEach(push);
              }
              if (seen.length) return seen[seen.length - 1];
              const nodes = [...document.querySelectorAll('message-content')];
              for (let i = nodes.length - 1; i >= 0; i--) {
                if (isModel(nodes[i])) {
                  const t = textOf(nodes[i]);
                  if (t.length >= minLen) return t;
                }
              }
              return null;
            }""",
            min_chars,
        )
        return (text or "").strip() or None
    except Exception:
        return None


def _locate_latest_model_response(page: Any) -> Optional[Any]:
    from playwright.sync_api import TimeoutError as PwTimeout

    for sel in RESPONSE_SELECTORS:
        if sel in ('message-content', '[class*="message-content"]'):
            continue
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:
            continue
        if n == 0:
            continue
        candidate = loc.last
        try:
            candidate.wait_for(state="visible", timeout=2_000)
            text = candidate.inner_text(timeout=3_000).strip()
            if len(text) >= 80 and not _looks_like_user_prompt(text):
                return candidate
        except PwTimeout:
            continue
        except Exception:
            continue
    return None


def _accept_candidate(text: str, *, baseline_model_count: int, page: Any) -> bool:
    if not text or len(text) < 80:
        return False
    if _looks_like_user_prompt(text):
        return False
    if _response_looks_complete(text):
        return True
    if _model_response_count(page) > baseline_model_count:
        return True
    if baseline_model_count == 0 and len(text) >= 500:
        return True
    return len(text) >= 200


def _wait_for_model_response(
    page: Any,
    *,
    baseline_model_count: int = 0,
    timeout_seconds: float = 600.0,
    poll_interval: float = 2.0,
    min_chars: int = 80,
) -> str:
    """Poll until Gemini finishes streaming a model reply (prompt can take several minutes)."""
    deadline = time.time() + timeout_seconds
    logger.info(
        "Waiting for model response (up to {:.0f} min, baseline model messages={}) …",
        timeout_seconds / 60,
        baseline_model_count,
    )
    last_logged = 0.0
    while time.time() < deadline:
        candidates: list[str] = []
        js_text = _extract_model_response_js(page, min_chars=min_chars)
        if js_text:
            candidates.append(js_text)
        fb_text = _extract_conversation_fallback_js(page)
        if fb_text:
            candidates.append(fb_text)

        loc = _locate_latest_model_response(page)
        if loc is not None:
            try:
                candidates.append(loc.inner_text(timeout=5_000).strip())
            except Exception:
                pass

        generating = _is_generating(page)
        for text in candidates:
            if not _accept_candidate(text, baseline_model_count=baseline_model_count, page=page):
                continue
            if _response_looks_complete(text):
                logger.info(
                    "Detected complete policy analysis ({} chars) — accepting response",
                    len(text),
                )
                return text
            if not generating:
                return text

        now = time.time()
        if now - last_logged >= 30:
            best_len = max((len(c) for c in candidates), default=0)
            logger.info(
                "Still waiting for Gemini response … (generating={}, best_candidate_chars={})",
                generating,
                best_len,
            )
            last_logged = now
        time.sleep(poll_interval)

    raise RuntimeError(
        "Timed out waiting for Gemini model response. "
        "Check the browser window (login, rate limit, or blocked YouTube). "
        f"Debug screenshots: data/cache/gemini_browser_policy/_debug/"
    )


def _scrape_latest_response(
    page: Any,
    *,
    baseline_model_count: int = 0,
    stable_polls: int = 3,
    poll_interval: float = 1.5,
    response_timeout_seconds: float = 600.0,
    min_chars: int = 80,
) -> str:
    text = _wait_for_model_response(
        page,
        baseline_model_count=baseline_model_count,
        timeout_seconds=response_timeout_seconds,
        poll_interval=2.0,
        min_chars=min_chars,
    )

    if _response_looks_complete(text):
        logger.info("Skipping stability poll — response already has policy analysis sections")
        return text

    previous = text
    stable = 0
    deadline = time.time() + min(response_timeout_seconds, 120.0)

    while stable < stable_polls and time.time() < deadline:
        current = _extract_model_response_js(page, min_chars=min_chars) or previous
        loc = _locate_latest_model_response(page)
        if loc is not None:
            try:
                current = loc.inner_text(timeout=5_000).strip() or current
            except Exception:
                pass
        if _response_looks_complete(current):
            return current
        if _is_generating(page) and not _response_looks_complete(current):
            stable = 0
            previous = current
            time.sleep(poll_interval)
            continue
        if (
            current == previous
            and len(current) >= min_chars
            and not _looks_like_user_prompt(current)
        ):
            stable += 1
        else:
            stable = 0
            previous = current
        time.sleep(poll_interval)

    if _looks_like_user_prompt(previous):
        raise RuntimeError(
            "Scrape ended on the user prompt, not a model reply — Gemini may not have responded."
        )
    return previous


def _fresh_profile_dir() -> Path:
    return _REPO_ROOT / "data" / "cache" / "gemini_browser_chrome_profile"


def _open_page(
    p: Any,
    *,
    user_data_dir: Path,
    profile_name: str,
    headless: bool,
    cdp_url: Optional[str],
    fresh_profile: bool,
) -> tuple[Any, Any, str, bool]:
    """
    Returns (page, context_or_browser, mode, should_close_context).
    mode is 'cdp' | 'persistent'.
    """
    if cdp_url:
        logger.info("Connecting via CDP to {} (use your normal Chrome — start it with --remote-debugging-port=9222)", cdp_url)
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        return page, browser, "cdp", False

    if fresh_profile:
        profile_path = _fresh_profile_dir()
        profile_path.mkdir(parents=True, exist_ok=True)
        logger.info("Using isolated Playwright Chromium profile: {}", profile_path)
        logger.info("First run: sign into Google in the window that opens.")
        chrome_data_dir = profile_path
        chrome_args: List[str] = []
        channel = "chromium"
    else:
        chrome_data_dir, chrome_args = resolve_chrome_launch(user_data_dir, profile_name)
        if not chrome_data_dir.is_dir():
            raise FileNotFoundError(
                f"Chrome user data dir not found: {chrome_data_dir}\n"
                "Use --fresh-profile or --cdp-url instead."
            )
        logger.info("Launching system Chrome (profile={}) …", profile_name)
        logger.info("User data dir: {}", chrome_data_dir)
        logger.warning("Quit all Chrome windows using this profile before continuing.")
        channel = "chrome"

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(chrome_data_dir),
        channel=channel,
        headless=headless,
        viewport={"width": 1280, "height": 800},
        ignore_default_args=["--enable-automation"],
        args=[
            "--disable-blink-features=AutomationControlled",
            *chrome_args,
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )
    page = context.pages[0] if context.pages else context.new_page()
    return page, context, "persistent", True


def _select_gemini_model_in_ui(page: Any, model_name: str) -> bool:
    """Try to pick a model from the Gemini composer dropdown (UI changes often)."""
    from playwright.sync_api import TimeoutError as PwTimeout

    target = model_name.strip()
    if not target:
        return False

    logger.info("Selecting Gemini model in UI: {}", target)
    opened = False
    for sel in (
        'button[aria-label*="model" i]',
        '[class*="model-switcher" i] button',
        '[class*="model-selector" i]',
        'button:has-text("Flash")',
        'button:has-text("Pro")',
        'button:has-text("3.1")',
    ):
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1_500):
                btn.click()
                opened = True
                time.sleep(0.8)
                break
        except Exception:
            continue

    if not opened:
        try:
            page.locator('[contenteditable="true"]').first.click(timeout=2_000)
            time.sleep(0.3)
        except Exception:
            pass

    candidates = [target, f"Gemini {target}"]
    if "3.1" in target and "Pro" in target:
        candidates.extend(["3.1 Pro", "Gemini 3.1 Pro", "3 Pro"])

    for label in candidates:
        for strategy in (
            lambda t: page.get_by_role("menuitem", name=re.compile(re.escape(t), re.I)).first,
            lambda t: page.get_by_role("option", name=re.compile(re.escape(t), re.I)).first,
            lambda t: page.get_by_text(t, exact=False).first,
        ):
            try:
                strategy(label).click(timeout=3_000)
                time.sleep(0.5)
                detected = _detect_gemini_model(page)
                if detected and (target.lower() in detected.lower() or "3.1" in detected):
                    logger.success("Model selected: {}", detected)
                    return True
                logger.info("Clicked {}; detected model: {}", label, detected)
                return True
            except PwTimeout:
                continue
            except Exception:
                continue

    logger.warning(
        "Could not click model '{}' in UI — select it manually in the browser, "
        "then continue (use --pause-after-open).",
        target,
    )
    return False


def _detect_gemini_model(page: Any, *, cli_override: Optional[str] = None) -> Optional[str]:
    if cli_override and cli_override.strip():
        return cli_override.strip()
    for sel in (
        'button[aria-label*="model" i]',
        '[class*="model-switcher" i] button',
        '[class*="model-selector" i]',
    ):
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=500):
                text = (loc.inner_text(timeout=1_000) or loc.get_attribute("aria-label") or "").strip()
                if text and len(text) < 60:
                    return text
        except Exception:
            continue
    try:
        found = page.evaluate(
            """() => {
              const known = [
                'Gemini 3.1 Pro', '3.1 Pro', 'Gemini 3 Pro', '3 Pro',
                'Gemini 2.5 Flash', '2.5 Flash', '1.5 Flash', 'Flash',
                'Gemini 2.5 Pro', '2.5 Pro', 'Pro', 'Advanced',
                'Thinking', 'Gemini 2.0 Flash',
              ];
              const roots = [
                ...document.querySelectorAll(
                  '[class*="composer"], [class*="input-area"], main, [role="main"]'
                ),
              ];
              const texts = roots.map((el) => (el.innerText || '').trim()).filter(Boolean);
              const blob = texts.join('\\n') || document.body.innerText || '';
              for (const k of known) {
                if (blob.includes(k)) return k;
              }
              for (const btn of document.querySelectorAll('button,[role="button"]')) {
                const label = (
                  btn.getAttribute('aria-label') || btn.innerText || ''
                ).trim();
                if (/^(Flash|Pro|Advanced|Thinking)\\b/i.test(label) && label.length < 40) {
                  return label;
                }
              }
              return null;
            }"""
        )
        return (found or "").strip() or None
    except Exception:
        return None


def _playwright_context(handle: Any, mode: str) -> Any:
    if mode == "cdp":
        return handle.contexts[0] if handle.contexts else handle.new_context(
            viewport={"width": 1280, "height": 800}
        )
    return handle


def _send_prompt_on_page(
    page: Any,
    prompt_text: str,
    *,
    debug_dir: Optional[Path] = None,
    gemini_model_override: Optional[str] = None,
) -> GeminiRunCapture:
    logger.info("Waiting for chat input at {} …", page.url)
    try:
        input_field = _first_visible_locator(page, INPUT_SELECTORS)
    except RuntimeError:
        if debug_dir:
            _debug_screenshot(page, debug_dir, "no_input_found")
        raise
    input_field.click()
    baseline_model_count = _model_response_count(page)
    logger.info("Sending prompt ({} chars) …", len(prompt_text))
    try:
        input_field.fill(prompt_text, timeout=120_000)
    except Exception:
        logger.warning("fill() failed — trying keyboard.type in chunks")
        input_field.click()
        chunk_size = 4000
        for i in range(0, len(prompt_text), chunk_size):
            input_field.type(prompt_text[i : i + chunk_size], delay=0)
    time.sleep(0.5)
    _click_send_if_present(page)
    time.sleep(1.0)
    _click_send_if_present(page)
    logger.info("Waiting for streamed response …")
    try:
        page.locator("text=MEDIA CONTEXT").first.wait_for(state="visible", timeout=120_000)
    except Exception:
        logger.warning("User message bubble not confirmed — continuing anyway")
    gemini_model = _detect_gemini_model(page, cli_override=gemini_model_override)
    if gemini_model:
        logger.info("Gemini model: {}", gemini_model)
    else:
        logger.warning("Could not detect Gemini model from UI — set --gemini-model to record it")
    response_text = _scrape_latest_response(page, baseline_model_count=baseline_model_count)
    return GeminiRunCapture(response_text=response_text, gemini_model=gemini_model)


def _reset_gemini_chat_same_tab(
    page: Any,
    gemini_url: str,
    *,
    navigation_timeout_ms: int,
) -> None:
    """Reload Gemini in the same tab so the next video gets a fresh conversation."""
    logger.info("Reloading Gemini in same tab for new conversation …")
    _navigate_to_gemini(page, gemini_url, timeout_ms=navigation_timeout_ms, allow_manual=False)


DOCUMENT_BREAK_TOKEN = "---DOCUMENT_BREAK---"
GEMINI_UI_CHROME_RE = re.compile(
    r"^(Flash|Pro|Advanced|Thinking|Gemini is AI|Google).*$",
    re.IGNORECASE,
)


def _document1_json_score(obj: Any) -> int:
    """Prefer full meeting payloads over nested fragments (e.g. lone frame_analysis)."""
    if not isinstance(obj, dict) or _is_placeholder_policy_json(obj):
        return -1
    decisions = obj.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        return -1
    if isinstance(decisions[0], dict) and str(decisions[0].get("decision_id", "")).startswith(
        "string"
    ):
        return -1
    score = len(json.dumps(obj, ensure_ascii=False))
    if "meeting" in obj:
        score += 500_000
    score += 2_000_000 + len(decisions) * 10_000
    if "people" in obj or "organizations" in obj:
        score += 50_000
    return score


def _is_placeholder_policy_json(obj: Any) -> bool:
    """Reject prompt schema examples mistaken for Document 1."""
    if not isinstance(obj, dict):
        return False
    if "meeting" not in obj and "decisions" not in obj:
        # Lone narrative_analysis / frame_analysis fragment — not Document 1 root
        if "dominant_frame" in obj or "dominant_narrative" in obj:
            return True
        if "frame_analysis" in obj and "decision_id" not in obj:
            return True
    if "meeting" not in obj:
        return False
    meeting = obj.get("meeting")
    if not isinstance(meeting, dict):
        return False
    meeting_id = meeting.get("meeting_id")
    if isinstance(meeting_id, str) and (
        "string" in meeting_id.lower() or "derive" in meeting_id.lower()
    ):
        return True
    for val in meeting.values():
        if isinstance(val, str) and val.startswith("string —"):
            return True
    return False


def _json_decode_at(text: str, start: int) -> Optional[tuple[Any, int]]:
    try:
        obj, end = json.JSONDecoder().raw_decode(text, start)
        return obj, end
    except json.JSONDecodeError:
        return None


def _extract_document1_json(text: str) -> Optional[Any]:
    """Pick the best full meeting JSON object in the scraped response."""
    # Prefer JSON after the model reply (skip echoed prompt schema).
    gs = text.rfind("Gemini said")
    if gs >= 0:
        start = text.find("{", gs)
        if start >= 0:
            decoded = _json_decode_at(text, start)
            if decoded:
                obj, _ = decoded
                if _document1_json_score(obj) > 0:
                    return obj

    decoder = json.JSONDecoder()
    best: Optional[Any] = None
    best_score = -1
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                score = _document1_json_score(obj)
                if score > best_score:
                    best_score = score
                    best = obj
            i = max(end, i + 1)
        except json.JSONDecodeError:
            i += 1
    return best


READABLE_START_MARKERS = (
    "**Bottom line:**",
    "Bottom line:",
    "**Why it matters:**",
    "Why it matters:",
    "One moment worth remembering",
    "Who was for it and why",
    "Who was against it and why",
    "The tension underneath",
    # Legacy markers (older prompt runs)
    "The short version",
    "What they're saying:",
    "**What they're saying:**",
    "Yes, but:",
    "**Yes, but:**",
    "Between the lines:",
    "**Between the lines:**",
    "Worth remembering:",
    "**Worth remembering:**",
    "Tuscaloosa City Council Meeting Analysis",
    "## Meeting Overview",
    "**Meeting Overview**",
    "Meeting Overview",
)


def _extract_readable_markdown(raw: str) -> str:
    """Human-readable Document 2 only — skip echoed prompt rules and embedded JSON."""
    search_from = 0
    break_pos = raw.rfind(DOCUMENT_BREAK_TOKEN)
    if break_pos >= 0:
        search_from = break_pos + len(DOCUMENT_BREAK_TOKEN)
    else:
        gs = raw.rfind("Gemini said")
        if gs >= 0:
            search_from = gs + len("Gemini said")
    best_idx = -1
    for marker in READABLE_START_MARKERS:
        idx = raw.rfind(marker, search_from)
        if idx > best_idx:
            best_idx = idx
    if best_idx < 0:
        return ""
    text = _strip_gemini_ui_chrome(raw[best_idx:])
    # Drop trailing JSON-looking tail if model appended schema after the narrative
    lines = text.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('{"') or stripped.startswith('"meeting_id":'):
            break
        if stripped == "{" and len(clean) > 20:
            break
        clean.append(line)
    return "\n".join(clean).strip()


def _unescape_mermaid_field(value: str) -> str:
    if not value:
        return ""
    return value.replace("\\n", "\n").replace('\\"', '"').strip()


def _write_diagrams_from_raw(raw: str, path: Path) -> bool:
    """Fallback when Document 1 JSON is invalid but diagram fields appear in the scrape."""
    chunks = [
        "# Mermaid diagrams\n",
        "Open in Cursor with **Markdown Preview**.\n",
    ]
    wrote = False
    for did, timeline, mindmap in re.findall(
        r'"decision_id":\s*"(D\d+)"[\s\S]{0,12000}?'
        r'"diagram_timeline":\s*"((?:\\.|[^"\\])*)"[\s\S]{0,4000}?'
        r'"diagram_mindmap":\s*"((?:\\.|[^"\\])*)"',
        raw,
    ):
        t = _unescape_mermaid_field(timeline)
        m = _unescape_mermaid_field(mindmap)
        if "timeline" not in t and "mindmap" not in m:
            continue
        chunks.append(f"\n## {did}\n")
        if t and "timeline" in t:
            chunks.append(f"\n### Timeline\n\n```mermaid\n{t}\n```\n")
            wrote = True
        if m and "mindmap" in m:
            chunks.append(f"\n### Mindmap\n\n```mermaid\n{m}\n```\n")
            wrote = True
    if wrote:
        path.write_text("".join(chunks) + "\n", encoding="utf-8")
    return wrote


def _write_diagrams_md(parsed: dict[str, Any], path: Path) -> bool:
    """Extract per-decision Mermaid from JSON into a preview-friendly markdown file."""
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        return False
    chunks = [
        "# Mermaid diagrams\n",
        "Open this file in Cursor and use **Markdown Preview** (or preview side-by-side).\n",
    ]
    wrote = False
    for d in decisions:
        if not isinstance(d, dict):
            continue
        did = d.get("decision_id") or "?"
        title = d.get("headline") or d.get("topic") or did
        timeline = _unescape_mermaid_field(str(d.get("diagram_timeline") or ""))
        mindmap = _unescape_mermaid_field(str(d.get("diagram_mindmap") or ""))
        if not timeline and not mindmap:
            continue
        chunks.append(f"\n## {did} — {title}\n")
        if timeline:
            chunks.append(f"\n### Timeline\n\n```mermaid\n{timeline}\n```\n")
            wrote = True
        if mindmap:
            chunks.append(f"\n### Mindmap\n\n```mermaid\n{mindmap}\n```\n")
            wrote = True
    if wrote:
        path.write_text("".join(chunks) + "\n", encoding="utf-8")
    return wrote


def _strip_gemini_ui_chrome(text: str) -> str:
    lines = text.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if GEMINI_UI_CHROME_RE.match(last):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


def _strip_markdown_preamble(text: str) -> str:
    text = text.strip()
    text = re.sub(rf"^{re.escape(DOCUMENT_BREAK_TOKEN)}\s*", "", text)
    text = re.sub(r"^Gemini said\s*", "", text, flags=re.IGNORECASE)
    if "Meeting Overview" in text:
        idx = text.find("Meeting Overview")
        if 0 < idx < 800:
            text = text[idx:]
    return text.strip()


def _is_ui_chrome_only(text: str) -> bool:
    t = text.strip()
    if len(t) > 400 or "Meeting Overview" in t or "## " in t:
        return False
    return len(t) < 80 or bool(GEMINI_UI_CHROME_RE.match(t))


def _markdown_after_json(raw: str, json_end: int) -> str:
    md = _strip_markdown_preamble(raw[json_end:])
    if md.lstrip().startswith("{"):
        return ""
    parts = [p.strip() for p in md.split(DOCUMENT_BREAK_TOKEN) if p.strip()]
    parts = [_strip_gemini_ui_chrome(p) for p in parts if not _is_ui_chrome_only(p)]
    return "\n\n".join(parts)


def _split_gemini_documents(text: str) -> tuple[Optional[Any], list[str]]:
    """
    Split Gemini output into Document 1 (JSON) and Document 2+ (markdown).

    Naive splits on ---DOCUMENT_BREAK--- fail because that token appears in the
    echoed prompt before the model reply; Document 2 may also be truncated in scrape.
    """
    raw = text.strip()
    parsed = _extract_document1_json(raw)
    markdown_docs: list[str] = []

    if parsed is not None:
        meeting_id = str(parsed.get("meeting", {}).get("meeting_id", ""))
        start = raw.find("{")
        if meeting_id:
            pos = raw.find(meeting_id)
            if pos > 0:
                start = raw.rfind("{", 0, pos)
        try:
            _, json_end = json.JSONDecoder().raw_decode(raw, start)
            md = _markdown_after_json(raw, json_end)
            if md:
                markdown_docs.append(md)
        except json.JSONDecodeError:
            logger.warning("Found meeting JSON but could not locate its end offset in raw text")

    if parsed is None:
        parsed = _try_parse_json_from_response(raw)
        if parsed is not None and _is_placeholder_policy_json(parsed):
            parsed = None

    readable = _extract_readable_markdown(raw)
    if readable and len(readable) >= 500:
        markdown_docs = [readable]
    elif not markdown_docs and DOCUMENT_BREAK_TOKEN in raw:
        parts = [p.strip() for p in raw.split(DOCUMENT_BREAK_TOKEN) if p.strip()]
        for part in parts:
            if part.lstrip().startswith("{") or "meeting" not in part:
                continue
            cleaned = _strip_gemini_ui_chrome(_strip_markdown_preamble(part))
            if cleaned and not _is_ui_chrome_only(cleaned):
                markdown_docs.append(cleaned)

    if markdown_docs and len(markdown_docs[0]) < 500:
        logger.warning(
            "Document 2 markdown is only {} chars — Gemini may have been cut off "
            "before finishing the narrative (check browser or re-run).",
            len(markdown_docs[0]),
        )

    return parsed, markdown_docs


def _load_manifest_records(folder: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    json_path = folder / "_manifest.json"
    jsonl_path = folder / "_manifest.jsonl"
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            logger.warning("Could not parse {}; rebuilding manifest", json_path)
    if jsonl_path.is_file():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _render_manifest_md(records: list[dict[str, Any]]) -> str:
    lines = [
        "# Gemini browser policy runs\n",
        "| generated_at | video_id | prompt | model | analysis | document 2 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(records, key=lambda x: x.get("generated_at", ""), reverse=True):
        files = r.get("files") or {}
        lines.append(
            "| {generated_at} | `{video_id}` | {prompt_name} | {gemini_model} | "
            "[json]({analysis}) | [md]({doc2}) |".format(
                generated_at=r.get("generated_at", ""),
                video_id=r.get("video_id", ""),
                prompt_name=r.get("prompt_name", r.get("prompt_file", "")),
                gemini_model=r.get("gemini_model") or "unknown",
                analysis=files.get("analysis_json", "—"),
                doc2=files.get("report_md", "—"),
            )
        )
    return "\n".join(lines) + "\n"


def _write_manifest(folder: Path, record: dict[str, Any]) -> None:
    records = _load_manifest_records(folder)
    records.append(record)
    json_path = folder / "_manifest.json"
    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "_manifest.md").write_text(_render_manifest_md(records), encoding="utf-8")


def _try_parse_json_from_response(text: str) -> Optional[Any]:
    """Best-effort extract of JSON from Gemini markdown (fenced blocks or bare object)."""
    if not text.strip():
        return None
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def run_video_batch(
    videos: List[VideoRow],
    policy_prompt: str,
    *,
    user_data_dir: Path,
    profile_name: str,
    gemini_url: str = DEFAULT_GEMINI_URL,
    headless: bool = False,
    navigation_timeout_ms: int = 120_000,
    hold_open_seconds: float = 2.0,
    delay_between_videos: float = 5.0,
    output_dir: Path,
    prompt_path: Path,
    debug_dir: Optional[Path] = None,
    pause_after_open: bool = False,
    cdp_url: Optional[str] = None,
    fresh_profile: bool = False,
    new_tab_per_video: bool = False,
    gemini_model_override: Optional[str] = None,
    select_model: Optional[str] = None,
    save_raw_response: bool = False,
) -> int:
    """One browser session; loop URLs → prompt → save response for each video."""
    from playwright.sync_api import sync_playwright

    saved = 0
    with sync_playwright() as p:
        page, handle, mode, should_close = _open_page(
            p,
            user_data_dir=user_data_dir,
            profile_name=profile_name,
            headless=headless,
            cdp_url=cdp_url,
            fresh_profile=fresh_profile,
        )
        ctx = _playwright_context(handle, mode)
        try:
            _navigate_to_gemini(
                page,
                gemini_url,
                timeout_ms=navigation_timeout_ms,
                allow_manual=pause_after_open,
            )
            if select_model:
                _select_gemini_model_in_ui(page, select_model)
            if pause_after_open:
                logger.info("Gemini ready at {} — press Enter to start batch …", page.url)
                input()

            for i, video in enumerate(videos, 1):
                logger.info("=" * 72)
                logger.info("[{}/{}] {}", i, len(videos), video.video_url)
                if i > 1:
                    if new_tab_per_video:
                        logger.info("Opening new browser tab for next video …")
                        page = ctx.new_page()
                        _navigate_to_gemini(
                            page, gemini_url, timeout_ms=navigation_timeout_ms, allow_manual=False
                        )
                    else:
                        _reset_gemini_chat_same_tab(
                            page, gemini_url, navigation_timeout_ms=navigation_timeout_ms
                        )
                        if select_model:
                            _select_gemini_model_in_ui(page, select_model)
                    if delay_between_videos > 0:
                        time.sleep(delay_between_videos)

                user_message = build_user_message(
                    policy_prompt, video, media_source_id=f"MS{i:03d}"
                )
                try:
                    capture = _send_prompt_on_page(
                        page,
                        user_message,
                        debug_dir=debug_dir,
                        gemini_model_override=gemini_model_override,
                    )
                    time.sleep(hold_open_seconds)
                except Exception as exc:
                    logger.error("Failed for {}: {}", video.video_id, exc)
                    if debug_dir:
                        _debug_screenshot(page, debug_dir, f"error_{video.video_id}")
                    continue

                out_path = save_run_output(
                    output_dir,
                    video,
                    capture,
                    prompt_path=prompt_path,
                    save_raw_response=save_raw_response,
                )
                logger.success(
                    "Saved {} ({} chars, model={})",
                    out_path,
                    len(capture.response_text),
                    capture.gemini_model or "unknown",
                )
                saved += 1
        finally:
            if should_close and mode == "persistent":
                handle.close()
            elif mode == "cdp":
                logger.info("CDP: left your Chrome running")

    logger.success("Batch done — {}/{} saved", saved, len(videos))
    return saved


def ask_gemini_in_browser(
    prompt_text: str,
    *,
    user_data_dir: Path,
    profile_name: str,
    gemini_url: str = DEFAULT_GEMINI_URL,
    headless: bool = False,
    navigation_timeout_ms: int = 120_000,
    hold_open_seconds: float = 2.0,
    new_chat_per_prompt: bool = False,
    debug_dir: Optional[Path] = None,
    pause_after_open: bool = False,
    open_only: bool = False,
    cdp_url: Optional[str] = None,
    fresh_profile: bool = False,
) -> str:
    from playwright.sync_api import sync_playwright

    if headless:
        logger.warning(
            "headless=True is discouraged — Google often blocks headless Gemini automation"
        )

    with sync_playwright() as p:
        page, handle, mode, should_close = _open_page(
            p,
            user_data_dir=user_data_dir,
            profile_name=profile_name,
            headless=headless,
            cdp_url=cdp_url,
            fresh_profile=fresh_profile,
        )
        try:
            if new_chat_per_prompt and mode == "persistent":
                page = handle.new_page()

            _navigate_to_gemini(
                page,
                gemini_url,
                timeout_ms=navigation_timeout_ms,
                allow_manual=pause_after_open or open_only,
            )

            if debug_dir:
                _debug_screenshot(page, debug_dir, "after_navigate")

            if pause_after_open and not open_only:
                logger.info("Paused at {} — press Enter to send prompt …", page.url)
                input()

            if open_only:
                logger.info("open-only: browser at {}", page.url)
                if pause_after_open:
                    input("Press Enter to close …")
                return ""

            capture = _send_prompt_on_page(page, prompt_text, debug_dir=debug_dir)
            time.sleep(hold_open_seconds)
            return capture.response_text
        finally:
            if should_close and mode == "persistent":
                handle.close()
            elif mode == "cdp":
                logger.info("CDP: left your Chrome running (disconnect only)")


def _safe_stem(video: VideoRow) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", (video.title or video.video_id)[:80]).strip("_")
    return base or video.video_id


def save_run_output(
    output_dir: Path,
    video: VideoRow,
    capture: GeminiRunCapture,
    *,
    prompt_path: Path,
    save_raw_response: bool = False,
) -> Path:
    response_text = capture.response_text
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = output_dir / video.jurisdiction_id
    folder.mkdir(parents=True, exist_ok=True)
    prompt_name = prompt_path.stem
    prompt_tag = _sanitize_tag(prompt_name)
    model_tag = _sanitize_tag(capture.gemini_model or "unknown_model")
    stem = f"{video.video_id}_{_safe_stem(video)}_{prompt_tag}_{model_tag}_{ts}"

    parsed, markdown_docs = _split_gemini_documents(response_text)
    rel = lambda p: str(p.relative_to(_REPO_ROOT))

    meta_path = folder / f"{stem}_meta.json"
    analysis_path = folder / f"{stem}_analysis.json"
    report_md_path = folder / f"{stem}_report.md"
    diagrams_md_path = folder / f"{stem}_diagrams.md"

    if parsed is None or not isinstance(parsed, dict) or "decisions" not in parsed:
        logger.warning(
            "Could not parse full Document 1 JSON for {} — analysis.json will contain an error stub",
            video.video_id,
        )
        analysis_payload: Any = {
            "_error": "Could not parse full meeting JSON (expected meeting + decisions[])",
            "document1_excerpt": response_text[:2000],
            "parsed_fragment": parsed,
        }
        json_parsed = False
    else:
        analysis_payload = parsed
        json_parsed = True

    analysis_path.write_text(
        json.dumps(analysis_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report_body = markdown_docs[0] if markdown_docs else ""
    if report_body:
        report_md_path.write_text(report_body + "\n", encoding="utf-8")
    else:
        report_md_path.write_text(
            "# Report unavailable\n\nCould not extract human-readable markdown from the response.\n",
            encoding="utf-8",
        )

    has_diagrams = False
    if json_parsed and isinstance(analysis_payload, dict):
        has_diagrams = _write_diagrams_md(analysis_payload, diagrams_md_path)
    elif not has_diagrams:
        has_diagrams = _write_diagrams_from_raw(response_text, diagrams_md_path)

    files: dict[str, str] = {
        "meta_json": rel(meta_path),
        "analysis_json": rel(analysis_path),
        "report_md": rel(report_md_path),
    }
    if has_diagrams:
        files["diagrams_md"] = rel(diagrams_md_path)
    if save_raw_response:
        raw_path = folder / f"{stem}_response_raw.md"
        raw_path.write_text(response_text + "\n", encoding="utf-8")
        files["response_raw_md"] = rel(raw_path)

    meta_payload: dict[str, Any] = {
        "video_id": video.video_id,
        "video_url": video.video_url,
        "title": video.title,
        "jurisdiction_id": video.jurisdiction_id,
        "last_updated": (
            video.last_updated.isoformat() if video.last_updated is not None else None
        ),
        "prompt_name": prompt_name,
        "prompt_file": str(prompt_path.relative_to(_REPO_ROOT)),
        "gemini_model": capture.gemini_model,
        "generation_source": "gemini_web_ui",
        "generated_at": ts,
        "response_chars": len(response_text),
        "json_parsed": json_parsed,
        "has_diagrams_md": has_diagrams,
        "report_chars": len(report_body),
        "files": files,
    }
    meta_path.write_text(
        json.dumps(meta_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_record = {
        "video_id": video.video_id,
        "video_url": video.video_url,
        "title": video.title,
        "prompt_name": prompt_name,
        "prompt_file": str(prompt_path.relative_to(_REPO_ROOT)),
        "gemini_model": capture.gemini_model,
        "generation_source": "gemini_web_ui",
        "generated_at": ts,
        "response_chars": len(response_text),
        "json_parsed": json_parsed,
        "has_diagrams_md": has_diagrams,
        "files": files,
    }
    _write_manifest(folder, manifest_record)

    logger.info(
        "Wrote: {} (JSON), {} (readable markdown){}",
        analysis_path.name,
        report_md_path.name,
        f", {diagrams_md_path.name}" if has_diagrams else "",
    )
    return analysis_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv(_REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Gemini web UI + policy_analysis_v1 for bronze YouTube videos"
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help=f"Policy prompt markdown (default: {DEFAULT_PROMPT_PATH})",
    )
    parser.add_argument(
        "--jurisdiction-id",
        default=DEFAULT_JURISDICTION_ID,
        help=f"bronze.bronze_events_youtube.jurisdiction_id (default: {DEFAULT_JURISDICTION_ID})",
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--video-id", default=None, help="Single YouTube video_id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--chrome-user-data-dir",
        type=Path,
        default=None,
        help="Override Chrome User Data (default: platform-specific or GEMINI_CHROME_USER_DATA_DIR)",
    )
    parser.add_argument(
        "--chrome-profile",
        default=None,
        help="Chrome profile folder name (Default, Profile 1, …)",
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--hold-open", type=float, default=2.0, help="Seconds before closing browser")
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="Only open Gemini in Chrome (no prompt); use with --pause-after-open to debug blank page",
    )
    parser.add_argument(
        "--pause-after-open",
        action="store_true",
        help="Wait for Enter in terminal after navigation (debug login / blank page)",
    )
    parser.add_argument(
        "--cdp-url",
        default=os.getenv("GEMINI_CDP_URL", "").strip() or None,
        help="Attach to Chrome already running with remote debugging (recommended on WSL)",
    )
    parser.add_argument(
        "--fresh-profile",
        action="store_true",
        help="Use data/cache/gemini_browser_chrome_profile (Playwright Chromium; sign in once)",
    )
    parser.add_argument(
        "--delay-between",
        type=float,
        default=5.0,
        help="Seconds to wait between videos in batch mode (default 5)",
    )
    parser.add_argument(
        "--new-tab-per-video",
        action="store_true",
        help="Open a new browser tab per video (default: same tab, reload Gemini)",
    )
    parser.add_argument(
        "--gemini-model",
        default=os.getenv("GEMINI_MODEL"),
        help="Label recorded in output filenames/metadata (default: auto-detect from UI)",
    )
    parser.add_argument(
        "--select-model",
        default=os.getenv("GEMINI_SELECT_MODEL"),
        metavar="NAME",
        help='Try to pick model in gemini.google.com UI before sending (e.g. "3.1 Pro")',
    )
    parser.add_argument(
        "--save-raw-response",
        action="store_true",
        help="Also save full browser scrape as {stem}_response_raw.md (debug only)",
    )
    args = parser.parse_args(argv)

    db_url = _database_url(args.database_url)
    videos = fetch_videos(
        db_url,
        args.jurisdiction_id,
        limit=args.limit,
        video_id=args.video_id,
    )
    if not videos:
        logger.error("No videos found for jurisdiction_id={}", args.jurisdiction_id)
        return 1

    logger.info("Found {} video(s) for {}", len(videos), args.jurisdiction_id)
    for v in videos:
        logger.info("  {} | {} | {}", v.video_id, v.last_updated, (v.title or "")[:70])

    user_data = args.chrome_user_data_dir or default_chrome_user_data_dir()
    profile = args.chrome_profile or default_chrome_profile()
    debug_dir = args.output_dir.resolve() / "_debug"

    if args.dry_run:
        policy = load_policy_prompt(args.prompt_file.resolve())
        logger.info("Policy prompt: {} chars from {}", len(policy), args.prompt_file)
        logger.info("[dry-run] Would open Gemini and send {} prompt(s)", len(videos))
        return 0

    if args.open_only:
        ask_gemini_in_browser(
            "",
            user_data_dir=user_data,
            profile_name=profile,
            headless=args.headless,
            hold_open_seconds=args.hold_open,
            debug_dir=debug_dir,
            pause_after_open=args.pause_after_open,
            open_only=True,
            cdp_url=args.cdp_url,
            fresh_profile=args.fresh_profile,
        )
        return 0

    policy_prompt = load_policy_prompt(args.prompt_file.resolve())

    run_video_batch(
        videos,
        policy_prompt,
        user_data_dir=user_data,
        profile_name=profile,
        headless=args.headless,
        hold_open_seconds=args.hold_open,
        delay_between_videos=args.delay_between,
        output_dir=args.output_dir.resolve(),
        prompt_path=args.prompt_file.resolve(),
        debug_dir=debug_dir,
        pause_after_open=args.pause_after_open,
        cdp_url=args.cdp_url,
        fresh_profile=args.fresh_profile,
        new_tab_per_video=args.new_tab_per_video,
        gemini_model_override=args.gemini_model,
        select_model=args.select_model,
        save_raw_response=args.save_raw_response,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
