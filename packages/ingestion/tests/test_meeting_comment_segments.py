"""Comment segmentation over realistic caption snippets (#1233)."""

from __future__ import annotations

from ingestion.meetings.comment_segments import (
    Cue,
    clean_name,
    cues_from_segments,
    cues_from_timed_text,
    segment_comments,
)


def _cues(lines: list[tuple[float, str]], duration: float = 2.0) -> list[Cue]:
    return [Cue(start, duration, text) for start, text in lines]


FILLER = (
    "I am here tonight because the proposed data center would use millions of gallons of water every day "
    "and our wells are already running low in the summer and nobody has told us where that water comes from"
)


def _speech(start: float, words: str, step: float = 2.0, per_cue: int = 7) -> list[tuple[float, str]]:
    toks = words.split()
    out = []
    t = start
    for i in range(0, len(toks), per_cue):
        out.append((t, " ".join(toks[i : i + per_cue])))
        t += step
    return out


def test_two_self_introduced_speakers_become_two_comments() -> None:
    lines = [(0.0, "Okay we'll now open the public comment period. Each speaker gets three minutes.")]
    lines += [(10.0, "Good evening, Mayor and council."), (12.0, "My name is Bonnie Larson, and I live")]
    lines += _speech(14.0, "on Ridge Road. " + FILLER + " thank you")
    lines += [(70.0, "Thank you for your comments."), (75.0, ">> Next speaker please.")]
    lines += [(80.0, ">> Hi, my name is Michael Plappa. I've lived in Joliet since I was nine.")]
    lines += _speech(82.0, FILLER + " and I am asking you to vote no")
    comments = segment_comments("vid1", _cues(lines))

    assert len(comments) == 2
    first, second = comments
    assert first.intro_name == "Bonnie Larson"
    assert first.comment_text.startswith("Good evening, Mayor and council.")
    assert "Michael" not in first.comment_text
    assert first.end_seconds < second.start_seconds
    assert second.intro_name == "Michael Plappa"
    assert first.in_public_comment_section and second.in_public_comment_section
    assert first.block_index == second.block_index == 0
    assert [c.comment_index for c in comments] == [0, 1]


def test_short_procedure_is_not_a_comment() -> None:
    lines = [(0.0, "My name is Sam. Thank you."), (3.0, ">> Motion to adjourn. Second. All in favor? Aye.")]
    assert segment_comments("vid2", _cues(lines)) == []


def test_no_anchor_means_no_comments() -> None:
    lines = _speech(0.0, FILLER + " " + FILLER)
    assert segment_comments("vid3", _cues(lines)) == []


def test_timer_closing_ends_the_comment() -> None:
    lines = [(0.0, "My name is Alma Montero and I live in Joliet.")]
    lines += _speech(2.0, FILLER + " " + FILLER)
    lines += [(27.0, "Ma'am, your time is up."), (29.0, "Okay. So the council will now discuss the item")]
    lines += _speech(31.0, "the staff report recommends approval subject to the conditions in the packet " * 3)
    (comment,) = segment_comments("vid4", _cues(lines))
    assert comment.boundary_basis == "self_intro>closing"
    assert "staff report" not in comment.comment_text


def test_long_pause_and_max_length() -> None:
    lines = [(0.0, "My name is Jeff Becker. I have a little cold.")]
    lines += _speech(2.0, FILLER + " " + FILLER)
    lines += _speech(200.0, "after a long recess we are back in session " * 5)
    (comment,) = segment_comments("vid5", _cues(lines))
    assert comment.boundary_basis == "self_intro>pause"
    assert comment.end_seconds < 200.0

    long_lines = [(0.0, "My name is Nancy Rivera.")] + _speech(2.0, "word " * 2000, step=3.0)
    (long_comment,) = segment_comments("vid6", _cues(long_lines))
    assert long_comment.boundary_basis == "self_intro>max_length"
    assert long_comment.end_seconds - long_comment.start_seconds <= 485.0


