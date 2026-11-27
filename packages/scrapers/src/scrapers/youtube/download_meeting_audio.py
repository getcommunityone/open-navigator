"""Download meeting audio (Opus) and store it on OneDrive, a mounted Drive folder, or local disk.

Issue #1255. Owner decision on the YouTube source and the constraints we keep:
``web_docs/docs/development/meeting-audio-source-decision.md``.

Hard rule (owner, 2026-11-27): **never re-download audio we already hold.** Every run first builds
an inventory keyed by YouTube ``video_id`` from

* the target folder (``rclone lsf -R`` of the whole OneDrive tree, any audio extension),
* the bronze tracking columns (``audio_downloaded_at`` / ``audio_file_path``),
* local audio folders the older downloaders used (default ``data/cache/youtube_audio``; read only,
  nothing under ``data/cache`` is ever deleted).

A file counts as held when its name contains the ``video_id`` (any date/title format), when it is the
legacy ``YYYY-MM-DD_<title>.<ext>`` name for that video, or when the tracking column points at it.
Held on the target → skip. Held only locally → upload that file (the original stays). Held only in the
tracking column with no file found → skip and report it. What was found is saved to
``bronze.bronze_meeting_audio_inventory`` (one row per video_id and location) so later runs can see it.

Then, for each video left, one at a time: download audio-only Opus with yt-dlp into a temp dir on the
WSL disk, upload it (``rclone copyto``), check the remote size, delete the temp copy, stamp the
tracking columns, and sleep. A 403, a 429 or a YouTube bot check doubles the pause; ``--max-blocks``
of them in a row stop the run (exit code 3) instead of retrying harder. No proxies and no custom user
agent; the repo's existing cookies file is used if present. YouTube is reached only through the VPN
(``vpn_guard``, #488).

Examples::

    python -m scrapers.youtube.download_meeting_audio --data-centers-2026 --dry-run
    python -m scrapers.youtube.download_meeting_audio --data-centers-2026 --target onedrive --limit 3
    python -m scrapers.youtube.download_meeting_audio --scope data-centers --year 2026 \\
        --target local --output-dir /tmp/audio --limit 5
"""

from __future__ import annotations

import argparse
import functools
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

#: yt-dlp copies YouTube's Opus stream as-is (often ~120 kbps, itag 251), so a file above
#: ``kbps * TRANSCODE_SLACK`` is re-encoded locally with ffmpeg (libopus, voip) before upload.
DEFAULT_OPUS_KBPS = 64
TRANSCODE_SLACK = 1.25
AUDIO_FORMAT = "ba[acodec=opus][abr<=80]/wa[acodec=opus]/ba[abr<=96]/wa"
#: Average length used for videos with no ``duration_minutes`` when estimating.
FALLBACK_MINUTES = 100
DEFAULT_REMOTE = "onedrive"
#: Parent folder on the remote; each source gets its own sibling folder under it (owner, 2026-11-27).
DEFAULT_COMMUNITY_ROOT = "CommunityOne"
SOURCE_FOLDERS: dict[str, str] = {
    "youtube": "youtube_audio",
    "suiteone": "suiteone_audio",
    "granicus": "granicus_audio",
}
AUDIO_EXTENSIONS = (".opus", ".m4a", ".mp3", ".webm", ".ogg", ".wav", ".aac", ".flac")
EXIT_BLOCKED = 3

_BLOCK_MARKERS = (
    "http error 403",
    "http error 429",
    "too many requests",
    "sign in to confirm",
    "not a bot",
    "403: forbidden",
)


