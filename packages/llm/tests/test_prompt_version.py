"""llm.prompt_version: a prompt's version follows its content."""

from __future__ import annotations

from llm import prompt_version as pv


def test_label_changes_with_the_text():
    a = pv.prompt_version_label("policy_analysis_part_1", pv.prompt_sha256("v one"))
    b = pv.prompt_version_label("policy_analysis_part_1", pv.prompt_sha256("v two"))
    assert a != b and a.startswith("policy_analysis_part_1@") and len(a.split("@")[1]) == 12
    assert len(a) <= pv.MAX_LEN


def test_old_analyses_say_unrecorded_not_a_fake_version():
    meta = {"prompt_name": "policy_analysis_part_1", "prompt_file": "prompts/policy_analysis_part_1.md"}
    assert pv.prompt_version_from_meta(meta) == "policy_analysis_part_1@unrecorded"
    assert pv.prompt_version_from_meta({"prompt_file": "prompts/x.md"}) == "x@unrecorded"
    assert pv.prompt_version_from_meta({}) is None
    assert pv.prompt_version_from_meta(None) is None


def test_meta_with_hash(tmp_path):
    f = tmp_path / "p.md"
    f.write_text("prompt body")
    sha = pv.prompt_file_sha256(f)
    assert sha == pv.prompt_sha256("prompt body")
    assert pv.prompt_version_from_meta({"prompt_name": "p", "prompt_sha256": sha}) == f"p@{sha[:12]}"
    assert pv.prompt_file_sha256(tmp_path / "missing.md") is None


def test_long_names_fit_the_column_and_keep_the_hash():
    label = pv.prompt_version_label("x" * 80, "a" * 64)
    assert len(label) == pv.MAX_LEN
    assert label.endswith("@" + "a" * 12)
    other = pv.prompt_version_label("x" * 80, "b" * 64)
    assert other != label
    unrecorded = pv.prompt_version_label("x" * 80, None)
    assert len(unrecorded) == pv.MAX_LEN and unrecorded.endswith("@unrecorded")
