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

    # Default: two-part prompts (JSON in part 1, Smart Brevity report in part 2, same chat)
    python scripts/gemini/browser_policy_analysis.py --fresh-profile --video-id ajsME66iXbY --select-model "3.1 Pro"

    # Legacy single combined prompt
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
DEFAULT_PROMPT_PART_1 = _REPO_ROOT / "prompts" / "policy_analysis_part_1.md"
DEFAULT_PROMPT_PART_2 = _REPO_ROOT / "prompts" / "policy_analysis_part_2.md"
PART2_USER_MARKER = "JSON from Step 1"
DEFAULT_JURISDICTION_ID = "tuscaloosa_0177256"
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
    '"decisions"',
    "Bottom line:",
    "---DOCUMENT_BREAK---",
    "**Who won:**",
    "Who won:",
    "#### Timeline",
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
    channel_id: Optional[str] = None
    duration_minutes: Optional[int] = None
    has_transcript: bool = False


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
    order_by: str = "last_updated",
    dedupe_duplicate_meetings: bool = True,
    only_has_transcript: bool = False,
) -> List[VideoRow]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT DISTINCT ON (y.video_url)
            y.video_id,
            y.video_url,
            y.title,
            y.last_updated,
            y.event_date::text AS event_date,
            y.audio_file_path,
            y.jurisdiction_id,
            y.channel_id,
            y.duration_minutes,
            y.published_at,
            COALESCE(t.has_transcript, false) AS has_transcript
        FROM bronze.bronze_events_youtube y
        LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = y.video_id
        WHERE y.jurisdiction_id = %s
          AND y.video_url IS NOT NULL
          AND BTRIM(y.video_url) <> ''
    """
    params: list[Any] = [jurisdiction_id]
    if video_id:
        sql += " AND y.video_id = %s"
        params.append(video_id)
    if only_has_transcript:
        sql += " AND t.has_transcript IS TRUE"
    sql += """
          AND (
            t.video_id IS NULL
            OR COALESCE(t.transcript_source, '') NOT LIKE 'excluded:%%'
          )
    """
    sql += " ORDER BY y.video_url, y.last_updated DESC NULLS LAST"
    if order_by == "published_at":
        sub_order = (
            "COALESCE(sub.published_at, sub.event_date::timestamp) DESC NULLS LAST, sub.video_id"
        )
    elif order_by == "meeting_date":
        sub_order = "event_date::date DESC NULLS LAST, last_updated DESC NULLS LAST"
    else:
        sub_order = "last_updated DESC NULLS LAST"
    sql = f"SELECT * FROM ({sql}) sub ORDER BY {sub_order}"
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    from scripts.gemini.transcript_cache_paths import resolve_meeting_event_date

    out: List[VideoRow] = []
    for r in rows:
        title = r.get("title") or None
        out.append(
            VideoRow(
                video_id=str(r["video_id"] or ""),
                video_url=str(r["video_url"] or "").strip(),
                title=title,
                last_updated=r.get("last_updated"),
                event_date=resolve_meeting_event_date(
                    str(title or ""),
                    event_date=r.get("event_date"),
                    published_at=r.get("published_at"),
                    audio_file_path=r.get("audio_file_path"),
                ),
                audio_file_path=r.get("audio_file_path"),
                jurisdiction_id=str(r.get("jurisdiction_id") or jurisdiction_id),
                channel_id=str(r.get("channel_id") or "").strip() or None,
                duration_minutes=r.get("duration_minutes"),
                has_transcript=bool(r.get("has_transcript")),
            )
        )

    if dedupe_duplicate_meetings and not video_id and len(out) > 1:
        from scripts.datasources.youtube.dedupe_meeting_videos import (
            dedupe_meeting_rows,
            log_duplicate_skips,
        )

        row_maps = [
            {
                "video_id": v.video_id,
                "title": v.title,
                "event_date": v.event_date,
                "duration_minutes": v.duration_minutes,
                "has_transcript": v.has_transcript,
            }
            for v in out
        ]
        kept_maps, dedupe = dedupe_meeting_rows(row_maps)
        log_duplicate_skips(dedupe)
        kept_ids = {m["video_id"] for m in kept_maps}
        out = [v for v in out if v.video_id in kept_ids]

    return out


def load_policy_prompt(prompt_path: Path) -> str:
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Policy prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def _prepare_part1_prompt(prompt_text: str) -> str:
    """Part 1 uses YouTube via MEDIA CONTEXT — drop placeholder transcript block."""
    return re.sub(
        r"<transcript>.*?</transcript>",
        "Use the YouTube recording in MEDIA CONTEXT as the transcript source.",
        prompt_text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()


def _diagram_lines_to_mermaid(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        return "\n".join(str(line) for line in value).strip()
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("\\n", "\n").replace('\\"', '"').strip()


def _decision_has_diagrams(decision: dict[str, Any]) -> bool:
    if decision.get("decision_profile") == "procedural_light":
        return False
    timeline, mindmap = _decision_diagram_fields(decision)
    return bool(timeline or mindmap)


def _format_vote_label(tally: Any) -> str:
    if not isinstance(tally, dict):
        return "unanimous"
    yes, no = tally.get("yes"), tally.get("no")
    if yes is not None and no is not None:
        return f"{yes}-{no}"
    if yes is not None:
        return str(yes)
    return "unanimous"


def _legacy_procedural_to_uncontested(d: dict[str, Any], seq: int) -> dict[str, Any]:
    """Move pre-split `procedural_light` rows from decisions[] into lite uncontested_items[]."""
    raw_id = str(d.get("decision_id") or f"U{seq:03d}")
    item_id = raw_id if raw_id.startswith("U") else f"U{seq:03d}"
    summary = (d.get("decision_statement") or d.get("headline") or "").strip()
    if len(summary) > 200:
        summary = summary[:197] + "..."
    return {
        "item_id": item_id,
        "headline": (d.get("headline") or summary[:80] or "Council action").strip(),
        "outcome": d.get("outcome") or "Approved",
        "vote": _format_vote_label(d.get("vote_tally")),
        "one_line_summary": summary or (d.get("headline") or ""),
        "subject_id": d.get("subject_id"),
        "legislation_refs": d.get("legislation_refs") or [],
        "primary_theme": d.get("primary_theme"),
    }


def _part1_json_ok(obj: Any) -> bool:
    if not isinstance(obj, dict) or "meeting" not in obj:
        return False
    decisions = obj.get("decisions")
    if not isinstance(decisions, list):
        return False
    uncontested = obj.get("uncontested_items")
    if uncontested is not None and not isinstance(uncontested, list):
        return False
    n_unc = len(uncontested or [])
    return len(decisions) + n_unc > 0


def _normalize_part1_analysis(parsed: dict[str, Any]) -> dict[str, Any]:
    """Split legacy procedural rows; add diagram strings for contested decisions only."""
    out = json.loads(json.dumps(parsed, ensure_ascii=False))
    raw_decisions = out.get("decisions")
    if not isinstance(raw_decisions, list):
        raw_decisions = []
    uncontested: list[dict[str, Any]] = [
        x for x in (out.get("uncontested_items") or []) if isinstance(x, dict)
    ]
    kept: list[dict[str, Any]] = []
    u_seq = len(uncontested) + 1
    for d in raw_decisions:
        if not isinstance(d, dict):
            continue
        if d.get("decision_profile") == "procedural_light":
            uncontested.append(_legacy_procedural_to_uncontested(d, u_seq))
            u_seq += 1
            continue
        d.pop("decision_profile", None)
        from scripts.gemini.mermaid_diagrams import normalize_decision_diagrams

        normalize_decision_diagrams(d)
        kept.append(d)
    out["decisions"] = kept
    out["uncontested_items"] = uncontested
    return out


def _places_digest_for_part2(payload: dict[str, Any]) -> str:
    """Short location index so Part 2 names sites, not only ``place_id`` slugs."""
    places = {
        p["place_id"]: p
        for p in (payload.get("places") or [])
        if isinstance(p, dict) and p.get("place_id")
    }
    if not places:
        return (
            "**Places:** Part 1 JSON has no `places[]` — name street addresses from "
            "`subjects[]` / `decision_statement` in **Why it matters** or **The big picture**.\n"
        )
    people = {
        p["person_id"]: p.get("full_name") or p.get("person_id")
        for p in (payload.get("people") or [])
        if isinstance(p, dict) and p.get("person_id")
    }
    lines: list[str] = ["**Places (use in contested blocks — plain language, not slugs):**"]
    for decision in payload.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        pid = decision.get("primary_place_id") or ""
        refs = decision.get("place_refs") or []
        if not pid and refs:
            pid = refs[0]
        place = places.get(pid) if pid else None
        if not place:
            continue
        addr = (
            place.get("normalized_address")
            or place.get("street_address")
            or place.get("label")
            or pid
        )
        extras: list[str] = []
        if place.get("place_type") and place.get("place_type") != "street_address":
            extras.append(str(place["place_type"]))
        if place.get("geocode_status") == "ok":
            extras.append("geocoded")
        sid = decision.get("subject_id") or ""
        for person in (payload.get("people") or []):
            if not isinstance(person, dict):
                continue
            if sid and sid.replace("subject_", "") in str(person.get("person_id") or ""):
                name = people.get(person["person_id"])
                if name:
                    extras.append(f"applicant/contact: {name}")
                break
        extra = f" ({'; '.join(extras)})" if extras else ""
        lines.append(f"- **{decision.get('headline', 'Decision')}:** {addr}{extra}")
    return "\n".join(lines) + "\n"


_APPEARED_AS_GROUP_ORDER: tuple[tuple[str, str], ...] = (
    ("commissioner", "Commissioners"),
    ("councilwoman", "Commissioners"),
    ("councilor", "Commissioners"),
    ("staff", "Staff"),
    ("applicant", "Applicants"),
    ("public", "Public"),
)


def _meeting_at_a_glance_digest(payload: dict[str, Any]) -> str:
    """Instructions + data for Part 2 ``## At a glance`` (attendees + summary)."""
    meeting = payload.get("meeting") if isinstance(payload.get("meeting"), dict) else {}
    summary = str(meeting.get("meeting_summary") or "").strip()
    agenda = str(meeting.get("agenda_summary") or "").strip()

    grouped: dict[str, list[str]] = {}
    for person in payload.get("people") or []:
        if not isinstance(person, dict):
            continue
        name = str(person.get("full_name") or "").strip()
        if not name:
            continue
        appeared = str(person.get("appeared_as") or person.get("role") or "Other").strip()
        key = appeared.lower()
        label = appeared
        for prefix, group_label in _APPEARED_AS_GROUP_ORDER:
            if key.startswith(prefix):
                label = group_label
                key = group_label
                break
        grouped.setdefault(key, [])
        if name not in grouped[key]:
            grouped[key].append(name)

    attendee_parts: list[str] = []
    seen_groups: set[str] = set()
    for _prefix, group_label in _APPEARED_AS_GROUP_ORDER:
        names = grouped.get(group_label)
        if not names:
            continue
        seen_groups.add(group_label)
        cap = names[:12]
        suffix = " (and others)" if len(names) > 12 else ""
        attendee_parts.append(f"{group_label}: {', '.join(cap)}{suffix}")
    for key, names in sorted(grouped.items()):
        if key in seen_groups:
            continue
        cap = names[:8]
        suffix = " (and others)" if len(names) > 8 else ""
        attendee_parts.append(f"{key}: {', '.join(cap)}{suffix}")

    lines = [
        "**At a glance (required — `## At a glance` immediately after the H1):**",
        "",
        "- **Attendees:** Use this list from `people[]` (group by role; you may shorten but keep names accurate):",
    ]
    if attendee_parts:
        for part in attendee_parts:
            lines.append(f"  - {part}")
    else:
        lines.append("  - (No `people[]` in JSON — infer attendees only if named in decisions/transcript fields.)")
    lines.append("")
    if summary:
        lines.append(f"- **Summary (use verbatim or tighten slightly):** {summary}")
    else:
        lines.append(
            "- **Summary:** Write 1–2 sentences from `decisions[]` headlines + "
            "`uncontested_items[]` themes"
            + (f"; agenda hint: {agenda}" if agenda else "")
            + "."
        )
    if agenda and summary:
        lines.append(f"- **Agenda topics (reference):** {agenda}")
    lines.append("")
    return "\n".join(lines)


