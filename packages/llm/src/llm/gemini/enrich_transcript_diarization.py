#!/usr/bin/env python3
"""
Add speaker labels to caption-cache JSON (``YYYY-MM-DD_<title>.json``) using contacts + optional WhisperX.

**Heuristic mode** (no audio): match councilor/staff names from ``contacts.json`` in caption text.

**WhisperX mode** (needs local Opus/MP3 + ``HF_TOKEN``): diarize audio, merge SPEAKER_* labels,
then map to contact names.

Examples::

    # Label all cached Tuscaloosa transcripts from contacts (fast, no GPU)
    python -m llm.gemini.enrich_transcript_diarization \\
        --jurisdiction-id municipality_0177256 --state AL

    # One video with WhisperX (Tuscaloosa Opus already under city channel folder)
    python -m llm.gemini.enrich_transcript_diarization \\
        --video-id zpaawfaNsQM --whisperx
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.diarize_postprocess import (  # noqa: E402
    diarize_audio_whisperx,
    format_diarized_transcript,
    merge_caption_speakers,
)
from llm.gemini.meeting_transcript_policy import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    DEFAULT_YOUTUBE_AUDIO_ROOT,
    find_local_audio,
    resolve_scrape_cache_dir,
    tuscaloosa_youtube_audio_dir,
)
from llm.gemini.transcript_cache_paths import (  # noqa: E402
    iter_transcript_cache_files,
    resolve_transcript_cache_path,
)
from llm.gemini.speaker_hints import (  # noqa: E402
    format_speaker_hints_block,
    known_speaker_names,
    label_segments_from_contacts,
    load_contacts_bundle,
)

DEFAULT_JURISDICTION = "tuscaloosa_0177256"


def enrich_payload(
    payload: Dict[str, Any],
    *,
    known: List[Dict[str, str]],
    speaker_hints_block: str,
    use_whisperx: bool,
    audio_path: Optional[Path],
    whisper_model: str,
    device: str,
) -> Dict[str, Any]:
    yt = payload.get("youtube") or {}
    segments: List[Dict[str, Any]] = list(yt.get("segments") or [])
    if not segments:
        raise ValueError(f"No segments in transcript for {payload.get('video_id')}")

    diarize_meta: Optional[Dict[str, Any]] = None
    if use_whisperx:
        if audio_path is None or not audio_path.is_file():
            raise FileNotFoundError(
                f"WhisperX requires --audio-path or audio under {DEFAULT_YOUTUBE_AUDIO_ROOT}"
            )
        names = [k.get("person_name", "") for k in known]
        diarize_meta = diarize_audio_whisperx(
            audio_path,
            model_size=whisper_model,
            device=device,
            known_names=names,
        )
        segments = merge_caption_speakers(segments, diarize_meta["segments"])
        label_segments_from_contacts(segments, known)
    else:
        label_segments_from_contacts(segments, known)

    yt = dict(yt)
    yt["segments"] = segments
    out = dict(payload)
    out["youtube"] = yt
    out["diarization"] = {
        "engine": "whisperx" if use_whisperx else "contacts_heuristic",
        "whisperx": diarize_meta,
        "speaker_hints_chars": len(speaker_hints_block),
    }
    out["speaker_hints"] = speaker_hints_block
    out["formatted_transcript"] = (
        f"{speaker_hints_block}\n"
        f"=== TRANSCRIPT (labeled) ===\n"
        f"{format_diarized_transcript(segments)}\n"
    )
    labeled = sum(1 for s in segments if s.get("speaker_guess") or s.get("speaker"))
    out["labeled_segment_count"] = labeled
    out["segment_count"] = len(segments)
    return out


def main() -> None:
    load_dotenv(_REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-id", default=DEFAULT_JURISDICTION)
    parser.add_argument("--state", default="AL")
    parser.add_argument("--video-id", default="", help="Single video; default all caption-cache JSON files")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Root gemini_transcript_policy cache",
    )
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_YOUTUBE_AUDIO_ROOT)
    parser.add_argument("--audio-path", default="")
    parser.add_argument(
        "--whisperx",
        action="store_true",
        help="Use WhisperX on local audio (requires HF_TOKEN and pip install)",
    )
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--device", default=os.environ.get("WHISPER_DEVICE", "cpu"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jid = args.jurisdiction_id.strip()
    folder = Path(args.cache_dir) / jid
    if not folder.is_dir():
        raise SystemExit(f"Cache folder not found: {folder}")

    scrape_dir = resolve_scrape_cache_dir(jid, state=args.state, repo_root=_REPO_ROOT)
    bundle = load_contacts_bundle(scrape_dir)
    known = known_speaker_names(bundle)
    hints_block = format_speaker_hints_block(bundle)
    logger.info("Loaded {} speaker(s) from {}", len(known), scrape_dir)

    paths = iter_transcript_cache_files(folder)
    if args.video_id:
        resolved = resolve_transcript_cache_path(folder, video_id=args.video_id.strip())
        if resolved is None:
            raise SystemExit(f"No transcript cache for video_id={args.video_id!r} in {folder}")
        paths = [resolved]
    if args.limit:
        paths = paths[: args.limit]

    if args.dry_run:
        for p in paths:
            print(p.name)
        return

    ok = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        vid = (payload.get("video_id") or "").strip()
        if not vid and path.name.endswith("_transcript.json"):
            vid = path.stem.replace("_transcript", "")
        audio_path: Optional[Path] = None
        if args.whisperx:
            explicit = Path(args.audio_path) if args.audio_path else None
            if explicit and explicit.is_file():
                audio_path = explicit
            else:
                search_dirs: List[Path] = []
                if jid == "tuscaloosa_0177256":
                    tdir = tuscaloosa_youtube_audio_dir(Path(args.audio_root))
                    if tdir.is_dir():
                        search_dirs.append(tdir)
                audio_path = find_local_audio(
                    vid,
                    audio_root=Path(args.audio_root),
                    title=str(payload.get("title") or ""),
                    event_date=str(payload.get("event_date") or ""),
                    search_dirs=search_dirs or None,
                )
                if audio_path is None and search_dirs:
                    logger.warning(
                        "No Opus for {} in {} (title={!r})",
                        vid,
                        search_dirs[0],
                        payload.get("title"),
                    )

        try:
            enriched = enrich_payload(
                payload,
                known=known,
                speaker_hints_block=hints_block,
                use_whisperx=args.whisperx,
                audio_path=audio_path,
                whisper_model=args.whisper_model,
                device=args.device,
            )
            path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            logger.info(
                "Updated {} — {}/{} segments labeled",
                path.name,
                enriched.get("labeled_segment_count"),
                enriched.get("segment_count"),
            )
            ok += 1
        except Exception as exc:
            logger.warning("Skipped {}: {}", path.name, exc)

    logger.info("Enriched {} file(s)", ok)


if __name__ == "__main__":
    main()
