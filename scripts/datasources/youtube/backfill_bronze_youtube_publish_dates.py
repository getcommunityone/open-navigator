#!/usr/bin/env python3
"""
Backfill bronze.bronze_events_youtube.published_at, event_date, event_time, and channel_id
(from yt-dlp metadata when present) via extract_info (no download). Use when rows were inserted
without dates or channel_id should be refreshed from the video metadata.

Throttling / anti-block behavior (aligned with ``download_audio_to_drive.py`` where possible):
  - Default ``--sleep`` **5s** between videos × **random jitter** U(0.5, 1.5).
  - **First** try **Android client only, no cookies, no EJS** (often works for public gov videos
    and avoids immediate web “Sign in / bot” walls). Then cookie/web clients if configured.
  - Cool-off **``--strategy-cooloff``** seconds between strategy switches after hard blocks.
  - Optional **``--startup-delay``** before the first yt-dlp call (warm up / rotate VPN).
  - After bot-style errors, extra spacing ramps with a short streak multiplier.
  - yt-dlp: retries, optional **EJS** when using cookies + web (Node/Deno; ``YTDLP_NO_EJS=1`` to skip).
  - **Cookies:** ``--cookies-from-browser`` (wins), else ``--cookies`` / ``YOUTUBE_COOKIES``,
    else ``<repo>/youtube_cookies.txt`` if present.
  - **Per-strategy retries** with exponential backoff; optional ``--skip-android-public-first``
    to go straight to authenticated clients.
  - **Proxy:** ``--proxy`` or ``YOUTUBE_HTTPS_PROXY`` / ``HTTPS_PROXY`` / ``HTTP_PROXY``.
  - If the **Sign in / not a bot** wall hits the cookie+web client, the script skips extra per-try
    retries, the **45s** post-strategy pause, and the **stripped-cookie** follow-up (same session
    rarely recovers until cookies, browser export, IP, or yt-dlp change).

If you still get **immediate** bot detection: raise ``--sleep`` (try 12–20), use
``--cookies-from-browser chrome``, ensure **Node** is on PATH for EJS when using cookies,
use a **residential / VPN** proxy, and export a **fresh** Netscape cookie file.

Examples:
  ./scripts/datasources/youtube/run_backfill_bronze_youtube_publish_dates.sh --dry-run --limit 10
  ./scripts/datasources/youtube/run_backfill_bronze_youtube_publish_dates.sh \\
    --states AL,GA,IN,MA,MT,WA,WI --sleep 3 --extract-retries 4 \\
    --cookies-from-browser chrome
"""

from __future__ import annotations

import argparse
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import psycopg2
from dotenv import load_dotenv
from loguru import logger
import yt_dlp

load_dotenv()

_LOCAL_DEV = "postgresql://postgres:password@localhost:5433/open_navigator"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_COOKIES_FILE = _PROJECT_ROOT / "youtube_cookies.txt"


def _database_url() -> str:
    return (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or _LOCAL_DEV
    )


def _ejs_opts() -> Dict[str, Any]:
    """Same policy as download_audio_to_drive._yt_dlp_youtube_ejs_opts (kept local to avoid heavy import)."""
    if os.environ.get("YTDLP_NO_EJS", "").strip().lower() in ("1", "true", "yes", "on"):
        return {}
    js_runtimes: Dict[str, Dict[str, Any]] = {}
    if shutil.which("node"):
        js_runtimes["node"] = {}
    if shutil.which("deno"):
        js_runtimes["deno"] = {}
    if not js_runtimes:
        return {}
    return {
        "js_runtimes": js_runtimes,
        "remote_components": {"ejs:github"},
    }


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def _looks_hard_youtube_block(msg: str) -> bool:
    m = _strip_ansi(msg).lower()
    needles = (
        "429",
        "too many requests",
        "sign in to confirm",
        "not a bot",
        "http error 403",
        "unable to download video webpage",
        "blocked",
        "ip blocked",
        "captcha",
    )
    return any(n in m for n in needles)


