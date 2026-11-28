"""#1391: each public speaker's side and heat on a topic, read by Jev. Jev is faked; nothing is sent."""

import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from llm.typesafe import speaker_stance as ss
from llm.typesafe import speaker_stance_gold as gold
from llm.typesafe import topic_lean as tl
from llm.typesafe.client import JevAnswer, JevError, JevResponse

DBT = Path(__file__).resolve().parents[3] / "dbt_project"

# The question_version of every topic's side + heat questions, as read by the committed gold run and the full run
# (#1391). Rewording a topic changes its hash, and a run would then pay to re-read all of its speakers. Change a value
# here only together with a deliberate, owner-approved re-read of that topic.
PINNED_QUESTION_VERSIONS: dict[str, str] = {
    "data-centers": "94796ad1fa0a",
    "water-fluoridation": "a300273008bd",
    "short-term-rentals": "a4c63db84fc9",
    "license-plate-readers": "5d8bbb26dc72",
    "guns": "f441bed4b77e",
    "pickleball": "63b1c05d9121",
    "traffic-safety": "6487b09240b8",
    "police-staffing": "269fda0b7529",
    "parks-funding": "7e9edf06331c",
    "homelessness-and-shelters": "03bc8d1930de",
    "immigration-and-sanctuary": "fd4f4a1806bc",
    "bike-lanes": "d59af5e6534f",
    "local-taxation": "6bfe729947f4",
    "affordable-housing": "207105896b3e",
    "zoning-regulations": "240068ce2036",
    "renewable-energy": "ebaebc26ed30",
    "surveillance-cameras": "eab4d415a535",
    "public-transit": "5546e557c76b",
    "alcohol-licensing": "e6393db1e018",
    # #1436 coverage topics (new; held until their gold check passes)
    "missing-middle-housing": "0d76267e8e1d",
    "road-diets": "3112665afa83",
    "backyard-chickens": "8e07cba2cec4",
    "speed-cameras": "8ae8d3b0f77a",
    "speed-bumps": "5c790ba201c9",
    "roundabouts": "d19f8d1791fe",
    "gas-stations": "7921e9f64e09",
    "artificial-turf": "9a71a0753f17",
    "homeless-encampments": "f475e5b73573",
    "solar-farms": "030a6804e08c",
    "battery-storage": "4cd0b9054486",
}

# The meeting-level topics' stored hashes (test_topic_lean.STORED_QUESTION_VERSIONS) must never move because of this work.
STORED_MEETING_VERSIONS = {
    "guns": "48468cc5296e",
    "short-term-rentals": "357daa1ae513",
    "pickleball": "ec1984d88dd7",
    "license-plate-readers": "9a2753c719c8",
    "water-fluoridation": "5a7828a925fd",
}


def test_question_versions_are_pinned() -> None:
    got = {slug: ss.question_version(t) for slug, t in ss.TOPICS.items()}
    assert got == PINNED_QUESTION_VERSIONS
    assert len(set(got.values())) == len(got)


def test_meeting_topic_hashes_unchanged() -> None:
    assert {s: tl.question_version(tl.TOPICS[s]) for s in STORED_MEETING_VERSIONS} == STORED_MEETING_VERSIONS


def test_topics_ids_and_priority() -> None:
    assert len(ss.TOPICS) == 30
    assert len({t.topic_id for t in ss.TOPICS.values()}) == 30
    assert ss.PRIORITY[0] == "data-centers"
    assert set(ss.PRIORITY) == set(ss.TOPICS)
    for slug, t in ss.TOPICS.items():
        assert t.slug == slug
        # the 19 original topics: curated (>= 100000) use their seed keywords, reframed CivicSearch topics carry their
        # own phrases; the coverage topics (#1436) all carry their own whole-word phrases
        if slug in ss.NEW_TOPICS:
            assert t.keywords and t.topic_id > 100100, slug
        else:
            assert (t.keywords is None) == (t.topic_id >= 100000), slug


