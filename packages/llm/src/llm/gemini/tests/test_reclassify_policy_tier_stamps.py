"""Unit tests for prompt-tier classification (#766)."""

from llm.gemini.reclassify_policy_tier_stamps import classify_prompt_meta


def test_classify_part_1_as_full() -> None:
    assert (
        classify_prompt_meta(
            {
                "prompt_name": "policy_analysis_part_1",
                "prompt_file": "prompts/policy_analysis_part_1.md",
            }
        )
        == "full"
    )


def test_classify_lite_as_light() -> None:
    assert (
        classify_prompt_meta(
            {
                "prompt_name": "policy_analysis_lite",
                "prompt_file": "prompts/policy_analysis_lite.md",
            }
        )
        == "light"
    )


def test_classify_explicit_tier_wins() -> None:
    assert classify_prompt_meta({"analysis_tier": "full", "prompt_name": "x"}) == "full"
    assert classify_prompt_meta({"analysis_tier": "light", "prompt_name": "x"}) == "light"


def test_classify_unknown_returns_none() -> None:
    assert classify_prompt_meta({"prompt_name": "custom_experiment"}) is None
    assert classify_prompt_meta({}) is None
