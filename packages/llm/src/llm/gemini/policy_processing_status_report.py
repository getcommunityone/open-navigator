#!/usr/bin/env python3
"""
Markdown status report: jurisdictions, YouTube catalog, transcripts, policy JSON, reports.

Combines Postgres (bronze YouTube + text_ai + public.jurisdiction) with on-disk
``data/cache/gemini_transcript_policy/`` counts.

Usage (repo root):
  .venv/bin/python -m llm.gemini.policy_processing_status_report
  .venv/bin/python -m llm.gemini.policy_processing_status_report --states AL,GA,IN
  .venv/bin/python -m llm.gemini.policy_processing_status_report --all-states
  .venv/bin/python -m llm.gemini.policy_processing_status_report -o docs/policy_processing_status.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Set, Tuple

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[5]  # repo root (…/llm/gemini/ → …/)
# Allow ``scripts.*`` imports when run as a file (not just ``python -m``).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_DEFAULT_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
_DEFAULT_OUT = _REPO_ROOT / "data" / "reports" / "policy_processing_status.md"
_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "MT", "WA", "WI")

_DIR_TRANSCRIPTS = "01_transcripts"
_DIR_ANALYSIS = "02_analysis"
_DIR_REPORTS = "03_reports"
_DIR_RUNS = "04_runs"
_DEFAULT_STALE_MINUTES = 30
_DEFAULT_TARGET_VIDEOS = 2
_JID_FROM_FOLDER = re.compile(
    r"^(?P<slug>.+)_(?P<geoid>[0-9]+)$"
)
_LEGACY_NUMERIC = re.compile(r"^[0-9]+$")


@dataclass
class CacheCounts:
    jurisdictions: int = 0
    channels: int = 0
    transcripts: int = 0
    analysis_json: int = 0
    reports_md: int = 0


@dataclass
class JurisdictionCacheStats:
    state_code: str
    jurisdiction_id: str
    transcripts: int = 0
    analysis_json: int = 0
    reports_md: int = 0
    # Files whose mtime falls within the rolling recency window (default 24h),
    # i.e. analyses summarised / reports generated "recently". Used by the batch
    # dashboard to show throughput rather than only the all-time on-disk totals.
    analysis_recent: int = 0
    reports_recent: int = 0
    latest_mtime: float = 0.0
    recent_touch_min: float = 0.0
    meeting_durations_sec: List[float] = field(default_factory=list)


@dataclass
class JurisdictionProgress:
    state_code: str
    jurisdiction_id: str
    jurisdiction_name: str
    youtube_videos: int = 0
    bronze_transcripts: int = 0
    cache_transcripts: int = 0
    cache_analysis: int = 0
    cache_reports: int = 0
    db_last_updated: Optional[datetime] = None
    cache_last_updated: Optional[datetime] = None
    stage: str = "idle"
    in_progress: bool = False
    in_progress_since: Optional[datetime] = None
    elapsed_seconds: Optional[int] = None
    est_remaining_seconds: Optional[int] = None


@dataclass
class RunTiming:
    completed_jurisdictions: int = 0
    total_jurisdictions: int = 0
    in_progress: Optional[JurisdictionProgress] = None
    last_activity_utc: Optional[datetime] = None
    avg_seconds_per_jurisdiction: Optional[float] = None
    estimated_remaining_seconds: Optional[int] = None


@dataclass
class StateRollup:
    state_code: str
    municipalities: int = 0
    counties: int = 0
    school_districts: int = 0
    other_jurisdictions: int = 0
    youtube_jurisdictions: int = 0
    youtube_channels: int = 0
    youtube_videos: int = 0
    bronze_has_transcript: int = 0
    cache: CacheCounts = field(default_factory=CacheCounts)
    videos_by_year: Dict[str, int] = field(default_factory=dict)
    channel_year_rows: List[Dict[str, Any]] = field(default_factory=list)
    channel_total_rows: List[Dict[str, Any]] = field(default_factory=list)


def _database_url() -> Optional[str]:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL")
    )


# Canonical jurisdiction table is ``public.civic_jurisdiction`` (state column ``state``,
# type column ``classification``). Legacy ``public.jurisdiction`` (``state_code``/``type``)
# is still supported as a fallback.
_JURISDICTION_TABLE_CANDIDATES = ("civic_jurisdiction", "jurisdiction")


def _jurisdiction_table_meta(conn) -> Tuple[str, str, str]:
    """Resolve ``(table, state_col, type_col)`` for the public jurisdiction table."""
    with conn.cursor() as cur:
        for table in _JURISDICTION_TABLE_CANDIDATES:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table,),
            )
            cols = {r[0] for r in cur.fetchall()}
            if not cols:
                continue
            state_col = "state_code" if "state_code" in cols else ("state" if "state" in cols else None)
            type_col = "type" if "type" in cols else ("classification" if "classification" in cols else None)
            if state_col and type_col:
                return table, state_col, type_col
    raise RuntimeError(
        "No public.civic_jurisdiction or public.jurisdiction table with state/type columns found"
    )


def _map_jurisdiction_type(raw: str) -> str:
    t = (raw or "").strip().lower()
    if t in ("county",):
        return "county"
    if t in ("school_district", "school"):
        return "school_district"
    if t in ("city", "town", "village", "municipality", "borough"):
        return "municipality"
    if t in ("state", "township"):
        return t
    return "other"


def _jurisdiction_group_from_id(jurisdiction_id: str) -> str:
    from scripts.jurisdictions.jurisdiction_id import parse_jurisdiction_id

    jid = (jurisdiction_id or "").strip().lower()
    if jid.startswith("county_"):
        return "county"
    if jid.startswith("municipality_"):
        return "city"
    if jid.startswith("school_district_"):
        return "school"
    if jid.startswith("state_"):
        return "state"
    if jid.startswith("township_"):
        return "township"
    jt, _geoid, _slug = parse_jurisdiction_id(jid)
    if jt == "county":
        return "county"
    if jt == "municipality":
        return "city"
    if jt == "school_district":
        return "school"
    if jt == "state":
        return "state"
    if jt == "township":
        return "township"
    return "other"


def _folder_to_jurisdiction_id(folder_name: str, cache_type: str) -> str:
    name = folder_name.strip()
    if _LEGACY_NUMERIC.fullmatch(name):
        return name
    m = _JID_FROM_FOLDER.match(name)
    if not m:
        return name
    geoid = m.group("geoid")
    seg = (cache_type or "municipality").strip().lower()
    if seg == "school":
        return f"school_district_{geoid}"
    if seg in ("municipality", "county", "state", "township"):
        return f"{seg}_{geoid}"
    return f"municipality_{geoid}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _format_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _touch_file_stats(
    path: Path,
    *,
    stats: JurisdictionCacheStats,
    stale_cutoff: float,
) -> float:
    """Fold ``path``'s mtime into ``stats``; return that mtime (0.0 on error)."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return 0.0
    stats.latest_mtime = max(stats.latest_mtime, mtime)
    if mtime >= stale_cutoff:
        if stats.recent_touch_min <= 0:
            stats.recent_touch_min = mtime
        else:
            stats.recent_touch_min = min(stats.recent_touch_min, mtime)
    return mtime


