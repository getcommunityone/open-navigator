"""#1126: Jev reads how the public and officials leaned on any topic, per meeting. Jev is faked; nothing is sent."""

import re
from pathlib import Path

import pytest
import yaml

from llm.typesafe import screen_transcripts as st
from llm.typesafe import topic_lean as tl

DBT = Path(__file__).resolve().parents[3] / "dbt_project"

# The question_version of every row in bronze.bronze_transcript_topic_lean_jev (local warehouse, 2026-11-27:
# guns 7,036 rows, short-term rentals 4,156, pickleball 3,960, license plate readers 1,216, water fluoridation 526).
# Rewording a topic changes its hash, and a run would then pay to re-read every one of its meetings (#1201, #1239).
# Change a value here only together with a deliberate, owner-approved re-read of that topic.
STORED_QUESTION_VERSIONS = {
    "guns": "48468cc5296e",
    "short-term-rentals": "357daa1ae513",
    "pickleball": "ec1984d88dd7",
    "license-plate-readers": "9a2753c719c8",
    "water-fluoridation": "5a7828a925fd",
}


def _create_columns() -> list[str]:
    return re.findall(r"^\s{4}(\w+)\s+(?:text|integer|jsonb|timestamptz)\b", tl.CREATE_SQL, re.MULTILINE)


class _Ans:
    def __init__(self, probabilities=None):
        self.probabilities = probabilities
        self.noul = None


class _Resp:
    def __init__(self, answers, input_tokens=10):
        self.answers = {k: _Ans(v) for k, v in answers.items()}
        self.input_tokens = input_tokens
        self.model = "jev-test"
        self.raw = {"answers": answers}


def test_cli_topics_match_definitions_and_ids() -> None:
    assert set(st.TOPIC_SLUGS) == set(tl.TOPICS)
    ids = {slug: t.topic_id for slug, t in tl.TOPICS.items()}
    assert ids == {
        "guns": 100005, "short-term-rentals": 100003, "pickleball": 100006,
        "license-plate-readers": 100004, "water-fluoridation": 100002,
    }
    args = st.build_parser().parse_args(["--topic", "pickleball", "--limit", "20", "--max-input-tokens", "5"])
    assert args.topic == "pickleball" and args.max_input_tokens == 5


def test_generic_topics_ask_the_shared_labels() -> None:
    for slug in ("guns", "short-term-rentals", "pickleball", "license-plate-readers"):
        q = tl.topic_questions(tl.TOPICS[slug])
        assert set(q) == {"public_lean", "official_lean", "outcome"}
        assert tuple(q["public_lean"]["criteria"]) == tl.LEAN_LABELS
        assert tuple(q["official_lean"]["criteria"]) == tl.LEAN_LABELS
        assert tuple(q["outcome"]["criteria"]) == tl.OUTCOME_LABELS
    # Each definition rules out its false hits.
    assert "staple" in tl.topic_questions(tl.TOPICS["guns"])["public_lean"]["instructions"]
    assert "noise" in tl.topic_questions(tl.TOPICS["pickleball"])["public_lean"]["instructions"]


def test_fluoridation_mirrors_carequest_positions() -> None:
    q = tl.topic_questions(tl.TOPICS["water-fluoridation"])
    positions = ["support_require_all", "support_local_choice", "no_opinion", "oppose_local_choice", "oppose_ban_all"]
    assert list(q["public_lean"]["criteria"]) == [*positions, "did_not_speak"]
    assert list(q["official_lean"]["criteria"]) == [*positions, "did_not_speak"]
    assert list(q["outcome"]["criteria"]) == [
        "voted_to_end_fluoridation", "voted_to_keep_or_start", "tabled_or_deferred", "discussion_only",
        "no_fluoridation_item",
    ]


def test_question_versions_are_per_topic() -> None:
    versions = {tl.question_version(t) for t in tl.TOPICS.values()}
    assert len(versions) == len(tl.TOPICS)


