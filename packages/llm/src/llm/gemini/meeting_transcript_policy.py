#!/usr/bin/env python3
"""
Policy analysis via **AI Studio API** + **text transcript** (max free volume).

Pipeline:
1. Load speaker hints from ``_contact_images/contacts.json`` (optional).
2. Fetch YouTube captions (free) via ``youtube_transcript_api``.
3. Optional **diarization post-processing** on local Opus/audio (WhisperX + pyannote).
4. Call ``gemini-2.5-flash-lite`` (or ``GEMINI_FLASH_LITE_MODEL``) with ``policy_analysis_part_1.md``.
5. Optional ``--run-part-2``: same API with ``policy_analysis_part_2.md`` → ``*_report.md``.

This does **not** open gemini.google.com or send video to the browser UI.

Full pipeline (local captions → JSON + Markdown)::

    python -m llm.gemini.meeting_transcript_policy \\
        --from-bronze --jurisdiction-id municipality_0177256 --state AL \\
        --use-local-transcript --run-part-2 --limit 5

Markdown only from existing analysis JSON::

    python -m llm.gemini.meeting_transcript_policy \\
        --part-2-only --jurisdiction-id municipality_0177256 --limit 5

Examples::

    export GEMINI_API_KEY=...   # from https://aistudio.google.com/apikey

    # YouTube captions only (no GPU, no HF token)
    python -m llm.gemini.meeting_transcript_policy \\
        --video-id ajsME66iXbY \\
        --jurisdiction-id municipality_0177256 \\
        --state AL

    # Merge WhisperX speaker labels into caption lines, then Flash-Lite
    python -m llm.gemini.meeting_transcript_policy \\
        --video-id ajsME66iXbY \\
        --audio-path data/cache/youtube_audio/al/tuscaloosa/ajsME66iXbY.opus \\
        --diarize

    # Transcript only (no API call)
    python -m llm.gemini.meeting_transcript_policy --video-id ajsME66iXbY --transcript-only

    # Northport: N newest meetings that already have bronze captions → analyze (Part 1 + 2)
    python -m llm.gemini.meeting_transcript_policy \\
        --newest 5 --jurisdiction-id municipality_0155200 --state AL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _db_events_enabled(args: "argparse.Namespace") -> bool:
    """Whether to stamp analysis/report outcomes onto bronze_event_youtube."""
    if getattr(args, "no_db_events", False):
        return False
    return os.getenv("POLICY_RECORD_DB_EVENTS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _rel_to_repo(path: Path) -> str:
    """Repo-relative path string, falling back to the absolute path."""
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _record_policy_event_safe(
    video_id: str,
    *,
    stage: str,
    ok: bool,
    path: Optional[Path] = None,
    error: Optional[str] = None,
    database_url: Optional[str] = None,
) -> None:
    """Thin best-effort wrapper around ``record_policy_event`` (never raises)."""
    if not (video_id or "").strip():
        return
    try:
        from llm.gemini.persist_policy_analysis_bronze import record_policy_event

        record_policy_event(
            video_id,
            stage=stage,
            ok=ok,
            path=_rel_to_repo(path) if path is not None else None,
            error=error,
            database_url_override=database_url or _database_url(None),
        )
    except Exception as exc:  # tracking must never break the pipeline
        logger.warning("policy event record skipped for {} ({}): {}", video_id, stage, exc)

from llm.gemini.browser_policy_analysis import (  # noqa: E402
    DEFAULT_JURISDICTION_ID,
    DEFAULT_PROMPT_PART_1,
    DEFAULT_PROMPT_PART_2,
    GeminiRunCapture,
    VideoRow,
    _database_url,
    _normalize_part1_analysis,
    _output_stem,
    _part1_json_ok,
    _sanitize_tag,
    _split_gemini_documents,
    _write_diagrams_md,
    _write_manifest,
    build_part2_message,
    build_user_message,
    fetch_videos,
)
from llm.gemini.agenda_presenter_hints import (  # noqa: E402
    enrich_uncontested_media_anchors,
    format_agenda_presenter_hints_block,
    segment_agenda_blocks,
)
from llm.gemini.diarize_postprocess import (  # noqa: E402
    diarize_audio_whisperx,
    format_diarized_transcript,
    merge_caption_speakers,
)
from llm.gemini.genai_text_client import (  # noqa: E402
    GenAIDailyQuotaGiveUp,
    GenAIModelUnavailableGiveUp,
    GenAIServerOverloadGiveUp,
    GenAITransientGiveUp,
    call_gemini_text,
    default_flash_lite_model,
    ensure_valid_gemini_api_key,
    extract_json_from_model_text,
)
from llm.gemini.speaker_hints import (  # noqa: E402
    format_speaker_hints_block,
    known_speaker_names,
    label_segments_from_contacts,
    load_contacts_bundle,
)
from llm.gemini.transcript_cache_paths import (  # noqa: E402
    _sanitize_audio_title,
    analysis_cache_path,
    ensure_jurisdiction_layout,
    jurisdiction_root,
    load_local_transcript_payload,
    meta_path_for_analysis,
    report_cache_path,
    report_path_for_analysis,
    resolve_analysis_path,
    resolve_transcript_cache_path,
    run_diagrams_path,
    run_meta_path,
    transcript_cache_path,
)
from llm.gemini.transcript_fetch import fetch_youtube_transcript  # noqa: E402

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
DEFAULT_YOUTUBE_AUDIO_ROOT = _REPO_ROOT / "data" / "cache" / "youtube_audio"


def coalesce_part1_analysis(data: Any) -> Dict[str, Any]:
    """
    Use top-level Part 1 JSON, or hoist ``parsed_fragment`` from a parse-error stub.

    Gemini often wraps JSON in markdown fences; the model may also return ``meeting`` with
    empty ``decisions[]`` for promos or bad captions (still usable for a thin Part 2 report).
    """
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("meeting"), dict):
        return data
    frag = data.get("parsed_fragment")
    if isinstance(frag, dict) and isinstance(frag.get("meeting"), dict):
        out = dict(frag)
        for key in ("_error", "document1_excerpt"):
            if data.get(key) and not out.get(key):
                out[key] = data[key]
        return out
    excerpt = data.get("document1_excerpt")
    if isinstance(excerpt, str) and excerpt.strip():
        from llm.gemini.genai_text_client import extract_json_from_model_text

        recovered = extract_json_from_model_text(excerpt)
        if isinstance(recovered, dict) and isinstance(recovered.get("meeting"), dict):
            return recovered
    return data


def analysis_ready_for_part2(data: Any) -> bool:
    """True when Part 2 can run (needs ``meeting``; decisions may be empty)."""
    co = coalesce_part1_analysis(data)
    return isinstance(co, dict) and isinstance(co.get("meeting"), dict)


def _policy_state_code(args: argparse.Namespace) -> Optional[str]:
    return (getattr(args, "state", None) or "").strip().upper() or None

# City of Tuscaloosa @TuscaloosaCityAL — matches download_tuscaloosa_city_meeting_audio.py
TUSCALOOSA_CHANNEL_ID = "UC74dczS0B3MhDhUHp2ZGRPA"
TUSCALOOSA_CHANNEL_TITLE = "City of Tuscaloosa"
TUSCALOOSA_STATE = "AL"


def tuscaloosa_youtube_audio_dir(
    audio_root: Path = DEFAULT_YOUTUBE_AUDIO_ROOT,
) -> Path:
    """``…/youtube_audio/al/city_of_tuscaloosa_uc74dczs0b3mhdhuhp2zgrpa`` (117+ Opus files)."""
    from scrapers.youtube.download_audio_to_drive import channel_cache_dir_name

    dir_name = channel_cache_dir_name(TUSCALOOSA_CHANNEL_TITLE, TUSCALOOSA_CHANNEL_ID)
    return audio_root / TUSCALOOSA_STATE.lower() / dir_name


def resolve_scrape_cache_dir(
    jurisdiction_id: str,
    *,
    state: str = "AL",
    repo_root: Optional[Path] = None,
    explicit: Optional[Path] = None,
) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    from llm.gemini.transcript_cache_paths import cache_type_segment

    root = repo_root or _REPO_ROOT
    st = (state or "AL").strip().upper()
    jid = (jurisdiction_id or "").strip()
    segment = cache_type_segment(jid)
    return root / "data/cache/scraped_meetings" / st / segment / jid


def find_local_audio(
    video_id: str,
    *,
    audio_root: Path,
    title: Optional[str] = None,
    event_date: Optional[str] = None,
    search_dirs: Optional[List[Path]] = None,
) -> Optional[Path]:
    """
    Resolve local Opus/MP3 for a YouTube row.

    Tuscaloosa downloads use ``YYYY-MM-DD_<sanitized title>.opus`` under the channel
    folder (not ``<video_id>.opus``). Pass ``title`` / ``event_date`` from transcript JSON
    or bronze, or set ``search_dirs`` to ``tuscaloosa_youtube_audio_dir()``.
    """
    vid = (video_id or "").strip()
    roots: List[Path] = []
    for d in search_dirs or []:
        p = Path(d)
        if p.is_dir():
            roots.append(p)
    if not roots:
        roots = [audio_root]

    def _glob(root: Path, pattern: str) -> List[Path]:
        if root == audio_root:
            return [p for p in root.rglob(pattern) if p.is_file()]
        return [p for p in root.glob(pattern) if p.is_file()]

    safe_title = _sanitize_audio_title(title or "")
    ed = (event_date or "").strip()[:10] if event_date else ""

    for root in roots:
        if safe_title and ed:
            exact = root / f"{ed}_{safe_title}.opus"
            if exact.is_file():
                return exact
        if safe_title:
            hits = _glob(root, f"*{safe_title}.opus")
            if hits:
                if ed:
                    dated = [h for h in hits if ed in h.name]
                    if dated:
                        return sorted(dated, key=lambda p: len(p.name))[0]
                return sorted(hits, key=lambda p: len(p.name))[0]

    if not vid:
        return None
    patterns = (f"{vid}.opus", f"{vid}.mp3", f"{vid}.m4a", f"{vid}.webm", f"*{vid}*.opus")
    for root in roots:
        for pat in patterns:
            for hit in _glob(root, pat):
                return hit
    return None


def resolve_audio_path(
    video: VideoRow,
    *,
    audio_root: Path,
    explicit: Optional[Path] = None,
) -> Optional[Path]:
    if explicit is not None and explicit.is_file():
        return explicit
    rel = (video.audio_file_path or "").strip()
    if rel:
        candidate = audio_root / rel
        if candidate.is_file():
            return candidate
    return find_local_audio(
        video.video_id,
        audio_root=audio_root,
        title=video.title,
        event_date=str(video.event_date) if video.event_date else None,
    )


def load_speaker_context(
    args: argparse.Namespace,
    jurisdiction_id: str,
) -> tuple[str, List[Dict[str, str]]]:
    if args.no_speaker_hints:
        return "", []
    cache_dir = resolve_scrape_cache_dir(
        jurisdiction_id,
        state=args.state,
        explicit=Path(args.scraped_cache_dir) if args.scraped_cache_dir else None,
    )
    try:
        bundle = load_contacts_bundle(cache_dir)
        logger.info("Loaded speaker hints from {}", cache_dir)
        return format_speaker_hints_block(bundle), known_speaker_names(bundle)
    except FileNotFoundError as exc:
        logger.warning("{}", exc)
        return "", []


def inject_transcript_into_prompt(prompt_text: str, transcript_block: str) -> str:
    block = transcript_block.strip()
    if re.search(r"<transcript>.*?</transcript>", prompt_text, flags=re.DOTALL | re.IGNORECASE):
        return re.sub(
            r"<transcript>.*?</transcript>",
            f"<transcript>\n{block}\n</transcript>",
            prompt_text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()
    return f"{prompt_text.strip()}\n\n<transcript>\n{block}\n</transcript>"


def build_transcript_block(
    *,
    speaker_hints: str,
    segments: List[Dict[str, Any]],
    source_note: str,
    agenda_hints: str = "",
    agenda_legislation_hints: str = "",
) -> str:
    body = format_diarized_transcript(segments)
    parts = [speaker_hints]
    if agenda_hints.strip():
        parts.append(agenda_hints.strip())
    if agenda_legislation_hints.strip():
        parts.append(agenda_legislation_hints.strip())
    parts.append(f"=== TRANSCRIPT SOURCE ===\n{source_note}\n\n=== TRANSCRIPT ===\n{body}\n")
    return "\n".join(parts)


def save_transcript_policy_output(
    output_dir: Path,
    video: VideoRow,
    *,
    model: str,
    response_text: str,
    prompt_path: Path,
    transcript_meta: Dict[str, Any],
    geocode_places: bool = False,
    agenda_blocks: Optional[List[Dict[str, Any]]] = None,
    enrich_legislation: bool = True,
    persist_bronze: bool = False,
    database_url: Optional[str] = None,
    state_code: Optional[str] = None,
    record_db_events: bool = False,
    defer_report_event: bool = False,
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jid = video.jurisdiction_id
    geo = {
        "state_code": state_code,
        "channel_id": getattr(video, "channel_id", None),
        "video_id": video.video_id,
    }
    jid_root = jurisdiction_root(output_dir, jid, **geo)
    ensure_jurisdiction_layout(jid_root)
    title = video.title or ""
    event_date = video.event_date
    prompt_name = prompt_path.stem
    rel = lambda p: str(p.relative_to(_REPO_ROOT))

    analysis_path = analysis_cache_path(
        output_dir, jid, title=title, event_date=event_date, **geo
    )
    report_md_path = report_cache_path(
        output_dir, jid, title=title, event_date=event_date, **geo
    )
    meta_path = run_meta_path(output_dir, jid, title=title, event_date=event_date, **geo)
    diagrams_md_path = run_diagrams_path(
        output_dir, jid, title=title, event_date=event_date, **geo
    )

    parsed, markdown_docs = _split_gemini_documents(response_text)
    if parsed is None:
        parsed = extract_json_from_model_text(response_text)

    if not _part1_json_ok(parsed):
        if isinstance(parsed, dict) and isinstance(parsed.get("meeting"), dict):
            analysis_payload = _normalize_part1_analysis(parsed)
            analysis_payload["_error"] = str(
                parsed.get("_error")
                or "No decisions or uncontested items extracted from transcript."
            )[:2000]
            json_parsed = False
        else:
            analysis_payload = {
                "_error": "Could not parse meeting JSON (expected meeting + decisions[])",
                "document1_excerpt": response_text[:4000],
                "parsed_fragment": parsed,
            }
            json_parsed = False
    else:
        analysis_payload = enrich_uncontested_media_anchors(
            _normalize_part1_analysis(parsed),
            video_url=video.video_url or "",
        )
        if enrich_legislation:
            from llm.gemini.legislation_analysis import enrich_part1_legislation

            analysis_payload = enrich_part1_legislation(
                analysis_payload, agenda_blocks=agenda_blocks
            )
        if geocode_places:
            from llm.gemini.enrich_analysis_places import enrich_places_in_analysis

            analysis_payload = enrich_places_in_analysis(
                analysis_payload,
                jurisdiction_id=jid,
                geocode=True,
            )
        json_parsed = True

    analysis_path.write_text(
        json.dumps(analysis_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if record_db_events:
        analysis_error = analysis_payload.get("_error") if isinstance(analysis_payload, dict) else None
        _record_policy_event_safe(
            video.video_id,
            stage="analysis",
            ok=not analysis_error,
            path=analysis_path,
            error=str(analysis_error) if analysis_error else None,
            database_url=database_url,
        )

    if persist_bronze and json_parsed and not analysis_payload.get("_error"):
        from llm.gemini.persist_policy_analysis_bronze import (
            persist_policy_analysis_bronze,
            resolve_event_id_for_video,
        )

        db_url = database_url or _database_url(None)
        event_id = resolve_event_id_for_video(db_url, video.video_id)
        if event_id:
            persist_policy_analysis_bronze(
                analysis_payload,
                video_id=video.video_id,
                source_event_id=event_id,
                source_ai_model=model,
                database_url_override=db_url,
                analysis_cache_path=str(analysis_path.resolve()),
            )
        else:
            logger.warning(
                "persist-bronze skipped for {} — no bronze.bronze_event_youtube row",
                video.video_id,
            )

    report_body = markdown_docs[0] if markdown_docs else ""
    if report_body:
        report_md_path.write_text(report_body + "\n", encoding="utf-8")
    else:
        report_md_path.write_text(
            "# Report unavailable\n\n"
            "Part 1 JSON-only run; use ``policy_analysis_part_2`` separately if needed.\n",
            encoding="utf-8",
        )

    if record_db_events and not defer_report_event:
        _record_policy_event_safe(
            video.video_id,
            stage="report",
            ok=bool(report_body),
            path=report_md_path if report_body else None,
            error=None if report_body else "No Part 2 report markdown produced (Part 1 JSON-only run)",
            database_url=database_url,
        )

    has_diagrams = False
    if json_parsed and isinstance(analysis_payload, dict):
        has_diagrams = _write_diagrams_md(analysis_payload, diagrams_md_path)

    tx_path = resolve_transcript_cache_path(
        jid_root,
        video_id=video.video_id,
        title=title,
        event_date=event_date,
    )
    files: Dict[str, str] = {
        "meta_json": rel(meta_path),
        "analysis_json": rel(analysis_path),
        "report_md": rel(report_md_path),
        "transcript_json": rel(tx_path) if tx_path else "",
    }
    if has_diagrams:
        files["diagrams_md"] = rel(diagrams_md_path)

    meta_payload: Dict[str, Any] = {
        "video_id": video.video_id,
        "video_url": video.video_url,
        "title": video.title,
        "jurisdiction_id": video.jurisdiction_id,
        "prompt_name": prompt_name,
        "prompt_file": str(prompt_path.relative_to(_REPO_ROOT)),
        "gemini_model": model,
        "generation_source": "ai_studio_api",
        "pipeline": "transcript_flash_lite",
        "generated_at": ts,
        "response_chars": len(response_text),
        "json_parsed": json_parsed,
        "has_diagrams_md": has_diagrams,
        "transcript": transcript_meta,
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
        "gemini_model": model,
        "generation_source": "ai_studio_api",
        "pipeline": "transcript_flash_lite",
        "generated_at": ts,
        "json_parsed": json_parsed,
        "files": files,
    }
    _write_manifest(jid_root, manifest_record)
    logger.info("Wrote {}", analysis_path)
    return analysis_path


def _recording_title_for_analysis(analysis_path: Optional[Path]) -> str:
    if analysis_path is None:
        return ""
    meta_path = meta_path_for_analysis(analysis_path)
    if not meta_path.is_file():
        return ""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    title = meta.get("title")
    if title:
        return str(title).strip()
    transcript = meta.get("transcript")
    if isinstance(transcript, dict) and transcript.get("title"):
        return str(transcript["title"]).strip()
    return ""


def generate_part2_markdown(
    analysis: Dict[str, Any],
    args: argparse.Namespace,
    api_key: str,
    *,
    analysis_path: Optional[Path] = None,
) -> str:
    """Resident-facing Markdown via ``policy_analysis_part_2.md`` + Part 1 JSON."""
    prompt_path = Path(args.prompt_part_2).resolve()
    user_message = build_part2_message(
        prompt_path.read_text(encoding="utf-8"),
        analysis,
        recording_title=_recording_title_for_analysis(analysis_path),
    )
    model = (args.part_2_model or args.model or default_flash_lite_model()).strip()
    logger.info("Part 2: calling {} ({} chars in)", model, len(user_message))
    result = call_gemini_text(
        api_key=api_key,
        model=model,
        user_text=user_message,
        system_instruction=args.system_instruction,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    return result.text.strip()


def write_part2_report(
    analysis_path: Path,
    markdown: str,
    *,
    validate_mermaid: bool = True,
) -> Path:
    from llm.gemini.mermaid_diagrams import repair_mermaid_fences_in_markdown
    from llm.gemini.part2_report_normalize import strip_one_big_thing_lines

    report_path = report_path_for_analysis(analysis_path)
    body = strip_one_big_thing_lines(repair_mermaid_fences_in_markdown(markdown))
    report_path.write_text(body + "\n", encoding="utf-8")
    logger.info("Wrote {}", report_path)
    if validate_mermaid:
        _log_mermaid_validation(report_path, body)
    return report_path


def _log_mermaid_validation(report_path: Path, body: str) -> None:
    try:
        from llm.gemini.mermaid_validate import (
            format_report,
            validate_markdown_text,
            write_errors_sidecar,
        )
    except ImportError:
        return
    try:
        report = validate_markdown_text(body, path=report_path)
    except RuntimeError as exc:
        logger.warning("Mermaid validation skipped for {}: {}", report_path.name, exc)
        return
    sidecar = report_path.with_name(report_path.stem + ".mermaid-errors.json")
    if report.ok:
        if sidecar.is_file():
            sidecar.unlink()
        logger.info("Mermaid OK ({} diagram(s)) {}", report.fence_count, report_path.name)
        return
    logger.warning("Mermaid validation failed for {}:\n{}", report_path.name, format_report(report))
    write_errors_sidecar(report, sidecar)
    logger.info("Wrote {}", sidecar)


def run_part2_for_analysis_file(
    analysis_path: Path,
    args: argparse.Namespace,
    api_key: str,
) -> Optional[Path]:
    try:
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Skipping {} — unreadable: {}", analysis_path.name, exc)
        return None
    if not analysis_ready_for_part2(data):
        logger.error("Skipping {} — not valid Part 1 JSON", analysis_path.name)
        return None
    data = coalesce_part1_analysis(data)
    if data.get("_error") or not _part1_json_ok(data):
        logger.warning(
            "Part 1 {} sparse or _error (continuing Part 2): {}",
            analysis_path.name,
            str(data.get("_error") or "no decisions[]")[:240],
        )
    markdown = generate_part2_markdown(data, args, api_key, analysis_path=analysis_path)
    report_path = write_part2_report(
        analysis_path,
        markdown,
        validate_mermaid=not getattr(args, "no_validate_mermaid", False),
    )
    if _db_events_enabled(args):
        _record_policy_event_safe(
            _video_id_from_analysis_path(analysis_path),
            stage="report",
            ok=True,
            path=report_path,
        )
    return report_path


def _video_id_from_analysis_path(path: Path) -> str:
    """Best-effort YouTube id from filename or Part 1 JSON."""
    from llm.gemini.transcript_cache_paths import video_id_from_analysis

    m = re.search(r"_([A-Za-z0-9_-]{11})_", path.name)
    if m:
        return m.group(1)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return video_id_from_analysis(data) if isinstance(data, dict) else ""
    except (json.JSONDecodeError, OSError):
        return ""


def _dedupe_latest_analysis_per_video(paths: List[Path]) -> List[Path]:
    """Keep newest file per video id (paths should be sorted newest-first)."""
    seen: set[str] = set()
    out: List[Path] = []
    for path in paths:
        vid = _video_id_from_analysis_path(path)
        key = vid or path.name
        if key in seen:
            logger.info("Skipping older duplicate analysis for {}: {}", vid or "?", path.name)
            continue
        seen.add(key)
        out.append(path)
    return out


def run_part2_only_batch(args: argparse.Namespace, api_key: str) -> None:
    """Generate Part 2 reports from existing Part 1 analysis JSON."""
    from llm.gemini.transcript_cache_paths import iter_analysis_files

    jurisdiction_id = (args.jurisdiction_id or DEFAULT_JURISDICTION_ID).strip()
    cache_dir = Path(args.output_dir).resolve()
    state_code = _policy_state_code(args)
    folder = jurisdiction_root(cache_dir, jurisdiction_id, state_code=state_code)
    if not folder.is_dir():
        raise SystemExit(f"No output folder: {folder}")

    paths = iter_analysis_files(cache_dir, jurisdiction_id, state_code=state_code)
    video_filter = (args.video_id or "").strip()
    if video_filter:
        from llm.gemini.transcript_cache_paths import resolve_analysis_path

        one = resolve_analysis_path(
            cache_dir, jurisdiction_id, video_id=video_filter, state_code=state_code
        )
        paths = [one] if one else [p for p in paths if _video_id_from_analysis_path(p) == video_filter]
    if getattr(args, "latest_only", True):
        paths = _dedupe_latest_analysis_per_video(paths)
    if args.limit is not None:
        paths = paths[: int(args.limit)]

    if not paths:
        raise SystemExit(f"No analysis JSON under {folder} (check 02_analysis/ or legacy flat files)")

    logger.info("Part 2 only: {} analysis file(s)", len(paths))
    for i, path in enumerate(paths, 1):
        logger.info("[{}/{}] {}", i, len(paths), path.name)
        try:
            run_part2_for_analysis_file(path, args, api_key)
        except GenAITransientGiveUp as exc:
            # Google-side network flake — never fatal, even with --stop-on-error.
            logger.warning("Skip {} — transient infra give-up: {}", path.name, exc)
            if _db_events_enabled(args):
                _record_policy_event_safe(
                    _video_id_from_analysis_path(path),
                    stage="report",
                    ok=False,
                    error=str(exc),
                )
            continue
        except Exception as exc:
            logger.exception("Part 2 failed for {}: {}", path.name, exc)
            if _db_events_enabled(args):
                _record_policy_event_safe(
                    _video_id_from_analysis_path(path),
                    stage="report",
                    ok=False,
                    error=str(exc),
                )
            if args.stop_on_error:
                raise


def process_one_video(
    video: VideoRow,
    args: argparse.Namespace,
    *,
    speaker_hints: str,
    known: List[Dict[str, str]],
    api_key: str,
) -> Optional[Path]:
    """Fetch transcript (and optional policy JSON) for one video. Returns analysis path if any."""
    video_id = video.video_id.strip()
    jurisdiction_id = video.jurisdiction_id
    state_code = _policy_state_code(args)
    explicit_audio = Path(args.audio_path).expanduser().resolve() if args.audio_path else None
    out_dir = Path(args.output_dir).resolve()
    cache_folder = jurisdiction_root(out_dir, jurisdiction_id, state_code=state_code)

    yt: Dict[str, Any] = {}
    source_parts: List[str] = []

    def _load_local_transcript(
        local_path: Path, local_payload: Dict[str, Any]
    ) -> Optional[tuple[Dict[str, Any], List[str]]]:
        local_yt = dict(local_payload.get("youtube") or local_payload)
        if not local_yt.get("segments"):
            return None
        logger.info("Using local transcript {}", local_path)
        return local_yt, [f"local_transcript_cache ({local_path.name})"]

    def _merge_video_metadata(local_payload: Dict[str, Any]) -> VideoRow:
        nonlocal video
        if video.title is None and local_payload.get("title"):
            return VideoRow(
                video_id=video.video_id,
                video_url=video.video_url or local_payload.get("video_url") or "",
                title=local_payload.get("title"),
                last_updated=video.last_updated,
                event_date=local_payload.get("event_date") or video.event_date,
                audio_file_path=video.audio_file_path,
                jurisdiction_id=video.jurisdiction_id,
            )
        return video

    cached_local = load_local_transcript_payload(
        out_dir,
        jurisdiction_id,
        video_id=video_id,
        title=video.title or "",
        event_date=video.event_date,
        state_code=state_code,
        channel_id=getattr(video, "channel_id", None),
    )

    # Primary source: the warehouse. bronze_event_youtube_transcript holds the
    # caption text (segments[] JSONB, {HH:MM:SS}-timed caption_text_timed, or
    # raw_text). Fall back to the on-disk cache / live YouTube captions only when
    # the DB has no usable row. Opt out with --no-db-transcript.
    if getattr(args, "use_db_transcript", True) and not source_parts:
        from llm.gemini.transcript_db import fetch_db_transcript

        try:
            db_yt = fetch_db_transcript(
                _database_url(getattr(args, "database_url", None) or None),
                video_id,
            )
        except Exception as exc:  # noqa: BLE001 - DB hiccup must not abort the run
            logger.warning("DB transcript lookup failed for {}: {}", video_id, exc)
            db_yt = None
        if db_yt is not None:
            yt = db_yt
            source_parts = [db_yt["transcript_source"]]

    if not source_parts and cached_local is not None:
        local_path, local_payload = cached_local
        loaded = _load_local_transcript(local_path, local_payload)
        if loaded is not None:
            yt, source_parts = loaded
            video = _merge_video_metadata(local_payload)
        else:
            logger.warning(
                "Local cache for {} has no segments ({}); trying YouTube captions",
                video_id,
                local_path.name,
            )

    if not source_parts:
        try:
            yt = fetch_youtube_transcript(video_id, languages=args.transcript_languages)
            source_parts = [
                f"youtube_captions ({yt.get('language')}, auto={yt.get('is_auto_generated')})"
            ]
            if args.use_local_transcript:
                logger.info(
                    "Fetched YouTube captions for {} (no usable file in {})",
                    video_id,
                    cache_folder,
                )
        except Exception as exc:
            if cached_local is not None and "IpBlocked" in type(exc).__name__:
                local_path, local_payload = cached_local
                loaded = _load_local_transcript(local_path, local_payload)
                if loaded is None:
                    logger.error(
                        "Skipping {} — YouTube IpBlocked and local cache has no segments: {}",
                        video_id,
                        local_path.name,
                    )
                    return None
                yt, source_parts = loaded
                video = _merge_video_metadata(local_payload)
                logger.warning(
                    "YouTube IpBlocked for {}; using local cache {}",
                    video_id,
                    local_path.name,
                )
            elif args.use_local_transcript and not source_parts:
                logger.error(
                    "Skipping {} — no local transcript in {} and YouTube fetch failed: {}",
                    video_id,
                    cache_folder,
                    exc,
                )
                return None
            else:
                raise

    segments: List[Dict[str, Any]] = list(yt.get("segments") or [])
    if known and not args.diarize:
        label_segments_from_contacts(segments, known)

    diarize_meta: Optional[Dict[str, Any]] = None
    if args.diarize:
        audio_root = Path(args.audio_root).resolve()
        audio_path = resolve_audio_path(
            video, audio_root=audio_root, explicit=explicit_audio
        )
        if audio_path is None or not audio_path.is_file():
            logger.error(
                "Skipping {} — no audio (download Opus first or pass --audio-path)",
                video_id,
            )
            return None
        logger.info("Diarizing {}", audio_path)
        diarize_meta = diarize_audio_whisperx(
            audio_path,
            model_size=args.whisper_model,
            device=args.device,
            known_names=[k.get("person_name", "") for k in known],
        )
        segments = merge_caption_speakers(segments, diarize_meta["segments"])
        source_parts.append(f"whisperx_diarization ({audio_path.name})")
    elif any(s.get("speaker") for s in segments):
        pass
    else:
        for seg in segments:
            seg.setdefault("speaker", None)
            if not seg.get("speaker_guess"):
                seg.setdefault("speaker_guess", None)

    source_note = "; ".join(source_parts)
    agenda_blocks = segment_agenda_blocks(segments, known)
    agenda_hints = format_agenda_presenter_hints_block(
        agenda_blocks,
        jurisdiction_id=jurisdiction_id,
    )
    from llm.gemini.legislation_analysis import format_pre_gemini_agenda_legislation_hints

    agenda_leg_hints = format_pre_gemini_agenda_legislation_hints(
        agenda_blocks, jurisdiction_id=jurisdiction_id
    )
    if agenda_blocks:
        logger.info("Built {} agenda segment hint(s) for presenter linking", len(agenda_blocks))
    transcript_block = build_transcript_block(
        speaker_hints=speaker_hints,
        segments=segments,
        source_note=source_note,
        agenda_hints=agenda_hints,
        agenda_legislation_hints=agenda_leg_hints,
    )

    transcript_meta: Dict[str, Any] = {
        "video_id": video_id,
        "video_url": video.video_url,
        "title": video.title,
        "event_date": video.event_date,
        "jurisdiction_id": jurisdiction_id,
        "youtube": yt,
        "diarize": diarize_meta,
        "segment_count": len(segments),
        "transcript_chars": len(transcript_block),
        "formatted_preview": transcript_block[:2000],
    }

    if args.transcript_only:
        out_dir = Path(args.output_dir).resolve()
        path = transcript_cache_path(
            out_dir,
            jurisdiction_id,
            title=video.title or "",
            event_date=video.event_date,
            state_code=state_code,
            channel_id=getattr(video, "channel_id", None),
            video_id=video_id,
        )
        transcript_meta["formatted_transcript"] = transcript_block
        path.write_text(json.dumps(transcript_meta, indent=2) + "\n", encoding="utf-8")
        logger.info("Wrote transcript {}", path)
        return path

    prompt_path = Path(args.prompt_file).resolve()
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    prompt_with_tx = inject_transcript_into_prompt(prompt_text, transcript_block)

    user_message = build_user_message(
        prompt_with_tx,
        video,
        task_line=(
            "Analyze the meeting from the <transcript> block only. "
            "Do not assume you can watch video; use MEDIA CONTEXT for metadata only. "
            "Extract all addresses and named sites into places[] and cross-link place_refs "
            "on every decisions[] and uncontested_items[] row."
        ),
    )

    model = (args.model or default_flash_lite_model()).strip()
    logger.info("Calling {} ({})", model, "AI Studio API")
    result = call_gemini_text(
        api_key=api_key,
        model=model,
        user_text=user_message,
        system_instruction=args.system_instruction,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )

    capture = GeminiRunCapture(response_text=result.text, gemini_model=model)
    transcript_meta["formatted_transcript"] = transcript_block
    analysis_path = save_transcript_policy_output(
        out_dir,
        video,
        model=model,
        response_text=capture.response_text,
        prompt_path=prompt_path,
        transcript_meta=transcript_meta,
        geocode_places=getattr(args, "geocode_places", False),
        agenda_blocks=agenda_blocks,
        enrich_legislation=not getattr(args, "skip_legislation_enrich", False),
        persist_bronze=getattr(args, "persist_bronze", False),
        database_url=_database_url(getattr(args, "database_url", None) or None),
        state_code=state_code,
        record_db_events=_db_events_enabled(args),
        defer_report_event=args.run_part_2,
    )
    if args.run_part_2 and analysis_path is not None:
        try:
            raw_analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw_analysis = {}
        if analysis_ready_for_part2(raw_analysis):
            analysis = coalesce_part1_analysis(raw_analysis)
            if analysis.get("_error") or not _part1_json_ok(analysis):
                logger.warning(
                    "Part 1 sparse for {} (continuing Part 2): {}",
                    video_id,
                    str(analysis.get("_error") or "no decisions[]")[:240],
                )
            try:
                report_path = write_part2_report(
                    analysis_path,
                    generate_part2_markdown(
                        analysis, args, api_key, analysis_path=analysis_path
                    ),
                    validate_mermaid=not getattr(args, "no_validate_mermaid", False),
                )
                if _db_events_enabled(args):
                    _record_policy_event_safe(
                        video_id, stage="report", ok=True, path=report_path
                    )
            except Exception as exc:
                if _db_events_enabled(args):
                    _record_policy_event_safe(
                        video_id, stage="report", ok=False, error=str(exc)
                    )
                raise
        else:
            logger.error(
                "Skipping Part 2 for {} — Part 1 JSON invalid (re-run Part 1 or check 02_analysis/)",
                video_id,
            )
            if _db_events_enabled(args):
                _record_policy_event_safe(
                    video_id,
                    stage="report",
                    ok=False,
                    error="Skipped Part 2 — Part 1 JSON invalid",
                )
    return analysis_path


def run_pipeline(args: argparse.Namespace) -> None:
    load_dotenv(_REPO_ROOT / ".env")
    newest_n = int(getattr(args, "newest", 0) or 0)
    if newest_n > 0:
        args.from_bronze = True
        args.limit = newest_n
        args.order_by = "published_at"
        args.use_local_transcript = True
        args.run_part_2 = True
        args.only_has_transcript = True
        args.ensure_local_from_bronze = True
        args.skip_analyzed = True

    # --from-bronze is transcript-driven by default: only analyze rows bronze knows
    # have a transcript. Without this, the batch pulls every video on the channel
    # (PSAs, promos, …) and each captionless one errors on the live YouTube fallback.
    # Opt out with --include-no-transcript.
    if args.from_bronze and not getattr(args, "include_no_transcript", False):
        args.only_has_transcript = True

    # Prefer disk captions when batching from bronze; sync bronze → 01_transcripts/ first.
    if args.from_bronze and args.use_local_transcript:
        args.ensure_local_from_bronze = True

    needs_api = not args.transcript_only
    api_key = ""
    if needs_api:
        api_key = ensure_valid_gemini_api_key(
            env_path=_REPO_ROOT / ".env",
            model=(args.model or args.part_2_model or default_flash_lite_model()).strip(),
        )
    if args.transcript_only and args.run_part_2:
        raise SystemExit("--transcript-only cannot be combined with --run-part-2")

    from llm.gemini.transcript_cache_paths import resolve_canonical_jurisdiction_id

    jurisdiction_id = resolve_canonical_jurisdiction_id(
        (args.jurisdiction_id or DEFAULT_JURISDICTION_ID).strip()
    )
    state_code = _policy_state_code(args)

    if args.part_2_only:
        run_part2_only_batch(args, api_key)
        return

    speaker_hints, known = load_speaker_context(args, jurisdiction_id)

    if args.from_bronze:
        db_url = _database_url(args.database_url or None)
        videos = fetch_videos(
            db_url,
            jurisdiction_id,
            limit=args.limit,
            video_id=(args.video_id or "").strip() or None,
            order_by=args.order_by,
            only_has_transcript=getattr(args, "only_has_transcript", False),
            dedupe_duplicate_meetings=not newest_n,
        )
        if not videos:
            hint = ""
            if getattr(args, "only_has_transcript", False):
                hint = (
                    " (no rows with bronze_event_youtube_transcript.has_transcript — "
                    "run packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py first)"
                )
            raise SystemExit(f"No bronze videos for {jurisdiction_id}{hint}")
        if args.dry_run:
            for i, v in enumerate(videos, 1):
                ed = v.event_date or "?"
                lu = v.last_updated.isoformat() if v.last_updated else "?"
                print(
                    f"{i:3}. {v.video_id}  event_date={ed}  last_updated={lu}  {v.title or ''}"
                )
            return

        from scrapers.youtube.backfill_jurisdiction_transcripts import (
            fetch_video_row,
            write_local_from_bronze,
        )

        out_dir = Path(args.output_dir).resolve()
        from llm.gemini.policy_exclusions import is_policy_video_excluded

        for i, video in enumerate(videos, 1):
            if is_policy_video_excluded(
                out_dir,
                jurisdiction_id,
                video.video_id,
                state_code=state_code,
                channel_id=getattr(video, "channel_id", None),
            ):
                logger.info(
                    "[{}/{}] Skip {} — excluded non-meeting (05_exceptions/)",
                    i,
                    len(videos),
                    video.video_id,
                )
                continue
            if getattr(args, "skip_analyzed", False):
                existing = resolve_analysis_path(
                    out_dir,
                    jurisdiction_id,
                    video_id=video.video_id,
                    title=video.title or "",
                    event_date=video.event_date,
                    state_code=state_code,
                    channel_id=getattr(video, "channel_id", None),
                )
                if existing is not None:
                    logger.info(
                        "[{}/{}] Skip {} — analysis exists ({})",
                        i,
                        len(videos),
                        video.video_id,
                        existing.name,
                    )
                    continue

            if getattr(args, "ensure_local_from_bronze", False):
                from llm.gemini.transcript_cache_paths import load_local_transcript_payload

                if load_local_transcript_payload(
                    out_dir,
                    jurisdiction_id,
                    video_id=video.video_id,
                    title=video.title or "",
                    event_date=video.event_date,
                    state_code=state_code,
                    channel_id=getattr(video, "channel_id", None),
                ) is None:
                    row = fetch_video_row(db_url, jurisdiction_id, video.video_id)
                    if row and write_local_from_bronze(
                        db_url, out_dir, jurisdiction_id, row, state_code=state_code
                    ):
                        logger.info("Synced bronze transcript to local cache for {}", video.video_id)
                    else:
                        logger.warning(
                            "No local cache for {} (bronze sync missed); process will try YouTube captions",
                            video.video_id,
                        )

            logger.info(
                "[{}/{}] {} — {}",
                i,
                len(videos),
                video.video_id,
                (video.title or "")[:80],
            )
            try:
                process_one_video(
                    video, args, speaker_hints=speaker_hints, known=known, api_key=api_key
                )
            except GenAITransientGiveUp as exc:
                # Google-side network flake — never fatal, even with --stop-on-error.
                logger.warning("Skip {} — transient infra give-up: {}", video.video_id, exc)
                if _db_events_enabled(args):
                    _record_policy_event_safe(
                        video.video_id, stage="analysis", ok=False, error=str(exc)
                    )
                continue
            except Exception as exc:
                # Opt-in: a pool-wide daily-quota wall, a sustained server-overload give-up,
                # OR a retired/unavailable-model give-up propagates so a model-cycling
                # driver can rotate models / wait (Pacific reset for quota, short cooldown
                # for overload, permanent drop for a retired model). Default-off, so
                # existing callers see the unchanged log-and-continue behaviour.
                if getattr(args, "stop_on_quota", False) and isinstance(
                    exc,
                    (
                        GenAIDailyQuotaGiveUp,
                        GenAIServerOverloadGiveUp,
                        GenAIModelUnavailableGiveUp,
                    ),
                ):
                    if isinstance(exc, GenAIDailyQuotaGiveUp):
                        wall = "daily quota wall"
                    elif isinstance(exc, GenAIModelUnavailableGiveUp):
                        wall = "model unavailable (retired)"
                    else:
                        wall = "server overload"
                    logger.warning(
                        "Stopping batch for {} — {} (stop_on_quota): {}",
                        jurisdiction_id,
                        wall,
                        exc,
                    )
                    raise
                logger.exception("Failed {}: {}", video.video_id, exc)
                if _db_events_enabled(args):
                    _record_policy_event_safe(
                        video.video_id, stage="analysis", ok=False, error=str(exc)
                    )
                if args.stop_on_error:
                    raise
        return

    video_id = (args.video_id or "").strip()
    if not video_id:
        raise SystemExit("Pass --video-id or use --from-bronze")

    video = VideoRow(
        video_id=video_id,
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        title=args.title,
        last_updated=None,
        event_date=args.event_date,
        audio_file_path=None,
        jurisdiction_id=jurisdiction_id,
    )
    process_one_video(
        video, args, speaker_hints=speaker_hints, known=known, api_key=api_key
    )


def build_parser() -> argparse.ArgumentParser:
    """Argument parser for the analyze pipeline.

    Factored out of ``main`` so in-process drivers (e.g. ``llm.gemini.analyze_backlog``)
    can derive a complete defaults-populated ``Namespace`` via ``parse_args([])`` instead
    of hand-maintaining the full attribute set ``run_pipeline`` expects.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", default="", help="YouTube video id (single-video mode)")
    parser.add_argument(
        "--from-bronze",
        action="store_true",
        help="Process videos from bronze.bronze_event_youtube",
    )
    parser.add_argument(
        "--order-by",
        choices=("meeting_date", "last_updated", "published_at"),
        default="meeting_date",
        help="Batch sort: published_at / meeting_date = newest first; last_updated = catalog touch time",
    )
    parser.add_argument(
        "--newest",
        type=int,
        default=0,
        metavar="N",
        help="Analyze N newest meetings with bronze captions (sets --from-bronze, local cache, Part 1+2)",
    )
    parser.add_argument(
        "--only-has-transcript",
        action="store_true",
        help="(default with --from-bronze) only rows where bronze.has_transcript is true",
    )
    parser.add_argument(
        "--include-no-transcript",
        action="store_true",
        help="Opt out of the transcript-only default: also process bronze rows with "
        "no transcript (will try a live YouTube caption fetch — noisy for PSAs/promos)",
    )
    parser.add_argument(
        "--ensure-local-from-bronze",
        action="store_true",
        help="Copy bronze transcript JSON to local cache before analysis if missing",
    )
    parser.add_argument(
        "--skip-analyzed",
        action="store_true",
        help="Skip videos that already have 02_analysis/*_analysis.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="With --from-bronze: max videos (default: all rows for jurisdiction)",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Postgres URL (default NEON_DATABASE_URL_DEV / NEON_DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --from-bronze: list videos that would run, no fetch/API",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="With --from-bronze: stop batch on first failure (default: continue)",
    )
    parser.add_argument(
        "--jurisdiction-id",
        default=DEFAULT_JURISDICTION_ID,
        help="e.g. municipality_0177256",
    )
    parser.add_argument(
        "--state",
        default="AL",
        help="Two-letter state for policy cache and scraped_meetings paths (e.g. GA/municipality/5583)",
    )
    parser.add_argument(
        "--scraped-cache-dir",
        default="",
        help="Override path to municipality scrape cache (contacts.json)",
    )
    parser.add_argument("--title", default=None, help="Meeting title for metadata")
    parser.add_argument("--event-date", default=None, help="Meeting date label")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=DEFAULT_PROMPT_PART_1,
        help="Policy prompt with <transcript> placeholder",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--model",
        default="",
        help="Default: GEMINI_FLASH_LITE_MODEL or gemini-2.5-flash-lite",
    )
    parser.add_argument("--system-instruction", default="", help="Optional system prompt")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument(
        "--transcript-languages",
        nargs="+",
        default=["en"],
        help="Preferred YouTube caption languages",
    )
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Fetch/format transcript only; no API call",
    )
    parser.add_argument(
        "--use-local-transcript",
        action="store_true",
        help="Prefer existing gemini_transcript_policy JSON; with --from-bronze also sync "
        "bronze → 01_transcripts/ first. Falls back to YouTube captions when missing on disk.",
    )
    parser.add_argument(
        "--no-db-transcript",
        action="store_false",
        dest="use_db_transcript",
        default=True,
        help="Don't read transcripts from bronze_event_youtube_transcript first; use the "
        "on-disk cache / live YouTube captions instead (default: read from the DB).",
    )
    parser.add_argument(
        "--run-part-2",
        action="store_true",
        help="After Part 1, call API with policy_analysis_part_2.md and write *_report.md",
    )
    parser.add_argument(
        "--part-2-only",
        action="store_true",
        help="Skip Part 1; generate *_report.md from existing *_analysis.json in output dir",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        default=True,
        help="With --part-2-only: one analysis per video_id (newest mtime). Default: true.",
    )
    parser.add_argument(
        "--all-analysis-runs",
        action="store_false",
        dest="latest_only",
        help="With --part-2-only: process every *_analysis.json (including older duplicates).",
    )
    parser.add_argument(
        "--geocode-places",
        action="store_true",
        help="After Part 1, geocode places[] via Nominatim (~1 req/s; Tuscaloosa bias for municipality_0177256)",
    )
    parser.add_argument(
        "--prompt-part-2",
        type=Path,
        default=DEFAULT_PROMPT_PART_2,
        help="Smart Brevity markdown prompt (default: policy_analysis_part_2.md)",
    )
    parser.add_argument(
        "--part-2-model",
        default="",
        help="Model for Part 2 (default: same as --model / GEMINI_FLASH_LITE_MODEL)",
    )
    parser.add_argument(
        "--no-validate-mermaid",
        action="store_true",
        help="Skip Mermaid parse check after writing Part 2 reports",
    )
    parser.add_argument(
        "--no-speaker-hints",
        action="store_true",
        help="Skip contacts.json speaker directory",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Run WhisperX diarization and merge labels into caption segments",
    )
    parser.add_argument("--audio-path", default="", help="Local Opus/MP3 for diarization")
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=DEFAULT_YOUTUBE_AUDIO_ROOT,
        help="Search root when --audio-path omitted",
    )
    parser.add_argument("--whisper-model", default="small", help="WhisperX model size")
    parser.add_argument(
        "--device",
        default=os.environ.get("WHISPER_DEVICE", "cpu"),
        choices=("cpu", "cuda"),
    )
    parser.add_argument(
        "--skip-legislation-enrich",
        action="store_true",
        help="Skip post-Part-1 legislation ref validation and agenda→leg_id mapping",
    )
    parser.add_argument(
        "--persist-bronze",
        action="store_true",
        help="Upsert bronze.bronze_bills / item legislation links after Part 1 (needs migration 018)",
    )
    parser.add_argument(
        "--no-db-events",
        action="store_true",
        help="Disable best-effort recording of analysis/report outcomes onto "
        "bronze_event_youtube (also via POLICY_RECORD_DB_EVENTS=0; needs migration 083)",
    )
    parser.add_argument(
        "--stop-on-quota",
        action="store_true",
        help="With --from-bronze: re-raise a pool-wide daily-quota wall "
        "(GenAIDailyQuotaGiveUp) instead of logging-and-continuing, so a model-cycling "
        "driver can rotate models / wait for the Pacific reset (default: off)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