def _looks_youtube_bot_signin_wall(msg: str) -> bool:
    """Risk-engine / PoW wall — retries and stripped-cookie client rarely help in the same session."""
    m = _strip_ansi(msg).lower()
    return "sign in to confirm" in m or "not a bot" in m


def _looks_proxy_unreachable(msg: str) -> bool:
    """SOCKS/HTTP proxy env points at a host:port that refuses connections or is down."""
    m = _strip_ansi(msg).lower()
    needles = (
        "connection refused",
        "errno 111",
        "failed to establish a new connection",
        "sockshttpsconnection",
        "socksconnection",
        "proxyerror",
        "unable to connect to proxy",
        "tunnel connection failed",
        "name or service not known",
        "nodename nor servname",
    )
    return any(n in m for n in needles)


def _android_public_metadata_opts(*, proxy: Optional[str]) -> Dict[str, Any]:
    """Minimal yt-dlp opts: Innertube ANDROID client only, no cookies, no EJS (often avoids web bot checks)."""
    o: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "socket_timeout": 60,
        "retries": 2,
        "fragment_retries": 2,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            },
        },
    }
    if proxy:
        o["proxy"] = proxy
    return o


def _build_ytdlp_opts(
    *,
    cookiefile: Optional[str],
    cookiesfrombrowser: Optional[Tuple[str, ...]],
    proxy: Optional[str],
    include_ejs: bool = True,
    player_clients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    clients = player_clients if player_clients else ["android", "web"]
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "socket_timeout": 45,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_args": {
            "youtube": {
                "player_client": clients,
            },
        },
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "referer": "https://www.youtube.com/",
        "http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
    }
    if include_ejs:
        opts.update(_ejs_opts())
    if proxy:
        opts["proxy"] = proxy
    if cookiesfrombrowser:
        opts["cookiesfrombrowser"] = cookiesfrombrowser
    elif cookiefile:
        opts["cookiefile"] = cookiefile
    return opts


def _strip_cookie_keys(opts: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in opts.items() if k not in ("cookiefile", "cookiesfrombrowser")}


def _published_from_ytdlp_info(info: Dict[str, Any]) -> Optional[datetime]:
    """Best-effort upload/publish instant in UTC (naive datetime for TIMESTAMP columns)."""
    ts = info.get("timestamp") or info.get("release_timestamp")
    if ts is not None:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            pass
    ud = info.get("upload_date") or info.get("release_date")
    if isinstance(ud, str) and re.fullmatch(r"\d{8}", ud.strip()):
        try:
            dt = datetime.strptime(ud.strip(), "%Y%m%d").replace(tzinfo=timezone.utc)
            return dt.replace(tzinfo=None)
        except ValueError:
            pass
    return None


def _channel_id_from_ytdlp_info(info: Dict[str, Any]) -> Optional[str]:
    """YouTube channel id (e.g. UC…) from yt-dlp metadata, if present."""
    raw = info.get("channel_id") or info.get("uploader_id")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return s[:50]


