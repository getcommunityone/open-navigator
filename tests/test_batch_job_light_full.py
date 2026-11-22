"""Launch steps and full_filters for analysis light vs full (#755)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

import api.routes.batch_jobs as bj
from llm.gemini.full_analysis_filters import normalize_full_filters


def test_normalize_full_filters_dedupes_and_drops_unknown() -> None:
    assert normalize_full_filters(
        ["has_decisions", "interestingness", "has_decisions", "nope"]
    ) == ["has_decisions", "interestingness"]
    assert normalize_full_filters([]) == []
    assert normalize_full_filters(None) == []


def test_run_all_argv_mentions_light_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    disc = tmp_path / "packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py"
    disc.parent.mkdir(parents=True)
    disc.write_text("# stub\n", encoding="utf-8")
    shell = tmp_path / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    shell.parent.mkdir(parents=True)
    shell.write_text("#!/bin/bash\n", encoding="utf-8")
    argv, env = bj._build_launch_argv(
        "all",
        states=["WI"],
        cohort="priority",
        n=10,
        parallel=2,
    )
    assert "analyze-light → reports-light" in argv[2]
    assert env.get("COHORT") == "priority"


def test_analyze_full_sets_full_filters_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    shell = tmp_path / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    shell.parent.mkdir(parents=True)
    shell.write_text("#!/bin/bash\n", encoding="utf-8")
    argv, env = bj._build_launch_argv(
        "analyze-full",
        states=["AL"],
        cohort="priority",
        n=5,
        parallel=1,
        full_filters=["has_decisions", "interestingness"],
    )
    assert argv == ["bash", str(shell), "analyze-full"]
    assert env["FULL_FILTERS"] == "has_decisions,interestingness"


def test_analyze_light_shell_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bj, "_repo_root", lambda: tmp_path)
    shell = tmp_path / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    shell.parent.mkdir(parents=True)
    shell.write_text("#!/bin/bash\n", encoding="utf-8")
    argv, _env = bj._build_launch_argv(
        "analyze",
        states=["AL"],
        cohort="priority",
        n=5,
        parallel=1,
    )
    assert argv[-1] == "analyze-light"


@pytest.mark.asyncio
async def test_launch_full_refuses_empty_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bj, "_launch_enabled", lambda: True)
    monkeypatch.setattr(bj, "_dashboard_runtime", lambda: (0, ""))
    monkeypatch.setattr(bj, "_read_launches", lambda: [])
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.resolve_launch_states",
        lambda cohort, states, conn=None: ["AL"],
    )

    with pytest.raises(HTTPException) as ei:
        await bj.launch_pipeline(
            bj.LaunchRequest(step="analyze-full", states=["AL"], full_filters=[])
        )
    assert ei.value.status_code == 400
    assert "full_filters" in str(ei.value.detail)
