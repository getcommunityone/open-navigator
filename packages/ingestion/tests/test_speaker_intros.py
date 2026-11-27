"""Unit tests for ingestion.youtube.speaker_intros (#1231): caption-style snippets, no database."""

from __future__ import annotations

from ingestion.youtube.speaker_intros import clean_name_tokens, find_intros


def _one(text: str, segments=None):
    rows = find_intros("vid", text, segments)
    assert len(rows) == 1, rows
    return rows[0]


def test_my_name_is_lowercase_auto_caption():
    r = _one("thank you mayor my name is jane doe and i live on elm street i'm here about the rezoning")
    assert r.pattern_id == "my_name_is"
    assert r.name_tokens == ("jane", "doe")
    assert r.confidence == 0.9
    assert r.mentions_minor is False


def test_my_name_is_with_filler_and_punctuation():
    r = _one("Good evening. My name is, uh, Marcus Webb. I've been in the county thirty years.")
    assert r.name_tokens == ("marcus", "webb")


def test_my_names_contraction_first_name_only():
    r = _one(">> hi my name's Tasha and i'm against the data center")
    assert r.name_tokens == ("tasha",)


def test_i_am_and_i_live():
    rows = find_intros("vid", "I'm Robert Lee and I live at the end of Oak Road. We don't want this.")
    assert [r.pattern_id for r in rows] == ["i_am_live"]
    assert rows[0].name_tokens == ("robert", "lee")


def test_i_am_resident_of():
    r = _one("hello i am carla mendez a resident of ward three")
    assert r.pattern_id == "i_am_live" and r.name_tokens == ("carla", "mendez")


def test_this_is_from():
    r = _one("this is derek olson from the neighborhood association")
    assert r.pattern_id == "this_is_from" and r.name_tokens == ("derek", "olson")


def test_greeting_name_here():
    r = _one("Good evening, Ana Ruiz here, 4120 Pine Street.")
    assert r.pattern_id == "greeting_name" and r.name_tokens == ("ana", "ruiz")


def test_next_speaker_chair_call():
    r = _one("thank you for your comments our next speaker is sam lee")
    assert r.pattern_id == "next_speaker" and r.confidence == 0.5
    assert r.name_tokens == ("sam", "lee")


def test_rejects_non_names():
    for text in (
        "my name is on the sign-up sheet",
        "i'm here and i live nearby",
        "this is the city of springfield from what i understand",
        "good evening everyone here tonight",
        "good evening mayor and council i live on maple",
        "my name is not important",
        "our next speaker is going to be brief",
        "i am a resident of the county",
    ):
        assert find_intros("vid", text) == [], text


def test_title_is_dropped_and_surname_alone_rejected():
    assert clean_name_tokens("Dr. Jane Doe")[1] == ("jane", "doe")
    assert clean_name_tokens("Dr. Doe") == ("dr", ())
    assert clean_name_tokens("Councilman Joe Roe and") == ("councilman", ("joe", "roe"))


def test_trailing_words_trimmed():
    assert clean_name_tokens("jane doe and i")[1] == ("jane", "doe")
    assert clean_name_tokens("Mary Ann Jones")[1] == ("mary", "ann", "jones")


def test_student_flag():
    r = _one("my name is emma clark and i'm a junior at central high school")
    assert r.mentions_minor is True
    r = _one("hi my name is liam i'm fourteen years old")
    assert r.mentions_minor is True
    r = _one("my name is olivia park i'm in the 8th grade")
    assert r.mentions_minor is True


def test_adult_not_flagged():
    r = _one("my name is helen ford i'm 67 years old and i live on route 9")
    assert r.mentions_minor is False


def test_seconds_from_segments():
    segs = [
        {"text": "thank you", "start": 10.0, "duration": 2.0},
        {"text": "my name is jane doe", "start": 12.5, "duration": 3.0},
        {"text": "and i live here", "start": 15.5, "duration": 2.0},
    ]
    raw = " ".join(s["text"] for s in segs)
    r = _one(raw, segs)
    assert r.char_offset == raw.index("my name")
    assert r.start_seconds == 12.5
    assert r.end_seconds == 15.5


def test_seconds_unknown_when_segments_dont_match_text():
    r = _one("my name is jane doe", [{"text": "something else", "start": 1.0}])
    assert r.start_seconds is None and r.char_offset == 0


def test_offsets_are_into_raw_text():
    text = "[Music] item four public comment. >> My name is Kevin Hart. I oppose this."
    r = _one(text)
    assert text[r.char_offset :].lower().startswith("my name is kevin hart")


def test_this_is_from_needs_first_and_last_name():
    for text in (
        "this is exempt from the ordinance",
        "this is consistent with the plan",
        "this is Carolina Environmental Systems with the permit",
    ):
        assert find_intros("vid", text) == [], text


def test_chair_call_followed_by():
    r = _one("first speaker will be patricia wilson followed by tom")
    assert r.name_tokens == ("patricia", "wilson")