def test_keyword_chunks_pick_the_passages_on_topic() -> None:
    pattern = tl.keyword_pattern(["firearm", "gun show", "short-term rental"])
    chunks = ["roads and sewers", "a gun-show at the fairgrounds", "Firearms in parks; firearm storage", "budget"]
    picked, with_hits = tl.pick_keyword_chunks(chunks, pattern, max_chunks=1)
    assert picked == [2] and with_hits == 2
    assert tl.pick_keyword_chunks(chunks, pattern, max_chunks=4) == ([1, 2], 2)
    # No hit anywhere: evenly spaced, like the screen.
    assert tl.pick_keyword_chunks(["a", "b", "c"], pattern, max_chunks=2) == ([0, 2], 0)


def test_aggregate_ignores_chunks_off_topic() -> None:
    quiet = _Resp({
        "public_lean": {"did_not_speak": 0.9, "mostly_opposed": 0.1},
        "official_lean": {"did_not_speak": 0.95, "mostly_supportive": 0.05},
        "outcome": {"no_item": 0.9, "advanced": 0.1},
    })
    spoke = _Resp({
        "public_lean": {"mostly_opposed": 0.8, "mixed": 0.1, "mostly_supportive": 0.05, "did_not_speak": 0.05},
        "official_lean": {"mostly_supportive": 0.6, "mixed": 0.3, "did_not_speak": 0.1},
        "outcome": {"advanced": 0.7, "blocked": 0.2, "no_item": 0.1},
    })
    out = tl.aggregate_topic([quiet, spoke, quiet])
    assert out["public_lean"] == "mostly_opposed"
    assert out["official_lean"] == "mostly_supportive"
    assert out["outcome"] == "advanced"
    assert "did_not_speak" not in out["public_lean_probabilities"]


def test_fluoridation_outcome_none_label() -> None:
    quiet = _Resp({"outcome": {"no_fluoridation_item": 0.97, "discussion_only": 0.03}})
    out = tl.aggregate_topic([quiet], outcome_none="no_fluoridation_item")
    assert out["outcome"] == "no_fluoridation_item"


def test_select_sql_is_resumable_per_topic_and_version() -> None:
    topic = tl.TOPICS["guns"]
    sql, params = tl.select_sql(topic, rescreen=False)
    assert "topic_transcript_link WHERE topic_id = %s" in sql
    assert tl.TABLE in sql and "s.question_version = %s" in sql
    assert params == [100005, 100005, tl.question_version(topic)]
    sql2, params2 = tl.select_sql(topic, rescreen=True, states=["al"])
    assert tl.TABLE not in sql2 and params2 == [100005, ["AL"]]


def test_screen_writes_one_row_per_meeting_and_topic() -> None:
    class _Client:
        model = "jev-test"

        def __init__(self):
            self.calls = []

        def system_one(self, *, state, questions):
            self.calls.append(state)
            return _Resp({
                "public_lean": {"mostly_supportive": 0.9, "did_not_speak": 0.1},
                "official_lean": {"mixed": 0.8, "did_not_speak": 0.2},
                "outcome": {"tabled_or_deferred": 0.8, "no_item": 0.2},
            }, input_tokens=100)

    client = _Client()
    topic = tl.TOPICS["pickleball"]
    segments = ["Item 4 pickleball courts at Elm Park.", "Residents on noise."]
    result = tl.screen_topic_transcript(
        client, "vid1", segments, topic, pattern=tl.keyword_pattern(["pickleball"]), chunk_chars=40, max_chunks=4
    )
    assert result is not None and len(client.calls) == 1 and result.keyword_chunks == 1
    row = result.row()
    assert row["topic_id"] == 100006 and row["question_version"] == tl.question_version(topic)
    assert row["public_lean"] == "mostly_supportive" and row["input_tokens"] == 100


def test_neighbor_chunks_and_coverage_1145() -> None:
    """#1145: the chunks sent are the keyword passages (never just the head), optionally with their neighbours."""
    pattern = tl.keyword_pattern(["flock camera"])
    chunks = ["call to order", "budget", "public comment: Flock cameras are surveillance", "votes", "adjourn"]
    picked, with_hits = tl.pick_keyword_chunks(chunks, pattern, max_chunks=4)
    assert picked == [2] and with_hits == 1
    assert tl.chunk_coverage(chunks, picked, pattern, with_hits) == ("keyword_passages", 1)
    wide, _ = tl.pick_keyword_chunks(chunks, pattern, max_chunks=4, neighbors=1)
    assert wide == [1, 2, 3]
    assert tl.chunk_coverage(chunks, wide, pattern, with_hits) == ("keyword_passages", 1)
    none, n = tl.pick_keyword_chunks(chunks, tl.keyword_pattern(["pickleball"]), max_chunks=2)
    assert none == [0, 4] and tl.chunk_coverage(chunks, none, tl.keyword_pattern(["pickleball"]), n) == ("evenly_spaced", 0)