def build_part2_message(
    part2_prompt: str,
    analysis: dict[str, Any],
    *,
    recording_title: str = "",
) -> str:
    """Second turn: Smart Brevity report from normalized Step 1 JSON."""
    payload = _normalize_part1_analysis(analysis)
    meeting = payload.get("meeting") if isinstance(payload.get("meeting"), dict) else {}
    body = str(meeting.get("body_name") or "").strip()
    date = str(meeting.get("meeting_date") or "").strip()
    title_hint = (recording_title or "").strip()
    n_contested = len(payload.get("decisions") or [])
    n_uncontested = len(payload.get("uncontested_items") or [])
    json_block = json.dumps(payload, indent=2, ensure_ascii=False)
    opener_note = (
        f"**Report H1 (required):** `# {body or 'Meeting'} — {date or 'date'}`"
        + (f"  \nIf `recording_title` disagrees with `body_name`, prefer the recording title for the H1: **{title_hint}**." if title_hint else "")
        + "\n"
    )
    mermaid_note = (
        "**Mermaid (contested items with diagrams):** Copy `diagram_timeline` and `diagram_mindmap` "
        "verbatim into fences. **Never** `graph TD` / `flowchart`.\n"
        "**Smart Brevity:** Per contested item merge `smart_brevity.one_big_thing` + `why_it_matters` "
        "into a single **Why it matters** bullet. **Never** label **The One Big Thing**. "
        "**Never** use `Who won` or `The tension`. "
        "Other axiom labels: **The big picture**, **By the numbers** (omit if none), "
        "**Who was for it (and why)**, **Who was against it (and why)** (omit if none), **What's next**.\n"
    )
    places_note = _places_digest_for_part2(payload)
    at_a_glance_note = _meeting_at_a_glance_digest(payload)
    return (
        f"{part2_prompt.strip()}\n\n---\n\n"
        f"## {PART2_USER_MARKER}\n\n"
        f"{opener_note}"
        f"{at_a_glance_note}"
        f"{places_note}"
        f"{mermaid_note}"
        f"**Contested** (`decisions[]`): **{n_contested}** — write that many full blocks under "
        f"`## Contested decisions`.\n"
        f"**Uncontested** (`uncontested_items[]`): **{n_uncontested}** — write one `## Uncontested "
        f"actions` section with exactly **{n_uncontested}** bullet(s) (one line each). "
        f"Omit that section if zero.\n\n"
        f"```json\n{json_block}\n```\n"
    )


