"""Tests for the human_element quote→timestamp resolver. Pure logic, no I/O."""

from llm.gemini.quote_timestamps import (
    _normalize,
    resolve_human_element_timestamps,
)


def _segments():
    # Mimics caption cues: short lines, each with a start second.
    return [
        {"start": 0.0, "text": "Good evening and welcome to the commission."},
        {"start": 12.5, "text": "I think this build-out will take"},
        {"start": 15.0, "text": "a decade or more, honestly."},
        {"start": 88.2, "text": "We never heard back from the other counties."},
    ]


def test_normalize_strips_punctuation_and_case():
    assert _normalize("A Decade, or MORE!") == "a decade or more"


def test_resolves_quote_spanning_two_cues():
    analysis = {
        "decisions": [
            {
                "human_element": {
                    "humor_and_light_moments": [
                        {"summary": "joke about the timeline", "quote": "this build-out will take a decade or more"}
                    ]
                }
            }
        ]
    }
    n = resolve_human_element_timestamps(analysis, _segments())
    assert n == 1
    moment = analysis["decisions"][0]["human_element"]["humor_and_light_moments"][0]
    # The quote begins in the cue that starts at 12.5s.
    assert moment["timestamp_start_seconds"] == 12


def test_resolves_personal_story_quote():
    analysis = {
        "decisions": [
            {
                "human_element": {
                    "personal_stories": [
                        {"story_detail": "paraphrase", "evidence_quote": "We never heard back from the other counties"}
                    ]
                }
            }
        ]
    }
    resolve_human_element_timestamps(analysis, _segments())
    story = analysis["decisions"][0]["human_element"]["personal_stories"][0]
    assert story["timestamp_start_seconds"] == 88


def test_unmatched_quote_gets_explicit_none():
    analysis = {
        "decisions": [
            {
                "human_element": {
                    "humor_and_light_moments": [
                        {"summary": "x", "quote": "a line that never appears in the transcript at all"}
                    ]
                }
            }
        ]
    }
    n = resolve_human_element_timestamps(analysis, _segments())
    assert n == 0
    moment = analysis["decisions"][0]["human_element"]["humor_and_light_moments"][0]
    assert moment["timestamp_start_seconds"] is None


def test_too_short_quote_is_not_matched():
    analysis = {
        "decisions": [
            {"human_element": {"humor_and_light_moments": [{"summary": "x", "quote": "the"}]}}
        ]
    }
    assert resolve_human_element_timestamps(analysis, _segments()) == 0


def test_safe_noop_without_segments_or_decisions():
    assert resolve_human_element_timestamps({"decisions": []}, []) == 0
    assert resolve_human_element_timestamps({}, _segments()) == 0