def _tally_channel_dirs(
    state: str,
    jpath: Path,
    channel_dirs: List[Path],
    cache_type: str,
    *,
    stale_cutoff: float,
    recent_cutoff: float,
    by_jid: Optional[Dict[str, JurisdictionCacheStats]] = None,
) -> CacheCounts:
    """Count transcripts/analysis/reports; optionally accumulate per-jurisdiction stats."""
    counts = CacheCounts()
    jid = _folder_to_jurisdiction_id(jpath.name, cache_type)
    jstats: Optional[JurisdictionCacheStats] = None
    if by_jid is not None:
        jstats = by_jid.setdefault(
            jid,
            JurisdictionCacheStats(state_code=state, jurisdiction_id=jid),
        )

    for ch in channel_dirs:
        tx_dir = ch / _DIR_TRANSCRIPTS
        if tx_dir.is_dir():
            for p in tx_dir.glob("*.json"):
                if not p.is_file():
                    continue
                counts.transcripts += 1
                if jstats:
                    jstats.transcripts += 1
                    _touch_file_stats(p, stats=jstats, stale_cutoff=stale_cutoff)
        an_dir = ch / _DIR_ANALYSIS
        if an_dir.is_dir():
            for p in an_dir.glob("*.json"):
                if not p.is_file() or p.name.startswith("_"):
                    continue
                counts.analysis_json += 1
                if jstats:
                    jstats.analysis_json += 1
                    m = _touch_file_stats(p, stats=jstats, stale_cutoff=stale_cutoff)
                    if m >= recent_cutoff:
                        jstats.analysis_recent += 1
        rp_dir = ch / _DIR_REPORTS
        if rp_dir.is_dir():
            for p in rp_dir.glob("*.md"):
                if not p.is_file():
                    continue
                counts.reports_md += 1
                if jstats:
                    jstats.reports_md += 1
                    m = _touch_file_stats(p, stats=jstats, stale_cutoff=stale_cutoff)
                    if m >= recent_cutoff:
                        jstats.reports_recent += 1
        runs_dir = ch / _DIR_RUNS
        if runs_dir.is_dir() and jstats:
            for p in runs_dir.glob("*.meta.json"):
                if p.is_file():
                    _touch_file_stats(p, stats=jstats, stale_cutoff=stale_cutoff)

    if jstats and jstats.transcripts and jstats.reports_md:
        for ch in channel_dirs:
            tx_dir = ch / _DIR_TRANSCRIPTS
            rp_dir = ch / _DIR_REPORTS
            if not tx_dir.is_dir() or not rp_dir.is_dir():
                continue
            for tx in tx_dir.glob("*.json"):
                if not tx.is_file():
                    continue
                stem = tx.stem
                for report in rp_dir.glob(f"{stem}.md"):
                    if report.is_file():
                        try:
                            dur = report.stat().st_mtime - tx.stat().st_mtime
                            if dur > 0:
                                jstats.meeting_durations_sec.append(dur)
                        except OSError:
                            pass
                        break

    counts.jurisdictions = 1 if counts.transcripts or counts.analysis_json or counts.reports_md else 0
    counts.channels = len(channel_dirs)
    return counts


def _iter_cache_jurisdiction_dirs(
    cache_root: Path,
) -> Iterable[Tuple[str, str, Path, List[Path]]]:
    """Yield ``(state_code, cache_type, jurisdiction_dir, channel_dirs)``."""
    if not cache_root.is_dir():
        return

    for state_dir in sorted(cache_root.iterdir()):
        if not state_dir.is_dir() or state_dir.name.startswith("."):
            continue
        state = state_dir.name.upper()
        if not re.fullmatch(r"[A-Z]{2}", state):
            continue
        for type_dir in state_dir.iterdir():
            if not type_dir.is_dir():
                continue
            cache_type = type_dir.name
            for jdir in type_dir.iterdir():
                if not jdir.is_dir():
                    continue
                channels = [c for c in jdir.iterdir() if c.is_dir() and c.name.startswith("UC")]
                if channels:
                    yield state, cache_type, jdir, channels

    for entry in cache_root.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if re.fullmatch(r"[A-Z]{2}", entry.name):
            continue
        channels = [c for c in entry.iterdir() if c.is_dir() and c.name.startswith("UC")]
        if not channels:
            continue
        state_guess = "??"
        try:
            from llm.gemini.transcript_cache_paths import lookup_jurisdiction_geo_from_db

            jid = entry.name
            sg, _ = lookup_jurisdiction_geo_from_db(jid if "_" in jid else jid)
            if sg:
                state_guess = sg
        except Exception:
            pass
        yield state_guess, "", entry, channels