def _extract_published_at_variants(
    video_id: str,
    variants: List[Tuple[str, Dict[str, Any]]],
    *,
    extract_retries: int,
    strategy_cooloff: float,
) -> Tuple[Optional[datetime], Optional[str], Optional[str]]:
    """Try each (label, opts) variant in order; return (published_ts, err, channel_id)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    last_err: Optional[str] = None
    dead_proxy = False
    for vi, (label, opts) in enumerate(variants):
        if dead_proxy:
            logger.warning(
                "  Skipping remaining yt-dlp strategies: proxy connection failed "
                "(unset YOUTUBE_HTTPS_PROXY / HTTPS_PROXY / HTTP_PROXY or start the SOCKS listener)"
            )
            return None, last_err, None
        if vi > 0 and strategy_cooloff > 0:
            logger.info(
                f"  Pausing {strategy_cooloff:.0f}s between yt-dlp strategies "
                f"({variants[vi - 1][0]!r} → {label!r})"
            )
            time.sleep(strategy_cooloff)
        for attempt in range(extract_retries):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False) or {}
                published = _published_from_ytdlp_info(info)
                channel_id = _channel_id_from_ytdlp_info(info)
                if published:
                    if vi > 0:
                        logger.info(f"  Strategy {label!r} succeeded for {video_id}")
                    return published, None, channel_id
                last_err = "metadata had no timestamp/upload_date"
            except Exception as e:
                last_err = _strip_ansi(str(e))
                if _looks_proxy_unreachable(last_err):
                    logger.error(
                        f"  [{label}] proxy unreachable (connection refused or SOCKS failure). "
                        f"Check {opts.get('proxy')!r} or unset YOUTUBE_HTTPS_PROXY / HTTPS_PROXY / HTTP_PROXY "
                        "if you are not running a local tunnel (e.g. WARP on 127.0.0.1:1080)."
                    )
                    dead_proxy = True
                    break
                if label == "android_public_no_cookie" and attempt == 0:
                    low = last_err.lower()
                    if "sign in to confirm" in low or "not a bot" in low:
                        logger.info(
                            f"  [{label}] immediate bot / sign-in wall — skipping further retries "
                            "for this strategy (use cookies, browser cookies, or proxy)"
                        )
                        break
                if label in (
                    "web_android_ejs_cookie_or_anon",
                    "web_android_ejs_no_cookie",
                ) and attempt == 0:
                    if _looks_youtube_bot_signin_wall(last_err):
                        logger.info(
                            f"  [{label}] immediate bot / sign-in wall — skipping further retries "
                            "for this strategy (same wall until cookies, browser export, IP, or yt-dlp change)"
                        )
                        break
                if attempt < extract_retries - 1:
                    backoff = min(120.0, 2.5 * (2**attempt))
                    if _looks_hard_youtube_block(last_err):
                        backoff = min(180.0, backoff * 1.75)
                    logger.warning(
                        f"  [{label}] yt-dlp attempt {attempt + 1}/{extract_retries} failed for {video_id}: "
                        f"{last_err[:200]!r} — sleeping {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                else:
                    logger.warning(
                        f"  [{label}] gave up after {extract_retries} tries for {video_id}: {last_err[:240]!r}"
                    )
        if (
            last_err
            and _looks_hard_youtube_block(last_err)
            and not _looks_youtube_bot_signin_wall(last_err)
            and not _looks_proxy_unreachable(last_err)
            and strategy_cooloff > 0
            and label != "android_public_no_cookie"
        ):
            bump = min(120.0, strategy_cooloff * 2.5)
            logger.info(
                f"  Extra cool-off {bump:.0f}s after hard-block on strategy {label!r} "
                "(429 / IP block / etc.; not used after android_public_no_cookie or for sign-in/bot wall)"
            )
            time.sleep(bump)
        if (
            last_err
            and label == "web_android_ejs_cookie_or_anon"
            and _looks_youtube_bot_signin_wall(last_err)
        ):
            logger.info(
                "  Skipping remaining yt-dlp strategies for this video: bot/sign-in wall already hit "
                "with cookie/web client — stripped-cookie retry will not help in the same session"
            )
            break
    return None, last_err, None


def _fetch_ids(
    conn,
    *,
    states: Optional[List[str]],
    limit: Optional[int],
) -> List[str]:
    cur = conn.cursor()
    q = """
        SELECT y.video_id
        FROM bronze.bronze_events_youtube y
        WHERE y.video_url IS NOT NULL
          AND y.event_date IS NULL
          AND y.published_at IS NULL
    """
    params: List[Any] = []
    if states:
        q += " AND y.state_code = ANY(%s)"
        params.append(states)
    q += " ORDER BY y.state_code NULLS LAST, y.channel_id, y.video_id"
    if limit is not None:
        q += " LIMIT %s"
        params.append(int(limit))
    cur.execute(q, params)
    rows = [r[0] for r in cur.fetchall() if r[0]]
    cur.close()
    return rows


def _update_row(
    conn,
    video_id: str,
    published_at: datetime,
    *,
    dry_run: bool,
    channel_id: Optional[str] = None,
) -> None:
    event_date = published_at.date()
    event_time = published_at.time()
    if dry_run:
        extra = f", channel_id={channel_id!r}" if channel_id else ""
        logger.info(f"[dry-run] would set {video_id} -> published_at={published_at}{extra}")
        return
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE bronze.bronze_events_youtube
        SET published_at = %s,
            event_date = %s,
            event_time = %s,
            channel_id = COALESCE(
                NULLIF(LEFT(BTRIM(COALESCE(%s::text, '')), 50), ''),
                channel_id
            ),
            last_updated = CURRENT_TIMESTAMP
        WHERE video_id = %s
          AND event_date IS NULL
          AND published_at IS NULL
        """,
        (published_at, event_date, event_time, channel_id, video_id),
    )
    conn.commit()
    cur.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill NULL published_at/event_date on bronze_events_youtube using yt-dlp."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (default: OPEN_NAVIGATOR_DATABASE_URL / NEON_* / DATABASE_URL / local dev)",
    )
    parser.add_argument(
        "--states",
        type=str,
        default=None,
        help="Comma-separated state codes to restrict (e.g. GA,AL)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max videos to process")
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="Base seconds between videos (default 5); actual sleep is base × jitter U(0.5,1.5) × bot-streak factor",
    )
    parser.add_argument(
        "--extract-retries",
        type=int,
        default=3,
        metavar="N",
        help="Per-strategy yt-dlp extract attempts before switching strategy (default 3)",
    )
    parser.add_argument(
        "--strategy-cooloff",
        type=float,
        default=18.0,
        metavar="SEC",
        help="Seconds to pause when switching yt-dlp strategies on the same video (default 18)",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=0.0,
        metavar="SEC",
        help="Sleep this many seconds before the first yt-dlp call (default 0; use e.g. 15 after VPN)",
    )
    parser.add_argument(
        "--skip-android-public-first",
        action="store_true",
        help="Do not try Android-only no-cookie metadata first (use if you know all targets need auth)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log actions only, no DB writes")
    parser.add_argument(
        "--cookies",
        default=os.getenv("YOUTUBE_COOKIES"),
        help="Netscape cookies file (optional; after --cookies-from-browser)",
    )
    parser.add_argument(
        "--cookies-from-browser",
        metavar="SPEC",
        dest="cookies_from_browser",
        default=None,
        help="yt-dlp cookiesfrombrowser, e.g. chrome or firefox,default",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help=(
            "Proxy URL for yt-dlp. If omitted, uses YOUTUBE_HTTPS_PROXY, YOUTUBE_HTTP_PROXY, "
            "HTTPS_PROXY, or HTTP_PROXY when set."
        ),
    )
    args = parser.parse_args()

    states = (
        [s.strip().upper() for s in args.states.split(",") if s.strip()]
        if args.states
        else None
    )
    db_url = args.database_url or _database_url()
    logger.info(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    cfb: Optional[Tuple[str, ...]] = None
    if args.cookies_from_browser and str(args.cookies_from_browser).strip():
        cfb = tuple(p.strip() for p in str(args.cookies_from_browser).split(",") if p.strip())
    cookie_path: Optional[str] = None
    if not cfb:
        raw = (args.cookies or "").strip()
        if raw and Path(raw).is_file():
            cookie_path = str(Path(raw).resolve())
        elif _DEFAULT_COOKIES_FILE.is_file():
            cookie_path = str(_DEFAULT_COOKIES_FILE.resolve())

    proxy = (
        (args.proxy or "").strip()
        or (os.getenv("YOUTUBE_HTTPS_PROXY") or "").strip()
        or (os.getenv("YOUTUBE_HTTP_PROXY") or "").strip()
        or (os.getenv("HTTPS_PROXY") or "").strip()
        or (os.getenv("HTTP_PROXY") or "").strip()
        or None
    )

    base_opts = _build_ytdlp_opts(
        cookiefile=cookie_path,
        cookiesfrombrowser=cfb,
        proxy=proxy,
    )
    used_cookie = bool(cfb or cookie_path)

    variants: List[Tuple[str, Dict[str, Any]]] = []
    if not args.skip_android_public_first:
        variants.append(
            ("android_public_no_cookie", _android_public_metadata_opts(proxy=proxy))
        )
    variants.append(("web_android_ejs_cookie_or_anon", base_opts))
    if used_cookie:
        stripped = _strip_cookie_keys(base_opts)
        variants.append(("web_android_ejs_no_cookie", stripped))

    logger.info(
        f"Throttle: base_sleep={args.sleep}s × jitter U(0.5,1.5) × bot-streak factor; "
        f"extract_retries={args.extract_retries}; strategy_cooloff={args.strategy_cooloff}s; "
        f"strategies={[v[0] for v in variants]}"
    )
    logger.info(
        f"yt-dlp auth: cookiesfrombrowser={cfb!r} cookiefile={cookie_path!r} proxy={'set' if proxy else 'none'}"
    )
    if used_cookie and not _ejs_opts():
        logger.warning(
            "Cookies are set but EJS is disabled or no Node/Deno on PATH — YouTube may block. "
            "Install Node LTS or Deno, or use --cookies-from-browser. "
            "See https://github.com/yt-dlp/yt-dlp/wiki/EJS"
        )

    conn = psycopg2.connect(db_url)
    try:
        ids = _fetch_ids(conn, states=states, limit=args.limit)
        logger.info(f"Found {len(ids)} video_id(s) to backfill")
        if ids and args.startup_delay and float(args.startup_delay) > 0:
            logger.info(
                f"Startup delay: sleeping {float(args.startup_delay):.1f}s before first yt-dlp request"
            )
            time.sleep(float(args.startup_delay))
        ok = 0
        fail = 0
        bot_streak = 0
        for i, vid in enumerate(ids, 1):
            published, err, ytdlp_channel_id = _extract_published_at_variants(
                vid,
                variants,
                extract_retries=max(1, int(args.extract_retries)),
                strategy_cooloff=max(0.0, float(args.strategy_cooloff)),
            )
            if published:
                bot_streak = 0
            else:
                if err and _looks_hard_youtube_block(err):
                    bot_streak += 1
                else:
                    bot_streak = max(0, bot_streak - 1)
            if not published:
                logger.warning(f"[{i}/{len(ids)}] FAIL {vid}: {err or 'no timestamp'}")
                fail += 1
            else:
                _update_row(
                    conn,
                    vid,
                    published,
                    dry_run=args.dry_run,
                    channel_id=ytdlp_channel_id,
                )
                ok += 1
                cid_note = f" channel_id={ytdlp_channel_id}" if ytdlp_channel_id else ""
                logger.info(f"[{i}/{len(ids)}] OK {vid} -> {published.isoformat()}{cid_note}")
            if args.sleep > 0 and i < len(ids):
                jitter = random.uniform(0.5, 1.5)
                mult = 1.0 + min(6, bot_streak) * 0.35
                nap = float(args.sleep) * jitter * mult
                logger.debug(f"Inter-video sleep {nap:.1f}s (bot_streak={bot_streak})")
                time.sleep(nap)
        logger.info(f"Done: updated/skipped dry-run ok={ok}, failed/no_ts={fail}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