def repo_root() -> Path:
    """The checkout root (the directory holding ``AGENTS.md``)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    return Path.cwd()


def default_local_dirs() -> list[Path]:
    """Folders older downloaders wrote to (``download_audio_to_drive`` default cache)."""
    return [repo_root() / "data" / "cache" / "youtube_audio"]


def is_block_error(message: str) -> bool:
    """True when a yt-dlp error means YouTube refused us (403, 429 or a bot check)."""
    low = (message or "").lower()
    return any(marker in low for marker in _BLOCK_MARKERS)


def is_audio_file(name: str) -> bool:
    return name.lower().endswith(AUDIO_EXTENSIONS)


def sanitize_title(text: str | None, max_length: int = 80) -> str:
    """Same rules as the legacy Drive downloader, so legacy filenames can be matched."""
    if not text:
        return "untitled"
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:max_length]


def channel_folder(row: dict[str, Any]) -> str:
    """Legacy layout folder: ``<state>/<channel_slug>_<channel_id>`` (see ``channel_cache_dir_name``)."""
    from core_lib.text import slug_snake_case

    title = row.get("channel_title") or row.get("jurisdiction_name") or "channel"
    title_slug = slug_snake_case(title, max_length=56)
    id_clean = (
        re.sub(r"[^a-z0-9]", "", (row.get("channel_id") or "").strip().lower())[:24]
        or "unknown"
    )
    state = (row.get("state_code") or "").strip().lower()[:2]
    leaf = f"{title_slug}_{id_clean}"
    return f"{state}/{leaf}" if state else leaf


def _channel_id_suffix(row: dict[str, Any]) -> str:
    """``_<channel id, lower, alnum, 24 chars>``: how a legacy channel folder name ends."""
    id_clean = re.sub(r"[^a-z0-9]", "", (row.get("channel_id") or "").strip().lower())[
        :24
    ]
    return f"_{id_clean}" if id_clean else ""


def _date_str(row: dict[str, Any]) -> str:
    d = row.get("meeting_date")
    return d.strftime("%Y-%m-%d") if isinstance(d, date) else "unknown-date"


def legacy_stem(row: dict[str, Any]) -> str:
    """``YYYY-MM-DD_<title>`` as the old downloader named files (no video_id, no extension)."""
    return f"{_date_str(row)}_{sanitize_title(row.get('title'))}"


def target_relpath(row: dict[str, Any]) -> str:
    """New files keep the legacy folder layout and add the id: ``…/YYYY-MM-DD_<title> [<id>].opus``."""
    title = sanitize_title(row.get("title"), max_length=70)
    return f"{channel_folder(row)}/{_date_str(row)}_{title} [{row['video_id']}].opus"


def scope_sql(scope: str) -> str:
    """SQL for the videos in scope; one row per video_id. ``%(start)s``/``%(end)s`` are bound."""
    if scope != "data-centers":
        raise ValueError(f"unknown scope {scope!r}")
    return """
        WITH s AS (
            SELECT video_id, min(meeting_date) AS meeting_date
            FROM (
                SELECT video_id, meeting_date FROM public.data_center_meeting_mention
                WHERE meeting_date >= %(start)s AND meeting_date < %(end)s
                UNION ALL
                SELECT video_id, meeting_date FROM public.data_center_meeting_lean
                WHERE meeting_date >= %(start)s AND meeting_date < %(end)s
            ) u
            GROUP BY video_id
        ),
        y0 AS (
            SELECT DISTINCT ON (video_id)
                video_id, video_url, title, event_date, channel_id, jurisdiction_name, state_code
            FROM bronze.bronze_event_youtube
            WHERE video_id IN (SELECT video_id FROM s)
            ORDER BY video_id, duration_minutes DESC NULLS LAST
        ),
        -- Tracking can sit on any duplicate row for a video_id: aggregate, never pick one row.
        t AS (
            SELECT
                video_id,
                max(duration_minutes) AS duration_minutes,
                max(audio_downloaded_at) AS audio_downloaded_at,
                (array_agg(audio_file_path ORDER BY audio_downloaded_at DESC NULLS LAST)
                    FILTER (WHERE audio_file_path IS NOT NULL))[1] AS audio_file_path
            FROM bronze.bronze_event_youtube
            WHERE video_id IN (SELECT video_id FROM s)
            GROUP BY video_id
        ),
        y AS (SELECT * FROM y0 JOIN t USING (video_id))
        SELECT
            s.video_id,
            COALESCE(y.video_url, 'https://www.youtube.com/watch?v=' || s.video_id) AS video_url,
            y.title,
            s.meeting_date,
            y.event_date,
            y.channel_id,
            y.jurisdiction_name,
            y.state_code,
            COALESCE(NULLIF(BTRIM(c.channel_title), ''), y.jurisdiction_name) AS channel_title,
            y.duration_minutes,
            y.audio_file_path,
            y.audio_downloaded_at
        FROM s
        LEFT JOIN y USING (video_id)
        LEFT JOIN public.meeting_video_kind k USING (video_id)
        LEFT JOIN LATERAL (
            SELECT channel_title FROM bronze.bronze_events_channels ch
            WHERE ch.channel_id = y.channel_id LIMIT 1
        ) c ON true
        WHERE COALESCE(k.is_public_meeting, true)
        ORDER BY s.meeting_date, s.video_id
    """


def estimate(
    rows: Iterable[dict[str, Any]], kbps: int = DEFAULT_OPUS_KBPS
) -> dict[str, float]:
    """Count, hours (known + estimated from the average) and GB at ``kbps``."""
    rows = list(rows)
    known = [r["duration_minutes"] for r in rows if r.get("duration_minutes")]
    unknown = len(rows) - len(known)
    avg = (sum(known) / len(known)) if known else FALLBACK_MINUTES
    hours = (sum(known) + unknown * avg) / 60.0
    gb = hours * 3600 * kbps * 1000 / 8 / 1e9
    return {
        "videos": len(rows),
        "with_duration": len(known),
        "avg_minutes": round(avg, 1),
        "hours": round(hours, 1),
        "gb": round(gb, 1),
    }


# ---------------------------------------------------------------- targets


class Target(Protocol):
    """Where audio is stored. ``listing`` maps relpath -> bytes (audio files only)."""

    kind: str

    def listing(self) -> dict[str, int]: ...
    def put(self, local: Path, relpath: str, *, move: bool) -> int: ...
    def remove(self, relpath: str) -> None: ...
    def display(self, relpath: str) -> str: ...


@dataclass
class OneDriveTarget:
    """An rclone remote (the owner's personal OneDrive) under ``<remote>:<root>``."""

    remote: str = DEFAULT_REMOTE
    root: str = f"{DEFAULT_COMMUNITY_ROOT}/{SOURCE_FOLDERS['youtube']}"
    rclone: str = "rclone"
    kind: str = "onedrive"

    def _path(self, relpath: str = "") -> str:
        base = f"{self.remote}:{self.root.strip('/')}"
        return f"{base}/{relpath}" if relpath else base

    def configured(self) -> bool:
        out = subprocess.run(
            [self.rclone, "listremotes"], capture_output=True, text=True, check=False
        )
        return f"{self.remote}:" in out.stdout.split()

    def listing(self) -> dict[str, int]:
        proc = subprocess.run(
            [
                self.rclone,
                "lsf",
                "-R",
                "--files-only",
                "--format",
                "sp",
                "--separator",
                "\t",
                self._path(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            if "directory not found" in proc.stderr.lower():
                return {}
            raise RuntimeError(f"rclone lsf failed: {proc.stderr.strip()}")
        files: dict[str, int] = {}
        for line in proc.stdout.splitlines():
            size, _, path = line.partition("\t")
            if path and is_audio_file(path):
                files[path] = int(size)
        return files

    def _rclone(self, *argv: str) -> str:
        proc = subprocess.run(
            [self.rclone, *argv], capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            raise RuntimeError(f"rclone {argv[0]} failed: {proc.stderr.strip()[:500]}")
        return proc.stdout

    def put(self, local: Path, relpath: str, *, move: bool) -> int:
        dest = self._path(relpath)
        self._rclone("copyto", str(local), dest)
        return int(self._rclone("lsf", "--format", "s", dest).strip() or 0)

    def remove(self, relpath: str) -> None:
        self._rclone("deletefile", self._path(relpath))

    def display(self, relpath: str) -> str:
        return self._path(relpath)


@dataclass
class LocalTarget:
    """A folder on disk (``--target local``) or a mounted Google Drive folder (``--target drive``)."""

    output_dir: Path
    kind: str = "local"

    def listing(self) -> dict[str, int]:
        return list_local_audio(self.output_dir)

    def put(self, local: Path, relpath: str, *, move: bool) -> int:
        dest = self.output_dir / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(local), dest)
        else:
            shutil.copy2(local, dest)
        return dest.stat().st_size

    def remove(self, relpath: str) -> None:
        (self.output_dir / relpath).unlink(missing_ok=True)

    def display(self, relpath: str) -> str:
        return str(self.output_dir / relpath)


def list_local_audio(root: Path) -> dict[str, int]:
    """Audio files under ``root`` (read only): relpath -> size."""
    if not root.is_dir():
        return {}
    return {
        p.relative_to(root).as_posix(): p.stat().st_size
        for p in root.rglob("*")
        if p.is_file() and is_audio_file(p.name)
    }


# ---------------------------------------------------------------- inventory


@dataclass
class Location:
    """One place a file sits: ``kind`` is ``target``, ``local`` or ``tracked``."""

    kind: str
    root: str  # target display root or local folder
    relpath: str
    size: int = 0

    @property
    def stem(self) -> str:
        name = self.relpath.rsplit("/", 1)[-1]
        return name.rsplit(".", 1)[0] if "." in name else name


@dataclass
class Inventory:
    """Audio we already hold, matched to in-scope videos by video_id."""

    locations: list[Location] = field(default_factory=list)
    _by_stem: dict[str, list[Location]] = field(default_factory=dict)
    _by_rel: dict[str, list[Location]] = field(default_factory=dict)

    def add(self, loc: Location) -> None:
        self.locations.append(loc)
        self._by_stem.setdefault(loc.stem, []).append(loc)
        self._by_rel.setdefault(loc.relpath, []).append(loc)

    def find(self, row: dict[str, Any]) -> list[Location]:
        """Every location holding this video. A video_id in the filename always counts (owner rule 4)."""
        vid = row["video_id"]
        hits = [loc for loc in self.locations if vid in loc.relpath.rsplit("/", 1)[-1]]
        tracked = (row.get("audio_file_path") or "").strip()
        if tracked:
            rel = (
                tracked.split(":", 1)[1]
                if re.match(r"^[A-Za-z0-9_-]+:", tracked)
                else tracked
            )
            for loc in self.locations:
                if (
                    rel == loc.relpath
                    or rel.endswith("/" + loc.relpath)
                    or loc.relpath.endswith("/" + rel)
                ):
                    hits.append(loc)
        channel_suffix = _channel_id_suffix(row)
        if row.get("title") and channel_suffix:
            for d in {row.get("meeting_date"), row.get("event_date")} - {None}:
                for loc in self._by_stem.get(
                    legacy_stem({**row, "meeting_date": d}), []
                ):
                    # Same date + title is common across towns: the legacy folder must be this channel's.
                    parent = loc.relpath.rsplit("/", 1)[0] if "/" in loc.relpath else ""
                    if parent.rsplit("/", 1)[-1].endswith(channel_suffix):
                        hits.append(loc)
        unique: dict[tuple[str, str, str], Location] = {
            (h.kind, h.root, h.relpath): h for h in hits
        }
        return list(unique.values())


def build_inventory(
    target: Target | None, target_files: dict[str, int], local_dirs: list[Path]
) -> Inventory:
    inv = Inventory()
    if target is not None:
        root = target.display("")
        for rel, size in target_files.items():
            inv.add(Location("target", root, rel, size))
    for d in local_dirs:
        for rel, size in list_local_audio(d).items():
            inv.add(Location("local", str(d), rel, size))
    return inv


@dataclass
class Plan:
    """What each in-scope video needs."""

    on_target: list[tuple[dict[str, Any], Location]] = field(default_factory=list)
    upload_local: list[tuple[dict[str, Any], Location]] = field(default_factory=list)
    tracked_only: list[dict[str, Any]] = field(default_factory=list)
    download: list[dict[str, Any]] = field(default_factory=list)


def plan(rows: list[dict[str, Any]], inv: Inventory) -> Plan:
    out = Plan()
    for row in rows:
        hits = inv.find(row)
        on_target = [h for h in hits if h.kind == "target"]
        local = [h for h in hits if h.kind == "local"]
        if on_target:
            out.on_target.append((row, on_target[0]))
        elif local:
            out.upload_local.append((row, local[0]))
        elif row.get("audio_downloaded_at") or row.get("audio_file_path"):
            out.tracked_only.append(row)
        else:
            out.download.append(row)
    return out


# ---------------------------------------------------------------- download


class Blocked(RuntimeError):
    """YouTube refused the request (403, 429 or a bot check)."""


def ydl_options(out_stem: Path, kbps: int, cookies: Path | None) -> dict[str, Any]:
    from scrapers.youtube.download_audio_to_drive import _yt_dlp_youtube_ejs_opts

    opts: dict[str, Any] = {
        "format": AUDIO_FORMAT,
        "outtmpl": str(out_stem),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": str(kbps),
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 2,
        "fragment_retries": 2,
        "keepvideo": False,
    }
    opts.update(_yt_dlp_youtube_ejs_opts())
    if cookies and cookies.is_file():
        opts["cookiefile"] = str(cookies)
    return opts


def download_audio(
    url: str, out_stem: Path, kbps: int, cookies: Path | None, *, transcode: bool = True
) -> Path:
    """Download one video's audio to ``<out_stem>.opus``; raise ``Blocked`` on a 403/429/bot check."""
    import yt_dlp

    from scrapers.youtube.vpn_guard import require_vpn

    require_vpn()
    try:
        with yt_dlp.YoutubeDL(ydl_options(out_stem, kbps, cookies)) as ydl:
            ydl.download([url])
    except (
        Exception
    ) as exc:  # yt-dlp raises DownloadError with the HTTP status in the text
        if is_block_error(str(exc)):
            raise Blocked(str(exc)) from exc
        raise
    out = out_stem.with_suffix(".opus")
    if not out.is_file():
        raise RuntimeError(f"yt-dlp finished but {out.name} is missing")
    return transcode_if_needed(out, kbps) if transcode else out


def audio_bitrate_kbps(path: Path) -> float | None:
    """Average bitrate from ffprobe (container duration and file size)."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        seconds = float(proc.stdout.strip())
    except ValueError:
        return None
    return path.stat().st_size * 8 / 1000 / seconds if seconds > 0 else None


def transcode_if_needed(path: Path, kbps: int) -> Path:
    """Re-encode to ``kbps`` Opus (mono-safe voip profile) when the copied stream is larger."""
    rate = audio_bitrate_kbps(path)
    if rate is None or rate <= kbps * TRANSCODE_SLACK:
        return path
    tmp = path.with_name(path.stem + ".enc.opus")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(path),
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            f"{kbps}k",
            "-application",
            "voip",
            str(tmp),
        ],
        check=True,
    )
    tmp.replace(path)
    logger.debug("  re-encoded {:.0f} → {} kbps", rate, kbps)
    return path


# ---------------------------------------------------------------- database

INVENTORY_DDL = """
CREATE TABLE IF NOT EXISTS bronze.bronze_meeting_audio_inventory (
    video_id       text        NOT NULL,
    location_kind  text        NOT NULL,
    location       text        NOT NULL,
    size_bytes     bigint,
    seen_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, location)
)
"""


def database_url() -> str:
    from dotenv import load_dotenv

    load_dotenv(repo_root() / ".env")
    load_dotenv()  # a worktree without its own .env: fall back to the nearest one
    url = os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if not url:
        raise SystemExit("Set OPEN_NAVIGATOR_DATABASE_URL (local warehouse) in .env")
    return url


def fetch_scope(conn, scope: str, year: int) -> list[dict[str, Any]]:
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            scope_sql(scope), {"start": date(year, 1, 1), "end": date(year + 1, 1, 1)}
        )
        return [dict(r) for r in cur.fetchall()]


def record(conn, video_id: str, path: str, size_bytes: int) -> None:
    """Stamp the bronze tracking columns and the inventory. ``conn=None`` (``--no-record``) skips it."""
    if conn is None:
        return
    try:
        _record(conn, video_id, path, size_bytes)
    except Exception as exc:
        conn.rollback()  # keep the connection usable for the next video
        raise RecordError(f"stored at {path} but not recorded: {exc}") from exc


class RecordError(RuntimeError):
    """The file is stored but the bronze tracking write failed."""


def _record(conn, video_id: str, path: str, size_bytes: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE bronze.bronze_event_youtube
            SET audio_downloaded_at = COALESCE(audio_downloaded_at, CURRENT_TIMESTAMP),
                audio_file_path = %s,
                audio_file_size_mb = %s
            WHERE video_id = %s
            """,
            (path, round(size_bytes / 1_048_576, 2), video_id),
        )
    conn.commit()
    _write_inventory(conn, [(video_id, "target", path, size_bytes)])


def record_inventory(conn, items: list[tuple[str, str, str, int]]) -> None:
    if conn is None or not items:
        return
    try:
        _write_inventory(conn, items)
    except Exception:
        conn.rollback()
        raise


def _write_inventory(conn, items: list[tuple[str, str, str, int]]) -> None:
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        cur.execute(INVENTORY_DDL)
        execute_values(
            cur,
            """
            INSERT INTO bronze.bronze_meeting_audio_inventory (video_id, location_kind, location, size_bytes)
            VALUES %s
            ON CONFLICT (video_id, location) DO UPDATE
            SET size_bytes = EXCLUDED.size_bytes, location_kind = EXCLUDED.location_kind, seen_at = now()
            """,
            items,
        )
    conn.commit()


def save_inventory(conn, p: Plan) -> None:
    """Persist every in-scope video we found a file for (video_id -> location)."""
    items: list[tuple[str, str, str, int]] = []
    for row, loc in p.on_target + p.upload_local:
        where = (
            f"{loc.root}/{loc.relpath}"
            if loc.kind == "local"
            else f"{loc.root.rstrip('/')}/{loc.relpath}"
        )
        items.append((row["video_id"], loc.kind, where, loc.size))
    for row in p.tracked_only:
        items.append((row["video_id"], "tracked", row.get("audio_file_path") or "", 0))
    record_inventory(conn, items)


# ---------------------------------------------------------------- run


@dataclass
class RunStats:
    done: int = 0
    failed: int = 0
    uploaded_existing: int = 0
    not_recorded: int = 0
    bytes_uploaded: int = 0


def store_verified(target: Target, local: Path, relpath: str, *, move: bool) -> int:
    """Store ``local`` at ``relpath``; on a size mismatch remove our copy so it never counts as held."""
    expected = local.stat().st_size
    stored = target.put(local, relpath, move=move)
    if stored != expected:
        try:
            target.remove(relpath)
        finally:
            raise RuntimeError(
                f"size mismatch: local {expected} vs stored {stored}; removed"
            )
    return stored


def report_plan(p: Plan, total: int, kbps: int, *, target_checked: bool = True) -> None:
    rest = estimate(p.download, kbps)
    if not target_checked:
        logger.warning(
            "The target folder was not listed: 'left to download' is an upper bound until it is."
        )
    logger.info(
        "In scope {:,} · held on target {:,} · held locally (upload, no download) {:,} · "
        "tracked in bronze only {:,} · left to download {:,} (~{:,} h, ~{} GB)",
        total,
        len(p.on_target),
        len(p.upload_local),
        len(p.tracked_only),
        rest["videos"],
        rest["hours"],
        rest["gb"],
    )


def run(
    p: Plan,
    target: Target,
    conn,
    *,
    limit: int | None,
    kbps: int,
    cookies: Path | None,
    sleep_seconds: float,
    max_blocks: int,
    temp_root: Path,
    downloader: Callable[..., Path] = download_audio,
    sleeper: Callable[[float], None] = time.sleep,
) -> RunStats:
    stats = RunStats()
    for row, loc in p.on_target:
        path = target.display(loc.relpath)
        if row.get("audio_file_path") != path:
            try:
                record(conn, row["video_id"], path, loc.size)
            except RecordError as exc:
                stats.not_recorded += 1
                logger.error("  {}", str(exc)[:300])

    for (
        row,
        loc,
    ) in p.upload_local:  # held locally: upload the existing file, keep the original
        relpath = loc.relpath if row["video_id"] in loc.relpath else target_relpath(row)
        src = Path(loc.root) / loc.relpath
        try:
            stored = store_verified(target, src, relpath, move=False)
            stats.uploaded_existing += 1
            stats.bytes_uploaded += stored
            logger.success("  uploaded existing {} → {}", src.name, relpath)
            record(conn, row["video_id"], target.display(relpath), stored)
        except RecordError as exc:
            stats.not_recorded += 1
            logger.error("  {}", str(exc)[:300])
        except Exception as exc:  # noqa: BLE001 — one failed upload must not end the run
            stats.failed += 1
            logger.error("  upload of existing {} failed: {}", src, str(exc)[:300])

    todo = p.download[:limit] if limit is not None else p.download
    blocks_in_row = 0
    pause = sleep_seconds
    for i, row in enumerate(todo, 1):
        relpath = target_relpath(row)
        logger.info("[{}/{}] {} → {}", i, len(todo), row["video_id"], relpath)
        workdir = Path(tempfile.mkdtemp(prefix="audio_", dir=temp_root))
        try:
            local = downloader(
                row["video_url"], workdir / row["video_id"], kbps, cookies
            )
            stored = store_verified(target, local, relpath, move=True)
            stats.done += 1
            stats.bytes_uploaded += stored
            blocks_in_row = 0
            pause = sleep_seconds
            logger.success(
                "  stored {:.1f} MB · done {} failed {} · {:.2f} GB total",
                stored / 1_048_576,
                stats.done,
                stats.failed,
                stats.bytes_uploaded / 1e9,
            )
            record(conn, row["video_id"], target.display(relpath), stored)
        except RecordError as exc:
            stats.not_recorded += 1
            logger.error("  {}", str(exc)[:300])
        except Blocked as exc:
            stats.failed += 1
            blocks_in_row += 1
            logger.warning(
                "  blocked by YouTube ({}/{} in a row): {}",
                blocks_in_row,
                max_blocks,
                str(exc)[:200],
            )
            if blocks_in_row >= max_blocks:
                logger.error(
                    "Stopping: {} blocks in a row. Not escalating workarounds.",
                    blocks_in_row,
                )
                raise SystemExit(EXIT_BLOCKED)
            pause *= 2
        except Exception as exc:  # noqa: BLE001 — one bad video must not end the run
            stats.failed += 1
            logger.error("  failed: {}", str(exc)[:300])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)  # only this run's temp dir
        if i < len(todo):
            sleeper(pause + random.uniform(0, 3))
    return stats


def build_target(args: argparse.Namespace) -> Target:
    if args.target == "onedrive":
        root = (
            args.remote_root or f"{args.community_root}/{SOURCE_FOLDERS[args.source]}"
        )
        return OneDriveTarget(remote=args.remote, root=root, rclone=args.rclone)
    if not args.output_dir:
        raise SystemExit(f"--target {args.target} needs --output-dir")
    return LocalTarget(Path(args.output_dir))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("--scope", default="data-centers", choices=["data-centers"])
    p.add_argument("--year", type=int, default=2026)
    p.add_argument(
        "--data-centers-2026",
        action="store_true",
        help="Shortcut for --scope data-centers --year 2026",
    )
    p.add_argument(
        "--target", default="onedrive", choices=["onedrive", "local", "drive"]
    )
    p.add_argument(
        "--source",
        default="youtube",
        choices=sorted(SOURCE_FOLDERS),
        help="Audio source; picks the sibling folder <community-root>/<source>_audio",
    )
    p.add_argument(
        "--remote", default=os.environ.get("AUDIO_RCLONE_REMOTE", DEFAULT_REMOTE)
    )
    p.add_argument(
        "--community-root",
        default=os.environ.get("AUDIO_COMMUNITY_ROOT", DEFAULT_COMMUNITY_ROOT),
    )
    p.add_argument(
        "--remote-root",
        default=os.environ.get("AUDIO_REMOTE_ROOT"),
        help="Override the whole remote folder (default <community-root>/<source>_audio)",
    )
    p.add_argument("--rclone", default=shutil.which("rclone") or "rclone")
    p.add_argument("--output-dir", help="Folder for --target local/drive")
    p.add_argument(
        "--local-audio-dir",
        action="append",
        default=None,
        help="Extra local folder of audio already held (repeatable; default data/cache/youtube_audio)",
    )
    p.add_argument(
        "--temp-dir",
        default=None,
        help="Temp dir on the WSL disk (default: system temp)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, help="Download at most this many new videos")
    p.add_argument("--opus-bitrate", type=int, default=DEFAULT_OPUS_KBPS)
    p.add_argument(
        "--no-transcode",
        action="store_true",
        help="Keep YouTube's Opus stream as-is (~120 kbps, about twice the size; saves ~2.5 CPU-min per hour)",
    )
    p.add_argument("--sleep-seconds", type=float, default=8.0)
    p.add_argument("--max-blocks", type=int, default=3)
    p.add_argument(
        "--no-record",
        action="store_true",
        help="Do not write bronze tracking/inventory (scratch tests)",
    )
    p.add_argument(
        "--cookies",
        default=os.environ.get("YOUTUBE_COOKIES"),
        help="Existing Netscape cookies file (default: <repo>/youtube_cookies.txt if present)",
    )
    args = p.parse_args(argv)
    if args.data_centers_2026:
        args.scope, args.year = "data-centers", 2026
    return args


def main(argv: list[str] | None = None) -> int:
    import psycopg2

    args = parse_args(argv)
    conn = psycopg2.connect(database_url())
    rows = fetch_scope(conn, args.scope, args.year)
    est = estimate(rows, args.opus_bitrate)
    logger.info(
        "Scope {} {}: {videos:,} videos ({with_duration:,} with a duration, avg {avg_minutes} min) · "
        "~{hours:,} h · ~{gb} GB at {kbps} kbps",
        args.scope,
        args.year,
        kbps=args.opus_bitrate,
        **est,
    )

    target = build_target(args)
    target_files: dict[str, int] = {}
    target_checked = True
    if isinstance(target, OneDriveTarget) and not target.configured():
        target_checked = False
        msg = (
            f"rclone remote {target.remote!r} is not configured. One-time, as the owner, signed in to the "
            "PERSONAL Microsoft account (never the CDC work account): "
            f"`rclone config create {target.remote} onedrive` and choose 'OneDrive Personal'."
        )
        if not args.dry_run:
            raise SystemExit(msg)
        logger.warning("{} Dry run continues without the OneDrive listing.", msg)
    else:
        target_files = target.listing()
        logger.info(
            "Target {} holds {:,} audio files", target.display(""), len(target_files)
        )

    local_dirs = (
        [Path(d) for d in args.local_audio_dir]
        if args.local_audio_dir
        else default_local_dirs()
    )
    inv = build_inventory(target if target_checked else None, target_files, local_dirs)
    logger.info(
        "Inventory: {:,} audio files across target + {}",
        len(inv.locations),
        [str(d) for d in local_dirs],
    )
    p = plan(rows, inv)
    report_plan(p, len(rows), args.opus_bitrate, target_checked=target_checked)
    missing = sum(1 for r in rows if not r.get("title") and not r.get("channel_id"))
    if missing:
        logger.warning(
            "{:,} in-scope videos have no bronze_event_youtube row (cannot be stamped)",
            missing,
        )
    store = None if args.no_record else conn
    if target_checked and not args.dry_run:
        save_inventory(store, p)

    if args.dry_run:
        for row in p.download[: args.limit or 10]:
            logger.info(
                "  {} {} {} {}",
                row["meeting_date"],
                row["state_code"],
                row["video_id"],
                (row["title"] or "")[:70],
            )
        return 0

    cookies = (
        Path(args.cookies) if args.cookies else repo_root() / "youtube_cookies.txt"
    )
    temp_root = Path(args.temp_dir or tempfile.gettempdir())
    temp_root.mkdir(parents=True, exist_ok=True)
    stats = run(
        p,
        target,
        store,
        limit=args.limit,
        kbps=args.opus_bitrate,
        cookies=cookies if cookies.is_file() else None,
        sleep_seconds=args.sleep_seconds,
        max_blocks=args.max_blocks,
        temp_root=temp_root,
        downloader=functools.partial(download_audio, transcode=not args.no_transcode),
    )
    logger.success(
        "Finished: downloaded {} · uploaded existing {} · failed {} · stored but not recorded {} · "
        "{:.2f} GB uploaded",
        stats.done,
        stats.uploaded_existing,
        stats.failed,
        stats.not_recorded,
        stats.bytes_uploaded / 1e9,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