def scan_jurisdiction_cache(
    cache_root: Path,
    *,
    stale_minutes: int = _DEFAULT_STALE_MINUTES,
    recent_minutes: int = 24 * 60,
) -> Dict[str, JurisdictionCacheStats]:
    """Scan the policy cache per jurisdiction.

    ``recent_minutes`` defines the rolling window (default 24h) used to populate
    ``analysis_recent`` / ``reports_recent`` from each file's mtime.
    """
    now = _utc_now().timestamp()
    stale_cutoff = now - stale_minutes * 60
    recent_cutoff = now - recent_minutes * 60
    by_jid: Dict[str, JurisdictionCacheStats] = {}
    for state, cache_type, jdir, channels in _iter_cache_jurisdiction_dirs(cache_root):
        _tally_channel_dirs(
            state,
            jdir,
            channels,
            cache_type,
            stale_cutoff=stale_cutoff,
            recent_cutoff=recent_cutoff,
            by_jid=by_jid,
        )
    return by_jid


def scan_policy_cache(cache_root: Path) -> Tuple[Dict[str, CacheCounts], Dict[str, Set[str]]]:
    """Per-state cache file counts; second dict = jurisdiction_ids with any cache file."""
    by_state: Dict[str, CacheCounts] = defaultdict(CacheCounts)
    jids_with_cache: Dict[str, Set[str]] = defaultdict(set)

    if not cache_root.is_dir():
        return by_state, jids_with_cache

    stale_cutoff = 0.0
    for state, cache_type, jdir, channels in _iter_cache_jurisdiction_dirs(cache_root):
        counts = _tally_channel_dirs(
            state,
            jdir,
            channels,
            cache_type,
            stale_cutoff=stale_cutoff,
            recent_cutoff=0.0,
            by_jid=None,
        )
        st = by_state[state]
        if counts.jurisdictions:
            st.jurisdictions += 1
        st.channels += counts.channels
        st.transcripts += counts.transcripts
        st.analysis_json += counts.analysis_json
        st.reports_md += counts.reports_md
        if counts.transcripts or counts.analysis_json or counts.reports_md:
            jids_with_cache[state].add(_folder_to_jurisdiction_id(jdir.name, cache_type))

    return by_state, jids_with_cache


