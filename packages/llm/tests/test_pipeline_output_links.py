"""The end-of-run output index lists technical meeting summaries instead of crashing (#311).

Every meeting summary comes with a `_meeting_summary_technical.md` beside it. The index appended those to a list
that only existed in `collect_pipeline_outputs`, so it raised NameError once any summary existed, and the jurisdiction
pipeline failed after "All jurisdictions complete".
"""

from __future__ import annotations

from pathlib import Path

from llm.governance.pipeline_output_links import collect_pipeline_outputs, print_pipeline_output_index


def _roots(tmp_path: Path) -> dict[str, Path]:
    pipe = tmp_path / "pipeline"
    roots = {
        "pipe_root": pipe,
        "gemma_json_root": pipe / "03_processed_outputs" / "02_gemma_json",
        "summaries_root": pipe / "03_processed_outputs" / "03_human_summaries",
    }
    for p in roots.values():
        p.mkdir(parents=True, exist_ok=True)
    return roots


def _write_meeting(summaries_root: Path) -> Path:
    session = summaries_root / "al" / "tuscaloosa" / "meetings" / "2026-11-01" / "session"
    session.mkdir(parents=True)
    (session / "_meeting_summary.md").write_text("# Summary\n", encoding="utf-8")
    (session / "_meeting_summary_technical.md").write_text("# Technical\n", encoding="utf-8")
    return session


def test_technical_summaries_are_collected_beside_the_judge_summaries(tmp_path):
    roots = _roots(tmp_path)
    session = _write_meeting(roots["summaries_root"])

    kinds = {(a.kind, a.path.name) for a in collect_pipeline_outputs(**roots)}

    assert ("meeting_summary", "_meeting_summary.md") in kinds
    assert ("meeting_summary_technical", "_meeting_summary_technical.md") in kinds
    technical = [a for a in collect_pipeline_outputs(**roots) if a.kind == "meeting_summary_technical"]
    assert [a.path for a in technical] == [session / "_meeting_summary_technical.md"]


def test_the_index_prints_the_technical_manifests_section(tmp_path, capsys):
    roots = _roots(tmp_path)
    _write_meeting(roots["summaries_root"])

    print_pipeline_output_index(**roots, show_file_links=False)

    out = capsys.readouterr().out
    assert "## Meeting summaries for judges (start here) (1)" in out
    assert "## Technical manifests (pipeline/debug) (1)" in out


def test_with_nothing_written_the_index_still_prints_the_hint(tmp_path, capsys):
    print_pipeline_output_index(**_roots(tmp_path), show_file_links=False)

    assert "no processed artifacts found yet" in capsys.readouterr().out
