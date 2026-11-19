"""Export meeting transcripts and their Part 1 requests for a Colab Gemma run, from the local warehouse (#511).

Runs on the laptop. For each video it builds the exact Part 1 request the Gemini pipeline would send
(``meeting_transcript_policy.prepare_part1_request``: the same prompt, transcript block, speaker and agenda hints and
official-record context), with the transcript read from ``bronze.bronze_event_youtube_transcript`` only, never from
YouTube. The Colab runner (``llm.gpu.colab_policy_analyze``) only has to run the model on it.

    # the data center meetings since June that aren't analyzed yet, plus 3 already-analyzed ones for the pilot
    python -m llm.gpu.colab_policy_export --data-center-since 2026-06-01 --pilot 3 \\
        --repo-root /home/developer/projects/open-navigator

    # a list of video ids
    python -m llm.gpu.colab_policy_export --videos-file my_videos.txt

The bundle, ``<out>/<export_date>/`` (default ``data/cache/colab_gemma_export/<date>/``)::

    manifest.json            prompt name, sha256 and version; every video with its sizes; what was skipped and why
    videos.txt               the videos to analyze, one id per line
    pilot_videos.txt         --pilot: meetings that already have a Gemini analysis
    requests/<video_id>.json the Part 1 request (``Part1Request.to_json``)
    references/<video_id>.json       --pilot: the existing Gemini analysis
    references/<video_id>.meta.json  --pilot: its run meta (which model made it)

Copy the bundle to the Drive folder ``MyDrive/open-navigator/crawl/policy_export/<export_date>/`` or to the landing
volume ``/Volumes/open_navigator/open_navigator_landing/crawl/policy_export/<export_date>/``.

The database is ``--database-url``, else ``OPEN_NAVIGATOR_DATABASE_URL``, else the local warehouse on
localhost:5433. Neon URLs in the environment are never used. Credentials are never logged.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from llm.prompt_version import prompt_file_sha256, prompt_version_label

_REPO_ROOT = Path(__file__).resolve().parents[5]
LOCAL_DATABASE_URL = "postgresql://postgres:password@localhost:5433/open_navigator"
DB_TRANSCRIPT_PREFIX = "database:"

DATA_CENTER_SQL = """
    SELECT m.video_id, MIN(m.jurisdiction_id) AS jurisdiction_id, MIN(m.state_code) AS state_code,
           MAX(m.meeting_date) AS meeting_date
    FROM public.data_center_meeting_mention m
    WHERE m.meeting_date BETWEEN %(since)s AND %(until)s
      AND m.video_id IS NOT NULL
      AND {analyzed} EXISTS (SELECT 1 FROM public.event_meeting e WHERE e.video_id = m.video_id)
    GROUP BY m.video_id
    ORDER BY MAX(m.meeting_date) DESC, m.video_id
"""
VIDEO_GEO_SQL = """
    SELECT DISTINCT ON (video_id) video_id, jurisdiction_id, state_code
    FROM event_youtube_with_jurisdiction
    WHERE video_id = ANY(%(ids)s) AND jurisdiction_id IS NOT NULL
    ORDER BY video_id, last_updated DESC NULLS LAST
"""


# ------------------------------------------------------------------------------------------------- plain helpers
def resolve_database_url(explicit: str | None = None) -> str:
    """``explicit``, else ``OPEN_NAVIGATOR_DATABASE_URL``, else the local warehouse. Never a Neon variable."""
    return (explicit or os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or LOCAL_DATABASE_URL).strip()


def database_label(url: str) -> str:
    """``host:port/db`` with no user or password, for logs and the manifest."""
    p = urlparse(url)
    return f"{p.hostname}:{p.port or 5432}{p.path}"


def read_video_ids(text: str) -> list[str]:
    """Video ids from a file's text: one per line or comma separated; ``#`` comments and duplicates dropped."""
    out: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for part in line.split(","):
            vid = part.strip()
            if vid and vid not in out:
                out.append(vid)
    return out


def transcript_text(request_json: dict[str, Any]) -> str:
    """The plain transcript (caption text joined) of an exported request: what quotes are checked against."""
    yt = (request_json.get("transcript_meta") or {}).get("youtube") or {}
    raw = (yt.get("raw_text") or "").strip()
    if raw:
        return raw
    return " ".join(str(s.get("text") or "").strip() for s in yt.get("segments") or [] if s.get("text"))


