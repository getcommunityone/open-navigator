"""Per-field size of Part 1 answers (#269). No network."""

from __future__ import annotations

import json

from llm.gemini import part1_field_sizes as fs


def _analysis():
    return {
        "meeting": {"body_name": "Council"},
        "people": [{"full_name": "Ann Lowe"}],
        "decisions": [
            {"headline": "H1", "diagram_mindmap": "mindmap\n  root((A))"},
            {"headline": "H2", "diagram_mindmap": "mindmap\n  root((B))", "speaker_segments": []},
        ],
        "_error": "bookkeeping is left out",
    }


def test_field_sizes():
    sizes = fs.field_sizes(_analysis())
    body = {k: v for k, v in _analysis().items() if k != "_error"}
    assert sizes["(total)"] == len(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
    assert sizes["decisions[].headline"] == len('"H1"') + len('"H2"')
    assert sizes["decisions[].speaker_segments"] == len("[]")
    assert "_error" not in sizes


def test_summarize_shares_and_presence():
    rows = fs.summarize([fs.field_sizes(_analysis()), {"(total)": 100, "people": 50}])
    by_field = {r["field"]: r for r in rows}
    assert by_field["people"]["answers_with_field"] == 2 and by_field["people"]["answer_count"] == 2
    assert by_field["decisions[].speaker_segments"]["answers_with_field"] == 1
    assert rows[0]["chars"] >= rows[-1]["chars"]
    total = fs.field_sizes(_analysis())["(total)"] + 100
    assert by_field["people"]["share_pct"] == round(100 * by_field["people"]["chars"] / total, 1)


def test_field_texts_match_sizes():
    texts = fs.field_texts(_analysis())
    sizes = fs.field_sizes(_analysis())
    assert len(texts["decisions[].headline"]) == sizes["decisions[].headline"] + 1  # joined with one newline
    assert texts["meeting"] == '{"body_name":"Council"}'
