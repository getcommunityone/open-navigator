"""Regression fixtures for transcript-vs-metadata keep / skip / review decisions."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from llm.typesafe import keep_decision as kd

# Scores from data/cache/jev_meta_vs_transcript_al_review.csv (AL compare @ T=0.6).
FIXTURE_ROWS: list[dict[str, object]] = [
    {
        "video_id": "pJcvLTgE430",
        "title": "Tuscaloosa Pre-Council Briefing - May 19, 2026",
        "transcript_keep_score": 1.0,
        "meta_keep_score": 0.54,
        "expected": "keep",
    },
    {
        "video_id": "OdjbcdXSnWA",
        "title": "Tuscaloosa Pre-Council Briefing - May 12, 2026",
        "transcript_keep_score": 1.0,
        "meta_keep_score": 0.55,
        "expected": "keep",
    },
    {
        "video_id": "E9pLIBIEZNw",
        "title": "Tuscaloosa Pre-Council Briefing - May 05, 2026",
        "transcript_keep_score": 1.0,
        "meta_keep_score": 0.58,
        "expected": "keep",
    },
    {
        "video_id": "knzF3UzO8LY",
        "title": "Tuscaloosa Pre-Council Briefing - Apr 28, 2026",
        "transcript_keep_score": 1.0,
        "meta_keep_score": 0.54,
        "expected": "keep",
    },
    {
        "video_id": "kwQgq7Ei1OA",
        "title": "Houston County Commission's Personal Meeting Room",
        "transcript_keep_score": 1.0,
        "meta_keep_score": 0.53,
        "expected": "keep",
    },
    {
        "video_id": "p7PiGrJa-p8",
        "title": "April 2026 Employee Recognitions",
        "transcript_keep_score": 0.64,
        "meta_keep_score": 0.01,
        "expected": "review",
    },
    {
        "video_id": "2dtKQadQRVY",
        "title": "Smart Planning, Strong Results!",
        "transcript_keep_score": 0.57,
        "meta_keep_score": 0.0,
        "expected": "skip",
    },
    {
        "video_id": "BZvO5OusY9Y",
        "title": "Budget Surplus - News Conference",
        "transcript_keep_score": 0.45,
        "meta_keep_score": 0.0,
        "expected": "skip",
    },
    {
        "video_id": "6HnqOeeXVyY",
        "title": "Council Highlights: April 28 Edition",
        "transcript_keep_score": 0.28,
        "meta_keep_score": 0.19,
        "expected": "skip",
    },
]


@pytest.mark.parametrize("row", FIXTURE_ROWS, ids=lambda r: str(r["video_id"]))
def test_fixture_final_decisions(row: dict[str, object]):
    meta = kd.apply_meta_title_cues(str(row["title"]), float(row["meta_keep_score"]))
    decision = kd.final_keep_decision(
        float(row["transcript_keep_score"]),
        meta,
        threshold=0.6,
    )
    assert decision == row["expected"]


def test_title_cues_listed():
    cues = {c.lower() for c in kd.META_GOV_MEETING_TITLE_CUES}
    assert {"pre-council", "briefing", "meeting room"} <= cues


def test_title_cue_boosts_meta_toward_government_meeting():
    # Without cue, 0.53 stays below 0.6; with "meeting room" it is lifted for scoring.
    raw = 0.53
    boosted = kd.apply_meta_title_cues(
        "Houston County Commission's Personal Meeting Room", raw
    )
    assert boosted is not None and boosted >= 0.6
    assert kd.apply_meta_title_cues("Budget Surplus - News Conference", 0.0) == 0.0


def test_threshold_unchanged_default():
    assert kd.DEFAULT_KEEP_THRESHOLD == pytest.approx(0.6)


def test_write_review_csv(tmp_path: Path):
    rows = [
        {
            "video_id": "p7PiGrJa-p8",
            "title": "April 2026 Employee Recognitions",
            "final_decision": "review",
            "transcript_keep_score": 0.64,
            "meta_keep_score_adj": 0.01,
        },
        {
            "video_id": "x",
            "title": "Council Meeting",
            "final_decision": "keep",
            "transcript_keep_score": 0.9,
            "meta_keep_score_adj": 0.9,
        },
    ]
    out = tmp_path / "review.csv"
    written = kd.write_review_csv(rows, out)
    assert written == 1
    got = list(csv.DictReader(out.open()))
    assert len(got) == 1 and got[0]["video_id"] == "p7PiGrJa-p8"