@dataclass
class Target:
    video_id: str
    jurisdiction_id: str
    state_code: str


@dataclass
class ExportResult:
    bundle_dir: Path
    exported: list[str] = field(default_factory=list)
    pilot: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


# ----------------------------------------------------------------------------------------------- database reads
def _query(database_url: str, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    data_schema = (os.getenv("API_DB_SCHEMA") or "gold").strip() or "gold"
    search_path = data_schema if data_schema == "public" else f"{data_schema},public"
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET search_path TO {search_path}")
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def data_center_targets(database_url: str, since: str, until: str, *, analyzed: bool = False) -> list[Target]:
    """Data center meetings in a date range: not yet in ``public.event_meeting`` (or, ``analyzed=True``, already
    there: the pilot's candidates)."""
    sql = DATA_CENTER_SQL.format(analyzed="" if analyzed else "NOT")
    rows = _query(database_url, sql, {"since": since, "until": until})
    return [Target(r["video_id"], r["jurisdiction_id"] or "", (r["state_code"] or "").upper()) for r in rows]


def targets_for_ids(database_url: str, video_ids: list[str]) -> tuple[list[Target], dict[str, str]]:
    """Jurisdiction and state for each id (from ``event_youtube_with_jurisdiction``); ids it lacks are skipped."""
    rows = {r["video_id"]: r for r in _query(database_url, VIDEO_GEO_SQL, {"ids": video_ids})}
    targets, skipped = [], {}
    for vid in video_ids:
        r = rows.get(vid)
        if r is None:
            skipped[vid] = "no jurisdiction for this video in event_youtube_with_jurisdiction"
        else:
            targets.append(Target(vid, r["jurisdiction_id"], (r["state_code"] or "").upper()))
    return targets, skipped


# ------------------------------------------------------------------------------------------- building requests
def _namespace(target: Target, database_url: str, repo_root: Path) -> argparse.Namespace:
    """The analyze backlog's settings for this video's jurisdiction, reading the policy and scrape caches under
    ``repo_root`` (so a worktree can export against the main checkout's caches)."""
    from llm.gemini.analyze_backlog import JurisdictionPlan, build_pipeline_namespace
    from llm.gemini.meeting_transcript_policy import resolve_scrape_cache_dir

    plan = JurisdictionPlan(jurisdiction_id=target.jurisdiction_id, state_code=target.state_code,
                            pending=0, newest_pending=None)
    ns = build_pipeline_namespace(plan, model="colab_hf", database_url=database_url, limit=None)
    ns.output_dir = repo_root / "data" / "cache" / "gemini_transcript_policy"
    ns.scraped_cache_dir = str(resolve_scrape_cache_dir(target.jurisdiction_id, state=target.state_code or "AL",
                                                        repo_root=repo_root))
    ns.prompt_file = repo_root / "prompts" / "policy_analysis_part_1.md"
    ns.video_id = target.video_id
    ns.use_db_transcript = True
    ns.diarize = False
    # build_request has already read the transcript from bronze_event_youtube_transcript; the has_transcript flag
    # can lag the row, so it must not hide the video.
    ns.only_has_transcript = False
    return ns


def build_request(target: Target, database_url: str, repo_root: Path) -> tuple[Any | None, str]:
    """``(Part1Request, "")`` for one video, or ``(None, reason)``. Refuses any transcript not from the warehouse."""
    from llm.gemini.meeting_transcript_policy import load_speaker_context, prepare_part1_request, select_bronze_videos
    from llm.gemini.transcript_cache_paths import resolve_canonical_jurisdiction_id
    from llm.gemini.transcript_db import fetch_db_transcript

    if not target.jurisdiction_id:
        return None, "no jurisdiction_id"
    if fetch_db_transcript(database_url, target.video_id) is None:
        return None, "no usable row in bronze_event_youtube_transcript"
    ns = _namespace(target, database_url, repo_root)
    jid = resolve_canonical_jurisdiction_id(target.jurisdiction_id)
    try:
        videos = select_bronze_videos(ns, jid)
    except SystemExit as exc:
        return None, f"not in event_youtube_with_jurisdiction for {jid}: {exc}"
    video = next((v for v in videos if v.video_id == target.video_id), None)
    if video is None:
        return None, f"not in event_youtube_with_jurisdiction for {jid}"
    speaker_hints, known = load_speaker_context(ns, jid)
    request = prepare_part1_request(video, ns, speaker_hints=speaker_hints, known=known)
    if request is None:
        return None, "prepare_part1_request skipped it (see log)"
    source = str(((request.transcript_meta or {}).get("youtube") or {}).get("transcript_source") or "")
    if not source.startswith(DB_TRANSCRIPT_PREFIX):
        return None, f"transcript did not come from the warehouse ({source or 'unknown'})"
    request.model = ""   # set from the Colab run's meta on import
    return request, ""


def existing_reference(request: Any) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The meeting's saved Gemini analysis and its meta, when it has one with at least one item."""
    from llm.gemini.compare_models import _reference_analysis
    from llm.gemini.transcript_cache_paths import meta_path_for_analysis, resolve_analysis_path

    analysis = _reference_analysis(request)
    if not analysis or analysis.get("_error"):
        return None
    if not (analysis.get("decisions") or analysis.get("uncontested_items")):
        return None
    video = request.video
    path = resolve_analysis_path(request.out_dir, video.jurisdiction_id, video_id=video.video_id,
                                 title=video.title or "", event_date=video.event_date,
                                 state_code=request.state_code, channel_id=getattr(video, "channel_id", None))
    meta: dict[str, Any] = {}
    meta_path = meta_path_for_analysis(path) if path else None
    if meta_path and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    slim = {k: meta.get(k) for k in ("video_id", "gemini_model", "generation_source", "prompt_name",
                                     "prompt_sha256", "generated_at", "usage") if k in meta}
    return analysis, slim


# ------------------------------------------------------------------------------------------------------ export
def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def request_record(request: Any, prompt_sha: str | None) -> dict[str, Any]:
    data = request.to_json()
    data["prompt_name"] = Path(request.prompt_path).stem
    data["prompt_sha256"] = prompt_sha
    return data


def export_bundle(targets: Iterable[Target], pilot_candidates: Iterable[Target], *, bundle_dir: Path,
                  database_url: str, repo_root: Path, pilot: int = 0, limit: int | None = None,
                  skipped: dict[str, str] | None = None, build=build_request,
                  reference=existing_reference) -> ExportResult:
    """Write the bundle (see the module docstring). A video already in ``requests/`` is not rebuilt."""
    prompt_path = repo_root / "prompts" / "policy_analysis_part_1.md"
    prompt_sha = prompt_file_sha256(prompt_path)
    result = ExportResult(bundle_dir=bundle_dir, skipped=dict(skipped or {}))
    sizes: dict[str, dict[str, Any]] = {}

    def one(target: Target) -> dict[str, Any] | None:
        out = bundle_dir / "requests" / f"{target.video_id}.json"
        if out.is_file():
            return json.loads(out.read_text(encoding="utf-8"))
        try:
            request, why = build(target, database_url, repo_root)
        except Exception as exc:  # noqa: BLE001 - one bad video never stops the export
            request, why = None, f"{type(exc).__name__}: {str(exc)[:200]}"
        if request is None:
            result.skipped[target.video_id] = why
            logger.warning("skip {}: {}", target.video_id, why)
            return None
        data = request_record(request, prompt_sha)
        data["_reference"] = reference(request) if target in pilot_set else None
        return data

    pilot_set: list[Target] = list(pilot_candidates) if pilot > 0 else []
    for target in targets:
        if limit is not None and len(result.exported) >= limit:
            break
        data = one(target)
        if data is None:
            continue
        data.pop("_reference", None)
        _write_json(bundle_dir / "requests" / f"{target.video_id}.json", data)
        result.exported.append(target.video_id)
        sizes[target.video_id] = _sizes(data, target)
        logger.success("exported {} ({:,} chars of prompt)", target.video_id, len(data.get("user_message") or ""))

    for target in pilot_set:
        if len(result.pilot) >= pilot:
            break
        data = one(target)
        if data is None:
            continue
        ref = data.pop("_reference", None)
        if ref is None:
            ref_file = bundle_dir / "references" / f"{target.video_id}.json"
            if not ref_file.is_file():
                result.skipped.setdefault(target.video_id, "pilot: no usable Gemini analysis on disk")
                continue
        else:
            analysis, meta = ref
            _write_json(bundle_dir / "references" / f"{target.video_id}.json", analysis)
            _write_json(bundle_dir / "references" / f"{target.video_id}.meta.json", meta)
        _write_json(bundle_dir / "requests" / f"{target.video_id}.json", data)
        result.pilot.append(target.video_id)
        sizes[target.video_id] = _sizes(data, target)
        logger.success("pilot {} (has a Gemini analysis)", target.video_id)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "videos.txt").write_text("".join(f"{v}\n" for v in result.exported), encoding="utf-8")
    if pilot > 0:
        (bundle_dir / "pilot_videos.txt").write_text("".join(f"{v}\n" for v in result.pilot), encoding="utf-8")
    _write_json(bundle_dir / "manifest.json", {
        "export_date": bundle_dir.name,
        "database": database_label(database_url),
        "prompt_name": prompt_path.stem,
        "prompt_file": "prompts/policy_analysis_part_1.md",
        "prompt_sha256": prompt_sha,
        "prompt_version": prompt_version_label(prompt_path.stem, prompt_sha),
        "transcript_source": "bronze.bronze_event_youtube_transcript (no YouTube fetch)",
        "video_count": len(result.exported),
        "pilot_count": len(result.pilot),
        "videos": sizes,
        "skipped": result.skipped,
    })
    return result


