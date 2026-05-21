"""
Fetch YouTube captions (free) for transcript-first analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def fetch_youtube_transcript(video_id: str, *, languages: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Return ``{video_id, language, is_auto_generated, raw_text, segments}``.

    ``segments`` items: ``{text, start, duration}`` (seconds).
    """
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id required")

    from scripts.datasources.youtube.transcript_api_client import build_youtube_transcript_api

    langs = languages or ["en"]
    api = build_youtube_transcript_api()
    try:
        fetched = api.fetch(vid, languages=langs)
        language = getattr(fetched, "language", "en") or "en"
        is_auto = bool(getattr(fetched, "is_generated", True))
        snippets = list(fetched.snippets)
    except NoTranscriptFound:
        transcript_list = api.list(vid)
        available = list(transcript_list)
        if not available:
            raise NoTranscriptFound(vid)
        first = available[0]
        fetched = first.fetch()
        language = first.language_code
        is_auto = first.is_generated
        snippets = list(fetched.snippets)

    segments = [
        {
            "text": (s.text or "").strip(),
            "start": float(s.start),
            "duration": float(s.duration),
        }
        for s in snippets
        if (s.text or "").strip()
    ]
    raw_text = " ".join(s["text"] for s in segments)

    return {
        "video_id": vid,
        "language": language,
        "is_auto_generated": is_auto,
        "transcript_source": "youtube_transcript_api",
        "raw_text": raw_text,
        "segments": segments,
    }