def test_chair_call_opens_a_comment_without_a_self_intro() -> None:
    lines = [(0.0, "First is Miss Candice Cooper.")]
    lines += [(3.0, ">> Um uh good evening everybody, Mr. Mayor, city manager.")]
    lines += _speech(5.0, FILLER + " " + FILLER)
    (comment,) = segment_comments("vid7", _cues(lines))
    assert comment.boundary_basis.startswith("chair_call")
    assert comment.comment_text.lower().startswith("um uh good evening") or "good evening" in comment.comment_text


def test_comments_far_apart_get_separate_blocks() -> None:
    lines = [(0.0, "My name is Dale Lewis.")] + _speech(2.0, FILLER + " " + FILLER)
    lines += [(1000.0, "My name is Janet Smith.")] + _speech(1002.0, FILLER + " " + FILLER)
    comments = segment_comments("vid8", _cues(lines))
    assert [c.block_index for c in comments] == [0, 1]


def test_clean_name_stops_at_non_name_words() -> None:
    assert clean_name("Lilly and I'm a lifelong") == "Lilly"
    assert clean_name("SHAWN MILLER. I am") == "Shawn Miller"
    assert clean_name("Dr. Glenda Wright-McCollum, and") == "Glenda Wright-McCollum"
    assert clean_name("not Kip Klein") is None
    assert clean_name("") is None


def test_cue_parsers() -> None:
    cues = cues_from_segments('[{"text": "hello there", "start": 1.5, "duration": 2}, {"text": "", "start": 3}]')
    assert cues == [Cue(1.5, 2.0, "hello there")]
    timed = cues_from_timed_text("{00:00:01} good evening {00:01:05} my name is Pat")
    assert [c.start for c in timed] == [1.0, 65.0]
    assert timed[0].duration == 64.0


def test_home_addresses_are_scrubbed_but_public_places_kept() -> None:
    from ingestion.meetings.comment_segments import ADDRESS_REDACTION
    from ingestion.meetings.comment_segments import scrub_personal_location as scrub

    assert scrub("I live at one uh 1703 Heritage Point, Plainfield, Illinois.") == (
        f"I live at {ADDRESS_REDACTION}, Plainfield, Illinois."
    )
    assert scrub("I live on Ridge Road and I oppose this") == f"I live on {ADDRESS_REDACTION} and I oppose this"
    assert scrub("We are at 412 N. Oak Street right now") == f"We are at {ADDRESS_REDACTION} right now"
    # A town of residence, acreage on a named road and a route number are public, not a home address.
    assert scrub("I live in Joliet.") == "I live in Joliet."
    assert scrub("The site is 300 acres on Ridge Road near Route 9") == "The site is 300 acres on Ridge Road near Route 9"
    assert scrub(None) is None


def test_segmented_comment_text_never_holds_a_house_address() -> None:
    lines = [(0.0, "Good evening. My name is Frederick Dahlmeyer. I live at 1703 Heritage Point, Plainfield.")]
    lines += _speech(4.0, FILLER + " " + FILLER)
    (comment,) = segment_comments("vid9", _cues(lines))
    assert "1703" not in comment.comment_text and "Heritage" not in comment.comment_text
    assert comment.intro_text is not None and "1703" not in comment.intro_text


def test_scrub_covers_review_cases() -> None:
    """Cases from the PR #1247 review: other subjects, adverbs, home/house phrasing, lowercase, no punctuation."""
    from ingestion.meetings.comment_segments import ADDRESS_REDACTION as R
    from ingestion.meetings.comment_segments import scrub_personal_location as scrub

    assert scrub("We live on Ridge Road.") == f"We live on {R}."
    assert scrub("I live right on Ridge Road.") == f"I live right on {R}."
    assert scrub("my home on Ridge Road is a quarter mile from the site.") == f"my home on {R} is a quarter mile from the site."
    assert scrub("my house is 412 oak street") == f"my house is {R}"
    assert scrub("i live on ridge road been here thirty years") == f"i live on {R} been here thirty years"
    # Not a home location: left alone.
    assert scrub("my home is very important to me") == "my home is very important to me"
    assert scrub("our property values will drop") == "our property values will drop"
    assert scrub("we have lived here for 30 years") == "we have lived here for 30 years"
