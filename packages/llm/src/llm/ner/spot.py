"""Scan timed caption segments for stock motion/vote phrases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from llm.ner.phrases import PHRASE_PATTERNS


@dataclass(frozen=True)
class VotePhraseHit:
    video_id: str
    phrase_code: str
    start_seconds: float | None
    char_offset: int
    match_end: int


def canonical_transcript_bytes(segments: list[dict]) -> bytes:
    """UTF-8 bytes of segment lines ``{start:.3f}\\t{text}\\n`` in order."""
    lines = []
    for seg in segments:
        start = float(seg.get("start", 0.0))
        text = seg.get("text") or ""
        lines.append(f"{start:.3f}\t{text}\n")
    return "".join(lines).encode("utf-8")


def file_sha256(segments: list[dict]) -> str:
    """SHA-256 hex digest of :func:`canonical_transcript_bytes`."""
    return hashlib.sha256(canonical_transcript_bytes(segments)).hexdigest()


def _pattern_sort_key(code: str) -> int:
    return len(PHRASE_PATTERNS[code].pattern)


def spot_segments(video_id: str, segments: list[dict]) -> list[VotePhraseHit]:
    """Return phrase hits for each segment's ``text``.

    ``start_seconds`` is taken from the segment's ``start`` when present.
    ``char_offset`` and ``match_end`` are character indices within that
    segment's ``text`` (not the full transcript).
    When matches overlap, the longest span wins; shorter overlaps are skipped.
    """
    hits: list[VotePhraseHit] = []
    codes_by_len = sorted(PHRASE_PATTERNS, key=_pattern_sort_key, reverse=True)

    for seg in segments:
        text = seg.get("text") or ""
        if not text.strip():
            continue
        start_seconds = seg.get("start")
        if start_seconds is not None:
            start_seconds = float(start_seconds)

        candidates: list[tuple[int, int, str]] = []
        for code in codes_by_len:
            pattern = PHRASE_PATTERNS[code]
            for match in pattern.finditer(text):
                candidates.append((match.start(), match.end(), code))

        candidates.sort(key=lambda t: (t[1] - t[0], t[0]), reverse=True)

        occupied: list[tuple[int, int]] = []

        def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
            return a[0] < b[1] and b[0] < a[1]

        seg_hits: list[VotePhraseHit] = []
        for char_offset, match_end, phrase_code in candidates:
            span = (char_offset, match_end)
            if any(overlaps(span, occ) for occ in occupied):
                continue
            occupied.append(span)
            seg_hits.append(
                VotePhraseHit(
                    video_id=video_id,
                    phrase_code=phrase_code,
                    start_seconds=start_seconds,
                    char_offset=char_offset,
                    match_end=match_end,
                )
            )

        seg_hits.sort(key=lambda h: h.char_offset)
        hits.extend(seg_hits)

    return hits