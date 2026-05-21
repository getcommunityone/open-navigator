"""
Optional audio diarization post-processing (WhisperX).

Install optional deps::

    pip install -r requirements-transcript-diarize.txt
    # Hugging Face token for pyannote diarization models:
    export HF_TOKEN=...

Heavy GPU recommended; CPU works but is slow.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _format_ts(seconds: float) -> str:
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def diarize_audio_whisperx(
    audio_path: Path,
    *,
    model_size: str = "small",
    device: str = "cpu",
    hf_token: Optional[str] = None,
    known_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run WhisperX ASR + alignment + diarization on ``audio_path``.

    Returns ``{segments: [{start, end, text, speaker}], raw_text, engine}``.
    """
    try:
        import whisperx
    except ImportError as exc:
        raise ImportError(
            "WhisperX not installed. Run: pip install -r requirements-transcript-diarize.txt"
        ) from exc

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    token = (hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "").strip()
    if not token:
        raise EnvironmentError(
            "HF_TOKEN (or HUGGINGFACE_TOKEN) required for pyannote diarization inside WhisperX"
        )

    compute_type = "float16" if device == "cuda" else "int8"
    model = whisperx.load_model(model_size, device=device, compute_type=compute_type)
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=8)

    lang = result.get("language") or "en"
    align_model, metadata = whisperx.load_align_model(language_code=lang, device=device)
    aligned = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    diarize_model = whisperx.DiarizationPipeline(use_auth_token=token, device=device)
    diarize_segments = diarize_model(audio)

    annotated = whisperx.assign_word_speakers(diarize_segments, aligned)

    segments: List[Dict[str, Any]] = []
    for seg in annotated.get("segments") or []:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or 0)
        end = float(seg.get("end") or start)
        speaker = str(seg.get("speaker") or "SPEAKER_00")
        segments.append(
            {
                "start": start,
                "end": end,
                "duration": max(0.0, end - start),
                "text": text,
                "speaker": speaker,
            }
        )

    apply_name_hints_to_segments(segments, known_names or [])

    return {
        "engine": "whisperx",
        "model_size": model_size,
        "device": device,
        "language": lang,
        "raw_text": " ".join(s["text"] for s in segments),
        "segments": segments,
    }


def apply_name_hints_to_segments(
    segments: List[Dict[str, Any]],
    known_speakers: List[Dict[str, str]],
) -> None:
    """
    Heuristic: if segment text mentions a known ``person_name``, set ``speaker_guess``.
    """
    if not known_speakers:
        return
    for seg in segments:
        blob = (seg.get("text") or "").lower()
        for sp in known_speakers:
            name = (sp.get("person_name") or "").strip()
            if not name:
                continue
            last = name.split(",")[0].split()[-1].lower()
            full = name.lower()
            if last and len(last) >= 3 and last in blob:
                seg["speaker_guess"] = name
                break
            if full in blob:
                seg["speaker_guess"] = name
                break


def merge_caption_speakers(
    caption_segments: List[Dict[str, Any]],
    diarize_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Attach ``speaker`` / ``speaker_guess`` to YouTube caption segments by time overlap.
    """
    if not diarize_segments:
        return [{**s, "speaker": None} for s in caption_segments]

    out: List[Dict[str, Any]] = []
    for cap in caption_segments:
        c0 = float(cap.get("start") or 0)
        c1 = c0 + float(cap.get("duration") or 0)
        best_sp: Optional[str] = None
        best_guess: Optional[str] = None
        best_overlap = 0.0
        for d in diarize_segments:
            d0 = float(d.get("start") or 0)
            d1 = float(d.get("end") or d0)
            overlap = max(0.0, min(c1, d1) - max(c0, d0))
            if overlap > best_overlap:
                best_overlap = overlap
                best_sp = d.get("speaker")
                best_guess = d.get("speaker_guess")
        row = dict(cap)
        row["speaker"] = best_sp
        row["speaker_guess"] = best_guess
        out.append(row)
    return out


def format_diarized_transcript(
    segments: List[Dict[str, Any]],
    *,
    include_timestamps: bool = True,
) -> str:
    """Render lines for the policy prompt."""
    lines: List[str] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        sp = seg.get("speaker_guess") or seg.get("speaker") or "UNKNOWN"
        if include_timestamps:
            ts = _format_ts(float(seg.get("start") or 0))
            lines.append(f"[{ts}] {sp}: {text}")
        else:
            lines.append(f"{sp}: {text}")
    return "\n".join(lines)