def _sizes(data: dict[str, Any], target: Target) -> dict[str, Any]:
    meta = data.get("transcript_meta") or {}
    return {
        "jurisdiction_id": target.jurisdiction_id,
        "state_code": target.state_code,
        "title": (data.get("video") or {}).get("title"),
        "event_date": (data.get("video") or {}).get("event_date"),
        "segment_count": meta.get("segment_count"),
        "transcript_chars": len(transcript_text(data)),
        "prompt_chars": len(data.get("user_message") or ""),
    }


def folder_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m llm.gpu.colab_policy_export",
                                description="Export Part 1 requests from the local warehouse for a Colab Gemma run.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--videos-file", type=Path, help="video ids, one per line (or comma separated)")
    src.add_argument("--data-center-since", help="data center meetings from this date (YYYY-MM-DD) not yet in "
                     "public.event_meeting")
    p.add_argument("--until", default=None, help="last meeting date with --data-center-since (default today)")
    p.add_argument("--pilot", type=int, default=0, help="also export N data center meetings that already have a "
                   "Gemini analysis, with that analysis as the reference")
    p.add_argument("--limit", type=int, default=None, help="most videos to export (pilot not counted)")
    p.add_argument("--repo-root", type=Path, default=_REPO_ROOT,
                   help="checkout whose prompts/ and data/cache/ are read (default this one)")
    p.add_argument("--out", type=Path, default=None,
                   help="bundle root (default <repo-root>/data/cache/colab_gemma_export)")
    p.add_argument("--export-date", default=None, help="bundle folder name, YYYY-MM-DD (default today)")
    p.add_argument("--database-url", default=None, help="default OPEN_NAVIGATOR_DATABASE_URL, else localhost:5433")
    return p


