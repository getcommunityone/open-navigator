#!/usr/bin/env python3
"""
Download YouTube Audio from bronze_event_youtube to Google Drive

This script downloads audio-only files from YouTube videos in the ``bronze.bronze_event_youtube``
table (optionally restricted to channels present in ``bronze.bronze_events_channels``) and saves
audio to disk organized by channel and date.

Features:
- Downloads audio in **Opus** (default **64 kbps** voice-oriented encode; override with ``--opus-bitrate``)
- Organizes files by channel → YYYY-MM-DD_title.opus
- yt-dlp writes ``*.part`` / ``*.ytdl`` while downloading; interrupted or failed runs can leave them.
  On download failure, those fragments for that target basename are removed (finished files are
  ``*.opus``). Turn on “File name extensions” in Explorer if ``.opus`` is hidden.
- With **cookies**, yt-dlp needs a **JS runtime** (Node or Deno on ``PATH``) plus remote **EJS**
  (``ejs:github``) so YouTube’s web path can list formats; otherwise you may see “no formats” then a
  no-cookie retry that hits “not a bot”. Set ``YTDLP_NO_EJS=1`` to disable. See the yt-dlp EJS wiki.
- Skips already downloaded files
- Optional **meeting-first** mode: title / ``meeting_type`` heuristics, news-style exclusions,
  ``--years-back`` window (e.g. five years), and join filters on ``bronze_events_channels``
- Works in Google Colab with mounted Drive
- Progress tracking and resumable

Usage (VS Code Extension):
    1. Open this file in VS Code
    2. Press F1 → "Python: Run Python File in Terminal"
       OR right-click → "Run Python File in Terminal"
    3. Or use integrated terminal:
       cd /home/developer/projects/open-navigator
       source .venv/bin/activate
       python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \\
           --limit 50 \\
           --days 30

       Default ``--output-dir`` is ``<repo>/data/cache/youtube_audio``; channel folders use
       lowercase snake_case (e.g. ``ma/city_of_medford_massachusetts_ucxxxxxxxxxxxxxxxx``).

    4. To run with arguments from VS Code tasks (Ctrl+Shift+P → "Tasks: Run Task"):
       Add to .vscode/tasks.json:
       {
           "label": "Download YouTube Audio",
           "type": "shell",
           "command": "${workspaceFolder}/.venv/bin/python",
           "args": [
               "${workspaceFolder}/packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py",
               "--output-dir", "${workspaceFolder}/data/cache/youtube_audio",
               "--limit", "50",
               "--days", "30"
           ],
           "problemMatcher": []
       }

Usage (Google Colab):
    # Mount Google Drive first
    from google.colab import drive
    drive.mount('/content/drive')
    
    # Navigate to project
    %cd /content/drive/MyDrive/CommunityOne/open-navigator
    
    # Run script
    !python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
        --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
        --limit 100 \
        --channels "City of Seattle,City of Portland"

Usage (Local Terminal — meeting-heavy, ~5y window, bronze channel list):
    python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \\
        --bronze-channels-only --government-channel-types-only \\
        --meetings-only --exclude-news --years-back 5 \\
        --not-yet-downloaded --limit 200

Usage (Local Terminal):
    python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \\
        --limit 50
"""

import os
import sys
import argparse
import glob
import re
import shutil
import time
import random
from urllib.parse import urlparse, unquote
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from textwrap import dedent

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv
import yt_dlp

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Default cache root for opus output (``data/`` is gitignored).
DEFAULT_YOUTUBE_AUDIO_OUTPUT_DIR = project_root / "data" / "cache" / "youtube_audio"
# If present, used when ``--cookies`` / ``YOUTUBE_COOKIES`` not set (Netscape format).
DEFAULT_YOUTUBE_COOKIES_FILE = project_root / "youtube_cookies.txt"


def slug_snake_case(text: str, *, max_length: int = 64) -> str:
    """Lowercase snake_case for cache directory names (non-alphanumeric → single ``_``)."""
    if not text:
        return "unknown"
    s = str(text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_length].rstrip("_") or "unknown")


def channel_cache_dir_name(channel_title: str, channel_id: str, *, title_max: int = 56) -> str:
    """Folder name: ``{title_slug}_{channel_id}`` (e.g. ``city_of_medford_massachusetts_ucxxxx...``)."""
    title_slug = slug_snake_case(channel_title or "channel", max_length=title_max)
    id_clean = re.sub(r"[^a-z0-9]", "", (channel_id or "").strip().lower())[:24] or "unknown"
    return f"{title_slug}_{id_clean}"


def cleanup_ytdlp_partial_files(expected_opus_path: Path) -> None:
    """
    Remove yt-dlp incomplete downloads and sidecars for a target ``…/YYYY-MM-DD_title.opus``.

    While downloading, yt-dlp typically writes ``<basename>.<container>.part`` (or similar);
    if extraction stops (error, killed client), those files can remain next to the intended
    ``.opus``. Finished outputs from this script are always ``*.opus``.
    """
    parent = expected_opus_path.parent
    if not parent.is_dir():
        return
    stem = expected_opus_path.stem
    esc = glob.escape(stem)
    for pattern in (f"{esc}*.part", f"{esc}*.ytdl"):
        for p in parent.glob(pattern):
            if not p.is_file():
                continue
            try:
                p.unlink()
                logger.debug(f"  🧹 Removed stale yt-dlp file: {p.name}")
            except OSError as exc:
                logger.debug(f"  🧹 Could not remove {p.name}: {exc}")


def cleanup_ytdlp_extract_audio_leftovers(expected_opus_path: Path) -> None:
    """
    Remove the downloaded **video/container** file left beside ``…``.opus after ``FFmpegExtractAudio``.

    With ``outtmpl`` set to the basename without an extension, yt-dlp often writes a combined
    stream (e.g. MP4) to that basename **with no ``.mp4`` suffix**. yt-dlp normally schedules that
    file for deletion when ``keepvideo`` is false, but removal can still fail; then Explorer shows
    two rows (extensionless + ``.opus``) and the large file looks “stuck.”
    """
    if expected_opus_path.suffix.lower() != ".opus":
        return
    parent = expected_opus_path.parent
    if not parent.is_dir():
        return
    stem = expected_opus_path.stem
    extless = parent / stem
    if extless.is_file():
        try:
            if extless.resolve() != expected_opus_path.resolve():
                extless.unlink()
                logger.debug(f"  🧹 Removed leftover pre-opus container: {extless.name}")
        except OSError as exc:
            logger.warning(
                f"  ⚠️  Could not remove leftover download {extless.name!r} ({exc}). "
                "Close other programs using it or delete manually."
            )
    for ext in (".mp4", ".webm", ".mkv", ".m4a", ".mov", ".flv"):
        p = parent / f"{stem}{ext}"
        if not p.is_file() or p.resolve() == expected_opus_path.resolve():
            continue
        try:
            p.unlink()
            logger.debug(f"  🧹 Removed leftover media: {p.name}")
        except OSError as exc:
            logger.debug(f"  🧹 Could not remove {p.name}: {exc}")


def _yt_dlp_youtube_ejs_opts() -> Dict[str, Any]:
    """
    yt-dlp options so YouTube's web player path can solve ``n`` challenges (real format list).

    With cookies, yt-dlp cannot use the Android client, so formats often need this unless you
    disable cookies entirely. Requires ``node`` or ``deno`` on PATH. Set ``YTDLP_NO_EJS=1`` to
    skip (air-gapped installs). See https://github.com/yt-dlp/yt-dlp/wiki/EJS
    """
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


