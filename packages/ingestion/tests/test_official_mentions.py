"""Officials heard in a meeting (#1444): roster-matched chair calls and roll calls, on real caption phrasings."""

from __future__ import annotations

from ingestion.youtube.official_mentions import Member, classify, find_mentions

J = "tuscaloosa_0177256"
ROSTER = [
    Member(J, "p-maddox", "Walt Maddox", "walt maddox"),
    Member(J, "p-howard", "Raevan Howard", "raevan howard"),
    Member(J, "p-lanier", "Cassius Lanier", "cassius lanier"),
    Member(J, "p-busby", "Lee Busby", "lee busby"),
    Member(J, "p-henry", "Richard Henry", "richard henry"),
]


def kinds(text: str, roster=ROSTER) -> list[tuple[str, str]]:
    return [(m.member.member_name, m.pattern_id) for m in find_mentions("vid", text, roster)]


def test_roll_call_vote() -> None:
    # Real caption text (Tuscaloosa City Council, 2026).
    assert kinds("Motion second. Um voting with councelor Howard. >> Yes. >> Yes. >> Yes.") == [("Raevan Howard", "roll_call")]
    assert kinds("Seeing none, voting on the application, Mr. Lanier. No. No. No.") == [("Cassius Lanier", "roll_call")]


def test_chair_call_handoff() -> None:
    assert kinds("Okay. Thank you, Zach. Mayor Maddox. >> Yes, sir. I don't have anything") == [("Walt Maddox", "chair_call")]
    assert kinds("tatue of Project Warrior. Councilman Busby. >> Yeah, I'll do these two.") == [("Lee Busby", "chair_call")]
    assert kinds("I recognize Councilor Busby for a motion") == [("Lee Busby", "chair_call")]


def test_plain_mention_is_not_heard() -> None:
    assert kinds("And um and Mr. Henry will be here at 2:00. He'll be late.") == []
    assert kinds("I spoke with Councilor Busby yesterday about the road") == []


def test_name_not_on_roster_never_matches() -> None:
    # "Councilor Smith" is not on this place's roster: speech alone never makes someone an official.
    assert kinds("Councilor Smith. >> Thank you, I have a question") == []


def test_shared_surname_needs_first_name() -> None:
    roster = ROSTER + [Member(J, "p-howard2", "Dana Howard", "dana howard")]
    assert kinds("voting with Councilor Howard. >> Yes.", roster) == []
    assert kinds("voting with Councilor Dana Howard. >> Yes.", roster) == [("Dana Howard", "roll_call")]


def test_self_intro_and_seconds() -> None:
    text = "Good evening this is Councilor Howard from district two"
    segs = [{"start": 10.0, "text": "Good evening"}, {"start": 12.5, "text": "this is Councilor Howard from district two"}]
    found = find_mentions("vid", text, ROSTER, segs)
    assert [(m.pattern_id, m.start_seconds) for m in found] == [("self_intro", 12.5)]


def test_classify_order() -> None:
    t = "Commissioner Smith? >> Here."
    assert classify(t, 0, len("Commissioner Smith")) == "roll_call"