def test_coverage_topics_are_held_until_validated() -> None:
    assert set(ss.NEW_TOPICS) <= ss.HELD
    assert not set(ss.NEW_TOPICS) & {t.slug for t in ss.resolve_topics("all")}
    # renewable energy stays as it was; solar farms and battery storage are separate questions beside it
    assert ss.TOPICS["renewable-energy"].topic_id == 90
    pat = ss.strict_pattern(ss.TOPICS["speed-bumps"].keywords)
    assert pat.search("we need speed humps on Elm") and not pat.search("a bump in the road")
    turf = ss.strict_pattern(ss.TOPICS["roundabouts"].keywords)
    assert not turf.search("the Rotary club met") and turf.search("a new roundabout at Main")


def test_questions_ask_side_and_heat_ladder() -> None:
    q = ss.speaker_questions(ss.TOPICS["guns"])
    assert set(q) == {"side", "heat_2", "heat_3", "heat_4", "heat_5"}
    assert tuple(q["side"]["criteria"]) == ss.SIDES
    assert q["side"]["type"] == "choice"
    assert all(q[f"heat_{k}"]["type"] == "noul" for k in ss.HEAT_LEVELS)
    assert "staple" in q["side"]["instructions"]  # the gun definition's false hits come along


def test_build_state_windows_keyword_passages() -> None:
    pat = tl.keyword_pattern(["data center"])
    filler = "word " * 400
    text = f"{filler}I oppose the data center on Main Street. {filler}"
    state = ss.build_state(text, pat)
    assert state is not None and "I oppose the data center" in state
    assert len(state) <= 2 * ss.WINDOW_CHARS + 20
    assert ss.build_state("nothing here", pat) is None
    # many hits far apart: capped, in speech order
    long = (" data center " + "x " * 800) * 6
    capped = ss.build_state(long, pat)
    assert capped is not None and len(capped) <= ss.MAX_STATE_CHARS + 50


@pytest.mark.parametrize(
    ("probs", "heat"),
    [
        ({"heat_2": 0.2, "heat_3": 0.1, "heat_4": 0.0, "heat_5": 0.0}, 1),
        ({"heat_2": 0.9, "heat_3": 0.7, "heat_4": 0.3, "heat_5": 0.1}, 3),
        ({"heat_2": 0.9, "heat_3": 0.4, "heat_4": 0.8, "heat_5": 0.9}, 2),  # the ladder stops at the first no
        ({"heat_2": 0.99, "heat_3": 0.99, "heat_4": 0.99, "heat_5": 0.99}, 5),
    ],
)
def test_heat_ladder(probs: dict[str, float], heat: int) -> None:
    assert ss.heat_from(probs)[0] == heat


def _resp(side: str, p: float, heats: tuple[float, ...] = (0.8, 0.3, 0.1, 0.0)) -> JevResponse:
    answers = {"side": JevAnswer(type="choice", choice=side, probabilities={side: p})}
    answers.update({f"heat_{k}": JevAnswer(type="noul", noul=h) for k, h in zip(ss.HEAT_LEVELS, heats)})
    return JevResponse(model="jev-1.14.0", answers=answers, input_tokens=900, output_tokens=0, raw={"answers": {}})


def test_read_response_row_matches_bronze_columns() -> None:
    r = ss.read_response(_resp("against", 0.91), speaker_id="abc", video_id="v1", topic=ss.TOPICS["data-centers"],
                         state="text")
    row = r.row()
    cols = re.findall(r"^\s{4}(\w+)\s+(?:text|integer|jsonb|timestamptz|numeric)", ss.CREATE_SQL, re.MULTILINE)
    assert set(row) == set(cols)
    assert row["side"] == "against" and row["heat"] == 2 and row["side_confidence"] == 0.91
    assert row["question_version"] == ss.question_version(ss.TOPICS["data-centers"])


def test_bronze_source_lists_create_sql_columns() -> None:
    cols = re.findall(r"^\s{4}(\w+)\s+(?:text|integer|jsonb|timestamptz|numeric)", ss.CREATE_SQL, re.MULTILINE)
    src = yaml.safe_load((DBT / "models/staging/_staging.yml").read_text())
    tables = {t["name"]: t for s in src["sources"] for t in s.get("tables", [])}
    assert [c["name"] for c in tables["bronze_speaker_topic_stance_jev"]["columns"]] == cols


def test_confidence_floor_matches_dbt_var() -> None:
    proj = yaml.safe_load((DBT / "dbt_project.yml").read_text())
    assert proj["vars"]["speaker_side_min_confidence"] == ss.MIN_SIDE_CONFIDENCE


