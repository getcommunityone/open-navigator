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

    python scripts/gemini/meeting_transcript_policy.py \\
        --from-bronze --jurisdiction-id municipality_0177256 --state AL \\
        --use-local-transcript --run-part-2 --limit 5

Markdown only from existing analysis JSON::

    python scripts/gemini/meeting_transcript_policy.py \\
        --part-2-only --jurisdiction-id municipality_0177256 --limit 5

Examples::

    export GEMINI_API_KEY=...   # from https://aistudio.google.com/apikey

    # YouTube captions only (no GPU, no HF token)
    python scripts/gemini/meeting_transcript_policy.py \\
        --video-id ajsME66iXbY \\
        --jurisdiction-id municipality_0177256 \\
        --state AL

    # Merge WhisperX speaker labels into caption lines, then Flash-Lite
    python scripts/gemini/meeting_transcript_policy.py \\
        --video-id ajsME66iXbY \\
        --audio-path data/cache/youtube_audio/al/tuscaloosa/ajsME66iXbY.opus \\
        --diarize

    # Transcript only (no API call)
    python scripts/gemini/meeting_transcript_policy.py --video-id ajsME66iXbY --transcript-only

    # Tuscaloosa: newest bronze rows first (transcripts only)
    python scripts/gemini/meeting_transcript_policy.py \\
        --from-bronze --jurisdiction-id municipality_0177256 --state AL \\
        --limit 10 --transcript-only
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

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.gemini.browser_policy_analysis import (  # noqa: E402
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
from scripts.gemini.agenda_presenter_hints import (  # noqa: E402
    enrich_uncontested_media_anchors,
    format_agenda_presenter_hints_block,
    segment_agenda_blocks,
)
from scripts.gemini.diarize_postprocess import (  # noqa: E402
    diarize_audio_whisperx,
    format_diarized_transcript,
    merge_caption_speakers,
)
from scripts.gemini.genai_text_client import (  # noqa: E402
    call_gemini_text,
    default_flash_lite_model,
    extract_json_from_model_text,
)
from scripts.gemini.speaker_hints import (  # noqa: E402
    format_speaker_hints_block,
    known_speaker_names,
    label_segments_from_contacts,
    load_contacts_bundle,
)
from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    _sanitize_audio_title,
    load_local_transcript_payload,
    transcript_cache_path,
)
from scripts.gemini.transcript_fetch import fetch_youtube_transcript  # noqa: E402

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
DEFAULT_YOUTUBE_AUDIO_ROOT = _REPO_ROOT / "data" / "cache" / "youtube_audio"

# City of Tuscaloosa @TuscaloosaCityAL — matches download_tuscaloosa_city_meeting_audio.py
TUSCALOOSA_CHANNEL_ID = "UC74dczS0B3MhDhUHp2ZGRPA"
TUSCALOOSA_CHANNEL_TITLE = "City of Tuscaloosa"
TUSCALOOSA_STATE = "AL"