def test_rows_carry_chunk_selection() -> None:
    result = tl.TopicLeanResult(
        video_id="v", topic=tl.TOPICS["guns"], model="m", public_lean=None, public_lean_probabilities=None,
        official_lean=None, official_lean_probabilities=None, outcome=None, outcome_probabilities=None,
        chunk_count=3, chunks_screened=1, keyword_chunks=1, transcript_chars=10, input_tokens=5, answers=[],
        chunk_selection="keyword_passages", passages_covered=1,
    )
    row = result.row()
    assert row["chunk_selection"] == "keyword_passages" and row["passages_covered"] == 1
    assert "passages_covered" in tl.UPSERT_SQL and "ADD COLUMN IF NOT EXISTS chunk_selection" in tl.ALTER_SQL
    assert st.build_parser().parse_args(["--topic", "guns", "--neighbor-chunks", "1"]).neighbor_chunks == 1


def test_question_versions_match_the_stored_readings_1201_1239() -> None:
    assert {slug: tl.question_version(t) for slug, t in tl.TOPICS.items()} == STORED_QUESTION_VERSIONS


def test_guns_is_the_gun_control_question_1239() -> None:
    guns = tl.TOPICS["guns"]
    assert guns.subject.startswith("a local gun-control measure")
    assert "proposal before the body" not in tl.topic_questions(guns)["public_lean"]["instructions"]
    assert "asking for limits on guns" in guns.sides and "defending gun rights" in guns.sides


def test_create_and_upsert_columns_match_the_table_and_its_dbt_source_1201() -> None:
    create = _create_columns()
    insert = [c.strip() for c in tl.UPSERT_SQL.split("(", 1)[1].split(")", 1)[0].split(",")]
    assert len(create) == len(set(create)) == 20
    assert set(insert) == set(create)
    for col in ("topic_slug", "keyword_chunks", "transcript_chars", "chunk_selection", "passages_covered"):
        assert col in create
    for col in ("topic_slug", "model", "chunk_count", "chunks_screened", "keyword_chunks", "transcript_chars", "answers"):
        assert re.search(rf"^\s{{4}}{col}\s+\w+ NOT NULL", tl.CREATE_SQL, re.MULTILINE), col
    # The dbt source lists exactly the writer's columns, and the staging model reads only those.
    staging = yaml.safe_load((DBT / "models" / "staging" / "_staging.yml").read_text())
    source = next(
        t for src in staging["sources"] for t in src.get("tables", []) if t["name"] == "bronze_transcript_topic_lean_jev"
    )
    assert [c["name"] for c in source["columns"]] == create
    stg = (DBT / "models" / "staging" / "stg_jev__transcript_topic_lean.sql").read_text()
    assert set(re.findall(r"\bs\.(\w+)", stg)) <= set(create)
    for col in ("topic_slug", "keyword_chunks", "chunk_selection", "passages_covered"):
        assert f"s.{col}" in stg


def test_topic_all_and_comma_lists() -> None:
    assert [t.slug for t in tl.resolve_topics("all")] == list(tl.TOPICS)
    assert [t.slug for t in tl.resolve_topics("guns, pickleball")] == ["guns", "pickleball"]
    with pytest.raises(SystemExit):
        tl.resolve_topics("bike-lanes")
    args = st.build_parser().parse_args(["--topic", "all", "--dry-run"])
    assert args.topic == "all" and args.dry_run


def test_run_loops_each_topic(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(tl, "run_topic", lambda args, *, topic=None: seen.append(topic.slug) or {"selected": 0})
    out = tl.run(st.build_parser().parse_args(["--topic", "all", "--dry-run"]))
    assert seen == list(tl.TOPICS) and set(out["topics"]) == set(tl.TOPICS)