def fetch_states_with_data() -> List[str]:
    """Distinct USPS state codes present in bronze YouTube — the DB universe.

    Used by ``--all-states`` so the report covers every state that actually has
    data, not just the priority dev set.
    """
    import psycopg2

    url = _database_url()
    if not url:
        raise SystemExit("Set NEON_DATABASE_URL or DATABASE_URL in .env")

    found: Set[str] = set()
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT UPPER(state_code) AS sc
            FROM bronze.bronze_event_youtube
            WHERE state_code IS NOT NULL AND BTRIM(state_code) <> ''
            """
        )
        for row in cur.fetchall():
            sc = (row[0] or "").strip().upper()
            if re.fullmatch(r"[A-Z]{2}", sc):
                found.add(sc)
    return sorted(found)


def fetch_db_rollups(states: List[str]) -> Dict[str, StateRollup]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = _database_url()
    if not url:
        raise SystemExit("Set NEON_DATABASE_URL or DATABASE_URL in .env")

    rollups: Dict[str, StateRollup] = {s: StateRollup(state_code=s) for s in states}

    with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        table, state_col, type_col = _jurisdiction_table_meta(conn)
        cur.execute(
            f"""
            SELECT UPPER({state_col}) AS state_code,
                   {type_col} AS type,
                   COUNT(*)::bigint AS n
            FROM {table}
            WHERE UPPER({state_col}) = ANY(%s)
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            (states,),
        )
        for row in cur.fetchall():
            st = row["state_code"]
            if st not in rollups:
                continue
            bucket = _map_jurisdiction_type(row["type"])
            n = int(row["n"] or 0)
            if bucket == "municipality":
                rollups[st].municipalities += n
            elif bucket == "county":
                rollups[st].counties += n
            elif bucket == "school_district":
                rollups[st].school_districts += n
            else:
                rollups[st].other_jurisdictions += n

        cur.execute(
            """
            SELECT UPPER(y.state_code) AS state_code,
                   COUNT(DISTINCT y.jurisdiction_id)::bigint AS youtube_jurisdictions,
                   COUNT(DISTINCT y.channel_id)::bigint AS youtube_channels,
                   COUNT(*)::bigint AS youtube_videos,
                   COUNT(*) FILTER (
                       WHERE COALESCE(t.has_transcript, FALSE)
                         OR (t.raw_text IS NOT NULL AND BTRIM(t.raw_text) <> '')
                   )::bigint AS bronze_has_transcript
            FROM bronze.bronze_event_youtube y
            LEFT JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
            WHERE UPPER(y.state_code) = ANY(%s)
              AND y.jurisdiction_id IS NOT NULL
              AND BTRIM(y.jurisdiction_id) <> ''
            GROUP BY 1
            ORDER BY 1
            """,
            (states,),
        )
        for row in cur.fetchall():
            st = row["state_code"]
            if st not in rollups:
                continue
            r = rollups[st]
            r.youtube_jurisdictions = int(row["youtube_jurisdictions"] or 0)
            r.youtube_channels = int(row["youtube_channels"] or 0)
            r.youtube_videos = int(row["youtube_videos"] or 0)
            r.bronze_has_transcript = int(row["bronze_has_transcript"] or 0)

        cur.execute(
            """
            SELECT UPPER(y.state_code) AS state_code,
                   COALESCE(
                       EXTRACT(YEAR FROM y.published_at),
                       EXTRACT(YEAR FROM y.event_date),
                       0
                   )::int AS yr,
                   COUNT(*)::bigint AS n
            FROM bronze.bronze_event_youtube y
            WHERE UPPER(y.state_code) = ANY(%s)
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            (states,),
        )
        for row in cur.fetchall():
            st = row["state_code"]
            if st in rollups:
                yr_val = int(row["yr"] or 0)
                yr_key = "unknown" if yr_val == 0 else str(yr_val)
                rollups[st].videos_by_year[yr_key] = int(row["n"] or 0)

        cur.execute(
            """
            SELECT UPPER(y.state_code) AS state_code,
                   y.jurisdiction_name,
                   y.jurisdiction_id,
                   y.channel_id,
                   COALESCE(
                       EXTRACT(YEAR FROM y.published_at),
                       EXTRACT(YEAR FROM y.event_date),
                       0
                   )::int AS yr,
                   COUNT(*)::bigint AS videos,
                   COUNT(*) FILTER (
                       WHERE COALESCE(t.has_transcript, FALSE)
                         OR (t.raw_text IS NOT NULL AND BTRIM(t.raw_text) <> '')
                   )::bigint AS with_transcript
            FROM bronze.bronze_event_youtube y
            LEFT JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
            WHERE UPPER(y.state_code) = ANY(%s)
              AND y.channel_id IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
            ORDER BY 1, 2, 4, 5 DESC
            """,
            (states,),
        )
        for row in cur.fetchall():
            st = row["state_code"]
            if st in rollups:
                rollups[st].channel_year_rows.append(dict(row))

        cur.execute(
            """
            SELECT UPPER(y.state_code) AS state_code,
                   y.jurisdiction_name,
                   y.jurisdiction_id,
                   y.channel_id,
                   COUNT(*)::bigint AS videos,
                   COUNT(*) FILTER (
                       WHERE COALESCE(t.has_transcript, FALSE)
                         OR (t.raw_text IS NOT NULL AND BTRIM(t.raw_text) <> '')
                   )::bigint AS with_transcript
            FROM bronze.bronze_event_youtube y
            LEFT JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
            WHERE UPPER(y.state_code) = ANY(%s)
              AND y.channel_id IS NOT NULL
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 2, 4
            """,
            (states,),
        )
        for row in cur.fetchall():
            st = row["state_code"]
            if st in rollups:
                rollups[st].channel_total_rows.append(dict(row))

    return rollups


def fetch_jurisdiction_db_stats(states: List[str]) -> Dict[str, Dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = _database_url()
    if not url:
        raise SystemExit("Set NEON_DATABASE_URL or DATABASE_URL in .env")

    out: Dict[str, Dict[str, Any]] = {}
    with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT UPPER(y.state_code) AS state_code,
                   y.jurisdiction_id,
                   MAX(y.jurisdiction_name) AS jurisdiction_name,
                   COUNT(*)::bigint AS youtube_videos,
                   COUNT(*) FILTER (
                       WHERE COALESCE(t.has_transcript, FALSE)
                         OR (t.raw_text IS NOT NULL AND BTRIM(t.raw_text) <> '')
                   )::bigint AS bronze_transcripts,
                   MAX(y.last_updated) AS youtube_last_updated,
                   MAX(t.last_updated) AS transcript_last_updated
            FROM bronze.bronze_event_youtube y
            LEFT JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
            WHERE UPPER(y.state_code) = ANY(%s)
              AND y.jurisdiction_id IS NOT NULL
              AND BTRIM(y.jurisdiction_id) <> ''
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            (states,),
        )
        for row in cur.fetchall():
            jid = str(row["jurisdiction_id"])
            yt_ts = row.get("youtube_last_updated")
            tx_ts = row.get("transcript_last_updated")
            db_last: Optional[datetime] = None
            for ts in (yt_ts, tx_ts):
                if ts is None:
                    continue
                if isinstance(ts, datetime):
                    dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                else:
                    continue
                if db_last is None or dt > db_last:
                    db_last = dt
            out[jid] = {
                "state_code": row["state_code"],
                "jurisdiction_id": jid,
                "jurisdiction_name": row.get("jurisdiction_name") or jid,
                "youtube_videos": int(row.get("youtube_videos") or 0),
                "bronze_transcripts": int(row.get("bronze_transcripts") or 0),
                "db_last_updated": db_last,
            }
    return out


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _infer_stage(
    *,
    target_videos: int,
    cache_reports: int,
    cache_transcripts: int,
    cache_analysis: int,
    in_progress: bool,
) -> str:
    if cache_reports >= target_videos:
        return "complete"
    if in_progress:
        if cache_analysis < cache_transcripts or cache_reports < cache_analysis:
            return "analyze"
        return "captions"
    if cache_transcripts < target_videos:
        return "captions"
    if cache_analysis < target_videos or cache_reports < target_videos:
        return "analyze"
    return "idle"


def build_jurisdiction_progress(
    db_by_jid: Dict[str, Dict[str, Any]],
    cache_by_jid: Dict[str, JurisdictionCacheStats],
    *,
    states: List[str],
    stale_minutes: int,
    target_videos: int,
    avg_seconds_per_jurisdiction: Optional[float],
) -> List[JurisdictionProgress]:
    now = _utc_now()
    stale_cutoff = (now - timedelta(minutes=stale_minutes)).timestamp()
    all_jids = sorted(set(db_by_jid) | set(cache_by_jid))
    rows: List[JurisdictionProgress] = []

    for jid in all_jids:
        db = db_by_jid.get(jid, {})
        cache = cache_by_jid.get(jid)
        state = (db.get("state_code") or (cache.state_code if cache else "") or "??").upper()
        if states and state not in states and jid not in db_by_jid:
            continue
        name = str(db.get("jurisdiction_name") or jid)

        cache_reports = cache.reports_md if cache else 0
        cache_tx = cache.transcripts if cache else 0
        cache_an = cache.analysis_json if cache else 0

        cache_last: Optional[datetime] = None
        if cache and cache.latest_mtime > 0:
            cache_last = _utc_from_timestamp(cache.latest_mtime)

        in_progress = bool(cache and cache.recent_touch_min >= stale_cutoff)
        stage = _infer_stage(
            target_videos=target_videos,
            cache_reports=cache_reports,
            cache_transcripts=cache_tx,
            cache_analysis=cache_an,
            in_progress=in_progress,
        )
        if stage == "complete":
            in_progress = False

        in_progress_since: Optional[datetime] = None
        elapsed: Optional[int] = None
        if in_progress and cache and cache.recent_touch_min > 0:
            in_progress_since = _utc_from_timestamp(cache.recent_touch_min)
            elapsed = max(0, int((now - in_progress_since).total_seconds()))

        est_remaining: Optional[int] = None
        if stage != "complete":
            per_meeting = _median(cache.meeting_durations_sec if cache else []) or (
                (avg_seconds_per_jurisdiction or 600.0) / max(target_videos, 1)
            )
            meetings_left = max(0, target_videos - cache_reports)
            if meetings_left > 0:
                est_remaining = int(per_meeting * meetings_left)
                if stage == "captions" and cache_tx < target_videos:
                    est_remaining = int(est_remaining + per_meeting * 0.5)
            elif not in_progress and avg_seconds_per_jurisdiction:
                est_remaining = int(avg_seconds_per_jurisdiction)

        rows.append(
            JurisdictionProgress(
                state_code=state,
                jurisdiction_id=jid,
                jurisdiction_name=name,
                youtube_videos=int(db.get("youtube_videos") or 0),
                bronze_transcripts=int(db.get("bronze_transcripts") or 0),
                cache_transcripts=cache_tx,
                cache_analysis=cache_an,
                cache_reports=cache_reports,
                db_last_updated=db.get("db_last_updated"),
                cache_last_updated=cache_last,
                stage=stage,
                in_progress=in_progress,
                in_progress_since=in_progress_since,
                elapsed_seconds=elapsed,
                est_remaining_seconds=est_remaining,
            )
        )

    rows.sort(
        key=lambda r: (
            r.state_code,
            _jurisdiction_group_from_id(r.jurisdiction_id),
            r.jurisdiction_name,
            r.jurisdiction_id,
        )
    )
    return rows


def compute_run_timing(
    progress: List[JurisdictionProgress],
    *,
    target_videos: int,
    avg_seconds_per_jurisdiction: Optional[float],
) -> RunTiming:
    total = len(progress)
    completed = sum(1 for p in progress if p.cache_reports >= target_videos)
    avg_per_jurisdiction = avg_seconds_per_jurisdiction or 600.0

    remaining = max(0, total - completed)
    eta_seconds: Optional[int] = None
    if remaining:
        eta_seconds = int(avg_per_jurisdiction * remaining)

    last_activity: Optional[datetime] = None
    for p in progress:
        for dt in (p.cache_last_updated, p.db_last_updated):
            if dt and (last_activity is None or dt > last_activity):
                last_activity = dt

    in_progress_rows = [p for p in progress if p.in_progress]
    active: Optional[JurisdictionProgress] = None
    if in_progress_rows:
        active = max(
            in_progress_rows,
            key=lambda p: (
                p.cache_last_updated or datetime.min.replace(tzinfo=timezone.utc),
                p.in_progress_since or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        if active.est_remaining_seconds:
            tail = max(0, remaining - 1)
            eta_seconds = int(active.est_remaining_seconds + avg_per_jurisdiction * tail)

    return RunTiming(
        completed_jurisdictions=completed,
        total_jurisdictions=total,
        in_progress=active,
        last_activity_utc=last_activity,
        avg_seconds_per_jurisdiction=avg_per_jurisdiction,
        estimated_remaining_seconds=eta_seconds,
    )


def build_progress_and_timing(
    states: List[str],
    cache_root: Path,
    *,
    stale_minutes: int,
    target_videos: int,
) -> Tuple[List[JurisdictionProgress], RunTiming]:
    db_by_jid = fetch_jurisdiction_db_stats(states)
    cache_by_jid = scan_jurisdiction_cache(cache_root, stale_minutes=stale_minutes)

    # Median full-jurisdiction duration from completed places (sum of meeting durations).
    completed_durations: List[float] = []
    for jid, cache in cache_by_jid.items():
        if cache.reports_md >= target_videos and cache.meeting_durations_sec:
            completed_durations.append(sum(cache.meeting_durations_sec[:target_videos]))
    avg_jurisdiction = _median(completed_durations)

    progress = build_jurisdiction_progress(
        db_by_jid,
        cache_by_jid,
        states=states,
        stale_minutes=stale_minutes,
        target_videos=target_videos,
        avg_seconds_per_jurisdiction=avg_jurisdiction,
    )
    timing = compute_run_timing(
        progress,
        target_videos=target_videos,
        avg_seconds_per_jurisdiction=avg_jurisdiction,
    )
    return progress, timing


def _pct(num: int, denom: int) -> str:
    if denom <= 0:
        return "—"
    return f"{100.0 * num / denom:.1f}%"


def render_markdown(
    rollups: Dict[str, StateRollup],
    cache_by_state: Dict[str, CacheCounts],
    states: List[str],
    *,
    cache_root: Path,
    generated_at: str,
    progress: List[JurisdictionProgress],
    timing: RunTiming,
    target_videos: int,
    stale_minutes: int,
) -> str:
    lines: List[str] = []
    lines.append("# Policy & YouTube processing status")
    lines.append("")
    lines.append(f"Generated: **{generated_at}** (UTC)")
    lines.append(f"Cache root: `{cache_root}`")
    lines.append(f"Target per jurisdiction: **{target_videos}** report(s) on disk (`03_reports/`)")
    lines.append(f"In-progress window: last **{stale_minutes}** minutes of cache writes")
    lines.append("")
    lines.append("## Pipeline timing")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Last activity (DB or cache) | {_format_dt(timing.last_activity_utc)} |")
    _priority_set = set(_PRIORITY_STATES)
    _prio_rows = [p for p in progress if p.state_code in _priority_set]
    _prio_total = len(_prio_rows)
    _prio_done = sum(1 for p in _prio_rows if p.cache_reports >= target_videos)
    lines.append(
        f"| Jurisdictions complete (≥{target_videos} reports) — all states shown | "
        f"{timing.completed_jurisdictions:,} / {timing.total_jurisdictions:,} "
        f"({_pct(timing.completed_jurisdictions, timing.total_jurisdictions)}) |"
    )
    lines.append(
        f"| Jurisdictions complete (≥{target_videos} reports) — priority states ⭐ | "
        f"{_prio_done:,} / {_prio_total:,} ({_pct(_prio_done, _prio_total)}) |"
    )
    lines.append(
        f"| Avg time per jurisdiction (completed samples) | "
        f"{_format_duration(timing.avg_seconds_per_jurisdiction)} |"
    )
    lines.append(
        f"| Estimated remaining (all incomplete) | "
        f"{_format_duration(timing.estimated_remaining_seconds)} |"
    )
    if timing.in_progress:
        ip = timing.in_progress
        lines.append(
            f"| **In progress** | **{ip.state_code} — {ip.jurisdiction_name}** "
            f"(`{ip.jurisdiction_id}`) · stage **{ip.stage}** |"
        )
        lines.append(
            f"| In progress since | {_format_dt(ip.in_progress_since)} |"
        )
        lines.append(
            f"| Elapsed (current jurisdiction) | {_format_duration(ip.elapsed_seconds)} |"
        )
        lines.append(
            f"| Est. remaining (current jurisdiction) | "
            f"{_format_duration(ip.est_remaining_seconds)} |"
        )
    else:
        lines.append("| **In progress** | — (no cache writes in stale window) |")
    lines.append("")
    lines.append("## Jurisdiction progress")
    lines.append("")
    lines.append(
        "Sorted by state. **Last updated** is the later of bronze YouTube/text_ai touch "
        "and newest policy-cache file. **Stage** is inferred from on-disk folders."
    )
    lines.append(
        f"**Legend:** `T`=transcripts (`01_transcripts`), `A`=analysis JSON (`02_analysis`), "
        f"`R`=reports (`03_reports`); completion target is **{target_videos}** report(s)."
    )
    lines.append("")
    def _append_progress_table(title: str, rows: List[JurisdictionProgress]) -> None:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(
            "| State | Jurisdiction | Jurisdiction ID | Last updated | Stage | In progress | Elapsed | Est. remaining | "
            f"T(transcripts) / A(analysis) / R(reports) ({target_videos} target) |"
        )
        lines.append(
            "|-------|--------------|-----------------|--------------|-------|:-----------:|--------:|---------------:|"
            "------------------:|"
        )
        if not rows:
            lines.append("| — | — | — | — | — | — | — | — | — |")
            lines.append("")
            return

        for p in rows:
            last = p.cache_last_updated
            if p.db_last_updated and (last is None or p.db_last_updated > last):
                last = p.db_last_updated
            in_prog = "**yes**" if p.in_progress else ""
            lines.append(
                f"| {p.state_code} | {p.jurisdiction_name[:36]} | {p.jurisdiction_id} | {_format_dt(last)} | "
                f"{p.stage} | {in_prog} | {_format_duration(p.elapsed_seconds)} | "
                f"{_format_duration(p.est_remaining_seconds)} | "
                f"{p.cache_transcripts} / {p.cache_analysis} / {p.cache_reports} |"
            )
        lines.append("")

    city_rows = [p for p in progress if _jurisdiction_group_from_id(p.jurisdiction_id) == "city"]
    county_rows = [p for p in progress if _jurisdiction_group_from_id(p.jurisdiction_id) == "county"]
    other_rows = [
        p
        for p in progress
        if _jurisdiction_group_from_id(p.jurisdiction_id) not in ("city", "county")
    ]

    _append_progress_table("Cities", city_rows)
    _append_progress_table("Counties", county_rows)
    if other_rows:
        _append_progress_table("Other Jurisdiction Types", other_rows)
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("| Column | Meaning |")
    lines.append("|--------|---------|")
    lines.append("| **Muni / County / School** | Rows in `public.jurisdiction` by type |")
    lines.append("| **YT places** | Distinct `jurisdiction_id` in `bronze.bronze_event_youtube` |")
    lines.append("| **YT channels** | Distinct `channel_id` in bronze YouTube |")
    lines.append("| **YT videos** | Rows in bronze YouTube |")
    lines.append("| **Bronze transcript** | Join `bronze_event_youtube_transcript` (`has_transcript` or non-empty `raw_text`) |")
    lines.append("| **Disk transcripts** | `01_transcripts/*.json` under policy cache |")
    lines.append("| **Disk analysis** | `02_analysis/*.json` (Part 1 policy JSON) |")
    lines.append("| **Disk reports** | `03_reports/*.md` (Part 2 Smart Brevity) |")
    lines.append("")
    lines.append("## Per-state summary")
    lines.append("")
    lines.append(
        "⭐ = priority dev state. **Report %** = reports ÷ analysis JSON "
        "(falls back to ÷ transcripts). The **Priority subtotal** and **All states total** "
        "rows give completion against each universe."
    )
    lines.append("")
    lines.append(
        "| State | Municipalities | Counties | School dist. | YT places | YT channels | "
        "YT videos | Bronze transcript | Disk T / A / R | Report % |"
    )
    lines.append(
        "|-------|----------------|----------|--------------|-----------|-------------|"
        "----------|-------------------|----------------|----------|"
    )

    priority_set = set(_PRIORITY_STATES)
    has_non_priority = any(st not in priority_set for st in states)
    totals = StateRollup(state_code="ALL")
    priority_totals = StateRollup(state_code="PRIORITY")
    for st in states:
        r = rollups.get(st) or StateRollup(state_code=st)
        c = cache_by_state.get(st) or CacheCounts()
        report_pct = _pct(c.reports_md, c.analysis_json) if c.analysis_json else _pct(c.reports_md, c.transcripts)
        st_label = f"{st} ⭐" if st in priority_set else st
        lines.append(
            f"| {st_label} | {r.municipalities:,} | {r.counties:,} | {r.school_districts:,} | "
            f"{r.youtube_jurisdictions:,} | {r.youtube_channels:,} | {r.youtube_videos:,} | "
            f"{r.bronze_has_transcript:,} ({_pct(r.bronze_has_transcript, r.youtube_videos)}) | "
            f"{c.transcripts:,} / {c.analysis_json:,} / {c.reports_md:,} | {report_pct} |"
        )
        accumulators = [totals] + ([priority_totals] if st in priority_set else [])
        for tot in accumulators:
            tot.municipalities += r.municipalities
            tot.counties += r.counties
            tot.school_districts += r.school_districts
            tot.youtube_jurisdictions += r.youtube_jurisdictions
            tot.youtube_channels += r.youtube_channels
            tot.youtube_videos += r.youtube_videos
            tot.bronze_has_transcript += r.bronze_has_transcript
            tot.cache.transcripts += c.transcripts
            tot.cache.analysis_json += c.analysis_json
            tot.cache.reports_md += c.reports_md
            tot.cache.jurisdictions += c.jurisdictions
            tot.cache.channels += c.channels

    def _total_row(label: str, t: StateRollup) -> str:
        pct = (
            _pct(t.cache.reports_md, t.cache.analysis_json)
            if t.cache.analysis_json
            else _pct(t.cache.reports_md, t.cache.transcripts)
        )
        return (
            f"| {label} | {t.municipalities:,} | {t.counties:,} | {t.school_districts:,} | "
            f"{t.youtube_jurisdictions:,} | {t.youtube_channels:,} | {t.youtube_videos:,} | "
            f"{t.bronze_has_transcript:,} ({_pct(t.bronze_has_transcript, t.youtube_videos)}) | "
            f"{t.cache.transcripts:,} / {t.cache.analysis_json:,} / {t.cache.reports_md:,} | {pct} |"
        )

    if has_non_priority:
        lines.append(_total_row("**Priority subtotal** ⭐", priority_totals))
    lines.append(_total_row("**All states total**" if has_non_priority else "**Total**", totals))
    lines.append("")

    lines.append("## Videos per year (bronze YouTube)")
    lines.append("")
    all_years: Set[str] = set()
    for st in states:
        all_years.update((rollups.get(st) or StateRollup(state_code=st)).videos_by_year.keys())
    year_cols = sorted(
        all_years,
        key=lambda y: (y == "unknown", int(y) if y.isdigit() else 9999),
    )

    header = "| State | " + " | ".join(year_cols) + " |"
    sep = "|-------|" + "|".join(["---:" for _ in year_cols]) + "|"
    lines.append(header)
    lines.append(sep)
    for st in states:
        r = rollups.get(st) or StateRollup(state_code=st)
        cells = [str(r.videos_by_year.get(y, 0)) for y in year_cols]
        lines.append(f"| {st} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Policy cache coverage (on disk)")
    lines.append("")
    lines.append(
        "| State | Cache jurisdictions | Cache channels | Transcripts | Analysis JSON | Reports |"
    )
    lines.append("|-------|--------------------:|---------------:|------------:|--------------:|--------:|")
    for st in states:
        c = cache_by_state.get(st) or CacheCounts()
        lines.append(
            f"| {st} | {c.jurisdictions:,} | {c.channels:,} | {c.transcripts:,} | "
            f"{c.analysis_json:,} | {c.reports_md:,} |"
        )
    lines.append("")

    lines.append("## Channel × year detail (bronze)")
    lines.append("")
    lines.append(
        "Per government YouTube channel: video count and how many have bronze transcripts. "
        "Truncated to 40 rows per state; re-run with SQL for full export."
    )
    lines.append("")
    for st in states:
        r = rollups.get(st) or StateRollup(state_code=st)
        rows = r.channel_year_rows[:40]
        if not rows:
            continue
        lines.append(f"### {st}")
        lines.append("")
        lines.append("| Group | Jurisdiction | Jurisdiction ID | Channel | Year | Videos | w/ transcript |")
        lines.append("|-------|--------------|-----------------|---------|-----:|-------:|----------------:|")
        for row in rows:
            jname = (row.get("jurisdiction_name") or row.get("jurisdiction_id") or "")[:40]
            jid = str(row.get("jurisdiction_id") or "").strip()
            group = _jurisdiction_group_from_id(jid)
            channel_id = str(row.get("channel_id") or "").strip()
            ch_display = channel_id[:24]
            ch = f"[{ch_display}](https://www.youtube.com/channel/{channel_id})" if channel_id else ""
            yr_raw = int(row.get("yr") or 0)
            yr = "unknown" if yr_raw == 0 else str(yr_raw)
            lines.append(
                f"| {group} | {jname} | {jid} | {ch} | {yr} | {int(row.get('videos') or 0):,} | "
                f"{int(row.get('with_transcript') or 0):,} |"
            )
        if len(r.channel_year_rows) > 40:
            lines.append(f"| … | *{len(r.channel_year_rows) - 40} more rows* | | | |")
        lines.append("")

    lines.append("## Channel totals (all years combined)")
    lines.append("")
    lines.append(
        "One row per channel across all years. Truncated to 40 rows per state; "
        "re-run with SQL for full export."
    )
    lines.append("")
    for st in states:
        r = rollups.get(st) or StateRollup(state_code=st)
        rows = r.channel_total_rows[:40]
        if not rows:
            continue
        lines.append(f"### {st}")
        lines.append("")
        lines.append("| Group | Jurisdiction | Jurisdiction ID | Channel | Videos | w/ transcript |")
        lines.append("|-------|--------------|-----------------|---------|-------:|----------------:|")
        for row in rows:
            jname = (row.get("jurisdiction_name") or row.get("jurisdiction_id") or "")[:40]
            jid = str(row.get("jurisdiction_id") or "").strip()
            group = _jurisdiction_group_from_id(jid)
            channel_id = str(row.get("channel_id") or "").strip()
            ch_display = channel_id[:24]
            ch = f"[{ch_display}](https://www.youtube.com/channel/{channel_id})" if channel_id else ""
            lines.append(
                f"| {group} | {jname} | {jid} | {ch} | {int(row.get('videos') or 0):,} | "
                f"{int(row.get('with_transcript') or 0):,} |"
            )
        if len(r.channel_total_rows) > 40:
            lines.append(f"| … | *{len(r.channel_total_rows) - 40} more rows* | | |")
        lines.append("")

    lines.append("## How to refresh")
    lines.append("")
    lines.append("```bash")
    lines.append(
        ".venv/bin/python -m llm.gemini.policy_processing_status_report "
        f"--target-videos {target_videos}"
    )
    lines.append("```")
    lines.append("")
    lines.append("Round-robin pipeline (catalog → captions → analyze):")
    lines.append("")
    lines.append("```bash")
    lines.append("N=2 COOKIES=youtube_cookies.txt ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh each")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    load_dotenv(_REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Policy processing status markdown report")
    parser.add_argument(
        "--states",
        default=",".join(_PRIORITY_STATES),
        help="Comma-separated state codes (default: priority dev states)",
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Include every state present in the database (bronze YouTube), not just "
        "the priority dev states. Priority states are still flagged ⭐ and broken out "
        "as a subtotal.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE,
        help="gemini_transcript_policy cache root",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output markdown path",
    )
    parser.add_argument(
        "--target-videos",
        type=int,
        default=_DEFAULT_TARGET_VIDEOS,
        metavar="N",
        help="Reports on disk needed to mark a jurisdiction complete (default: 2)",
    )
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=_DEFAULT_STALE_MINUTES,
        help="Treat cache writes within this many minutes as in-progress (default: 30)",
    )
    args = parser.parse_args()
    cache_root = args.cache_dir.resolve()

    explicit = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    if args.all_states:
        # Universe of states comes from the database; priority states are always
        # listed first (then every other DB state, alphabetically).
        discovered = set(fetch_states_with_data()) | set(explicit)
        states = list(_PRIORITY_STATES) + sorted(discovered - set(_PRIORITY_STATES))
    else:
        states = explicit

    cache_by_state, _ = scan_policy_cache(cache_root)
    rollups = fetch_db_rollups(states)
    progress, timing = build_progress_and_timing(
        states,
        cache_root,
        stale_minutes=args.stale_minutes,
        target_videos=args.target_videos,
    )

    for st in states:
        if st in cache_by_state:
            rollups[st].cache = cache_by_state[st]

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    md = render_markdown(
        rollups,
        cache_by_state,
        states,
        cache_root=cache_root,
        generated_at=generated_at,
        progress=progress,
        timing=timing,
        target_videos=args.target_videos,
        stale_minutes=args.stale_minutes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote {args.output}")
    print(
        f"Complete: {timing.completed_jurisdictions}/{timing.total_jurisdictions} jurisdictions "
        f"(≥{args.target_videos} reports)"
    )
    print(f"Last activity: {_format_dt(timing.last_activity_utc)}")
    if timing.in_progress:
        ip = timing.in_progress
        print(
            f"In progress: {ip.state_code} {ip.jurisdiction_name} [{ip.stage}] "
            f"elapsed {_format_duration(ip.elapsed_seconds)} "
            f"est {_format_duration(ip.est_remaining_seconds)}"
        )
    print(f"Est. remaining (all): {_format_duration(timing.estimated_remaining_seconds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