def test_build_jobs_skips_done_and_orders_by_priority_then_year() -> None:
    topics = [ss.TOPICS["guns"], ss.TOPICS["data-centers"]]
    pats = {"guns": tl.keyword_pattern(["firearm"]), "data-centers": tl.keyword_pattern(["data center"])}
    speakers = [
        ("s1", "v1", date(2025, 5, 1), "the data center and a firearm"),
        ("s2", "v2", date(2026, 3, 1), "the data center"),
        ("s3", "v3", date(2026, 4, 1), "a firearm"),
        ("s4", "v4", date(2024, 1, 1), "nothing"),
    ]
    done = {("s2", 100001, ss.question_version(ss.TOPICS["data-centers"]))}
    jobs, stats = ss.build_jobs(speakers, topics, pats, done)
    assert [(j.topic.slug, j.meeting_speaker_id) for j in jobs] == [
        ("data-centers", "s1"), ("guns", "s3"), ("guns", "s1"),
    ]
    assert stats["data-centers"] == {"matched": 2, "done": 1, "todo": 1, "todo_chars": len(jobs[0].state)}
    # a second pass with everything done reads nothing
    all_done = done | {(j.meeting_speaker_id, j.topic.topic_id, ss.question_version(j.topic)) for j in jobs}
    assert ss.build_jobs(speakers, topics, pats, all_done)[0] == []


def test_stop_statuses_include_payment_required() -> None:
    assert 402 in ss.STOP_STATUSES
    assert JevError("x", status_code=402).status_code in ss.STOP_STATUSES


def test_agreement_counts_swaps_and_clear_accuracy() -> None:
    items = [
        {"topic": "guns", "meeting_speaker_id": "a", "label": "for", "clear": True},
        {"topic": "guns", "meeting_speaker_id": "b", "label": "against", "clear": True},
        {"topic": "guns", "meeting_speaker_id": "c", "label": "concerns_only", "clear": False},
    ]
    preds = {"guns|a": {"side": "for", "side_confidence": 0.9}, "guns|b": {"side": "for", "side_confidence": 0.7},
             "guns|c": {"side": "concerns_only", "side_confidence": 0.5}}
    res = gold.agreement(items, preds)["guns"]
    assert res["clear"] == 2 and res["clear_correct"] == 1 and res["swaps"] == 1 and not res["passes"]
    assert res["exact_accuracy"] == round(2 / 3, 3)


