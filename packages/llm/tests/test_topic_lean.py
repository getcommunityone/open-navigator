"""#1126: Jev's per-topic lean (llm.typesafe.topic_lean). Jev is faked; nothing is sent."""

from __future__ import annotations

import csv
from types import SimpleNamespace

import pytest

from llm.typesafe import screen_transcripts as st
from llm.typesafe import topic_lean as tl


def _ans(probabilities):
    return SimpleNamespace(probabilities=probabilities, noul=None)


def _resp(**answers):
    return SimpleNamespace(answers={k: _ans(v) for k, v in answers.items()})


def test_every_topic_matches_its_curated_seed_row() -> None:
    with tl.SEED_PATH.open(newline="", encoding="utf-8") as f:
        seed = {int(r["topic_id"]): r["query_id"] for r in csv.DictReader(f)}
    for slug, t in tl.TOPICS.items():
        assert seed.get(t.topic_id) == slug, slug
    assert "data-centers" not in tl.TOPICS  # data centers keep their own screen


def test_questions_have_the_issue_labels_and_say_which_way_for_points() -> None:
    q = tl.questions_for(tl.TOPICS["pickleball"])
    assert set(q) == {"public_lean", "official_lean", "outcome"}
    assert set(q["public_lean"]["criteria"]) == {"mostly_opposed", "mostly_supportive", "mixed", "did_not_speak"}
    assert set(q["official_lean"]["criteria"]) == {"mostly_opposed", "mostly_supportive", "mixed", "did_not_speak"}
    assert "pickleball courts or venue" in q["public_lean"]["instructions"]
    assert "no_item" in q["outcome"]["criteria"]


def test_question_version_is_per_topic_and_changes_with_wording() -> None:
    a, b = tl.TOPICS["pickleball"], tl.TOPICS["guns"]
    assert tl.question_version(a) != tl.question_version(b)
    reworded = tl.TopicDef(a.slug, a.topic_id, a.thing + " (reworded)", a.stance, a.item)
    assert tl.question_version(reworded) != tl.question_version(a)


def test_only_chunks_naming_the_topic_are_read() -> None:
    pat = tl.keyword_regex(["pickleball", "pickleball courts"])
    chunks = ["budget talk", "the Pickleball courts again, pickleball noise", "roads", "one pickleball mention", "x"]
    assert tl.topic_chunks(chunks, pat, 3) == [1, 3]
    assert tl.topic_chunks(chunks, pat, 1) == [1]  # most hits first when capped
    assert tl.topic_chunks(["no hit here", "none"], pat, 3) == [0]  # no hit: the first chunk
    assert tl.topic_chunks([], pat, 3) == []
    with pytest.raises(ValueError):
        tl.topic_chunks(chunks, pat, 0)


def test_keyword_regex_is_whole_word() -> None:
    pat = tl.keyword_regex(["bike lane"])
    assert pat.search("a new Bike Lane on Main")
    assert not pat.search("bike lanes" .replace("lanes", "laneway"))


def test_lean_averages_only_chunks_where_someone_spoke() -> None:
    quiet = _resp(public_lean={"did_not_speak": 0.9, "mostly_opposed": 0.1})
    loud = _resp(public_lean={"did_not_speak": 0.1, "mostly_opposed": 0.6, "mixed": 0.3})
    out = tl.lean_from([quiet, loud], "public_lean")
    assert out["public_lean"] == "mostly_opposed"
    assert out["public_lean_probabilities"] == {"mostly_opposed": 0.6667, "mixed": 0.3333}
    none = tl.lean_from([quiet], "public_lean")
    assert none["public_lean"] == "did_not_speak"
    assert tl.lean_from([], "public_lean") == {"public_lean": None, "public_lean_probabilities": None}


def test_outcome_is_averaged_across_chunks() -> None:
    out = tl.outcome_from([_resp(outcome={"approved": 0.8, "no_item": 0.2}), _resp(outcome={"approved": 0.4, "no_item": 0.6})])
    assert out == {"outcome": "approved", "outcome_probabilities": {"approved": 0.6, "no_item": 0.4}}


def test_select_sql_reads_the_topic_links_and_skips_current_screens() -> None:
    t = tl.TOPICS["guns"]
    sql, params = tl.select_sql(t, states=["al"], rescreen=False)
    assert "public.topic_transcript_link l" in sql and "l.topic_id = %s" in sql
    assert params == [100005, ["AL"], 100005, tl.question_version(t)]
    sql2, params2 = tl.select_sql(t, states=[], rescreen=True)
    assert "NOT EXISTS" not in sql2 and params2 == [100005]


def test_resolve_topics() -> None:
    assert [t.slug for t in tl.resolve_topics("pickleball,guns")] == ["pickleball", "guns"]
    assert len(tl.resolve_topics("all")) == len(tl.TOPICS)
    with pytest.raises(SystemExit):
        tl.resolve_topics("data-centers")


def test_cli_has_topic_flag() -> None:
    args = st.build_parser().parse_args(["--topic", "pickleball", "--limit", "5", "--dry-run"])
    assert args.topic == "pickleball" and args.limit == 5 and args.dry_run


def test_screen_one_reads_topic_chunks_and_builds_a_row(monkeypatch) -> None:
    sent = []

    class FakeClient:
        model = "jev-test"

        def system_one(self, *, state, questions):
            sent.append(state)
            return SimpleNamespace(
                model="jev-test",
                input_tokens=100,
                raw={"answers": {}},
                answers={
                    "public_lean": _ans({"mostly_opposed": 0.8, "did_not_speak": 0.1, "mixed": 0.1}),
                    "official_lean": _ans({"mostly_supportive": 0.7, "did_not_speak": 0.2, "mixed": 0.1}),
                    "outcome": _ans({"approved": 0.9, "no_item": 0.1}),
                },
            )

    t = tl.TOPICS["pickleball"]
    segs = ["budget " * 50, "residents spoke about the pickleball courts", "roads " * 50]
    r = tl.screen_one(FakeClient(), t, "vid1", segs, tl.keyword_regex(["pickleball"]), chunk_chars=300, max_chunks=3)
    assert r is not None and r.chunks_screened == 1 and "pickleball" in sent[0]
    row = r.row()
    assert row["topic_id"] == 100006 and row["public_lean"] == "mostly_opposed" and row["official_lean"] == "mostly_supportive"
    assert row["outcome"] == "approved" and row["input_tokens"] == 100