# Title heuristics: government proceedings (not exhaustive; tune as you see false positives/negatives).
_MEETING_TITLE_SQL = dedent(
    """
    (
        NULLIF(BTRIM(COALESCE(y.meeting_type, '')), '') IS NOT NULL
        OR y.title ILIKE '%council%'
        OR y.title ILIKE '%commission%'
        OR y.title ILIKE '%committee%'
        OR y.title ILIKE '%board of%'
        OR y.title ILIKE '%school board%'
        OR y.title ILIKE '%trustees%'
        OR y.title ILIKE '%supervisors%'
        OR y.title ILIKE '%town hall%'
        OR y.title ILIKE '%public hearing%'
        OR y.title ILIKE '%hearing%'
        OR y.title ILIKE '%work session%'
        OR y.title ILIKE '%workshop%'
        OR y.title ILIKE '%planning and zoning%'
        OR y.title ILIKE '%zoning board%'
        OR y.title ILIKE '%board meeting%'
        OR y.title ILIKE '%town meeting%'
        OR y.title ILIKE '%city council%'
        OR y.title ILIKE '%county board%'
        OR y.title ILIKE '%selectboard%'
        OR y.title ILIKE '%select board%'
        OR y.title ILIKE '%agenda%'
        OR y.title ILIKE '%gavel%'
        OR y.title ILIKE '%minutes%'
    )
    """
).strip()

# Broadcast / general news (exclude from meeting-focused runs).
_NEWS_TITLE_SQL = dedent(
    """
    (
        y.title ILIKE '%breaking news%'
        OR y.title ILIKE '%top stories%'
        OR y.title ILIKE '%morning news%'
        OR y.title ILIKE '%evening news%'
        OR y.title ILIKE '%nightcast%'
        OR y.title ILIKE '%weather %'
        OR y.title ILIKE '%sports center%'
    )
    """
).strip()

_NEWS_CHANNEL_TITLE_SQL = dedent(
    """
    (
        COALESCE(c.channel_title, '') ILIKE '%WAVY%'
        OR COALESCE(c.channel_title, '') ILIKE '% CNN%'
        OR COALESCE(c.channel_title, '') ILIKE 'CNN %'
        OR COALESCE(c.channel_title, '') ILIKE '%Fox News%'
        OR COALESCE(c.channel_title, '') ILIKE '%MSNBC%'
        OR COALESCE(c.channel_title, '') ILIKE '%NBC %'
        OR COALESCE(c.channel_title, '') ILIKE '%ABC News%'
        OR COALESCE(c.channel_title, '') ILIKE '%CBS News%'
        OR COALESCE(c.channel_title, '') ILIKE '% Nexstar%'
    )
    """
).strip()

_MEETING_PRIORITY_SQL = dedent(
    """
    (
        (CASE WHEN y.title ILIKE '%council%' OR y.title ILIKE '%commissioners%' THEN 5 ELSE 0 END)
        + (CASE WHEN y.title ILIKE '%hearing%' OR y.title ILIKE '%public hearing%' THEN 4 ELSE 0 END)
        + (CASE WHEN y.title ILIKE '%school board%' OR y.title ILIKE '%board of education%' THEN 4 ELSE 0 END)
        + (CASE WHEN y.title ILIKE '%committee%' OR y.title ILIKE '%commission %' THEN 3 ELSE 0 END)
        + (CASE WHEN NULLIF(BTRIM(COALESCE(y.meeting_type, '')), '') IS NOT NULL THEN 3 ELSE 0 END)
        + (CASE WHEN y.title ILIKE '%work session%' OR y.title ILIKE '%workshop%' THEN 2 ELSE 0 END)
        + (CASE WHEN y.title ILIKE '%agenda%' THEN 1 ELSE 0 END)
    )
    """
).strip()


def _psycopg2_escape_sql_literal_percents(sql: str) -> str:
    """Double ``%`` in static SQL so ``cursor.execute(query, params)`` does not treat ``ILIKE '%x%'`` as format tokens."""
    return sql.replace("%", "%%")


