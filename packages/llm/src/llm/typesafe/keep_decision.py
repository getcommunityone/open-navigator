"""Final keep / skip / review over transcript + metadata Jev keep-scores.

Threshold ``DEFAULT_KEEP_THRESHOLD`` (0.6) is unchanged: both-pass still means
each score is at least that floor. Title cues adjust the metadata score before
the rule runs; review rows are written to a separate CSV by callers.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

Decision = Literal["keep", "skip", "review"]

DEFAULT_KEEP_THRESHOLD = 0.6

# Title substrings treated as government-meeting cues for the metadata scorer.
META_GOV_MEETING_TITLE_CUES: tuple[str, ...] = (
    "pre-council",
    "briefing",
    "meeting room",
)


def apply_meta_title_cues(
    title: str | None, meta_keep: float | None
) -> float | None:
    """Raise metadata keep-score to the default floor when a gov-meeting title cue matches.

    ``None`` stays ``None``. Titles without cues are unchanged.
    """
    if meta_keep is None:
        return None
    text = (title or "").lower()
    if any(cue in text for cue in META_GOV_MEETING_TITLE_CUES):
        return max(float(meta_keep), DEFAULT_KEEP_THRESHOLD)
    return float(meta_keep)


def final_keep_decision(
    transcript_keep: float | None,
    meta_keep: float | None,
    *,
    threshold: float = DEFAULT_KEEP_THRESHOLD,
) -> Decision:
    """Decide keep / skip / review from the two keep-scores (after title-cue adjust).

    Rules (threshold stays 0.6 by default):
    - transcript ≥ 0.9 and meta in [0.4, 0.6] → keep
    - transcript in [0.6, 0.7] and meta < 0.1 → review
    - else keep only if both ≥ threshold; otherwise skip
    """
    t = float(transcript_keep) if transcript_keep is not None else None
    m = float(meta_keep) if meta_keep is not None else None
    if t is None or m is None:
        return "skip"

    if t >= 0.9 and 0.4 <= m <= 0.6:
        return "keep"
    if 0.6 <= t <= 0.7 and m < 0.1:
        return "review"
    if t >= threshold and m >= threshold:
        return "keep"
    return "skip"


def write_review_csv(
    rows: Sequence[Mapping[str, Any]], path: Path
) -> int:
    """Write only rows whose ``final_decision`` is ``review``. Returns count written."""
    review_rows = [dict(r) for r in rows if r.get("final_decision") == "review"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not review_rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames = list(review_rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(review_rows)
    return len(review_rows)


def decide_row(
    *,
    title: str | None,
    transcript_keep: float | None,
    meta_keep: float | None,
    threshold: float = DEFAULT_KEEP_THRESHOLD,
) -> tuple[float | None, Decision]:
    """Apply title cues then final decision. Returns ``(meta_keep_adj, decision)``."""
    adj = apply_meta_title_cues(title, meta_keep)
    return adj, final_keep_decision(transcript_keep, adj, threshold=threshold)