def build_user_message(
    policy_prompt: str,
    video: VideoRow,
    *,
    media_source_id: str = "MS001",
    task_line: Optional[str] = None,
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

**Task:** {task_line or "Apply the policy analysis instructions below to this recording."} If you cannot access the video directly, state that limitation in JSON under a top-level `"_error"` field with a short explanation.

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


def _looks_like_attachment_chrome(text: str) -> bool:
    """YouTube attachment card mistaken for a finished model reply."""
    if len(text) > 1_000:
        return False
    if "{" in text and any(k in text for k in ('"meeting"', '"decisions"', '"meeting_id"')):
        return False
    if re.search(r"\d+\s*views?\)", text, re.I):
        return True
    if re.match(r"^Gemini said\s*\n", text, re.I) and "{" not in text:
        return True
    return False


def _looks_like_policy_json_blob(text: str) -> bool:
    return len(text) >= 800 and "{" in text and any(
        k in text for k in ('"meeting"', '"decisions"', '"meeting_id"')
    )


def _model_response_count(page: Any) -> int:
    try:
        n = page.locator('[data-message-author-role="model"]').count()
        n += page.locator('[data-message-author-role="assistant"]').count()
        n += page.locator("model-response").count()
        return n
    except Exception:
        return 0


def _model_reply_slice(text: str) -> str:
    """Score completeness on model output only — not echoed user prompt."""
    if not text:
        return ""
    for needle in ("Gemini said\n", "Gemini said\r\n"):
        i = text.rfind(needle)
        if i >= 0:
            return text[i + len(needle) :].lstrip()
    mj = re.search(r'\{\s*"meeting"', text)
    if mj:
        return text[mj.start() :]
    if PART2_USER_MARKER in text:
        fence = text.rfind("```")
        if fence >= 0:
            tail = text[fence + 3 :].lstrip()
            if tail.startswith("json"):
                tail = tail[4:].lstrip()
            if len(tail) > 200:
                return tail
    for marker in ("### ", "* **Who won", "**Who won:"):
        i = text.find(marker)
        if i >= 0 and i > len(text) * 0.25:
            return text[i:]
    return text


def _decision_id_count(blob: str) -> int:
    return len(re.findall(r'"decision_id"\s*:\s*"D\d+"', blob, re.I))


def _response_looks_complete(text: str, *, response_phase: str = "json") -> bool:
    slice_ = _model_reply_slice(text)
    if not slice_ or len(slice_) < 400:
        return False
    if response_phase == "json":
        span = _extract_document1_json(text)
        return span is not None and _document1_json_score(span[0]) > 0
    hits = sum(1 for m in RESPONSE_COMPLETE_MARKERS if m in slice_)
    if hits >= 2:
        return True
    return _part2_looks_done(slice_)


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
    """True only when a stop/thinking control is visible inside the chat panel."""
    root = _chat_root(page)
    for sel in GENERATING_SELECTORS:
        try:
            loc = root.locator(sel).first
            if loc.is_visible(timeout=300):
                return True
        except Exception:
            continue
    return False


def _extract_broad_model_reply_js(page: Any, *, min_chars: int = 80) -> Optional[str]:
    """Longest visible model reply in the chat (fallback when narrow selectors capture ~100 chars)."""
    try:
        text = page.evaluate(
            """(minChars) => {
              const textOf = (el) => (el.innerText || el.textContent || '').trim();
              const isUser = (el) => {
                if (!el) return false;
                if (el.closest('[data-message-author-role="user"]')) return true;
                const r = el.getAttribute?.('data-message-author-role');
                return r === 'user';
              };
              let best = '';
              const sels = [
                'model-response',
                '[data-message-author-role="model"]',
                '[data-message-author-role="assistant"]',
                'message-content',
                '.presented-response-container',
              ];
              for (const sel of sels) {
                for (const el of document.querySelectorAll(sel)) {
                  if (isUser(el)) continue;
                  const t = textOf(el);
                  if (t.length > best.length) best = t;
                }
              }
              return best.length >= minChars ? best : null;
            }""",
            min_chars,
        )
        return (text or "").strip() or None
    except Exception:
        return None


def _part2_looks_done(text: str) -> bool:
    if len(text) < 250:
        return False
    hits = sum(
        1
        for m in (
            "Who won",
            "**Who won",
            "### ",
            "```mermaid",
            "What's next",
            "The tension",
        )
        if m in text
    )
    return hits >= 2


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


def _accept_candidate(
    text: str,
    *,
    baseline_model_count: int,
    page: Any,
    response_phase: str = "json",
) -> bool:
    if not text or len(text) < 80:
        return False
    if _looks_like_user_prompt(text):
        return False
    if _looks_like_attachment_chrome(text):
        return False
    if _response_looks_complete(text, response_phase=response_phase):
        return True
    if _looks_like_policy_json_blob(text):
        return True
    if response_phase == "markdown":
        if _part2_looks_done(text):
            return True
        if len(text) >= 600 and ("Who won" in text or "### " in text):
            return True
    if _model_response_count(page) > baseline_model_count and len(text) >= 500:
        return True
    if baseline_model_count == 0 and len(text) >= 2_000:
        return True
    return False


def _wait_for_model_response(
    page: Any,
    *,
    baseline_model_count: int = 0,
    timeout_seconds: float = 600.0,
    poll_interval: float = 2.0,
    min_chars: int = 80,
    response_phase: str = "json",
) -> str:
    """Poll until Gemini finishes streaming a model reply (prompt can take several minutes)."""
    deadline = time.time() + timeout_seconds
    logger.info(
        "Waiting for model response (up to {:.0f} min, baseline={}, phase={}) …",
        timeout_seconds / 60,
        baseline_model_count,
        response_phase,
    )
    last_logged = 0.0
    idle_polls = 0
    while time.time() < deadline:
        candidates: list[str] = []
        js_text = _extract_model_response_js(page, min_chars=min_chars)
        if js_text:
            candidates.append(js_text)
        broad = _extract_broad_model_reply_js(page, min_chars=min_chars)
        if broad:
            candidates.append(broad)
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
        best = max(candidates, key=len) if candidates else ""
        if not generating:
            idle_polls += 1
        else:
            idle_polls = 0

        for text in candidates:
            if not _accept_candidate(
                text,
                baseline_model_count=baseline_model_count,
                page=page,
                response_phase=response_phase,
            ):
                continue
            if _response_looks_complete(text, response_phase=response_phase):
                logger.info(
                    "Detected complete policy analysis ({} chars) — accepting response",
                    len(text),
                )
                return text
            if (
                response_phase == "json"
                and not generating
                and _extract_document1_json(text) is not None
            ):
                logger.info(
                    "Detected parseable Document 1 JSON ({} chars) — accepting",
                    len(text),
                )
                return text
            if response_phase != "json" and _looks_like_policy_json_blob(text) and not generating:
                logger.info(
                    "Detected policy JSON in response ({} chars) — accepting",
                    len(text),
                )
                return text
            if response_phase == "markdown" and _part2_looks_done(text) and not generating:
                logger.info("Detected part 2 report ({} chars) — accepting", len(text))
                return text
            if not generating and len(text) >= 2_000:
                return text
            if (
                response_phase == "markdown"
                and not generating
                and len(text) >= 500
                and ("Who won" in text or "### " in text)
            ):
                logger.info("Accepting part 2 markdown ({} chars)", len(text))
                return text

        # UI shows a reply but narrow scrape stuck on YouTube card / short snippet
        if idle_polls >= 4 and best and not _looks_like_attachment_chrome(best):
            if _looks_like_policy_json_blob(best) or _part2_looks_done(best):
                logger.info(
                    "Accepting after idle scrape ({} chars, phase={})",
                    len(best),
                    response_phase,
                )
                return best
            if response_phase == "markdown" and len(best) >= 400:
                logger.info("Accepting idle part 2 text ({} chars)", len(best))
                return best

        now = time.time()
        if now - last_logged >= 30:
            best_len = len(best)
            logger.info(
                "Still waiting … (generating={}, best_chars={}, idle_polls={}, phase={})",
                generating,
                best_len,
                idle_polls,
                response_phase,
            )
            if best_len < 500 and idle_polls >= 2:
                logger.warning(
                    "Browser may show a full reply but scrape only sees {} chars — "
                    "check Gemini tab; will keep polling or use broad extract.",
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
    response_phase: str = "json",
) -> str:
    text = _wait_for_model_response(
        page,
        baseline_model_count=baseline_model_count,
        timeout_seconds=response_timeout_seconds,
        poll_interval=2.0,
        min_chars=min_chars,
        response_phase=response_phase,
    )

    if _response_looks_complete(text, response_phase=response_phase):
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
        if _response_looks_complete(current, response_phase=response_phase):
            return current
        if _is_generating(page) and not _response_looks_complete(
            current, response_phase=response_phase
        ):
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
    if _looks_like_attachment_chrome(previous) or len(previous) < 500:
        raise RuntimeError(
            "Scrape captured only UI chrome or a truncated reply ({} chars). "
            "Gemini may still be loading, blocked the video, or the chat DOM changed. "
            "Re-run with --save-raw-response and watch the browser window.".format(
                len(previous)
            )
        )
    return previous


def _fresh_profile_dir() -> Path:
    return _REPO_ROOT / "data" / "cache" / "gemini_browser_chrome_profile"


def _prepare_fresh_profile_dir(*, reset: bool) -> Path:
    """Ensure Playwright Chromium profile dir exists; optionally archive a broken profile."""
    path = _fresh_profile_dir()
    if reset and path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.bak.{ts}")
        logger.warning("Archiving fresh profile → {}", backup.name)
        path.rename(backup)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clear_stale_chrome_profile_locks(user_data_dir: Path) -> None:
    """Remove singleton files left when Chromium crashes (common on WSL)."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = user_data_dir / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError as exc:
            logger.debug("Could not remove {}: {}", path, exc)


def _playwright_chromium_args(*, wsl_safe: bool) -> List[str]:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if wsl_safe:
        args.extend(
            [
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
            ]
        )
    return args


def _open_page(
    p: Any,
    *,
    user_data_dir: Path,
    profile_name: str,
    headless: bool,
    cdp_url: Optional[str],
    fresh_profile: bool,
    reset_fresh_profile: bool = False,
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
        profile_path = _prepare_fresh_profile_dir(reset=reset_fresh_profile)
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

    launch_args = _playwright_chromium_args(wsl_safe=fresh_profile or platform.system() == "Linux")
    launch_args.extend(chrome_args)

    last_error: Optional[BaseException] = None
    context = None
    for attempt in range(1, 4):
        _clear_stale_chrome_profile_locks(chrome_data_dir)
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(chrome_data_dir),
                channel=channel,
                headless=headless,
                viewport={"width": 1280, "height": 800},
                ignore_default_args=["--enable-automation"],
                args=launch_args,
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Browser launch attempt {}/3 failed: {}",
                attempt,
                exc,
            )
            time.sleep(1.5)
    if context is None:
        hint = (
            "Close any Chrome using this profile, then retry. "
            "If the profile is corrupted (TargetClosedError on WSL), run with "
            "--fresh-profile --reset-fresh-profile once to start a clean sign-in. "
            "Or use --cdp-url to attach to your desktop Chrome."
        )
        raise RuntimeError(
            f"Could not launch Chromium (profile: {chrome_data_dir}). {hint}"
        ) from last_error

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
    response_phase: str = "json",
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
    response_text = _scrape_latest_response(
        page,
        baseline_model_count=baseline_model_count,
        response_phase=response_phase,
    )
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
    uncontested = obj.get("uncontested_items")
    n_d = len(decisions) if isinstance(decisions, list) else 0
    n_u = len(uncontested) if isinstance(uncontested, list) else 0
    if n_d + n_u == 0:
        return -1
    if (
        n_d
        and isinstance(decisions[0], dict)
        and str(decisions[0].get("decision_id", "")).startswith("string")
    ):
        return -1
    score = len(json.dumps(obj, ensure_ascii=False))
    if "meeting" in obj:
        score += 500_000
    score += 2_000_000 + n_d * 10_000 + n_u * 1_000
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


def _balanced_json_object_end(text: str, start: int) -> Optional[int]:
    """Index of closing `}` for object starting at `start`, or None if incomplete."""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _strip_json_label_prefix(text: str) -> str:
    """Remove Gemini UI labels before the root `{`."""
    t = text.strip()
    for prefix in ("JSON\n", "JSON\r\n", "json\n", "Json\n"):
        if t.startswith(prefix):
            return t[len(prefix) :].lstrip()
    return t


def _repair_json_blob(blob: str) -> Optional[str]:
    """Best-effort fix for invalid JSON from Gemini (e.g. unescaped quotes in diagrams)."""
    blob = _strip_json_label_prefix(blob.strip())
    if not blob:
        return None
    try:
        from json_repair import repair_json

        fixed = repair_json(blob)
        if isinstance(fixed, str) and fixed.strip():
            return fixed.strip()
    except ImportError:
        pass
    except Exception:
        pass
    return blob


def _json_decode_repaired(text: str, start: int) -> Optional[tuple[Any, int]]:
    decoded = _json_decode_at(text, start)
    if decoded:
        return decoded
    end = _balanced_json_object_end(text, start)
    if end is None:
        return None
    blob = text[start : end + 1]
    repaired = _repair_json_blob(blob)
    if not repaired or repaired == blob:
        repaired = _repair_json_blob(text[start:])
    if not repaired:
        return None
    try:
        obj = json.loads(repaired)
        return obj, end
    except json.JSONDecodeError:
        return None


def _iter_json_object_starts(text: str) -> list[int]:
    """Candidate `{` positions for Document 1 roots (prefer after model reply)."""
    starts: list[int] = []
    gs = text.rfind("Gemini said")
    search_from = gs if gs >= 0 else 0
    for pat in (r'\{\s*"meeting"', r'\{\s*\n\s*"meeting"'):
        for m in re.finditer(pat, text[search_from:]):
            starts.append(search_from + m.start())
    for m in re.finditer(r"```(?:json)?\s*\n\s*\{", text, re.I):
        i = m.end() - 1
        if i not in starts:
            starts.append(i)
    if not starts:
        i = text.find("{", search_from)
        if i >= 0:
            starts.append(i)
    # de-dupe preserving order
    seen: set[int] = set()
    out: list[int] = []
    for s in starts:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _extract_document1_json(text: str) -> Optional[tuple[Any, int, int]]:
    """Pick the best full meeting JSON object and its (start, end) span in the scrape."""
    raw = _strip_json_label_prefix(text)
    best: Optional[tuple[Any, int, int]] = None
    best_score = -1

    for start in _iter_json_object_starts(raw):
        decoded = _json_decode_repaired(raw, start)
        if not decoded:
            continue
        obj, end = decoded
        if not isinstance(obj, dict):
            continue
        score = _document1_json_score(obj)
        if score > best_score:
            best_score = score
            best = (obj, start, end)

    decoder = json.JSONDecoder()
    i = 0
    while i < len(raw):
        if raw[i] != "{":
            i += 1
            continue
        decoded = _json_decode_repaired(raw, i)
        if decoded:
            obj, end = decoded
            if isinstance(obj, dict):
                score = _document1_json_score(obj)
                if score > best_score:
                    best_score = score
                    best = (obj, i, end)
            i = max(decoded[1], i + 1)
        else:
            i += 1
    return best


def _looks_like_json_fragment(text: str) -> bool:
    """True when scraped 'markdown' is clearly a JSON tail, not Document 2."""
    head = text.lstrip()[:400]
    if not head:
        return False
    if head.startswith(",") or head.startswith('{"') or head.startswith("{"):
        return True
    return bool(
        re.search(r'^"?(meeting|people|decisions|organizations)"?\s*:', head, re.MULTILINE)
        or '"person_id"' in head
    )


PART2_REPORT_MARKERS = (
    "**Who won:**",
    "* **Who won:**",
    "Who won:",
    "### ",
    "#### Timeline",
)

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


def _extract_readable_markdown(raw: str, *, after_index: int = 0) -> str:
    """Human-readable Document 2 only — skip echoed prompt rules and embedded JSON."""
    search_from = max(0, after_index)
    break_pos = raw.rfind(DOCUMENT_BREAK_TOKEN)
    if break_pos >= 0:
        search_from = max(search_from, break_pos + len(DOCUMENT_BREAK_TOKEN))
    else:
        gs = raw.rfind("Gemini said")
        if gs >= 0:
            search_from = max(search_from, gs + len("Gemini said"))
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
        if re.match(r'^"?(people|decisions|organizations|meeting|legislation)"?\s*:', stripped):
            break
        if stripped in ("{", "},", "]", "},"):
            break
        clean.append(line)
    return "\n".join(clean).strip()


def _part2_response_start(raw: str) -> int:
    """Start of the model's part-2 reply (not the echoed JSON user turn)."""
    search_from = 0
    marker_pos = raw.rfind(PART2_USER_MARKER)
    if marker_pos >= 0:
        search_from = marker_pos + len(PART2_USER_MARKER)
    gemini_said = [m.start() for m in re.finditer(r"Gemini said", raw, re.IGNORECASE)]
    if len(gemini_said) >= 2:
        return max(search_from, gemini_said[-1] + len("Gemini said"))
    if gemini_said:
        return max(search_from, gemini_said[-1] + len("Gemini said"))
    return search_from


def _first_part2_report_start(slice_text: str) -> int:
    """First decision block in part 2 — never rfind (that kept only the last decision)."""
    patterns = (
        r"^###\s+",
        r"^\* \*\*Who won:\*\*",
        r"^\*\*Who won:\*\*",
        r"^Who won:",
    )
    starts = []
    for pat in patterns:
        m = re.search(pat, slice_text, re.MULTILINE)
        if m:
            starts.append(m.start())
    return min(starts) if starts else 0


def _normalize_gemini_report_markdown(text: str) -> str:
    """Repair Gemini web UI scrape: Code snippet → mermaid fences, plain labels → headings."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    section_stops = frozenset(
        {"Timeline", "Decision Map", "Code snippet", "Who won:", "Who was for it"}
    )

    def _bulletize(label: str, line: str) -> str:
        rest = line.split(":", 1)[1].strip() if ":" in line else ""
        return f"* **{label}:** {rest}".rstrip()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "Code snippet" and i + 1 < len(lines):
            next_s = lines[i + 1].strip()
            if next_s.startswith("timeline") or next_s.startswith("mindmap"):
                out.append("```mermaid")
                i += 1
                while i < len(lines):
                    s = lines[i].strip()
                    if s in section_stops or s.startswith("Who won"):
                        break
                    if s == "Code snippet":
                        break
                    out.append(lines[i])
                    i += 1
                out.append("```")
                continue

        if stripped == "Timeline":
            out.append("#### Timeline")
            i += 1
            continue
        if stripped == "Decision Map":
            out.append("#### Decision Map")
            i += 1
            continue
        if stripped.startswith("Who won:") and not stripped.startswith("*"):
            out.append(_bulletize("Who won", line))
            i += 1
            continue
        if stripped.startswith("Who was for it") and not stripped.startswith("*"):
            out.append(_bulletize("Who was for it (and why)", line))
            i += 1
            continue
        if stripped.startswith("Who was against it") and not stripped.startswith("*"):
            out.append(_bulletize("Who was against it (and why)", line))
            i += 1
            continue
        if stripped.startswith("The tension:") and not stripped.startswith("*"):
            out.append(_bulletize("The tension", line))
            i += 1
            continue
        if stripped.startswith("What's next:") and not stripped.startswith("*"):
            out.append(_bulletize("What's next", line))
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out).strip()


def _extract_part2_report(raw: str) -> str:
    """Plain-language part 2 markdown only (no JSON tail)."""
    search_from = _part2_response_start(raw)
    slice_text = raw[search_from:]
    start = _first_part2_report_start(slice_text)
    text = _strip_gemini_ui_chrome(slice_text[start:])
    lines = text.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('{"') or stripped.startswith('"meeting_id":'):
            break
        if stripped == "{" and len(clean) > 20:
            break
        if re.match(r'^"?(people|decisions|organizations|meeting)"?\s*:', stripped):
            break
        clean.append(line)
    body = "\n".join(clean).strip()
    return _normalize_gemini_report_markdown(body)


def _decision_diagram_fields(decision: dict[str, Any]) -> tuple[str, str]:
    timeline = _diagram_lines_to_mermaid(
        decision.get("diagram_timeline")
        or decision.get("diagram_timeline_lines")
    )
    mindmap = _diagram_lines_to_mermaid(
        decision.get("diagram_mindmap") or decision.get("diagram_mindmap_lines")
    )
    return timeline, mindmap


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
        if not _decision_has_diagrams(d):
            continue
        timeline, mindmap = _decision_diagram_fields(d)
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
    span = _extract_document1_json(raw)
    parsed: Optional[Any] = span[0] if span else None
    json_end = span[2] if span else 0
    markdown_docs: list[str] = []

    if parsed is not None and json_end > 0:
        md = _markdown_after_json(raw, json_end)
        if md:
            markdown_docs.append(md)

    if parsed is None:
        parsed = _try_parse_json_from_response(raw)
        if parsed is not None and _is_placeholder_policy_json(parsed):
            parsed = None

    readable = _extract_readable_markdown(raw, after_index=json_end)
    if readable and (
        not markdown_docs
        or _looks_like_json_fragment(markdown_docs[0])
        or len(readable) >= 500
    ):
        if len(readable) >= 200:
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


_RUN_SORT_SCALE = 10_000_000_000  # inverted unix prefix: ascending names ≈ newest first


def _run_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    """Sort key for runs: newest ``generated_at`` first, then ``video_id``."""
    return (str(record.get("generated_at") or ""), str(record.get("video_id") or ""))


def _sort_run_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=_run_sort_key, reverse=True)


def _run_filename_prefix(ts: str) -> str:
    """Leading token so default A→Z file sort lists newest run at the top."""
    dt = datetime.strptime(ts, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    inverted = _RUN_SORT_SCALE - int(dt.timestamp())
    return f"{inverted:010d}_{ts}"


def _output_stem(video: VideoRow, *, prompt_tag: str, model_tag: str, ts: str) -> str:
    """Audio-aligned basename + video_id + prompt/model tags (see ``policy_output_stem``)."""
    from scripts.gemini.transcript_cache_paths import policy_output_stem

    _ = ts  # run time lives in ``*_meta.json`` ``generated_at``, not the filename
    return policy_output_stem(
        title=video.title or "",
        event_date=video.event_date,
        video_id=video.video_id,
        prompt_tag=prompt_tag,
        model_tag=model_tag,
    )


def _load_manifest_records(folder: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    json_path = folder / "_manifest.json"
    jsonl_path = folder / "_manifest.jsonl"
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = data
        except json.JSONDecodeError:
            logger.warning("Could not parse {}; rebuilding manifest", json_path)
    if not records and jsonl_path.is_file():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return _sort_run_records(records)


def _render_manifest_md(records: list[dict[str, Any]]) -> str:
    lines = [
        "# Gemini browser policy runs\n",
        "Newest runs first (per meeting and overall).\n",
        "| generated_at | video_id | prompt | model | analysis | document 2 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in _sort_run_records(records):
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


def _write_video_run_index(folder: Path, video_id: str) -> None:
    """Per-meeting index: links to all runs for one ``video_id``, newest first."""
    records = [
        r for r in _load_manifest_records(folder) if str(r.get("video_id") or "") == video_id
    ]
    lines = [
        f"# Runs for `{video_id}`\n",
        "Newest downloads first.\n",
        "| generated_at | prompt | model | analysis | report | diagrams |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in records:
        files = r.get("files") or {}
        lines.append(
            "| {generated_at} | {prompt_name} | {gemini_model} | "
            "[json]({analysis}) | [report]({report}) | {diagrams} |".format(
                generated_at=r.get("generated_at", ""),
                prompt_name=r.get("prompt_name", r.get("prompt_file", "")),
                gemini_model=r.get("gemini_model") or "unknown",
                analysis=files.get("analysis_json", "—"),
                report=files.get("report_md", "—"),
                diagrams=(
                    f"[diagrams]({files['diagrams_md']})"
                    if files.get("diagrams_md")
                    else "—"
                ),
            )
        )
    index_path = folder / f"_index_{video_id}.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(folder: Path, record: dict[str, Any]) -> None:
    records = _sort_run_records(_load_manifest_records(folder) + [record])
    json_path = folder / "_manifest.json"
    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "_manifest.md").write_text(_render_manifest_md(records), encoding="utf-8")
    video_id = str(record.get("video_id") or "")
    if video_id:
        _write_video_run_index(folder, video_id)


def _try_parse_json_from_response(text: str) -> Optional[Any]:
    """Best-effort extract of JSON from Gemini markdown (fenced blocks or bare object)."""
    span = _extract_document1_json(text)
    if span:
        obj = span[0]
        if isinstance(obj, dict) and not _is_placeholder_policy_json(obj):
            return obj
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
    reset_fresh_profile: bool = False,
    new_tab_per_video: bool = False,
    gemini_model_override: Optional[str] = None,
    select_model: Optional[str] = None,
    save_raw_response: bool = False,
    two_part: bool = False,
    part1_prompt: str = "",
    part2_prompt: str = "",
    prompt_part1_path: Optional[Path] = None,
    prompt_part2_path: Optional[Path] = None,
) -> int:
    """One browser session; loop URLs → prompt(s) → save response for each video."""
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
            reset_fresh_profile=reset_fresh_profile,
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

                try:
                    if two_part:
                        if not prompt_part1_path or not prompt_part2_path:
                            raise RuntimeError("two_part mode requires prompt_part1_path and prompt_part2_path")
                        part1_message = build_user_message(
                            part1_prompt,
                            video,
                            media_source_id=f"MS{i:03d}",
                            task_line=(
                                "Apply **Step 1** (part 1) instructions below. "
                                "Output **only** the JSON object — no markdown summary. "
                                "Put **debated** items in `decisions[]` (full schema + diagrams). "
                                "Put **unanimous / no-debate** items in `uncontested_items[]` "
                                "(lite one-line rows only). Do not merge unrelated actions."
                            ),
                        )
                        logger.info("Sending part 1 ({} chars) …", len(part1_message))
                        part1_capture = _send_prompt_on_page(
                            page,
                            part1_message,
                            debug_dir=debug_dir,
                            gemini_model_override=gemini_model_override,
                            response_phase="json",
                        )
                        time.sleep(hold_open_seconds)
                        span = _extract_document1_json(part1_capture.response_text)
                        parsed_part1 = span[0] if span else None
                        if not _part1_json_ok(parsed_part1):
                            logger.error(
                                "Part 1 JSON parse failed for {} — skipping part 2",
                                video.video_id,
                            )
                            save_two_part_run_output(
                                output_dir,
                                video,
                                part1_capture,
                                GeminiRunCapture(response_text="", gemini_model=part1_capture.gemini_model),
                                prompt_part1_path=prompt_part1_path,
                                prompt_part2_path=prompt_part2_path,
                                parsed_part1=parsed_part1,
                                save_raw_response=save_raw_response,
                            )
                            continue
                        parsed_part1 = _normalize_part1_analysis(parsed_part1)
                        part2_message = build_part2_message(part2_prompt, parsed_part1)
                        logger.info("Sending part 2 ({} chars) …", len(part2_message))
                        part2_capture = _send_prompt_on_page(
                            page,
                            part2_message,
                            debug_dir=debug_dir,
                            gemini_model_override=gemini_model_override,
                            response_phase="markdown",
                        )
                        time.sleep(hold_open_seconds)
                        out_path = save_two_part_run_output(
                            output_dir,
                            video,
                            part1_capture,
                            part2_capture,
                            prompt_part1_path=prompt_part1_path,
                            prompt_part2_path=prompt_part2_path,
                            parsed_part1=parsed_part1,
                            save_raw_response=save_raw_response,
                        )
                        logger.success(
                            "Saved {} (part1={} chars, part2={} chars, model={})",
                            out_path,
                            len(part1_capture.response_text),
                            len(part2_capture.response_text),
                            part2_capture.gemini_model or "unknown",
                        )
                    else:
                        user_message = build_user_message(
                            policy_prompt,
                            video,
                            media_source_id=f"MS{i:03d}",
                            task_line=(
                                "Apply the policy analysis instructions below. "
                                "Document 1: debated votes in `decisions[]`, routine votes in "
                                "`uncontested_items[]`. Document 2: contested prose + uncontested bullets."
                            ),
                        )
                        capture = _send_prompt_on_page(
                            page,
                            user_message,
                            debug_dir=debug_dir,
                            gemini_model_override=gemini_model_override,
                        )
                        time.sleep(hold_open_seconds)
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
                except Exception as exc:
                    logger.error("Failed for {}: {}", video.video_id, exc)
                    if debug_dir:
                        _debug_screenshot(page, debug_dir, f"error_{video.video_id}")
                    continue
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
    reset_fresh_profile: bool = False,
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
            reset_fresh_profile=reset_fresh_profile,
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


def _warn_if_sparse_decisions(
    analysis: dict[str, Any], *, video_id: str, prompt_name: str
) -> None:
    analysis = _normalize_part1_analysis(analysis)
    decisions = analysis.get("decisions")
    uncontested = analysis.get("uncontested_items")
    if not isinstance(decisions, list):
        return
    n_d = len(decisions)
    n_u = len(uncontested) if isinstance(uncontested, list) else 0
    total = n_d + n_u
    if total < 2:
        logger.warning(
            "Only {} total action(s) ({} contested, {} uncontested) for {} — "
            "re-run if the meeting had more votes",
            total,
            n_d,
            n_u,
            video_id,
        )
    if n_d >= 5 and n_u == 0:
        logger.warning(
            "{} contested decision(s) and no uncontested_items for {} (prompt={}) — "
            "routine votes may be bloating decisions[]; use uncontested_items[] on re-run",
            n_d,
            video_id,
            prompt_name,
        )


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
    stem = _output_stem(video, prompt_tag=prompt_tag, model_tag=model_tag, ts=ts)

    parsed, markdown_docs = _split_gemini_documents(response_text)
    rel = lambda p: str(p.relative_to(_REPO_ROOT))

    meta_path = folder / f"{stem}_meta.json"
    analysis_path = folder / f"{stem}_analysis.json"
    report_md_path = folder / f"{stem}_report.md"
    diagrams_md_path = folder / f"{stem}_diagrams.md"

    raw_path = folder / f"{stem}_response_raw.md"
    if not _part1_json_ok(parsed):
        logger.warning(
            "Could not parse full Document 1 JSON for {} — analysis.json will contain an error stub",
            video.video_id,
        )
        raw_path.write_text(response_text + "\n", encoding="utf-8")
        analysis_payload: Any = {
            "_error": "Could not parse full meeting JSON (expected meeting + decisions[] + uncontested_items[])",
            "document1_excerpt": response_text[:2000],
            "parsed_fragment": parsed,
            "response_raw_md": str(raw_path.relative_to(_REPO_ROOT)),
        }
        json_parsed = False
    else:
        analysis_payload = _normalize_part1_analysis(parsed)
        json_parsed = True
        _warn_if_sparse_decisions(
            analysis_payload, video_id=video.video_id, prompt_name=prompt_name
        )

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
    if save_raw_response or not json_parsed:
        if not raw_path.is_file():
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


def save_two_part_run_output(
    output_dir: Path,
    video: VideoRow,
    part1_capture: GeminiRunCapture,
    part2_capture: GeminiRunCapture,
    *,
    prompt_part1_path: Path,
    prompt_part2_path: Path,
    parsed_part1: Optional[dict[str, Any]] = None,
    save_raw_response: bool = False,
) -> Path:
    """Persist analysis.json from part 1 and report.md from part 2."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = output_dir / video.jurisdiction_id
    folder.mkdir(parents=True, exist_ok=True)
    prompt_tag = "policy_analysis_2part"
    model_tag = _sanitize_tag(
        part2_capture.gemini_model or part1_capture.gemini_model or "unknown_model"
    )
    stem = _output_stem(video, prompt_tag=prompt_tag, model_tag=model_tag, ts=ts)
    rel = lambda p: str(p.relative_to(_REPO_ROOT))

    span = _extract_document1_json(part1_capture.response_text)
    parsed = parsed_part1
    if parsed is None and span:
        parsed = span[0]
    if _part1_json_ok(parsed):
        analysis_payload = _normalize_part1_analysis(parsed)
        json_parsed = True
        _warn_if_sparse_decisions(
            analysis_payload,
            video_id=video.video_id,
            prompt_name=prompt_part1_path.stem,
        )
    else:
        analysis_payload = {
            "_error": "Could not parse part 1 JSON (expected meeting + decisions[] + uncontested_items[])",
            "document1_excerpt": part1_capture.response_text[:2000],
            "parsed_fragment": parsed,
        }
        json_parsed = False

    report_body = _extract_part2_report(part2_capture.response_text)
    if not report_body:
        _, markdown_docs = _split_gemini_documents(part2_capture.response_text)
        report_body = markdown_docs[0] if markdown_docs else ""

    analysis_path = folder / f"{stem}_analysis.json"
    report_md_path = folder / f"{stem}_report.md"
    diagrams_md_path = folder / f"{stem}_diagrams.md"
    meta_path = folder / f"{stem}_meta.json"

    analysis_path.write_text(
        json.dumps(analysis_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if report_body and not _looks_like_json_fragment(report_body):
        report_md_path.write_text(report_body + "\n", encoding="utf-8")
    else:
        report_md_path.write_text(
            "# Report unavailable\n\n"
            "Part 2 did not return readable markdown (check browser or re-run).\n",
            encoding="utf-8",
        )

    has_diagrams = False
    if json_parsed and isinstance(analysis_payload, dict):
        has_diagrams = _write_diagrams_md(analysis_payload, diagrams_md_path)

    files: dict[str, str] = {
        "meta_json": rel(meta_path),
        "analysis_json": rel(analysis_path),
        "report_md": rel(report_md_path),
    }
    if has_diagrams:
        files["diagrams_md"] = rel(diagrams_md_path)
    if save_raw_response:
        p1_raw = folder / f"{stem}_part1_response_raw.md"
        p2_raw = folder / f"{stem}_part2_response_raw.md"
        p1_raw.write_text(part1_capture.response_text + "\n", encoding="utf-8")
        p2_raw.write_text(part2_capture.response_text + "\n", encoding="utf-8")
        files["part1_response_raw_md"] = rel(p1_raw)
        files["part2_response_raw_md"] = rel(p2_raw)

    meta_payload: dict[str, Any] = {
        "video_id": video.video_id,
        "video_url": video.video_url,
        "title": video.title,
        "jurisdiction_id": video.jurisdiction_id,
        "last_updated": (
            video.last_updated.isoformat() if video.last_updated is not None else None
        ),
        "prompt_mode": "two_part",
        "prompt_name": prompt_tag,
        "prompt_part_1": str(prompt_part1_path.relative_to(_REPO_ROOT)),
        "prompt_part_2": str(prompt_part2_path.relative_to(_REPO_ROOT)),
        "gemini_model": part2_capture.gemini_model or part1_capture.gemini_model,
        "generation_source": "gemini_web_ui",
        "generated_at": ts,
        "part1_response_chars": len(part1_capture.response_text),
        "part2_response_chars": len(part2_capture.response_text),
        "json_parsed": json_parsed,
        "has_diagrams_md": has_diagrams,
        "report_chars": len(report_body),
        "files": files,
    }
    meta_path.write_text(
        json.dumps(meta_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_manifest(
        folder,
        {
            "video_id": video.video_id,
            "video_url": video.video_url,
            "title": video.title,
            "prompt_name": prompt_tag,
            "prompt_file": meta_payload["prompt_part_1"],
            "gemini_model": meta_payload["gemini_model"],
            "generation_source": "gemini_web_ui",
            "generated_at": ts,
            "response_chars": len(part1_capture.response_text) + len(part2_capture.response_text),
            "json_parsed": json_parsed,
            "has_diagrams_md": has_diagrams,
            "files": files,
        },
    )
    logger.info(
        "Wrote: {} (JSON), {} (report){}",
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
        default=None,
        help="Single combined prompt file (legacy). If omitted, uses two-part prompts.",
    )
    parser.add_argument(
        "--prompt-part-1",
        type=Path,
        default=DEFAULT_PROMPT_PART_1,
        help=f"Step 1 JSON prompt (default: {DEFAULT_PROMPT_PART_1})",
    )
    parser.add_argument(
        "--prompt-part-2",
        type=Path,
        default=DEFAULT_PROMPT_PART_2,
        help=f"Step 2 report prompt (default: {DEFAULT_PROMPT_PART_2})",
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
        "--reset-fresh-profile",
        action="store_true",
        help="With --fresh-profile: archive the existing profile dir and create a clean one (fixes TargetClosedError / corrupt WSL profile)",
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

    two_part = args.prompt_file is None
    if args.dry_run:
        if two_part:
            p1 = _prepare_part1_prompt(load_policy_prompt(args.prompt_part_1.resolve()))
            p2 = load_policy_prompt(args.prompt_part_2.resolve())
            logger.info("Part 1 prompt: {} chars from {}", len(p1), args.prompt_part_1)
            logger.info("Part 2 prompt: {} chars from {}", len(p2), args.prompt_part_2)
            logger.info(
                "[dry-run] Would send {} video(s) × 2 prompts each (JSON then report)",
                len(videos),
            )
        else:
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
            reset_fresh_profile=args.reset_fresh_profile,
        )
        return 0

    if two_part:
        part1_path = args.prompt_part_1.resolve()
        part2_path = args.prompt_part_2.resolve()
        part1_prompt = _prepare_part1_prompt(load_policy_prompt(part1_path))
        part2_prompt = load_policy_prompt(part2_path)
        logger.info("Two-part mode: {} + {}", part1_path.name, part2_path.name)
        run_video_batch(
            videos,
            "",
            user_data_dir=user_data,
            profile_name=profile,
            headless=args.headless,
            hold_open_seconds=args.hold_open,
            delay_between_videos=args.delay_between,
            output_dir=args.output_dir.resolve(),
            prompt_path=part1_path,
            debug_dir=debug_dir,
            pause_after_open=args.pause_after_open,
            cdp_url=args.cdp_url,
            fresh_profile=args.fresh_profile,
            reset_fresh_profile=args.reset_fresh_profile,
            new_tab_per_video=args.new_tab_per_video,
            gemini_model_override=args.gemini_model,
            select_model=args.select_model,
            save_raw_response=args.save_raw_response,
            two_part=True,
            part1_prompt=part1_prompt,
            part2_prompt=part2_prompt,
            prompt_part1_path=part1_path,
            prompt_part2_path=part2_path,
        )
    else:
        prompt_path = args.prompt_file.resolve()
        policy_prompt = load_policy_prompt(prompt_path)
        run_video_batch(
            videos,
            policy_prompt,
            user_data_dir=user_data,
            profile_name=profile,
            headless=args.headless,
            hold_open_seconds=args.hold_open,
            delay_between_videos=args.delay_between,
            output_dir=args.output_dir.resolve(),
            prompt_path=prompt_path,
            debug_dir=debug_dir,
            pause_after_open=args.pause_after_open,
            cdp_url=args.cdp_url,
            fresh_profile=args.fresh_profile,
            reset_fresh_profile=args.reset_fresh_profile,
            new_tab_per_video=args.new_tab_per_video,
            gemini_model_override=args.gemini_model,
            select_model=args.select_model,
            save_raw_response=args.save_raw_response,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
