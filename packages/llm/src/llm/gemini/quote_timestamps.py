"""Attach exact playback times to ``human_element`` moments.

The decision page offers "jump to this moment" links next to personal stories and
lighter moments. The model's ``summary`` / ``story_detail`` are paraphrases, so the
UI cannot reliably locate them in the recording by fuzzy text matching — it lands
on the wrong spot. The fix: the prompt now requires a **verbatim** ``evidence_quote``
/ ``quote`` for each moment, and this module locates that exact quote in the
timestamped caption ``segments`` to compute ``timestamp_start_seconds``.

Deterministic and honest: a quote that can't be found verbatim gets no timestamp
(``None``), so the UI shows no jump link rather than an invented one.
"""
from __future__ import annotations

import bisect
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from loguru import logger

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# A normalized quote shorter than this is too generic to match safely.
_MIN_QUOTE_CHARS = 12


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace to single spaces."""
    return _NON_ALNUM_RE.sub(" ", text.lower()).strip()


class _TranscriptIndex:
    """Normalized concatenation of segment texts + a char→start-seconds map."""

    def __init__(self, segments: List[Dict[str, Any]]):
        self._offsets: List[int] = []  # char offset where each segment's text begins
        self._starts: List[float] = []  # start seconds for each kept segment
        parts: List[str] = []
        cursor = 0
        for seg in segments:
            norm = _normalize(str(seg.get("text") or ""))
            if not norm:
                continue
            self._offsets.append(cursor)
            self._starts.append(float(seg.get("start") or 0.0))
            parts.append(norm)
            cursor += len(norm) + 1  # +1 for the joining space
        self._haystack = " ".join(parts)

    def find_seconds(self, quote: str) -> Optional[int]:
        """Start-second of the segment where ``quote`` begins, or None if absent."""
        norm = _normalize(quote)
        if len(norm) < _MIN_QUOTE_CHARS:
            return None
        pos = self._haystack.find(norm)
        if pos < 0:
            return None
        # The segment containing `pos` is the last one whose offset is <= pos.
        idx = max(0, bisect.bisect_right(self._offsets, pos) - 1)
        return int(self._starts[idx])


def _iter_human_element_quotes(
    analysis: Dict[str, Any],
) -> Iterator[Tuple[Dict[str, Any], str]]:
    """Yield (moment_dict, quote_field_name) for every story / humor moment."""
    decisions = analysis.get("decisions")
    if not isinstance(decisions, list):
        return
    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        he = dec.get("human_element")
        if not isinstance(he, dict):
            continue
        for entry in he.get("personal_stories") or []:
            if isinstance(entry, dict):
                yield entry, "evidence_quote"
        for entry in he.get("humor_and_light_moments") or []:
            if isinstance(entry, dict):
                yield entry, "quote"


def resolve_human_element_timestamps(
    analysis: Dict[str, Any],
    segments: List[Dict[str, Any]],
) -> int:
    """Attach ``timestamp_start_seconds`` to human_element moments by locating their
    verbatim quote in ``segments``.

    Mutates ``analysis`` in place and returns the number of moments resolved. A
    safe no-op when there are no segments or no decisions. Moments whose quote
    can't be located are stamped ``timestamp_start_seconds: None`` (explicit gap).
    """
    if not isinstance(analysis, dict) or not segments:
        return 0
    index = _TranscriptIndex(segments)
    resolved = 0
    total = 0
    for entry, field in _iter_human_element_quotes(analysis):
        total += 1
        quote = entry.get(field)
        seconds = (
            index.find_seconds(quote)
            if isinstance(quote, str) and quote.strip()
            else None
        )
        if seconds is not None:
            entry["timestamp_start_seconds"] = seconds
            resolved += 1
        else:
            entry.setdefault("timestamp_start_seconds", None)
    if total:
        logger.info("Resolved {}/{} human_element quote timestamps", resolved, total)
    return resolved