def tuscaloosa_youtube_audio_dir(
    audio_root: Path = DEFAULT_YOUTUBE_AUDIO_ROOT,
) -> Path:
    """``…/youtube_audio/al/city_of_tuscaloosa_uc74dczs0b3mhdhuhp2zgrpa`` (117+ Opus files)."""
    from scripts.datasources.youtube.download_audio_to_drive import channel_cache_dir_name

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
    root = repo_root or _REPO_ROOT
    st = (state or "AL").strip().upper()
    jid = (jurisdiction_id or "").strip()
    if re.match(r"^municipality_\d+$", jid):
        return root / "data/cache/scraped_meetings" / st / "municipality" / jid
    return root / "data/cache/scraped_meetings" / jid


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
) -> str:
    body = format_diarized_transcript(segments)
    parts = [speaker_hints]
    if agenda_hints.strip():
        parts.append(agenda_hints.strip())
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
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = output_dir / video.jurisdiction_id
    folder.mkdir(parents=True, exist_ok=True)
    prompt_name = prompt_path.stem
    prompt_tag = _sanitize_tag(prompt_name)
    model_tag = _sanitize_tag(model.replace(".", "_"))
    stem = _output_stem(video, prompt_tag=prompt_tag, model_tag=model_tag, ts=ts)
    rel = lambda p: str(p.relative_to(_REPO_ROOT))

    parsed, markdown_docs = _split_gemini_documents(response_text)
    if parsed is None:
        parsed = extract_json_from_model_text(response_text)

    meta_path = folder / f"{stem}_meta.json"
    analysis_path = folder / f"{stem}_analysis.json"
    report_md_path = folder / f"{stem}_report.md"
    diagrams_md_path = folder / f"{stem}_diagrams.md"
    transcript_path = folder / f"{stem}_transcript.json"

    transcript_path.write_text(
        json.dumps(transcript_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not _part1_json_ok(parsed):
        analysis_payload: Any = {
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
            "# Report unavailable\n\n"
            "Part 1 JSON-only run; use ``policy_analysis_part_2`` separately if needed.\n",
            encoding="utf-8",
        )

    has_diagrams = False
    if json_parsed and isinstance(analysis_payload, dict):
        has_diagrams = _write_diagrams_md(analysis_payload, diagrams_md_path)

    files: Dict[str, str] = {
        "meta_json": rel(meta_path),
        "analysis_json": rel(analysis_path),
        "report_md": rel(report_md_path),
        "transcript_json": rel(transcript_path),
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
    _write_manifest(folder, manifest_record)
    logger.info("Wrote {}", analysis_path)
    return analysis_path


def report_path_for_analysis(analysis_path: Path) -> Path:
    name = analysis_path.name
    if name.endswith("_analysis.json"):
        return analysis_path.with_name(name.replace("_analysis.json", "_report.md"))
    return analysis_path.with_suffix(".report.md")


def _recording_title_for_analysis(analysis_path: Optional[Path]) -> str:
    if analysis_path is None:
        return ""
    meta_path = analysis_path.with_name(
        analysis_path.name.replace("_analysis.json", "_meta.json")
    )
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


def write_part2_report(analysis_path: Path, markdown: str) -> Path:
    report_path = report_path_for_analysis(analysis_path)
    report_path.write_text(markdown + "\n", encoding="utf-8")
    logger.info("Wrote {}", report_path)
    return report_path


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
    if data.get("_error") or not _part1_json_ok(data):
        logger.error("Skipping {} — not valid Part 1 JSON", analysis_path.name)
        return None
    markdown = generate_part2_markdown(data, args, api_key, analysis_path=analysis_path)
    return write_part2_report(analysis_path, markdown)


def run_part2_only_batch(args: argparse.Namespace, api_key: str) -> None:
    """Generate ``*_report.md`` from existing ``*_analysis.json`` files."""
    jurisdiction_id = (args.jurisdiction_id or DEFAULT_JURISDICTION_ID).strip()
    folder = Path(args.output_dir).resolve() / jurisdiction_id
    if not folder.is_dir():
        raise SystemExit(f"No output folder: {folder}")

    paths = sorted(
        folder.glob("*_analysis.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    video_filter = (args.video_id or "").strip()
    if video_filter:
        paths = [p for p in paths if video_filter in p.name]
    if args.limit is not None:
        paths = paths[: int(args.limit)]

    if not paths:
        raise SystemExit(f"No *_analysis.json under {folder}")

    logger.info("Part 2 only: {} analysis file(s)", len(paths))
    for i, path in enumerate(paths, 1):
        logger.info("[{}/{}] {}", i, len(paths), path.name)
        try:
            run_part2_for_analysis_file(path, args, api_key)
        except Exception as exc:
            logger.exception("Part 2 failed for {}: {}", path.name, exc)
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
    explicit_audio = Path(args.audio_path).expanduser().resolve() if args.audio_path else None
    out_dir = Path(args.output_dir).resolve()
    cache_folder = out_dir / jurisdiction_id

    yt: Dict[str, Any]
    source_parts: List[str]
    local_hit = load_local_transcript_payload(
        out_dir,
        jurisdiction_id,
        video_id=video_id,
        title=video.title or "",
        event_date=video.event_date,
    )
    if args.use_local_transcript:
        if local_hit is None:
            logger.error(
                "Skipping {} — --use-local-transcript but no cache JSON in {}",
                video_id,
                cache_folder,
            )
            return None
        local_path, local_payload = local_hit
        yt = dict(local_payload.get("youtube") or {})
        if not yt.get("segments"):
            logger.error("Skipping {} — local cache has no youtube.segments: {}", video_id, local_path)
            return None
        source_parts = [f"local_transcript_cache ({local_path.name})"]
        logger.info("Using local transcript {}", local_path)
        if video.title is None and local_payload.get("title"):
            video = VideoRow(
                video_id=video.video_id,
                video_url=video.video_url or local_payload.get("video_url") or "",
                title=local_payload.get("title"),
                last_updated=video.last_updated,
                event_date=local_payload.get("event_date") or video.event_date,
                audio_file_path=video.audio_file_path,
                jurisdiction_id=video.jurisdiction_id,
            )
    else:
        try:
            yt = fetch_youtube_transcript(video_id, languages=args.transcript_languages)
            source_parts = [
                f"youtube_captions ({yt.get('language')}, auto={yt.get('is_auto_generated')})"
            ]
        except Exception as exc:
            if local_hit is not None and "IpBlocked" in type(exc).__name__:
                local_path, local_payload = local_hit
                yt = dict(local_payload.get("youtube") or {})
                if yt.get("segments"):
                    source_parts = [f"local_transcript_cache ({local_path.name}; youtube IpBlocked)"]
                    logger.warning(
                        "YouTube IpBlocked for {}; using local cache {}",
                        video_id,
                        local_path.name,
                    )
                else:
                    raise
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
    if agenda_blocks:
        logger.info("Built {} agenda segment hint(s) for presenter linking", len(agenda_blocks))
    transcript_block = build_transcript_block(
        speaker_hints=speaker_hints,
        segments=segments,
        source_note=source_note,
        agenda_hints=agenda_hints,
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
        folder = out_dir / jurisdiction_id
        folder.mkdir(parents=True, exist_ok=True)
        path = transcript_cache_path(
            out_dir,
            jurisdiction_id,
            title=video.title or "",
            event_date=video.event_date,
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
            "Do not assume you can watch video; use MEDIA CONTEXT for metadata only."
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
    )
    if args.run_part_2 and analysis_path is not None:
        try:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            analysis = {}
        if not analysis.get("_error") and _part1_json_ok(analysis):
            write_part2_report(
                analysis_path,
                generate_part2_markdown(
                    analysis, args, api_key, analysis_path=analysis_path
                ),
            )
        else:
            logger.error("Skipping Part 2 for {} — Part 1 JSON invalid", video_id)
    return analysis_path


def run_pipeline(args: argparse.Namespace) -> None:
    load_dotenv(_REPO_ROOT / ".env")
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    needs_api = not args.transcript_only
    if needs_api and not api_key:
        raise SystemExit(
            "Set GEMINI_API_KEY (https://aistudio.google.com/apikey) or use --transcript-only"
        )
    if args.transcript_only and args.run_part_2:
        raise SystemExit("--transcript-only cannot be combined with --run-part-2")

    jurisdiction_id = (args.jurisdiction_id or DEFAULT_JURISDICTION_ID).strip()

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
        )
        if not videos:
            raise SystemExit(f"No bronze videos for {jurisdiction_id}")
        if args.dry_run:
            for i, v in enumerate(videos, 1):
                ed = v.event_date or "?"
                lu = v.last_updated.isoformat() if v.last_updated else "?"
                print(
                    f"{i:3}. {v.video_id}  event_date={ed}  last_updated={lu}  {v.title or ''}"
                )
            return
        for i, video in enumerate(videos, 1):
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
            except Exception as exc:
                logger.exception("Failed {}: {}", video.video_id, exc)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", default="", help="YouTube video id (single-video mode)")
    parser.add_argument(
        "--from-bronze",
        action="store_true",
        help="Process videos from bronze.bronze_events_youtube",
    )
    parser.add_argument(
        "--order-by",
        choices=("meeting_date", "last_updated"),
        default="meeting_date",
        help="Batch sort: meeting_date = newest event/published first (default); last_updated = catalog touch time",
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
    parser.add_argument("--state", default="AL", help="State folder under scraped_meetings")
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
        help="Use existing gemini_transcript_policy JSON (no YouTube fetch). "
        "If unset, still auto-fallback to local cache on IpBlocked.",
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
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
