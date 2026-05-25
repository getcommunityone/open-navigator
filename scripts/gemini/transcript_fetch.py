"""
Fetch YouTube captions (free) for transcript-first analysis.

Uses [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) via
``scripts.datasources.youtube.transcript_api_client``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def fetch_youtube_transcript(
    video_id: str,
    *,
    languages: Optional[List[str]] = None,
    cookies_file: Optional[str] = None,
    proxy_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return ``{video_id, language, is_auto_generated, raw_text, segments, transcript_source}``.

    ``segments`` items: ``{text, start, duration}`` (seconds).
    """
    from scripts.datasources.youtube.transcript_api_client import fetch_transcript_from_api

    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id required")

    return fetch_transcript_from_api(
        vid,
        languages=languages,
        cookies_file=cookies_file,
        proxy_url=proxy_url,
    )