class YouTubeAudioDownloader:
    """Download YouTube audio files organized by channel and date."""
    
    def __init__(
        self,
        database_url: str,
        output_dir: str,
        limit: Optional[int] = None,
        channels_filter: Optional[List[str]] = None,
        states_filter: Optional[List[str]] = None,
        days_recent: Optional[int] = None,
        skip_existing: bool = True,
        reorganize: bool = False,
        cookies_file: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,
        sleep_between_downloads: float = 2.0,
        *,
        bronze_channels_only: bool = False,
        government_channel_types_only: bool = False,
        meetings_only: bool = False,
        exclude_news_titles: bool = False,
        years_back: Optional[int] = None,
        not_yet_downloaded: bool = False,
        skip_flagged_channels: Optional[bool] = None,
        opus_bitrate_kbps: int = 64,
        allow_null_upload_date: bool = False,
        title_keywords: Optional[List[str]] = None,
        jurisdiction_ids: Optional[List[str]] = None,
    ):
        # Sanitize database URL (fix common issues with Neon/cloud connections)
        self.database_url = self._sanitize_database_url(database_url)
        self._validate_database_url(self.database_url)
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.channels_filter = channels_filter
        self.states_filter = states_filter
        self.days_recent = days_recent
        self.skip_existing = skip_existing
        self.reorganize = reorganize
        self.cookies_file = cookies_file
        self.cookies_from_browser = (cookies_from_browser or "").strip() or None
        self.sleep_between_downloads = sleep_between_downloads
        self.bronze_channels_only = bronze_channels_only
        self.government_channel_types_only = government_channel_types_only
        self.meetings_only = meetings_only
        self.exclude_news_titles = exclude_news_titles
        self.years_back = years_back
        self.allow_null_upload_date = allow_null_upload_date
        self.not_yet_downloaded = not_yet_downloaded
        self.title_keywords = [k.strip() for k in (title_keywords or []) if k and k.strip()]
        self.jurisdiction_ids = [
            j.strip() for j in (jurisdiction_ids or []) if j and j.strip()
        ]
        if skip_flagged_channels is None:
            self.skip_flagged_channels = bool(bronze_channels_only or government_channel_types_only)
        else:
            self.skip_flagged_channels = skip_flagged_channels

        ob = int(opus_bitrate_kbps)
        if ob < 32 or ob > 160:
            raise ValueError(f"opus_bitrate_kbps must be between 32 and 160 (got {ob})")
        self.opus_bitrate_kbps = ob
        
        if self.cookies_from_browser:
            logger.info(
                f"🍪 yt-dlp will use cookiesfrombrowser={self.cookies_from_browser!r} (reads your browser profile)"
            )
        elif self.cookies_file:
            cookie_path = Path(self.cookies_file)
            if cookie_path.exists():
                file_size = cookie_path.stat().st_size
                file_mtime = cookie_path.stat().st_mtime
                from datetime import datetime
                mod_time = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"🍪 Cookies enabled: Using Netscape authentication file")
                logger.info(f"   📁 Path: {cookie_path.resolve()}")
                logger.info(f"   📊 Size: {file_size} bytes")
                logger.info(f"   🕒 Modified: {mod_time}")
                
                # Verify file has content (read first line)
                try:
                    with open(cookie_path, 'r') as f:
                        first_line = f.readline().strip()
                        if first_line:
                            logger.info(f"   ✅ File is readable (first line: {first_line[:50]}...)")
                        else:
                            logger.warning(f"   ⚠️  File is EMPTY - this will cause bot detection errors!")
                except Exception as e:
                    logger.error(f"   ❌ Cannot read file: {e}")
            else:
                logger.warning(f"⚠️  Cookies file not found - downloads may fail due to bot detection")
                logger.warning(f"   Provided path: {self.cookies_file}")
                logger.warning(f"   Absolute path: {Path(self.cookies_file).resolve()}")
                logger.warning(f"   File does NOT exist at this location")
        else:
            logger.info(
                "🔓 No cookies for yt-dlp (no file, no --cookies-from-browser) — "
                "YouTube may demand bot confirmation."
            )
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.reorganized = 0
        self.synced = 0
        self._bronze_youtube_audio_schema_ready = False
        self._warned_ytdlp_no_js_runtime = False

    @staticmethod
    def _sanitize_database_url(url: str) -> str:
        """Sanitize database URL to fix common connection issues."""
        # Strip leading/trailing whitespace from entire URL
        url = url.strip()
        
        # Remove newlines and extra whitespace within the URL
        url = re.sub(r'\s+', ' ', url).replace('\n', '').replace('\r', '')
        
        # Fix channel_binding parameter (common issue with Neon/cloud PostgreSQL)
        # Remove quotes and any whitespace around values
        if 'channel_binding=' in url:
            # First, remove any quotes and whitespace around the value
            url = re.sub(r'channel_binding=\s*["\']?\s*(require|prefer)\s*["\']?\s*', r'channel_binding=prefer', url)
            # Catch any remaining quoted values (with potential whitespace inside)
            url = re.sub(r'channel_binding=\s*["\']([^"\'\&\s]+)\s*["\']', r'channel_binding=\1', url)
        
        # Also fix sslmode if it has quotes or whitespace
        if 'sslmode=' in url:
            url = re.sub(r'sslmode=\s*["\']([^"\'\&\s]+)\s*["\']', r'sslmode=\1', url)
        
        return url

    @staticmethod
    def _ellipsis_placeholder_host(url: str) -> bool:
        """True if hostname is clearly a doc/redaction placeholder (ellipsis), not a real host."""
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        host_decoded = unquote(host)
        if any(c in host_decoded for c in ("\u2026", "\u22ef")):
            return True
        if "%e2%80%a6" in host.lower():
            return True
        if host_decoded.strip(".") in ("…", "..."):
            return True
        return False

    @staticmethod
    def _validate_database_url(url: str) -> None:
        """Fail fast on placeholder hosts (e.g. Unicode …) that cause opaque DNS errors."""
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            raise ValueError(
                "Database URL has no hostname. Set NEON_DATABASE_URL_DEV in .env or pass "
                "--database-url with a full postgresql://USER:PASS@HOST/db URL."
            )
        host_decoded = unquote(host)
        ellipsis_chars = ("\u2026", "\u22ef")  # …, ⋯ (common doc/redaction placeholders)
        if any(c in host_decoded for c in ellipsis_chars):
            raise ValueError(
                "Database hostname contains an ellipsis character (… or ⋯). That is a placeholder, "
                "not a real host—use your Neon host (e.g. ep-xxxxx.region.aws.neon.tech). "
                "Fix NEON_DATABASE_URL_DEV or --database-url."
            )
        if "%e2%80%a6" in host.lower():  # percent-encoded HORIZONTAL ELLIPSIS
            raise ValueError(
                "Database hostname is percent-encoded ellipsis (%E2%80%A6), a placeholder. "
                "Use the real Neon hostname. Fix NEON_DATABASE_URL_DEV or --database-url."
            )
        if host_decoded.strip(".") in ("", "…", "..."):
            raise ValueError(
                "Database hostname is empty or a placeholder. Fix NEON_DATABASE_URL_DEV or --database-url."
            )

    def _ensure_bronze_youtube_audio_columns(self, conn) -> None:
        """Apply migration 006 columns if missing (idempotent). Matches packages/hosting/scripts/neon/migrations/006_add_audio_tracking_fields.sql."""
        if self._bronze_youtube_audio_schema_ready:
            return
        cur = conn.cursor()
        try:
            cur.execute(
                """
                ALTER TABLE bronze.bronze_event_youtube
                ADD COLUMN IF NOT EXISTS audio_downloaded_at TIMESTAMP,
                ADD COLUMN IF NOT EXISTS audio_file_path VARCHAR(500),
                ADD COLUMN IF NOT EXISTS audio_file_size_mb DOUBLE PRECISION
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bronze_youtube_audio_downloaded
                ON bronze.bronze_event_youtube (audio_downloaded_at)
                WHERE audio_downloaded_at IS NOT NULL
                """
            )
        finally:
            cur.close()
        conn.commit()
        self._bronze_youtube_audio_schema_ready = True

    def _connect_to_database(self):
        """Connect to database with helpful error handling."""
        try:
            conn = psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            
            # Provide helpful error messages for common issues
            if 'channel_binding' in error_msg:
                logger.error("❌ Database connection failed: channel_binding error")
                logger.error("This is a common issue with Neon/cloud PostgreSQL connections.")
                logger.error("")
                logger.error("🔧 Fix: Update your connection string to use channel_binding=prefer")
                logger.error("   Or remove the channel_binding parameter entirely.")
                logger.error("")
                logger.error("Example:")
                logger.error("  Before: postgresql://user:pass@host/db?sslmode=require&channel_binding=require")
                logger.error("  After:  postgresql://user:pass@host/db?sslmode=require")
                logger.error("")
            elif 'sslmode' in error_msg:
                logger.error("❌ Database connection failed: SSL error")
                logger.error("Try using sslmode=require or sslmode=prefer")
            elif 'could not translate host name' in error_msg:
                logger.error(f"❌ Database connection failed: {error_msg}")
                logger.error(
                    "If the host looks like “…” (ellipsis), your URL is a placeholder—paste the real "
                    "Neon hostname from the dashboard, or source a .env with NEON_DATABASE_URL_DEV."
                )
            else:
                logger.error(f"❌ Database connection failed: {error_msg}")
            
            raise
        if not self._bronze_youtube_audio_schema_ready:
            try:
                self._ensure_bronze_youtube_audio_columns(conn)
            except psycopg2.Error:
                conn.rollback()
                conn.close()
                logger.error(
                    "Could not ensure audio tracking columns on bronze.bronze_event_youtube. "
                    "If you use a read-only role, apply migration manually: "
                    "packages/hosting/scripts/neon/migrations/006_add_audio_tracking_fields.sql"
                )
                raise
        return conn

    def sanitize_filename(self, text: str, max_length: int = 100) -> str:
        """Sanitize text for use in filename."""
        if not text:
            return "untitled"
        
        # Remove special characters
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Trim and limit length
        text = text.strip()[:max_length]
        
        return text
    
    def get_channel_dir(self, channel_title: str, channel_id: str, state_code: str = None) -> Path:
        """Get or create directory for channel, organized by state (lowercase state + snake_case channel slug)."""
        dir_name = channel_cache_dir_name(channel_title, channel_id)
        if state_code:
            state_slug = slug_snake_case(state_code, max_length=2)
            state_dir = self.output_dir / state_slug
            state_dir.mkdir(parents=True, exist_ok=True)
            channel_dir = state_dir / dir_name
        else:
            channel_dir = self.output_dir / dir_name
        channel_dir.mkdir(parents=True, exist_ok=True)
        return channel_dir
    
    def get_output_filename(self, video: Dict, channel_dir: Path) -> Path:
        """Generate output filename: YYYY-MM-DD_title.opus"""
        # Get date prefix
        if video['event_date']:
            date_str = video['event_date'].strftime('%Y-%m-%d')
        else:
            # Try to extract date from title as fallback
            title = video['title']
            # Match patterns like "5-23-2023", "05-23-2023", "5/23/2023", "2023-05-23"
            date_patterns = [
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2023-05-23 or 2023-5-23
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # 5-23-2023 or 05-23-2023
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 5/23/2023 or 05/23/2023
            ]
            
            date_str = 'unknown-date'
            for pattern in date_patterns:
                match = re.search(pattern, title)
                if match:
                    groups = match.groups()
                    try:
                        # Determine if year is first or last
                        if len(groups[0]) == 4:  # YYYY-MM-DD format
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:  # MM-DD-YYYY or MM/DD/YYYY format
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        # Validate date
                        parsed_date = datetime(year, month, day)
                        date_str = parsed_date.strftime('%Y-%m-%d')
                        logger.debug(f"   📅 Extracted date from title: {date_str}")
                        break
                    except (ValueError, IndexError):
                        continue
            
            if date_str == 'unknown-date':
                logger.warning(f"   ⚠️  No valid date found in database or title: {title[:50]}...")
        
        # Sanitize title
        safe_title = self.sanitize_filename(video['title'], max_length=80)
        
        # Combine: YYYY-MM-DD_title.opus
        filename = f"{date_str}_{safe_title}.opus"
        
        return channel_dir / filename
    
    def get_videos_to_download(self) -> List[Dict]:
        """Query database for videos to download (``bronze_event_youtube``; optional join to ``bronze_events_channels``)."""
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        params: List[Any] = []

        use_channel_join = (
            self.bronze_channels_only
            or self.government_channel_types_only
            or self.exclude_news_titles
            or bool(self.channels_filter)
            or self.skip_flagged_channels
        )
        join_kw = "INNER JOIN" if self.bronze_channels_only else "LEFT JOIN"
        if use_channel_join:
            from_sql = f"""
                bronze.bronze_event_youtube y
                {join_kw} bronze.bronze_events_channels c ON c.channel_id = y.channel_id
            """.strip()
        else:
            from_sql = "bronze.bronze_event_youtube y"

        conditions = ["y.video_url IS NOT NULL"]

        if self.skip_flagged_channels and use_channel_join:
            conditions.append("NOT COALESCE(c.flagged_as_junk, false)")

        if self.government_channel_types_only:
            conditions.append(
                "COALESCE(c.channel_type, y.channel_type, '') IN ('municipal','county','state','school')"
            )

        if self.meetings_only:
            conditions.append(_psycopg2_escape_sql_literal_percents(_MEETING_TITLE_SQL))

        if self.exclude_news_titles:
            conditions.append(f"NOT ({_psycopg2_escape_sql_literal_percents(_NEWS_TITLE_SQL)})")
            conditions.append(f"NOT ({_psycopg2_escape_sql_literal_percents(_NEWS_CHANNEL_TITLE_SQL)})")

        if self.channels_filter:
            or_parts = []
            for ch in self.channels_filter:
                pat = f"%{ch.strip()}%"
                or_parts.append(
                    "(y.jurisdiction_name ILIKE %s OR COALESCE(c.channel_title, '') ILIKE %s OR y.channel_id ILIKE %s)"
                )
                params.extend([pat, pat, pat])
            conditions.append("(" + " OR ".join(or_parts) + ")")

        if self.title_keywords:
            kw_parts = []
            for kw in self.title_keywords:
                kw_parts.append("y.title ILIKE %s")
                params.append(f"%{kw}%")
            conditions.append("(" + " OR ".join(kw_parts) + ")")

        if self.jurisdiction_ids:
            conditions.append("y.jurisdiction_id = ANY(%s)")
            params.append(self.jurisdiction_ids)

        if self.states_filter:
            states_list = "','".join(s.replace("'", "''") for s in self.states_filter)
            conditions.append(f"y.state_code IN ('{states_list}')")

        if self.days_recent:
            conditions.append(f"y.event_date >= CURRENT_DATE - INTERVAL '{int(self.days_recent)} days'")

        if self.years_back is not None and self.years_back > 0:
            date_floor = (
                "COALESCE(y.event_date, (y.published_at AT TIME ZONE 'UTC')::date) >= "
                "(CURRENT_DATE - make_interval(years => %s))"
            )
            params.append(int(self.years_back))
            if self.allow_null_upload_date:
                conditions.append(
                    "(" + date_floor + " OR (y.event_date IS NULL AND y.published_at IS NULL))"
                )
            else:
                conditions.append(date_floor)

        if self.not_yet_downloaded:
            conditions.append("y.audio_downloaded_at IS NULL")

        where_clause = " AND ".join(conditions)

        order_parts = []
        if self.meetings_only:
            order_parts.append(f"{_psycopg2_escape_sql_literal_percents(_MEETING_PRIORITY_SQL)} DESC")
        order_parts.append("COALESCE(y.event_date, (y.published_at AT TIME ZONE 'UTC')::date) DESC NULLS LAST")
        order_parts.append("y.channel_id")
        order_sql = ", ".join(order_parts)

        if use_channel_join:
            channel_title_sql = (
                "COALESCE(NULLIF(BTRIM(c.channel_title), ''), y.jurisdiction_name) AS channel_title"
            )
        else:
            channel_title_sql = "y.jurisdiction_name AS channel_title"

        query = f"""
            SELECT
                y.id,
                y.video_id,
                y.video_url,
                y.title,
                y.event_date,
                y.channel_id,
                y.jurisdiction_name,
                y.state_code,
                {channel_title_sql}
            FROM {from_sql}
            WHERE {where_clause}
            ORDER BY {order_sql}
        """

        if self.limit:
            query += " LIMIT %s"
            params.append(int(self.limit))

        cursor.execute(query, params)
        videos = cursor.fetchall()

        cursor.close()
        conn.close()

        return videos
    
    def download_audio(self, video: Dict, output_path: Path) -> bool:
        """Download audio from YouTube video."""
        try:
            used_cookie_auth = False
            # yt-dlp: prefer **audio-only** streams first (``ba``, then ``worstaudio``). Only if those
            # are unavailable for this video/client do we fall back to ``b`` (best **combined** file,
            # often full video+audio — large download) then ``w``. FFmpegExtractAudio still outputs opus.
            ydl_opts = {
                'format': 'ba/worstaudio/b/w',
                'outtmpl': str(output_path.with_suffix('')),  # Remove extension, yt-dlp will add it
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'opus',
                    'preferredquality': str(self.opus_bitrate_kbps),
                }],
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    },
                },
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # Anti-bot detection measures
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                },
                # Retry on failures
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': False,
                # Do not keep the downloaded MP4/WebM after FFmpegExtractAudio → opus.
                'keepvideo': False,
            }
            ejs_opts = _yt_dlp_youtube_ejs_opts()
            if ejs_opts:
                ydl_opts.update(ejs_opts)
                logger.debug(
                    f"  🧩 yt-dlp YouTube EJS enabled "
                    f"(remote_components=ejs:github, js_runtimes={list(ejs_opts['js_runtimes'].keys())})"
                )

            # Cookies: ``cookiesfrombrowser`` wins over Netscape ``cookiefile`` (yt-dlp).
            if self.cookies_from_browser:
                spec = tuple(p.strip() for p in self.cookies_from_browser.split(",") if p.strip())
                if spec:
                    ydl_opts["cookiesfrombrowser"] = spec
                    used_cookie_auth = True
                    logger.debug(f"  🍪 cookiesfrombrowser={spec!r}")
            elif self.cookies_file:
                cookie_path = Path(self.cookies_file)
                if cookie_path.is_file():
                    ydl_opts["cookiefile"] = str(cookie_path.resolve())
                    used_cookie_auth = True
                    logger.debug(f"  🍪 cookiefile={cookie_path.resolve()}")
                else:
                    logger.debug(f"  🍪 Skipping missing cookie file: {self.cookies_file}")

            if used_cookie_auth and not ejs_opts and not self._warned_ytdlp_no_js_runtime:
                self._warned_ytdlp_no_js_runtime = True
                logger.warning(
                    "  🧩 Cookies are set but no Node/Deno was found on PATH — YouTube may list no "
                    "formats (then a no-cookie retry can hit “not a bot”). Install Node.js LTS or Deno, "
                    "or set YTDLP_NO_EJS=1 to skip remote EJS. https://github.com/yt-dlp/yt-dlp/wiki/EJS"
                )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['video_url']])

            cleanup_ytdlp_extract_audio_leftovers(output_path)
            return True

        except KeyboardInterrupt:
            logger.warning(
                f"  ⚠️  Interrupted (Ctrl+C) during yt-dlp/ffmpeg for {output_path.name!r} — "
                "you may have incomplete .opus, .part, or temp media next to the target path."
            )
            raise

        except Exception as e:
            err = str(e)
            # With any cookies, yt-dlp skips the Android player client; the web/TV path may then
            # expose no progressive/dash formats unless an external JS challenge solver (EJS) is
            # installed — often surfacing as "Requested format is not available" with only
            # storyboards. Public videos usually work again without cookies (Android client).
            if used_cookie_auth and "Requested format is not available" in err:
                logger.warning(
                    "  🍪 No usable formats with cookies (common without EJS when Android client is "
                    "disabled). Retrying once without cookies — "
                    "https://github.com/yt-dlp/yt-dlp/wiki/EJS"
                )
                cleanup_ytdlp_partial_files(output_path)
                try:
                    ydl_opts_retry = {
                        k: v
                        for k, v in ydl_opts.items()
                        if k not in ("cookiefile", "cookiesfrombrowser")
                    }
                    with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl:
                        ydl.download([video["video_url"]])
                    logger.info("  ✓ Download succeeded after retry without cookies")
                    cleanup_ytdlp_extract_audio_leftovers(output_path)
                    return True
                except KeyboardInterrupt:
                    logger.warning(
                        f"  ⚠️  Interrupted (Ctrl+C) during yt-dlp/ffmpeg for {output_path.name!r} — "
                        "you may have incomplete .opus, .part, or temp media next to the target path."
                    )
                    raise
                except Exception as e2:
                    err2 = str(e2)
                    logger.error(f"  ✗ Download failed (after retry without cookies): {e2}")
                    if "Sign in to confirm" in err2 or "not a bot" in err2:
                        logger.error(
                            "  💡 This video needs authenticated extraction; the no-cookie path hit "
                            "a bot wall. Keep cookies and enable EJS (Node or Deno on PATH; script "
                            "passes remote_components=ejs:github unless YTDLP_NO_EJS=1). "
                            "https://github.com/yt-dlp/yt-dlp/wiki/EJS"
                        )
                    cleanup_ytdlp_partial_files(output_path)
                    return False

            logger.error(f"  ✗ Download failed: {e}")
            if "Sign in to confirm" in err or "not a bot" in err:
                logger.error(
                    "  💡 YouTube still blocked the request. If you used a cookies.txt file, export again "
                    "while logged into YouTube in a normal browser, or try "
                    "`--cookies-from-browser chrome` (see yt-dlp wiki: exporting YouTube cookies)."
                )
            cleanup_ytdlp_partial_files(output_path)
            return False
    
    def update_database_download_info(self, video_id: str, file_path: str, file_size_mb: float):
        """Update database with download timestamp and file location."""
        try:
            conn = self._connect_to_database()
            cursor = conn.cursor()
            
            # Update the bronze table with download info
            cursor.execute("""
                UPDATE bronze.bronze_event_youtube
                SET 
                    audio_downloaded_at = CURRENT_TIMESTAMP,
                    audio_file_path = %s,
                    audio_file_size_mb = %s
                WHERE video_id = %s
            """, (file_path, file_size_mb, video_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.warning(f"  ⚠️  Could not update database: {e}")
            # Don't fail the download if DB update fails
    
    def reorganize_existing_files(self):
        """Reorganize existing files from old channel-only structure to state-based structure."""
        logger.info("="*80)
        logger.info("🔄 REORGANIZING EXISTING FILES")
        logger.info("="*80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info("")
        
        # Find all existing .opus files not already in state folders
        old_structure_files = []
        
        for file_path in self.output_dir.rglob('*.opus'):
            # Check if file is in old structure (direct child of channel dir, not state dir)
            # Old: output_dir/ChannelName_ChannelID/file.opus
            # New: output_dir/STATE/ChannelName_ChannelID/file.opus
            
            relative_parts = file_path.relative_to(self.output_dir).parts
            
            # If only 2 parts (channel_dir/file.opus), it's old structure
            # If 3 parts (state/channel_dir/file.opus), it's already organized
            if len(relative_parts) == 2:
                old_structure_files.append(file_path)
        
        if not old_structure_files:
            logger.success("✅ No files to reorganize - all files are already in state-based structure")
            return
        
        logger.info(f"📁 Found {len(old_structure_files)} files in old structure")
        logger.info("")
        
        # Get channel to state mapping from database
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT DISTINCT channel_id, state_code, jurisdiction_name
            FROM bronze.bronze_event_youtube
            WHERE state_code IS NOT NULL
        """)
        
        channel_state_map = {}
        for row in cursor.fetchall():
            channel_state_map[row['channel_id']] = {
                'state_code': row['state_code'],
                'jurisdiction_name': row['jurisdiction_name']
            }
        
        cursor.close()
        conn.close()
        
        logger.info(f"📊 Loaded state info for {len(channel_state_map)} channels")
        logger.info("")
        
        # Reorganize each file
        for old_path in old_structure_files:
            try:
                # Extract channel_id from directory name
                # Format: ChannelName_ChannelID
                channel_dir_name = old_path.parent.name
                
                # Get channel_id (last 8 chars after underscore)
                if '_' not in channel_dir_name:
                    logger.warning(f"⏭️  Skipped (invalid dir format): {channel_dir_name}")
                    continue
                
                channel_id_short = channel_dir_name.split('_')[-1]
                
                # Find matching channel_id in map
                matching_channel = None
                for full_channel_id, info in channel_state_map.items():
                    if full_channel_id.startswith(channel_id_short):
                        matching_channel = full_channel_id
                        state_code = info['state_code']
                        jurisdiction_name = info['jurisdiction_name']
                        break
                
                if not matching_channel:
                    logger.warning(f"⏭️  Skipped (channel not found in DB): {channel_dir_name}")
                    continue
                
                # Create new path with state organization
                new_channel_dir = self.get_channel_dir(
                    jurisdiction_name,
                    matching_channel,
                    state_code
                )
                new_path = new_channel_dir / old_path.name
                
                # Skip if destination already exists
                if new_path.exists():
                    logger.info(f"⏭️  Skipped (already exists): {new_path.relative_to(self.output_dir)}")
                    continue
                
                # Move file
                old_path.rename(new_path)
                
                # Update database with new path
                relative_new_path = str(new_path.relative_to(self.output_dir))
                file_size_mb = new_path.stat().st_size / (1024 * 1024)
                
                # Extract video_id from filename (need to query DB)
                conn = self._connect_to_database()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                cursor.execute("""
                    SELECT video_id
                    FROM bronze.bronze_event_youtube
                    WHERE audio_file_path = %s
                    LIMIT 1
                """, (str(old_path.relative_to(self.output_dir)),))
                
                result = cursor.fetchone()
                if result:
                    video_id = result['video_id']
                    
                    # Update with new path
                    cursor.execute("""
                        UPDATE bronze.bronze_event_youtube
                        SET audio_file_path = %s
                        WHERE video_id = %s
                    """, (relative_new_path, video_id))
                    
                    conn.commit()
                
                cursor.close()
                conn.close()
                
                logger.success(f"✓ Moved: {old_path.name}")
                logger.info(f"  From: {old_path.relative_to(self.output_dir)}")
                logger.info(f"  To:   {new_path.relative_to(self.output_dir)}")
                self.reorganized += 1
                
            except Exception as e:
                logger.error(f"✗ Failed to reorganize {old_path.name}: {e}")
        
        # Clean up empty old directories
        for dir_path in self.output_dir.iterdir():
            if dir_path.is_dir() and len(dir_path.name) == 2:  # Skip state dirs (2-letter codes)
                continue
            
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                logger.info(f"🗑️  Removed empty directory: {dir_path.name}")
        
        logger.info("")
        logger.success("="*80)
        logger.success("REORGANIZATION COMPLETE")
        logger.success("="*80)
        logger.success(f"✓ Reorganized: {self.reorganized:,} files")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
    
    def sync_metadata(self):
        """Sync metadata for existing files that don't have database records."""
        logger.info("="*80)
        logger.info("🔄 SYNCING METADATA FOR EXISTING FILES")
        logger.info("="*80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info("")
        
        # Find all existing .opus files
        all_files = list(self.output_dir.rglob('*.opus'))
        
        if not all_files:
            logger.warning("⚠️  No audio files found in output directory")
            return
        
        logger.info(f"📁 Found {len(all_files)} audio files")
        logger.info("")
        
        # Connect to database
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all videos from database
        cursor.execute("""
            SELECT video_id, channel_id, state_code, jurisdiction_name, title, event_date
            FROM bronze.bronze_event_youtube
        """)
        
        videos = cursor.fetchall()
        videos_by_id = {v['video_id']: v for v in videos}
        
        logger.info(f"📊 Loaded {len(videos)} videos from database")
        logger.info("")
        
        # Process each file
        for file_path in all_files:
            try:
                relative_path = str(file_path.relative_to(self.output_dir))
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                
                # Check if this file already has metadata
                cursor.execute("""
                    SELECT video_id, audio_downloaded_at, audio_file_path
                    FROM bronze.bronze_event_youtube
                    WHERE audio_file_path = %s
                """, (relative_path,))
                
                existing = cursor.fetchone()
                
                if existing and existing['audio_downloaded_at'] is not None:
                    # Already has metadata
                    continue
                
                # Try to match file to video by filename pattern
                # Expected format: YYYY-MM-DD_title.opus
                filename = file_path.stem  # Without .opus extension
                
                # Extract date from filename (YYYY-MM-DD)
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
                if not date_match:
                    logger.warning(f"⏭️  Skipped (no date in filename): {file_path.name}")
                    continue
                
                file_date = date_match.group(1)
                
                # Get state and channel from file path
                # Expected: STATE/Channel_ID/YYYY-MM-DD_title.opus
                parts = file_path.relative_to(self.output_dir).parts
                
                if len(parts) == 3:  # state/channel/file
                    state_code = parts[0].upper()
                    channel_dir = parts[1]
                    channel_id_short = channel_dir.split('_')[-1] if '_' in channel_dir else None
                elif len(parts) == 2:  # channel/file (old structure)
                    channel_dir = parts[0]
                    channel_id_short = channel_dir.split('_')[-1] if '_' in channel_dir else None
                    state_code = None
                else:
                    logger.warning(f"⏭️  Skipped (unexpected path structure): {relative_path}")
                    continue
                
                # Find matching video in database
                matching_video = None
                for video_id, video in videos_by_id.items():
                    # Match by date and channel
                    video_date = str(video['event_date'])
                    video_channel = video['channel_id']
                    
                    if video_date == file_date:
                        # Check if channel matches
                        if channel_id_short and video_channel.startswith(channel_id_short):
                            matching_video = video
                            break
                        # Or match by state if available
                        elif state_code and video.get('state_code') == state_code:
                            # Check if title similarity is high enough
                            video_title_clean = self.sanitize_filename(video['title'])
                            if video_title_clean[:30] in filename or filename[:30] in video_title_clean:
                                matching_video = video
                                break
                
                if not matching_video:
                    logger.warning(f"⏭️  Skipped (no matching video in DB): {file_path.name}")
                    continue
                
                # Update database with metadata
                cursor.execute("""
                    UPDATE bronze.bronze_event_youtube
                    SET 
                        audio_downloaded_at = CURRENT_TIMESTAMP,
                        audio_file_path = %s,
                        audio_file_size_mb = %s
                    WHERE video_id = %s
                """, (relative_path, file_size_mb, matching_video['video_id']))
                
                conn.commit()
                
                logger.success(f"✓ Synced: {file_path.name}")
                logger.info(f"  Path: {relative_path}")
                logger.info(f"  Video ID: {matching_video['video_id']}")
                logger.info(f"  Size: {file_size_mb:.1f} MB")
                self.synced += 1
                
            except Exception as e:
                logger.error(f"✗ Failed to sync {file_path.name}: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info("")
        logger.success("="*80)
        logger.success("METADATA SYNC COMPLETE")
        logger.success("="*80)
        logger.success(f"✓ Synced: {self.synced:,} files")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
    
    def run(self):
        """Run the download process."""
        logger.info("=" * 80)
        logger.info("YOUTUBE AUDIO DOWNLOADER")
        logger.info("=" * 80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Database: {self.database_url.split('@')[1] if '@' in self.database_url else 'localhost'}")
        
        # How yt-dlp will authenticate to YouTube (see startup logs in main() too)
        if self.cookies_from_browser:
            spec = tuple(p.strip() for p in self.cookies_from_browser.split(",") if p.strip())
            logger.info(f"🍪 yt-dlp cookiesfrombrowser {spec!r} (live browser profile)")
        elif self.cookies_file:
            if Path(self.cookies_file).is_file():
                logger.info(f"🍪 yt-dlp Netscape cookiefile: {Path(self.cookies_file).resolve()}")
            else:
                logger.warning(
                    f"🍪 --cookies path is not a readable file ({self.cookies_file!r}); continuing without cookies. "
                    "Export Netscape format from the browser (see packages/scrapers/src/scrapers/youtube/BYPASS_IP_BLOCK.md)."
                )
        else:
            logger.warning(
                "🍪 No cookies configured — YouTube may demand bot confirmation. "
                f"Add {DEFAULT_YOUTUBE_COOKIES_FILE.name} at repo root, set YOUTUBE_COOKIES, pass --cookies, "
                "or use --cookies-from-browser chrome."
            )

        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            logger.error(
                "ffmpeg and ffprobe must be on PATH (required for opus extraction). "
                "WSL/Ubuntu/Debian: sudo apt update && sudo apt install -y ffmpeg"
            )
            sys.exit(3)

        if self.limit:
            logger.info(f"Limit: {self.limit} videos")
        if self.channels_filter:
            logger.info(f"Channels filter: {', '.join(self.channels_filter)}")
        if self.states_filter:
            logger.info(f"States filter: {', '.join(self.states_filter)}")
        if self.days_recent:
            logger.info(f"Days recent (event_date): {self.days_recent}")
        if self.years_back:
            logger.info(f"Years back (event_date or published_at): {self.years_back}")
        if self.allow_null_upload_date and self.years_back:
            logger.info(
                "Date window: including rows with NULL event_date and NULL published_at "
                "(--allow-null-upload-date)"
            )
        if self.bronze_channels_only:
            logger.info("Channel scope: INNER JOIN bronze.bronze_events_channels only")
        if self.government_channel_types_only:
            logger.info("Channel scope: municipal / county / state / school types only")
        if self.meetings_only:
            logger.info("Video scope: meeting-like titles (council, hearing, board, …) or meeting_type set")
        if self.exclude_news_titles:
            logger.info("Excluding TV-style news titles and known broadcast channel names")
        if self.not_yet_downloaded:
            logger.info("Only rows with audio_downloaded_at IS NULL")
        if self.title_keywords:
            logger.info("Title keywords (any match): {}", ", ".join(self.title_keywords))
        if self.jurisdiction_ids:
            logger.info("Jurisdiction IDs: {}", ", ".join(self.jurisdiction_ids))
        if self.skip_flagged_channels and (self.bronze_channels_only or self.government_channel_types_only):
            logger.info("Skipping channels flagged_as_junk in bronze_events_channels")
        
        logger.info("")
        
        # Get videos to download
        logger.info("📊 Querying database for videos...")
        videos = self.get_videos_to_download()
        logger.info(f"Found {len(videos):,} videos to process")
        logger.info("")
        
        if not videos:
            logger.warning("No videos found matching criteria")
            return
        
        # Group by channel for organization
        videos_by_channel = {}
        for video in videos:
            channel_id = video['channel_id']
            if channel_id not in videos_by_channel:
                videos_by_channel[channel_id] = {
                    'videos': [],
                    'channel_title': video.get('channel_title') or video.get('jurisdiction_name') or 'Unknown',
                }
            videos_by_channel[channel_id]['videos'].append(video)
        
        logger.info(f"📁 Organized into {len(videos_by_channel)} channels")
        logger.info("")
        
        interrupted = False
        # Download videos
        try:
            for channel_id, channel_data in videos_by_channel.items():
                if interrupted:
                    break
                channel_title = channel_data['channel_title']
                channel_videos = channel_data['videos']
                
                # Get state from first video (all in same channel should have same state)
                state_code = channel_videos[0].get('state_code') if channel_videos else None
                
                logger.info(f"📺 Channel: {channel_title} ({len(channel_videos)} videos)")
                
                # Create channel directory (organized by state)
                channel_dir = self.get_channel_dir(channel_title, channel_id, state_code)
                logger.info(f"   Directory: {channel_dir}")
                
                # Download each video
                for i, video in enumerate(channel_videos, 1):
                    output_path = self.get_output_filename(video, channel_dir)
                    
                    # Check if already exists
                    if self.skip_existing and output_path.exists():
                        logger.info(f"   [{i}/{len(channel_videos)}] ⏭️  Skipped (exists): {output_path.name}")
                        self.skipped += 1
                        continue
                    
                    logger.info(f"   [{i}/{len(channel_videos)}] ⬇️  Downloading: {video['title'][:60]}...")
                    
                    try:
                        success = self.download_audio(video, output_path)
                    except KeyboardInterrupt:
                        interrupted = True
                        logger.warning("⚠️  Batch download stopped by user (Ctrl+C).")
                        break
                    
                    if success:
                        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                        logger.success(f"   ✓ Downloaded: {output_path.name} ({file_size:.1f} MB)")
                        self.downloaded += 1
                        
                        # Update database with download info
                        relative_path = str(output_path.relative_to(self.output_dir))
                        self.update_database_download_info(video['video_id'], relative_path, file_size)
                        
                        # Throttle to avoid rate limiting (add random jitter to look more human)
                        if self.sleep_between_downloads > 0 and i < len(channel_videos):
                            jitter = random.uniform(0.5, 1.5)  # ±50% random variance
                            sleep_time = self.sleep_between_downloads * jitter
                            logger.debug(f"   😴 Sleeping {sleep_time:.1f}s to avoid rate limiting...")
                            try:
                                time.sleep(sleep_time)
                            except KeyboardInterrupt:
                                interrupted = True
                                logger.warning("⚠️  Batch download stopped by user (Ctrl+C) during throttle sleep.")
                                break
                    else:
                        logger.error(f"   ✗ Failed: {video['title'][:60]}")
                        self.failed += 1
                
                logger.info("")
                if interrupted:
                    break
        except KeyboardInterrupt:
            interrupted = True
            logger.warning("⚠️  Batch download stopped by user (Ctrl+C).")
        
        # Summary
        logger.success("=" * 80)
        logger.success("DOWNLOAD STOPPED (Ctrl+C)" if interrupted else "DOWNLOAD COMPLETE")
        logger.success("=" * 80)
        logger.success(f"✓ Downloaded: {self.downloaded:,}")
        logger.success(f"⏭️  Skipped (existing): {self.skipped:,}")
        logger.success(f"✗ Failed: {self.failed:,}")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
        
        # List channel directories (STATE/Channel/ structure)
        channel_dirs = sorted([
            d for d in self.output_dir.rglob('*')
            if d.is_dir() and d.parent != self.output_dir and d.parent.parent == self.output_dir
        ])
        # Fall back to top-level dirs if no nested structure found
        if not channel_dirs:
            channel_dirs = sorted([d for d in self.output_dir.iterdir() if d.is_dir()])
        if channel_dirs:
            logger.info(f"📂 Channel directories ({len(channel_dirs)} total):")
            for d in channel_dirs:
                file_count = len(list(d.glob('*.opus')))
                state = d.parent.name if d.parent != self.output_dir else ''
                label = f"{state}/{d.name}" if state else d.name
                logger.info(f"   • {label} ({file_count} files)")

        if interrupted:
            sys.exit(130)


# Used when NEON_DATABASE_URL_DEV is unset or contains a doc-style ellipsis hostname.
_LOCAL_DEV_DATABASE_URL = "postgresql://postgres:password@localhost:5433/open_navigator"


def _explicit_database_url_on_cli(argv: List[str]) -> bool:
    for arg in argv:
        if arg == "--database-url" or arg.startswith("--database-url="):
            return True
    return False


def main():
    """Main entry point."""
    # Load .env here (CLI entrypoint) rather than at import time: importing this
    # module as a library must not mutate os.environ for unrelated callers/tests.
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Download YouTube audio from bronze_event_youtube to Google Drive"
    )
    
    parser.add_argument(
        '--output-dir',
        default=str(DEFAULT_YOUTUBE_AUDIO_OUTPUT_DIR),
        help=f'Output directory for .opus files (default: {DEFAULT_YOUTUBE_AUDIO_OUTPUT_DIR})',
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of videos to download'
    )
    
    parser.add_argument(
        '--channels',
        help='Comma-separated list of channel names to filter (partial match)'
    )

    parser.add_argument(
        '--title-keywords',
        help='Comma-separated substrings; title must match at least one (e.g. committee,meeting)',
    )

    parser.add_argument(
        '--jurisdiction-id',
        action='append',
        dest='jurisdiction_ids',
        default=[],
        help='Restrict to jurisdiction_id (repeatable or comma-separated in one value)',
    )
    
    parser.add_argument(
        '--states',
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Only download videos whose event_date is in the last N days',
    )

    parser.add_argument(
        '--bronze-channels-only',
        action='store_true',
        help='Restrict to channel_id rows present in bronze.bronze_events_channels (INNER JOIN)',
    )
    parser.add_argument(
        '--government-channel-types-only',
        action='store_true',
        help='Only municipal, county, state, or school channel_type (uses joined bronze_events_channels when available)',
    )
    parser.add_argument(
        '--meetings-only',
        action='store_true',
        help='Only videos whose title/meeting_type looks like a government meeting (council, hearing, board, …)',
    )
    parser.add_argument(
        '--exclude-news',
        action='store_true',
        help='Exclude TV-style news video titles and common broadcast channel name patterns (joins bronze_events_channels)',
    )
    parser.add_argument(
        '--years-back',
        type=int,
        metavar='N',
        help='Only videos on or after (today − N calendar years) using event_date or published_at',
    )
    parser.add_argument(
        '--allow-null-upload-date',
        action='store_true',
        help=(
            'With --years-back, also include rows where both event_date and published_at are NULL '
            '(otherwise the date predicate is unknown and those rows are excluded). '
            'Prefer fixing bronze via load_youtube_events_to_postgres refresh; this is a safety valve.'
        ),
    )
    parser.add_argument(
        '--not-yet-downloaded',
        action='store_true',
        help='Only rows where audio_downloaded_at IS NULL',
    )
    parser.add_argument(
        '--include-flagged-channels',
        action='store_true',
        help='Include channels flagged_as_junk in bronze_events_channels (default: skip when using government/bronze filters)',
    )
    
    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Re-download files even if they already exist'
    )
    
    parser.add_argument(
        '--reorganize',
        action='store_true',
        help='Reorganize existing files from old channel-only structure to new state-based structure'
    )
    
    parser.add_argument(
        '--sync-metadata',
        action='store_true',
        help='Sync metadata for existing files that are missing database records'
    )
    
    parser.add_argument(
        '--database-url',
        default=None,
        help=(
            'PostgreSQL URL (default: NEON_DATABASE_URL_DEV from .env, else localhost:5433 dev URL). '
            'If the env value uses an ellipsis placeholder host, it is ignored unless this flag is set explicitly.'
        ),
    )
    
    parser.add_argument(
        '--cookies',
        default=os.getenv("YOUTUBE_COOKIES") or None,
        help=(
            'Netscape cookies.txt path for yt-dlp. Env YOUTUBE_COOKIES; if unset and '
            f'{DEFAULT_YOUTUBE_COOKIES_FILE.name} exists at repo root, it is used automatically.'
        ),
    )

    parser.add_argument(
        '--cookies-from-browser',
        metavar='SPEC',
        dest='cookies_from_browser',
        default=None,
        help=(
            'yt-dlp cookiesfrombrowser, e.g. chrome or firefox,default (overrides --cookies). '
            'Use when an exported cookies.txt still gets "Sign in to confirm you are not a bot".'
        ),
    )

    parser.add_argument(
        '--sleep',
        type=float,
        default=2.0,
        help='Seconds to sleep between downloads (default: 2.0, with random jitter). Set to 0 to disable throttling.'
    )

    parser.add_argument(
        '--opus-bitrate',
        type=int,
        default=64,
        metavar='KBPS',
        dest='opus_bitrate',
        help=(
            'Target Opus bitrate in kbps for FFmpegExtractAudio (default: 64, typical “voice” tier). '
            'Range 32–160.'
        ),
    )
    
    args = parser.parse_args()

    if getattr(args, "cookies", None) == "":
        args.cookies = None

    # Defensive: ``--cookies-from-browser`` → ``cookies_from_browser``; tolerate missing dest.
    _cfb = getattr(args, "cookies_from_browser", None)
    if isinstance(_cfb, str) and _cfb.strip():
        args.cookies_from_browser = _cfb.strip()
    else:
        args.cookies_from_browser = None

    if not args.cookies_from_browser and not args.cookies and DEFAULT_YOUTUBE_COOKIES_FILE.is_file():
        args.cookies = str(DEFAULT_YOUTUBE_COOKIES_FILE.resolve())

    explicit_db_url = _explicit_database_url_on_cli(sys.argv)
    if args.database_url is None:
        args.database_url = os.getenv("NEON_DATABASE_URL_DEV") or _LOCAL_DEV_DATABASE_URL
    sanitized_for_check = YouTubeAudioDownloader._sanitize_database_url(args.database_url)
    if YouTubeAudioDownloader._ellipsis_placeholder_host(sanitized_for_check) and not explicit_db_url:
        logger.warning(
            "NEON_DATABASE_URL_DEV looks like a placeholder (ellipsis in hostname). "
            f"Using local dev database instead: {_LOCAL_DEV_DATABASE_URL.split('@', 1)[-1]}"
        )
        args.database_url = _LOCAL_DEV_DATABASE_URL

    # File logger: one rotating log per output directory, kept for 7 days
    log_dir = Path(args.output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "download_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # new file each day
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    # Show startup configuration for debugging
    logger.info("=" * 80)
    logger.info("🚀 YouTube Audio Downloader - Startup Configuration")
    logger.info("=" * 80)
    logger.info(f"📁 Output directory: {args.output_dir}")
    logger.info(f"🎯 Limit: {args.limit if args.limit else 'No limit'}")
    logger.info(f"📺 Channels filter: {args.channels if args.channels else 'All channels'}")
    logger.info(f"🗺️  States filter: {args.states if args.states else 'All states'}")
    logger.info(f"📅 Days recent: {args.days if args.days else 'All time'}")
    logger.info(f"📅 Years back: {args.years_back if args.years_back else 'All time'}")
    logger.info(f"📅 Allow null upload date (with years-back): {args.allow_null_upload_date}")
    logger.info(f"🎯 Bronze channels only: {args.bronze_channels_only}")
    logger.info(f"🏛️  Government channel types only: {args.government_channel_types_only}")
    logger.info(f"🎥 Meetings-only heuristic: {args.meetings_only}")
    logger.info(f"📺 Exclude news patterns: {args.exclude_news}")
    logger.info(f"💾 Not yet downloaded: {args.not_yet_downloaded}")
    logger.info(f"⏭️  Skip existing: {not args.no_skip_existing}")
    logger.info(f"📂 Reorganize mode: {args.reorganize}")
    logger.info(f"🔄 Sync metadata mode: {args.sync_metadata}")
    logger.info(f"🎚️  Opus bitrate: {args.opus_bitrate} kbps (FFmpegExtractAudio)")
    
    # Check cookies / browser auth for yt-dlp
    if args.cookies_from_browser:
        logger.info(f"🍪 Cookies-from-browser: {args.cookies_from_browser!r} (yt-dlp will read the browser profile)")
    elif args.cookies:
        cookie_path = Path(args.cookies)
        if cookie_path.is_file():
            file_size = cookie_path.stat().st_size
            logger.info(f"🍪 Netscape cookie file for yt-dlp: {cookie_path.resolve()} ({file_size} bytes)")
        else:
            logger.warning(f"🍪 Cookie path is not a file: {args.cookies!r}")
    else:
        logger.warning(
            "🍪 No cookies — export youtube_cookies.txt to repo root, set YOUTUBE_COOKIES, "
            "pass --cookies, or use --cookies-from-browser chrome."
        )
    
    logger.info(
        f"⏱️  Throttling: {args.sleep}s between downloads (with random jitter)"
        if args.sleep > 0
        else "⚡ Throttling: DISABLED (may trigger rate limiting)"
    )
    _db_log = args.database_url[:50] + "..." if len(args.database_url) > 50 else args.database_url
    logger.info(f"🗄️  Database: {_db_log}")
    logger.info("=" * 80)
    
    # Parse filters
    channels_filter = args.channels.split(',') if args.channels else None
    states_filter = args.states.split(',') if args.states else None
    title_keywords = (
        [k.strip() for k in args.title_keywords.split(',') if k.strip()]
        if args.title_keywords
        else None
    )
    jurisdiction_ids: List[str] = []
    for raw in args.jurisdiction_ids or []:
        jurisdiction_ids.extend(k.strip() for k in raw.split(',') if k.strip())

    if args.include_flagged_channels:
        skip_flagged_channels = False
    elif args.bronze_channels_only or args.government_channel_types_only:
        skip_flagged_channels = True
    else:
        skip_flagged_channels = False

    # Create downloader
    try:
        downloader = YouTubeAudioDownloader(
            database_url=args.database_url,
            output_dir=args.output_dir,
            limit=args.limit,
            channels_filter=channels_filter,
            states_filter=states_filter,
            days_recent=args.days,
            skip_existing=not args.no_skip_existing,
            reorganize=args.reorganize,
            cookies_file=args.cookies,
            cookies_from_browser=args.cookies_from_browser,
            sleep_between_downloads=args.sleep,
            bronze_channels_only=args.bronze_channels_only,
            government_channel_types_only=args.government_channel_types_only,
            meetings_only=args.meetings_only,
            exclude_news_titles=args.exclude_news,
            years_back=args.years_back,
            allow_null_upload_date=args.allow_null_upload_date,
            not_yet_downloaded=args.not_yet_downloaded,
            skip_flagged_channels=skip_flagged_channels,
            opus_bitrate_kbps=args.opus_bitrate,
            title_keywords=title_keywords,
            jurisdiction_ids=jurisdiction_ids or None,
        )
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(2)
    
    # Run reorganization if requested
    if args.reorganize:
        downloader.reorganize_existing_files()
    elif args.sync_metadata:
        downloader.sync_metadata()
    else:
        # Run normal download
        downloader.run()


if __name__ == '__main__':
    main()
