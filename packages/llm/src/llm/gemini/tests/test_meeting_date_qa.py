from datetime import date

from llm.gemini.meeting_date_qa import (
    is_future_meeting_date,
    qa_recorded_video_meeting_date,
    suggest_recorded_video_meeting_date,
)


def test_future_date_detected():
    assert is_future_meeting_date("2028-04-27", as_of=date(2026, 6, 22))


def test_same_day_not_future():
    assert not is_future_meeting_date("2026-06-22", as_of=date(2026, 6, 22))


def test_suggest_from_meeting_id_suffix():
    got = suggest_recorded_video_meeting_date(
        title="North Sherborn District Water Sewer Commission",
        meeting_id="dover_2517370_2026-03-16",
        as_of=date(2026, 6, 22),
    )
    assert got == "2026-03-16"


def test_qa_fixes_future_date_using_meeting_id():
    analysis = {
        "meeting": {
            "meeting_id": "dover_2517370_2026-03-16",
            "meeting_date": "2926-03-16",
            "body_name": "North Sherborn District Water Sewer Commission",
        },
        "event_date": "2926-03-16",
        "decisions": [],
    }
    fixed, warnings = qa_recorded_video_meeting_date(
        analysis,
        video_id="ZOemQ_WclcI",
        title="Meeting March 16, 2026",
        as_of=date(2026, 6, 22),
    )
    assert fixed["meeting"]["meeting_date"] == "2026-03-16"
    assert fixed["event_date"] == "2026-03-16"
    assert any("future meeting_date" in w for w in warnings)


def test_qa_skips_when_no_video_id():
    analysis = {"meeting": {"meeting_date": "2099-01-01"}, "decisions": []}
    out, warnings = qa_recorded_video_meeting_date(analysis, video_id=None)
    assert out["meeting"]["meeting_date"] == "2099-01-01"
    assert warnings == []