def main(argv: list[str] | None = None) -> int:
    from llm.gpu.colab_io import check_run_date

    args = build_parser().parse_args(argv)
    database_url = resolve_database_url(args.database_url)
    repo_root = args.repo_root.resolve()
    export_date = check_run_date(args.export_date or date.today().isoformat())
    bundle_dir = (args.out or repo_root / "data" / "cache" / "colab_gemma_export") / export_date
    until = args.until or date.today().isoformat()
    logger.info("export from {} to {}", database_label(database_url), bundle_dir)
    skipped: dict[str, str] = {}
    if args.videos_file:
        targets, skipped = targets_for_ids(database_url, read_video_ids(args.videos_file.read_text(encoding="utf-8")))
    else:
        targets = data_center_targets(database_url, args.data_center_since, until)
    # Pilot: data center meetings of any date that are already analyzed (the reference is their Gemini analysis).
    pilot_candidates = (data_center_targets(database_url, "2000-01-01", until, analyzed=True) if args.pilot else [])
    if args.pilot:
        logger.info("{} analyzed data center meetings are pilot candidates", len(pilot_candidates))
    result = export_bundle(targets, pilot_candidates, bundle_dir=bundle_dir, database_url=database_url,
                           repo_root=repo_root, pilot=args.pilot, limit=args.limit, skipped=skipped)
    size = folder_bytes(bundle_dir)
    logger.success("bundle {}: {} videos, {} pilot, {} skipped, {:.1f} MB", bundle_dir, len(result.exported),
                   len(result.pilot), len(result.skipped), size / 1e6)
    return 0 if result.exported or result.pilot else 1


if __name__ == "__main__":
    sys.exit(main())
