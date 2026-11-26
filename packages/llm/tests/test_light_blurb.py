"""Keeper light blurb helpers (#705)."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from llm.typesafe import light_blurb as lb


def test_choose_light_excerpt_precedence():
    assert (
        lb.choose_light_excerpt(
            meeting_summary="Full Part‑1 summary",
            blurb_text="Cheap blurb",
            youtube_description="x" * 200,
            transcript_snippet="snippet",
        )
        == "Full Part‑1 summary"
    )
    assert (
        lb.choose_light_excerpt(
            blurb_text="Cheap blurb",
            youtube_description="x" * 200,
            transcript_snippet="snippet",
        )
        == "Cheap blurb"
    )
    assert (
        lb.choose_light_excerpt(
            youtube_description="x" * 200,
            transcript_snippet="snippet",
        )
        == "x" * 200
    )
    assert (
        lb.choose_light_excerpt(
            youtube_description="short",
            transcript_snippet="snippet here",
        )
        == "snippet here"
    )
    assert lb.choose_light_excerpt(youtube_description="short") is None


def test_extractive_snippet_trims_at_word():
    text = "alpha beta gamma delta " * 40
    out = lb.extractive_snippet(text, max_chars=40)
    assert out.endswith("…")
    assert " " not in out[-2:]  # no dangling space before ellipsis mid-word issues ok
    assert len(out) <= 41


def test_build_user_prompt_includes_title_and_truncates():
    prompt = lb.build_user_prompt(
        title="City Council",
        description="Live stream",
        transcript="word " * 100,
        max_transcript_chars=20,
    )
    assert "City Council" in prompt
    assert "YouTube description" in prompt
    assert prompt.endswith("…") or "Transcript excerpt" in prompt


def test_generate_blurb_returns_none_on_empty(monkeypatch):
    fake = SimpleNamespace(
        text="   ",
        model="gemini-2.5-flash-lite",
        usage=SimpleNamespace(input_token_count=10, output_token_count=0),
    )
    monkeypatch.setattr(
        "llm.gemini.genai_text_client.call_gemini_text",
        lambda **kw: fake,
    )
    assert (
        lb.generate_blurb(
            api_key="k",
            model="gemini-2.5-flash-lite",
            video_id="v1",
            title="T",
            description=None,
            transcript="Motion carried.",
        )
        is None
    )


def test_generate_blurb_stores_clean_text(monkeypatch, tmp_path):
    fake = SimpleNamespace(
        text='"The council discussed zoning for a warehouse."',
        model="gemini-2.5-flash-lite",
        usage=SimpleNamespace(input_token_count=100, output_token_count=20),
    )
    monkeypatch.setattr(
        "llm.gemini.genai_text_client.call_gemini_text",
        lambda **kw: fake,
    )
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path))
    result = lb.generate_blurb(
        api_key="k",
        model="gemini-2.5-flash-lite",
        video_id="v1",
        title="Council",
        description=None,
        transcript="Zoning ordinance first reading.",
    )
    assert result is not None
    assert result.blurb_text == "The council discussed zoning for a warehouse."
    assert result.prompt_sha256 == lb.PROMPT_SHA256
    assert result.input_tokens == 100
    row = result.row()
    assert row["video_id"] == "v1"
    assert row["blurb_text"].startswith("The council")


def test_select_keeper_sql_includes_keep_threshold():
    sql, params = lb.select_keeper_sql(
        states=["al"],
        jurisdiction_id="",
        keep_t=0.6,
        include_analyzed=False,
    )
    assert "0.6" not in sql  # bound param
    assert params[0] == pytest.approx(0.6)
    assert "policy_analysis_at IS NULL" in sql
    assert params[1] == ["AL"]