GOLD_EXPECTED: dict[str, dict[str, object]] = {
    "affordable-housing": {
        "items": 50,
        "clear": 9,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "alcohol-licensing": {
        "items": 50,
        "clear": 11,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "bike-lanes": {
        "items": 50,
        "clear": 6,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
    "data-centers": {
        "items": 50,
        "clear": 32,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "guns": {
        "items": 50,
        "clear": 8,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "homelessness-and-shelters": {
        "items": 50,
        "clear": 9,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "immigration-and-sanctuary": {
        "items": 50,
        "clear": 21,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "license-plate-readers": {
        "items": 50,
        "clear": 27,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "local-taxation": {
        "items": 49,
        "clear": 7,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
    "parks-funding": {
        "items": 50,
        "clear": 7,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
    "pickleball": {
        "items": 50,
        "clear": 12,
        "clear_accuracy": 0.917,
        "swaps": 0,
        "passes": True
    },
    "police-staffing": {
        "items": 50,
        "clear": 23,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "public-transit": {
        "items": 36,
        "clear": 3,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
    "renewable-energy": {
        "items": 50,
        "clear": 10,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "short-term-rentals": {
        "items": 50,
        "clear": 18,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "surveillance-cameras": {
        "items": 50,
        "clear": 12,
        "clear_accuracy": 0.917,
        "swaps": 0,
        "passes": True
    },
    "traffic-safety": {
        "items": 50,
        "clear": 6,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
    "water-fluoridation": {
        "items": 50,
        "clear": 20,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": True
    },
    "zoning-regulations": {
        "items": 50,
        "clear": 5,
        "clear_accuracy": 1.0,
        "swaps": 0,
        "passes": False
    },
}


def test_committed_gold_run_numbers() -> None:
    """The committed gold set and Jev's answers give the per-topic numbers in the decision page."""
    items = gold.load_gold()
    preds = json.loads(gold.RESULTS_FILE.read_text(encoding="utf-8"))["predictions"]
    res = gold.agreement(items, preds, min_confidence=ss.MIN_SIDE_CONFIDENCE)
    got = {t: {"items": r["items"], "clear": r["clear"], "clear_accuracy": r["clear_accuracy"], "swaps": r["swaps"],
               "passes": r["passes"]} for t, r in res.items()}
    assert got == GOLD_EXPECTED
    # the gold file carries no speech: keys, labels and hashes only
    for it in items:
        assert set(it) <= {"topic", "meeting_speaker_id", "state_sha256", "label", "clear", "note"}
        assert re.fullmatch(r"[0-9a-f]{32}", it["meeting_speaker_id"]) and re.fullmatch(r"[0-9a-f]{64}", it["state_sha256"])


def test_meeting_heat_orders_hottest_meetings_first_within_a_topic() -> None:
    rows = [("calm", None, 2, 0), ("hot", 5, 40, 6), ("mid", 3, 10, 1)]
    heat = ss.meeting_heat_scores(rows, {("calm", 100005)}, [100005])
    assert heat[("hot", 100005)] > heat[("calm", 100005)]
    assert heat[("calm", 100005)] >= 1.0  # contested adds a full point
    topics = [ss.TOPICS["guns"]]
    pats = {"guns": tl.keyword_pattern(["firearm"])}
    speakers = [("a", "calm", date(2026, 5, 1), "firearm"), ("b", "hot", date(2024, 1, 1), "firearm"),
                ("c", "mid", date(2026, 1, 1), "firearm")]
    heat = ss.meeting_heat_scores(rows, set(), [100005])
    jobs, _ = ss.build_jobs(speakers, topics, pats, set(), heat=heat)
    assert [j.meeting_speaker_id for j in jobs] == ["b", "c", "a"]


def test_round2_gold_is_flagged_ai_helper_and_carries_no_speech() -> None:
    """#1436: the coverage topics' gold set (plus more held bike-lanes / zoning items) holds keys, labels and hashes
    only, and says its labels were made by an AI helper, not a person."""
    doc = json.loads(gold.ROUND2_GOLD_FILE.read_text(encoding="utf-8"))
    assert "AI helper" in doc["labelled_by"]
    items = doc["items"]
    assert {it["topic"] for it in items} == set(ss.NEW_TOPICS) | {"bike-lanes", "zoning-regulations"}
    assert len({(it["topic"], it["meeting_speaker_id"]) for it in items}) == len(items)
    for it in items:
        assert set(it) <= {"topic", "meeting_speaker_id", "state_sha256", "label", "clear", "note"}
        assert it["label"] in ss.SIDES
        assert not it["clear"] or it["label"] in gold.SIDED
        assert re.fullmatch(r"[0-9a-f]{32}", it["meeting_speaker_id"]) and re.fullmatch(r"[0-9a-f]{64}", it["state_sha256"])
        assert len(it["note"].split()) <= 14


def test_combined_rounds_count_each_item_once(tmp_path: Path) -> None:
    item = {"topic": "bike-lanes", "meeting_speaker_id": "a" * 32, "state_sha256": "b" * 64, "label": "for",
            "clear": True, "note": "asks for lanes"}
    g1, g2 = tmp_path / "g1.json", tmp_path / "g2.json"
    g1.write_text(json.dumps({"items": [item]}))
    g2.write_text(json.dumps({"items": [item, {**item, "meeting_speaker_id": "c" * 32, "label": "against"}]}))
    r = tmp_path / "r.json"
    r.write_text(json.dumps({"predictions": {
        f"bike-lanes|{'a' * 32}": {"side": "for", "side_confidence": 0.95},
        f"bike-lanes|{'c' * 32}": {"side": "against", "side_confidence": 0.9}}}))
    res = gold.combined([g1, g2], [r, tmp_path / "missing.json"])
    assert res["bike-lanes"]["items"] == 2 and res["bike-lanes"]["clear"] == 2 and res["bike-lanes"]["swaps"] == 0
