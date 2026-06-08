"""Pure-logic tests for the human_element quote-enrichment pass (no API, no DB)."""

from llm.gemini.enrich_human_element_quotes import (
    _build_prompt,
    _iter_moments,
    _parse_quotes,
)


def test_iter_moments_covers_stories_and_humor_variants():
    analysis = {
        "decisions": [
            {
                "human_element": {
                    "personal_stories": [{"story_detail": "a resident spoke", "person_id": "p1"}],
                    "humor_and_light_moments": [{"summary": "a joke", "speaker_id": "s1"}],
                    "humor": [{"summary": "shorthand-key joke"}],  # tolerate the short key
                }
            },
            {"human_element": None},  # ignored
        ]
    }
    ms = _iter_moments(analysis)
    kinds = sorted(m.kind for m in ms)
    assert kinds == ["humor", "humor", "story"]
    story = next(m for m in ms if m.kind == "story")
    assert story.field == "evidence_quote" and story.paraphrase == "a resident spoke" and story.speaker == "p1"


def test_parse_quotes_tolerates_code_fence_and_nulls():
    text = '```json\n[{"index": 0, "quote": "exact words"}, {"index": 1, "quote": null}]\n```'
    assert _parse_quotes(text) == {0: "exact words"}


def test_parse_quotes_empty_on_garbage():
    assert _parse_quotes("no json here") == {}


def test_build_prompt_lists_moments_and_wraps_transcript():
    analysis = {"decisions": [{"human_element": {"humor_and_light_moments": [{"summary": "joked about the budget", "speaker_id": "x"}]}}]}
    prompt = _build_prompt("[00:10] X: we joked about the budget", _iter_moments(analysis))
    assert "VERBATIM" in prompt
    assert "joked about the budget" in prompt
    assert "<transcript>" in prompt and "</transcript>" in prompt
