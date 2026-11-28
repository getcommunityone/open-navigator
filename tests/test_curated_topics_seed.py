"""Contract checks for dbt_project/seeds/curated_topics.csv (#1401).

Guards against regressions that renumber or drop curated topic IDs shared across
meeting_comment, topic_transcript_link, speaker_stance, and story slugs.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "dbt_project" / "seeds" / "curated_topics.csv"
LLM_SRC = ROOT / "packages" / "llm" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm.typesafe import speaker_stance as ss


def _load_rows() -> list[dict[str, str]]:
    with SEED_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_curated_topics_ids_and_slugs_are_unique_and_complete() -> None:
    rows = _load_rows()
    ids = [int(r["topic_id"]) for r in rows]
    slugs = [r["query_id"] for r in rows]
    names = [r["name"] for r in rows]

    assert len(ids) == len(set(ids)), "duplicate topic_id in curated_topics.csv"
    assert len(slugs) == len(set(slugs)), "duplicate query_id in curated_topics.csv"
    assert len(names) == len(set(names)), "duplicate name in curated_topics.csv"
    assert all(tid >= 100000 for tid in ids)
    assert all(r["keywords"].strip() for r in rows)

    by_id = {int(r["topic_id"]): r["query_id"] for r in rows}
    # 100001-100020 must match the warehouse; 100007 is violent-crime and 100020 is bike-lanes.
    for tid in range(100001, 100021):
        assert tid in by_id, f"missing curated topic_id {tid}"
    assert by_id[100007] == "violent-crime"
    assert by_id[100020] == "bike-lanes"

    # Coverage topics (#1436) and opioid settlement (#1396)
    for tid in range(100101, 100112):
        assert tid in by_id, f"missing coverage topic_id {tid}"
    assert by_id[100111] == "battery-storage"
    assert by_id[100901] == "opioid-settlement"


def test_curated_topics_match_speaker_stance_topics() -> None:
    by_id = {int(r["topic_id"]): r["query_id"] for r in _load_rows()}
    for slug, topic in ss.TOPICS.items():
        if topic.topic_id >= 100000:
            assert by_id.get(topic.topic_id) == slug
